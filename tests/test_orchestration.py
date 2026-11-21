from __future__ import annotations

import copy
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from agent_runtime.contracts import TOOLS, error_result
from agent_runtime.orchestration import run_task
from agent_runtime.search import execute


CONTRACT_VERSION = "1.0.0"
QUERY = TOOLS["search.query"]["examples"]["validInput"]
FIXTURE_RESULT = TOOLS["search.query"]["examples"]["validResult"]


def _task(stages, **options):
    return {"contractVersion": CONTRACT_VERSION, "objective": "Buscar e auditar resultados solicitados", "stages": stages, **options}


def _query(request: str = "Camisa branca tamanho M"):
    result = copy.deepcopy(QUERY)
    result["request"] = request
    return result


def _fixture_runner(calls=None):
    def runner(tool, payload, _cancel, timeout):
        if calls is not None:
            calls.append((tool, copy.deepcopy(payload), timeout))

        class FixtureProvider:
            def search(self, plan, *, timeout_seconds, cancel_event):
                assert timeout_seconds <= timeout
                assert plan.filters == tuple(type(plan.filters[0])(**item) for item in payload["filters"])
                value = copy.deepcopy(FIXTURE_RESULT)
                value["results"][0]["title"] = payload["request"]
                return value

        return execute(tool, payload, provider=FixtureProvider(), cancel_event=_cancel, timeout_seconds=timeout)

    return runner


class SearchOrchestrationTests(unittest.TestCase):
    def test_direct_search_and_composed_query_audit_are_explicitly_simulated(self):
        calls = []
        query = {"id": "query", "tool": "search.query", "input": _query()}
        direct = run_task(_task([query]), execute_tool=_fixture_runner(calls))
        composed = run_task(
            _task(
                [
                    query,
                    {"id": "audit", "tool": "search.audit", "dependsOn": ["query"], "input": {"sourceStage": "query"}},
                ]
            ),
            execute_tool=_fixture_runner(calls),
        )
        self.assertEqual(direct["stages"][0]["mode"], "simulated")
        self.assertEqual(direct["stages"][0]["status"], "partial")
        self.assertEqual(composed["stages"][1]["result"]["candidateCount"], 1)
        self.assertFalse(composed["stages"][1]["result"]["factsVerified"])
        self.assertEqual(composed["status"], "partial")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1], _query())

    def test_normal_cli_reports_missing_provider_and_blocks_audit(self):
        result = run_task(
            _task(
                [
                    {"id": "query", "tool": "search.query", "input": _query()},
                    {"id": "audit", "tool": "search.audit", "dependsOn": ["query"], "input": {"sourceStage": "query"}},
                ]
            )
        )
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["executed"])
        self.assertIn("No search provider is configured", result["stages"][0]["error"]["message"])
        self.assertEqual(result["stages"][1]["blockedBy"], ["query"])

    def test_multiple_sort_keys_fail_closed_before_source_access(self):
        calls = []
        request = _query()
        request["sort"].append({"field": "nota", "direction": "descending"})
        result = run_task(_task([{"id": "query", "tool": "search.query", "input": request}]), execute_tool=_fixture_runner(calls))
        self.assertEqual(calls, [])
        self.assertEqual(result["status"], "blocked")
        self.assertIn("not executed", result["stages"][0]["error"]["message"])

    def test_retry_requires_explicit_recoverable_error(self):
        calls = []
        real_runner = _fixture_runner(calls)

        def runner(tool, payload, cancel, timeout):
            if len(calls) == 0:
                calls.append(("first", payload, timeout))
                return error_result("source_unavailable", "temporary source delay", retryable=True)
            return real_runner(tool, payload, cancel, timeout)

        result = run_task(
            _task([{"id": "query", "tool": "search.query", "input": _query()}], limits={"maxAttempts": 2}),
            execute_tool=runner,
        )
        self.assertEqual(result["stages"][0]["attempts"], 2)
        self.assertEqual(result["missingDependencies"], [])
        self.assertEqual(result["stages"][0]["status"], "partial")

    def test_cancel_and_timeout_preserve_explicit_states(self):
        cancelled = threading.Event()
        cancelled.set()
        task = _task([{"id": "query", "tool": "search.query", "input": _query()}], limits={"timeoutMs": 1000})
        cancelled_result = run_task(task, cancel_event=cancelled)
        self.assertEqual(cancelled_result["status"], "cancelled")

        ticks = iter([0.0, 0.0, 0.0, 2.0, 2.0])
        timed = run_task(task, execute_tool=_fixture_runner(), clock=lambda: next(ticks, 2.0))
        self.assertEqual(timed["status"], "timed_out")

    def test_checkpoint_recomputes_results_and_rejects_drift(self):
        task = _task([{"id": "query", "tool": "search.query", "input": _query()}])
        first = run_task(task, execute_tool=_fixture_runner())
        replayed = run_task({**task, "resume": first["checkpoint"]}, execute_tool=_fixture_runner())
        self.assertEqual(replayed["stages"][0]["mode"], "simulated")
        self.assertTrue(replayed["stages"][0]["checkpointRecomputed"])
        self.assertTrue(replayed["executed"])

        changed = _fixture_runner()
        def changed_runner(tool, payload, cancel, timeout):
            value = changed(tool, payload, cancel, timeout)
            value["results"][0]["title"] = "Alterado desde o checkpoint"
            return value
        drift = run_task({**task, "resume": first["checkpoint"]}, execute_tool=changed_runner)
        self.assertEqual(drift["stages"][0]["status"], "failed")
        self.assertEqual(drift["stages"][0]["error"]["code"], "invalid_request")

    def test_graph_rejects_audit_without_query_dependency(self):
        result = run_task(_task([{"id": "audit", "tool": "search.audit", "input": {"sourceStage": "query"}}]))
        self.assertEqual(result["code"], "invalid_request")

    def test_concurrent_tasks_keep_ids_and_candidate_results_isolated(self):
        def search(name):
            task = _task([{"id": "query", "tool": "search.query", "input": _query(name)}])
            return run_task(task, execute_tool=_fixture_runner())

        with ThreadPoolExecutor(max_workers=2) as pool:
            a, b = list(pool.map(search, ["Camisa clara", "Sapato escuro"]))
        self.assertNotEqual(a["taskId"], b["taskId"])
        self.assertEqual(a["stages"][0]["result"]["results"][0]["title"], "Camisa clara")
        self.assertEqual(b["stages"][0]["result"]["results"][0]["title"], "Sapato escuro")


if __name__ == "__main__":
    unittest.main()
