"""Request-scoped search and result-audit coordination."""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from .contracts import CONTRACT, ERROR_SCHEMA, ContractViolation, error_result, validate, validate_input, validate_result
from .search import SearchProvider, _validate_provider_result, execute


ROOT = Path(__file__).resolve().parents[1]
TASK_SCHEMA = json.loads((ROOT / "contracts" / "v1" / "task.schema.json").read_text(encoding="utf-8"))
TASK_RESULT_SCHEMA = json.loads(
    (ROOT / "contracts" / "v1" / "task-result.schema.json").read_text(encoding="utf-8")
)
_TOOLS = {"search.query", "search.audit"}
_DEFAULT_LIMITS = {
    "maxSteps": 8,
    "timeoutMs": 60_000,
    "maxAttempts": 1,
    "maxConcurrency": 1,
    "maxDelegationDepth": 0,
    "maxOutputBytes": 256_000,
}
_Runner = Callable[[str, dict[str, Any], threading.Event | None, float], dict[str, Any]]


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _stage_digest(stage: dict[str, Any]) -> str:
    return _digest({"id": stage["id"], "tool": stage["tool"], "input": stage["input"], "dependsOn": stage.get("dependsOn", [])})


def _definition(task: dict[str, Any], limits: dict[str, int]) -> dict[str, Any]:
    return {
        "contractVersion": task["contractVersion"],
        "objective": task["objective"],
        "stages": [
            {"id": stage["id"], "tool": stage["tool"], "input": stage["input"], "dependsOn": stage.get("dependsOn", [])}
            for stage in task["stages"]
        ],
        "limits": limits,
    }


def _validate_graph(stages: list[dict[str, Any]], limits: dict[str, int]) -> None:
    if len(stages) > limits["maxSteps"]:
        raise ContractViolation("Task exceeds maxSteps")
    prior: set[str] = set()
    for stage in stages:
        if stage["id"] in prior or stage["tool"] not in _TOOLS:
            raise ContractViolation("Task has a duplicate ID or unsupported operation")
        dependencies = stage.get("dependsOn", [])
        if len(dependencies) != len(set(dependencies)) or any(item not in prior for item in dependencies):
            raise ContractViolation("Dependencies must be unique and point to earlier stages")
        if stage["tool"] == "search.query":
            if dependencies:
                raise ContractViolation("Search query inputs must stay explicit and independent")
            validate_input("search.query", stage["input"])
        else:
            source = stage["input"].get("sourceStage")
            if set(stage["input"]) != {"sourceStage"} or dependencies != [source]:
                raise ContractViolation("An audit stage requires one declared search.query dependency")
            if source not in prior or next(item for item in stages if item["id"] == source)["tool"] != "search.query":
                raise ContractViolation("Audit source must be an earlier search.query stage")
        prior.add(stage["id"])


def _resume_claims(checkpoint: dict[str, Any], digest: str, definitions: dict[str, dict[str, Any]]) -> dict[str, dict[str, str]]:
    if checkpoint["objectiveDigest"] != digest:
        raise ContractViolation("Checkpoint belongs to a different task definition")
    claims: dict[str, dict[str, str]] = {}
    for item in checkpoint["completedStages"]:
        stage = definitions.get(item["id"])
        if item["id"] in claims or stage is None or item["tool"] != stage["tool"] or item["stageDigest"] != _stage_digest(stage):
            raise ContractViolation("Checkpoint contains an unknown or changed stage")
        claims[item["id"]] = item
    return claims


def _audit(query_input: dict[str, Any], result: dict[str, Any], source_id: str) -> dict[str, Any]:
    checked = _validate_provider_result(query_input, result)
    if "code" in checked:
        raise ContractViolation("A search error cannot be audited as a result")
    return {
        "status": "audited",
        "sourceStage": source_id,
        "candidateCount": len(checked["results"]),
        "filterAudit": checked["filterAudit"],
        "sortAudit": checked["sortAudit"],
        "factsVerified": False,
    }


def _query_outcome(result: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    if "code" in result:
        code = result["code"]
        if code in {"source_unavailable", "access_not_authorized", "unavailable", "limit_exceeded"}:
            return "blocked", [result["message"]], []
        if code == "filter_unrepresentable":
            return "needs_input", [], [result["message"]]
        return "failed", [], []
    if result.get("status") == "needs_clarification":
        return "needs_input", [], ["A fonte precisa de esclarecimento antes de confirmar uma busca."]
    if result.get("status") == "partial":
        return "partial", [], []
    return "completed", [], []


def run_task(
    payload: Any,
    *,
    provider: SearchProvider | None = None,
    execute_tool: _Runner | None = None,
    cancel_event: threading.Event | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Execute a bounded search plan and optionally re-audit its result locally."""
    try:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        if len(encoded) > 80_000:
            return error_result("limit_exceeded", "Task exceeds 80000 bytes.")
        validate(TASK_SCHEMA, payload)
        limits = dict(_DEFAULT_LIMITS)
        limits.update(payload.get("limits", {}))
        _validate_graph(payload["stages"], limits)
        digest = _digest(_definition(payload, limits))
        definitions = {stage["id"]: stage for stage in payload["stages"]}
        claims = _resume_claims(payload["resume"], digest, definitions) if payload.get("resume") else {}
        task_id = str(uuid.UUID(payload.get("resume", {}).get("taskId", str(uuid.uuid4()))))
    except (ContractViolation, KeyError, TypeError, ValueError, RecursionError, StopIteration) as exc:
        return error_result("invalid_request", str(exc) or "Task contract is invalid")

    def default_runner(tool: str, data: dict[str, Any], event: threading.Event | None, remaining: float) -> dict[str, Any]:
        return execute(tool, data, provider=provider, cancel_event=event, timeout_seconds=remaining)

    runner = execute_tool or default_runner
    started = clock()
    states: dict[str, str] = {}
    results: dict[str, dict[str, Any]] = {}
    output_stages: list[dict[str, Any]] = []
    missing_dependencies: list[str] = []
    missing_inputs: list[str] = []
    stop_status: str | None = None
    capability_ran = False

    for stage in payload["stages"]:
        if cancel_event is not None and cancel_event.is_set():
            stop_status = "cancelled"
            break
        if clock() - started >= limits["timeoutMs"] / 1000:
            stop_status = "timed_out"
            break
        stage_id, tool = stage["id"], stage["tool"]
        blocked_by = [dependency for dependency in stage.get("dependsOn", []) if states.get(dependency) not in {"completed", "partial"}]
        if blocked_by:
            states[stage_id] = "blocked"
            output_stages.append({"id": stage_id, "tool": tool, "status": "blocked", "mode": "deterministic", "attempts": 0, "blockedBy": blocked_by})
            continue

        if tool == "search.audit":
            mode = "deterministic"
        elif execute_tool is not None:
            mode = "simulated"
        elif provider is not None:
            mode = "source_provider"
        else:
            mode = "unavailable"
        record: dict[str, Any] = {"id": stage_id, "tool": tool, "status": "failed", "mode": mode, "attempts": 0}

        if tool == "search.audit":
            source_id = stage["input"]["sourceStage"]
            source_result = results.get(source_id)
            if source_result is None:
                record.update(status="blocked", attempts=0, blockedBy=[source_id])
            else:
                try:
                    audit_result = _audit(definitions[source_id]["input"], source_result, source_id)
                    claim = claims.get(stage_id)
                    if claim is not None and claim["resultDigest"] != _digest(audit_result):
                        record.update(status="failed", attempts=1, error=error_result("invalid_request", "Checkpoint result changed; restart without this checkpoint"))
                    else:
                        record.update(status="completed", attempts=1, result=audit_result)
                        if claim is not None:
                            record["checkpointRecomputed"] = True
                        results[stage_id] = audit_result
                        capability_ran = True
                except ContractViolation as exc:
                    record.update(status="failed", attempts=1, error=error_result("internal_error", str(exc)))
            states[stage_id] = record["status"]
            output_stages.append(record)
            continue

        # The v1 query result has one sort-audit record. Do not silently claim a
        # complete multi-key ordering audit when the response contract cannot express it.
        if len(stage["input"]["sort"]) > 1:
            record.update(
                status="blocked",
                error=error_result("filter_unrepresentable", "Contract v1 cannot audit every requested sort key; multi-key sort was not executed."),
            )
            states[stage_id] = "blocked"
            missing_dependencies.append("result contract v1 supports only one auditable sort key")
            output_stages.append(record)
            continue

        attempts = limits["maxAttempts"]
        for attempt in range(1, attempts + 1):
            if cancel_event is not None and cancel_event.is_set():
                stop_status = "cancelled"
                record["status"] = "cancelled"
                break
            remaining = limits["timeoutMs"] / 1000 - (clock() - started)
            if remaining <= 0:
                stop_status = "timed_out"
                record["status"] = "timed_out"
                break
            record["attempts"] = attempt
            try:
                result = runner(tool, stage["input"], cancel_event, remaining)
            except KeyboardInterrupt:
                stop_status = "cancelled"
                record["status"] = "cancelled"
                break
            except Exception:
                result = error_result("source_unavailable", "The configured source provider failed without verified results.", True)
            if cancel_event is not None and cancel_event.is_set():
                stop_status = "cancelled"
                record["status"] = "cancelled"
                break
            if clock() - started >= limits["timeoutMs"] / 1000:
                stop_status = "timed_out"
                record["status"] = "timed_out"
                break
            if not isinstance(result, dict):
                result = error_result("internal_error", "Search runner returned a non-object result")
            if "code" in result:
                try:
                    validate(ERROR_SCHEMA, result)
                except ContractViolation:
                    result = error_result("internal_error", "Search error failed its output contract")
                outcome, absent, unanswered = _query_outcome(result)
                record["error"] = result
                record["status"] = outcome
                if result.get("retryable") is True and attempt < attempts:
                    continue
                missing_dependencies.extend(absent)
                missing_inputs.extend(unanswered)
                break
            try:
                validated = _audit(stage["input"], result, stage_id)
                validate_result("search.query", result)
            except ContractViolation:
                record["status"] = "failed"
                record["error"] = error_result("internal_error", "Search provider result failed the requested-filter audit")
                break
            capability_ran = execute_tool is not None or provider is not None
            outcome, absent, unanswered = _query_outcome(result)
            record["status"] = outcome
            record["result"] = result
            missing_dependencies.extend(absent)
            missing_inputs.extend(unanswered)
            if outcome in {"completed", "partial"}:
                results[stage_id] = result
            claim = claims.get(stage_id)
            if claim is not None and claim["resultDigest"] != _digest(result):
                record["status"] = "failed"
                record.pop("result", None)
                record["error"] = error_result("invalid_request", "Checkpoint result changed; restart without this checkpoint")
                results.pop(stage_id, None)
            elif claim is not None and outcome in {"completed", "partial"}:
                record["checkpointRecomputed"] = True
            break
        states[stage_id] = record["status"]
        output_stages.append(record)
        if stop_status:
            break

    if stop_status:
        for stage in payload["stages"][len(output_stages):]:
            output_stages.append({"id": stage["id"], "tool": stage["tool"], "status": stop_status, "mode": "deterministic", "attempts": 0})
    state_list = [stage["status"] for stage in output_stages]
    failures = any(state in {"failed", "blocked"} for state in state_list)
    successes = any(state in {"completed", "partial"} for state in state_list)
    if stop_status:
        status = stop_status
    elif any(state == "partial" for state in state_list) or (failures and successes):
        status = "partial"
    elif failures:
        status = "blocked" if all(state == "blocked" for state in state_list) else "failed"
    elif any(state == "needs_input" for state in state_list):
        status = "needs_input"
    else:
        status = "completed"

    completed = [
        {"id": stage["id"], "tool": stage["tool"], "stageDigest": _stage_digest(stage), "resultDigest": _digest(outcome["result"])}
        for stage, outcome in zip(payload["stages"], output_stages)
        if outcome["status"] in {"completed", "partial"} and "result" in outcome
    ]
    response = {
        "contractVersion": CONTRACT["contractVersion"],
        "taskId": task_id,
        "objective": payload["objective"],
        "status": status,
        "executed": capability_ran,
        "stages": output_stages,
        "missingDependencies": sorted(set(missing_dependencies)),
        "missingInputs": missing_inputs[:40],
        "limits": limits,
        "delegation": {"depthUsed": 0, "subagents": 0, "reason": "Busca e auditoria são etapas seriais no runtime; não existem subagentes."},
        "checkpoint": {"contractVersion": CONTRACT["contractVersion"], "taskId": task_id, "objectiveDigest": digest, "completedStages": completed},
    }
    validate(TASK_RESULT_SCHEMA, response)
    output_size = len(json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    if output_size > limits["maxOutputBytes"]:
        return error_result("limit_exceeded", "Task result exceeds maxOutputBytes; use fewer candidates or stages.")
    return response
