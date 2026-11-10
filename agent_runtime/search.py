"""Provider-neutral search orchestration with strict filter and sort auditing."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Any, Protocol

from .contracts import CONTRACT, ERROR_SCHEMA, ContractViolation, error_result, validate, validate_input, validate_result


VERSION = CONTRACT["contractVersion"]
_SOURCE_SLOT = threading.BoundedSemaphore(1)


@dataclass(frozen=True)
class SearchFilter:
    id: str
    criterion: str
    required: bool


@dataclass(frozen=True)
class SearchSort:
    field: str
    direction: str


@dataclass(frozen=True)
class SearchPlan:
    """Immutable request passed intact to any explicitly configured provider."""

    request: str
    query: str
    filters: tuple[SearchFilter, ...]
    source_hints: tuple[str, ...]
    sort: tuple[SearchSort, ...]
    page_limit: int
    cursor: str


class SearchProvider(Protocol):
    def search(
        self,
        plan: SearchPlan,
        *,
        timeout_seconds: float,
        cancel_event: threading.Event | None,
    ) -> dict[str, Any]: ...


def make_search_plan(payload: dict[str, Any]) -> SearchPlan:
    """Preserve every semantic criterion; source hints never become an allowlist."""
    return SearchPlan(
        request=payload["request"],
        query=payload["query"],
        filters=tuple(SearchFilter(**item) for item in payload["filters"]),
        source_hints=tuple(payload["sourceHints"]),
        sort=tuple(SearchSort(**item) for item in payload["sort"]),
        page_limit=payload["pageLimit"],
        cursor=payload["cursor"],
    )


def _timeout_seconds() -> float:
    try:
        value = float(os.environ.get("SOFIEE_AGENT_SOURCE_TIMEOUT_SECONDS", "30"))
    except ValueError as exc:
        raise ValueError("SOFIEE_AGENT_SOURCE_TIMEOUT_SECONDS must be numeric") from exc
    if not 1 <= value <= 120:
        raise ValueError("SOFIEE_AGENT_SOURCE_TIMEOUT_SECONDS must be between 1 and 120")
    return value


def _validate_provider_result(payload: dict[str, Any], value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractViolation("The source provider did not return an object")
    if "code" in value:
        validate(ERROR_SCHEMA, value)
        return value
    validate_result("search.query", value)

    expected_ids = [item["id"] for item in payload["filters"]]
    if len(expected_ids) != len(set(expected_ids)):
        raise ContractViolation("Filter identifiers must be unique")
    audit_ids = [item["filterId"] for item in value["filterAudit"]]
    if audit_ids != expected_ids:
        raise ContractViolation("The source provider omitted, duplicated, or reordered a user filter")

    required_ids = {item["id"] for item in payload["filters"] if item["required"]}
    for result in value["results"]:
        filter_results = result["filterResults"]
        if [item["filterId"] for item in filter_results] != expected_ids:
            raise ContractViolation("A result did not audit every user filter in the original order")
        statuses = {item["filterId"]: item["status"] for item in filter_results}
        if any(statuses[filter_id] == "fail" for filter_id in required_ids):
            raise ContractViolation("A result failed a required user filter")
        expected_matched = [filter_id for filter_id in expected_ids if filter_id in required_ids and statuses[filter_id] == "pass"]
        expected_unverifiable = [filter_id for filter_id in expected_ids if filter_id in required_ids and statuses[filter_id] == "unverifiable"]
        if result["matchedRequiredFilterIds"] != expected_matched:
            raise ContractViolation("Required matched filters do not match their evidence statuses")
        if result["unverifiableRequiredFilterIds"] != expected_unverifiable:
            raise ContractViolation("Required unverifiable filters do not match their evidence statuses")
        expected_match_status = "unverified_required_filters" if expected_unverifiable else "meets_required_filters"
        if result["matchStatus"] != expected_match_status:
            raise ContractViolation("Result status does not reflect required filter evidence")

    requested_sort = payload["sort"]
    sort_audit = value["sortAudit"]
    if requested_sort:
        if sort_audit["status"] == "not_requested" or sort_audit["field"] != requested_sort[0]["field"]:
            raise ContractViolation("The provider did not report the requested ordering field")
        if sort_audit["status"] == "applied" and not sort_audit["basis"].strip():
            raise ContractViolation("Applied ordering must identify its comparison basis")
        if sort_audit["status"] in {"partial", "not_comparable"} and not sort_audit["reason"].strip():
            raise ContractViolation("Unapplied or partial ordering must explain why")
    elif sort_audit["status"] != "not_requested":
        raise ContractViolation("The provider reported ordering that the user did not request")
    return value


def execute(
    tool_name: str,
    payload: dict[str, Any],
    *,
    provider: SearchProvider | None = None,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    try:
        validate_input(tool_name, payload)
        if tool_name != "search.query":
            raise ContractViolation("Unknown tool")
        plan = make_search_plan(payload)
        if provider is None:
            return error_result(
                "source_unavailable",
                "No search provider is configured; user filters and requested ordering were not relaxed.",
                True,
            )
        if cancel_event is not None and cancel_event.is_set():
            return error_result("unavailable", "The search request was cancelled before source access.")
        timeout = _timeout_seconds()
        if not _SOURCE_SLOT.acquire(blocking=False):
            return error_result("limit_exceeded", "The local source concurrency limit was reached.", True)
        try:
            response = provider.search(plan, timeout_seconds=timeout, cancel_event=cancel_event)
            if cancel_event is not None and cancel_event.is_set():
                return error_result("unavailable", "The search request was cancelled; provider output was discarded.")
            return _validate_provider_result(payload, response)
        except TimeoutError:
            return error_result("source_unavailable", "The configured source provider exceeded its timeout.", True)
        except ContractViolation:
            return error_result(
                "filter_unrepresentable",
                "The provider could not preserve and audit every required filter and requested ordering.",
                False,
            )
        except Exception:
            return error_result("source_unavailable", "The configured source provider failed without verified results.", True)
        finally:
            _SOURCE_SLOT.release()
    except ContractViolation as exc:
        return error_result("invalid_request", str(exc))
    except ValueError:
        return error_result("unavailable", "The local source timeout configuration is invalid.")
