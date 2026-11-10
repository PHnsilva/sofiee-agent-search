from __future__ import annotations

from copy import deepcopy
import os
import threading
import unittest
from unittest.mock import patch

from agent_runtime.contracts import TOOLS
from agent_runtime.search import SearchPlan, execute, make_search_plan


class FixtureProvider:
    """Synthetic contract fixture only; this does not access a real source."""

    def __init__(self, result):
        self.result = deepcopy(result)
        self.plan = None
        self.timeout_seconds = None
        self.cancel_event = None

    def search(self, plan, *, timeout_seconds, cancel_event):
        self.plan = plan
        self.timeout_seconds = timeout_seconds
        self.cancel_event = cancel_event
        return deepcopy(self.result)


class SearchRuntimeTests(unittest.TestCase):
    def test_plan_preserves_intersection_hints_sort_and_cursor(self):
        request = TOOLS["search.query"]["examples"]["validInput"]
        plan = make_search_plan(request)
        self.assertIsInstance(plan, SearchPlan)
        self.assertEqual([item.id for item in plan.filters], ["category", "color", "size", "shipping"])
        self.assertEqual([item.criterion for item in plan.filters], ["camisa", "branca", "M", "frete incluso"])
        self.assertEqual([(item.field, item.direction) for item in plan.sort], [("preço total com frete", "ascending")])
        self.assertEqual(plan.source_hints, ())
        self.assertEqual(plan.page_limit, 20)
        self.assertEqual(plan.cursor, "")

        open_sources = dict(request, sourceHints=["fonte oficial local", "vendedor original", "outra fonte pertinente"])
        self.assertEqual(make_search_plan(open_sources).source_hints, tuple(open_sources["sourceHints"]))

    def test_missing_provider_fails_without_synthetic_results_or_relaxation(self):
        request = TOOLS["search.query"]["examples"]["validInput"]
        result = execute("search.query", request)
        self.assertEqual(result["code"], "source_unavailable")
        self.assertIn("filters and requested ordering were not relaxed", result["message"])
        self.assertTrue(result["retryable"])

    def test_provider_output_is_checked_against_every_user_filter(self):
        request = TOOLS["search.query"]["examples"]["validInput"]
        provider = FixtureProvider(TOOLS["search.query"]["examples"]["validResult"])
        result = execute("search.query", request, provider=provider)
        self.assertEqual(result["status"], "partial")
        self.assertEqual([item.id for item in provider.plan.filters], [item["id"] for item in request["filters"]])
        self.assertEqual(provider.timeout_seconds, 30.0)
        self.assertEqual(result["results"][0]["unverifiableRequiredFilterIds"], ["shipping"])

    def test_provider_cannot_drop_color_or_other_required_filter(self):
        request = TOOLS["search.query"]["examples"]["validInput"]
        invalid = deepcopy(TOOLS["search.query"]["examples"]["validResult"])
        invalid["filterAudit"] = invalid["filterAudit"][:-1]
        result = execute("search.query", request, provider=FixtureProvider(invalid))
        self.assertEqual(result["code"], "filter_unrepresentable")
        self.assertNotIn("results", result)

    def test_provider_cannot_claim_required_filter_pass_when_result_is_unverifiable(self):
        request = TOOLS["search.query"]["examples"]["validInput"]
        invalid = deepcopy(TOOLS["search.query"]["examples"]["validResult"])
        invalid["results"][0]["matchedRequiredFilterIds"].append("shipping")
        result = execute("search.query", request, provider=FixtureProvider(invalid))
        self.assertEqual(result["code"], "filter_unrepresentable")

    def test_requested_sort_field_must_be_reported(self):
        request = TOOLS["search.query"]["examples"]["validInput"]
        invalid = deepcopy(TOOLS["search.query"]["examples"]["validResult"])
        invalid["sortAudit"]["field"] = "preço do item"
        result = execute("search.query", request, provider=FixtureProvider(invalid))
        self.assertEqual(result["code"], "filter_unrepresentable")

    def test_pre_cancelled_request_does_not_call_provider(self):
        request = TOOLS["search.query"]["examples"]["validInput"]
        cancelled = threading.Event()
        cancelled.set()
        provider = FixtureProvider(TOOLS["search.query"]["examples"]["validResult"])
        result = execute("search.query", request, provider=provider, cancel_event=cancelled)
        self.assertEqual(result["code"], "unavailable")
        self.assertIsNone(provider.plan)

    def test_timeout_and_invalid_request_fail_closed(self):
        request = TOOLS["search.query"]["examples"]["validInput"]

        class TimedOutProvider(FixtureProvider):
            def search(self, plan, *, timeout_seconds, cancel_event):
                raise TimeoutError

        self.assertEqual(execute("search.query", request, provider=TimedOutProvider({}))["code"], "source_unavailable")
        invalid = dict(request, filters=[])
        invalid["pageLimit"] = 0
        self.assertEqual(execute("search.query", invalid)["code"], "invalid_request")

        provider = FixtureProvider(TOOLS["search.query"]["examples"]["validResult"])
        with patch.dict(os.environ, {"SOFIEE_AGENT_SOURCE_TIMEOUT_SECONDS": "0.5"}):
            bad_timeout = execute("search.query", request, provider=provider)
        self.assertEqual(bad_timeout["code"], "unavailable")
        self.assertIsNone(provider.plan)

    def test_provider_output_after_cancellation_is_discarded(self):
        request = TOOLS["search.query"]["examples"]["validInput"]
        cancelled = threading.Event()

        class CancelDuringSearchProvider(FixtureProvider):
            def search(self, plan, *, timeout_seconds, cancel_event):
                cancel_event.set()
                return deepcopy(self.result)

        result = execute(
            "search.query",
            request,
            provider=CancelDuringSearchProvider(TOOLS["search.query"]["examples"]["validResult"]),
            cancel_event=cancelled,
        )
        self.assertEqual(result["code"], "unavailable")
        self.assertIn("discarded", result["message"])


if __name__ == "__main__":
    unittest.main()
