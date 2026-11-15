"""Provider-neutral search orchestration with strict filter and sort auditing."""

from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from .contracts import CONTRACT, ERROR_SCHEMA, ContractViolation, error_result, validate, validate_input, validate_result


VERSION = CONTRACT["contractVersion"]
_SOURCE_SLOT = threading.BoundedSemaphore(1)
_NUMERIC_VALUE = re.compile(r"^\s*(-?[0-9]+(?:[.,][0-9]+)?)\s*(.*?)\s*$")


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


def _sort_value(result: dict[str, Any], field: str) -> tuple[str, Decimal] | None:
    values = [item["value"] for item in result["attributes"] if item["name"] == field]
    if len(values) != 1:
        return None
    match = _NUMERIC_VALUE.fullmatch(values[0])
    if match is None:
        return None
    number, unit = match.groups()
    if "," in number and "." in number:
        return None
    unit = unit.strip()
    if unit and (unit[0].isdigit() or unit[0] in ".,"):
        return None
    try:
        return unit.casefold(), Decimal(number.replace(",", "."))
    except InvalidOperation:
        return None


def _order_matches_requested_prefix(
    results: list[dict[str, Any]], requested_prefix: list[dict[str, str]]
) -> bool | None:
    """Return None when the values cannot be compared under one numeric unit."""
    if not results or not requested_prefix:
        return None
    rows: list[list[tuple[str, Decimal]]] = []
    for result in results:
        row = [_sort_value(result, key["field"]) for key in requested_prefix]
        if any(value is None for value in row):
            return None
        rows.append([value for value in row if value is not None])
    for column in range(len(requested_prefix)):
        units = {row[column][0] for row in rows}
        if len(units) != 1:
            return None
    for left, right in zip(rows, rows[1:]):
        for index, key in enumerate(requested_prefix):
            left_value = left[index][1]
            right_value = right[index][1]
            if left_value == right_value:
                continue
            ordered = left_value < right_value if key["direction"] == "ascending" else left_value > right_value
            if not ordered:
                return False
            break
    return True


def _validate_sort_audit(payload: dict[str, Any], value: dict[str, Any]) -> None:
    requested = payload["sort"]
    audit = value["sortAudit"]
    applied = audit["applied"]
    if audit["requested"] != requested or applied != requested[: len(applied)]:
        raise ContractViolation("The sort audit did not preserve the requested ordered fields and directions")
    status = audit["status"]
    if status == "not_requested":
        if requested or applied:
            raise ContractViolation("The provider reported an unexpected sort audit")
        return
    if not requested:
        raise ContractViolation("The provider reported ordering that the user did not request")
    if status == "applied":
        if applied != requested or not audit["basis"].strip():
            raise ContractViolation("Applied ordering must cover every requested key and declare its basis")
        order = _order_matches_requested_prefix(value["results"], applied)
        if order is None:
            raise ContractViolation("The provider claimed applied ordering without comparable values")
        if not order:
            raise ContractViolation("The provider results do not follow the requested ordering and tie-breaks")
        return
    if status == "partial":
        if not 0 < len(applied) < len(requested) or not audit["reason"].strip():
            raise ContractViolation("Partial ordering must report an applied prefix and the remaining limitation")
        order = _order_matches_requested_prefix(value["results"], applied)
        if order is None:
            raise ContractViolation("The provider claimed a partial ordering without comparable applied values")
        if not order:
            raise ContractViolation("The provider results do not follow the applied ordering prefix")
        return
    if status == "not_comparable" and (applied or not audit["reason"].strip()):
        raise ContractViolation("Uncomparable ordering must report no applied keys and explain why")


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

    _validate_sort_audit(payload, value)
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
