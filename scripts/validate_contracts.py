"""Check public contract fixtures against the JSON Schema subset used here.

This is a zero-dependency fixture checker, not a production JSON Schema engine.
The runtime must validate the same schemas with its selected official SDK.
"""

import json
import re
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "v1" / "contracts.json"
SORT_TIE_BREAK_FIXTURE = ROOT / "contracts" / "v1" / "fixtures" / "sort-tie-break.json"


def matches(value, schema):
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(value, dict):
            return False
        if any(key not in value for key in schema.get("required", [])):
            return False
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False and set(value) - set(properties):
            return False
        return all(matches(child, properties[key]) for key, child in value.items() if key in properties)
    if kind == "array":
        if not isinstance(value, list):
            return False
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", float("inf")):
            return False
        return all(matches(item, schema["items"]) for item in value)
    if kind == "string":
        if not isinstance(value, str):
            return False
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", float("inf")):
            return False
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            return False
    elif kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            return False
    elif kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
    elif kind == "boolean":
        if not isinstance(value, bool):
            return False
    elif kind == "null":
        if value is not None:
            return False
    elif kind is not None:
        raise ValueError(f"Unsupported schema type: {kind}")
    if "const" in schema and value != schema["const"]:
        return False
    if "enum" in schema and value not in schema["enum"]:
        return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value < schema.get("minimum", float("-inf")) or value > schema.get("maximum", float("inf")):
            return False
    return True


def valid_sort_audit(requested, audit):
    if audit["requested"] != requested:
        return False
    applied = audit["applied"]
    if applied != requested[: len(applied)]:
        return False
    status = audit["status"]
    if status == "applied":
        return bool(requested) and applied == requested and bool(audit["basis"].strip())
    if status == "partial":
        return 0 < len(applied) < len(requested) and bool(audit["basis"].strip()) and bool(audit["reason"].strip())
    if status == "not_comparable":
        return bool(requested) and not applied and bool(audit["reason"].strip())
    if status == "not_requested":
        return not requested and not applied
    return False


def valid_search_result(result, requested_sort):
    for item in result["results"]:
        statuses = {check["status"] for check in item["filterResults"]}
        if "fail" in statuses:
            return False
        if item["matchStatus"] == "meets_required_filters":
            if item["unverifiableRequiredFilterIds"] or statuses != {"pass"}:
                return False
        elif item["matchStatus"] == "unverified_required_filters":
            if not item["unverifiableRequiredFilterIds"]:
                return False
    return valid_sort_audit(requested_sort, result["sortAudit"])


def sort_fixture_is_ordered(fixture):
    keys = fixture["sort"]
    if not valid_sort_audit(keys, fixture["sortAudit"]):
        return False
    if fixture["sortAudit"]["status"] != "applied":
        return False
    for left, right in zip(fixture["items"], fixture["items"][1:]):
        for key in keys:
            left_raw = left["attributes"].get(key["field"])
            right_raw = right["attributes"].get(key["field"])
            if left_raw is None or right_raw is None:
                return False
            try:
                left_value = Decimal(left_raw)
                right_value = Decimal(right_raw)
            except (ValueError, TypeError):
                return False
            if left_value == right_value:
                continue
            ordered = left_value < right_value if key["direction"] == "ascending" else left_value > right_value
            if not ordered:
                return False
            break
    return True


def main():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["contractVersion"] == "1.0.0"
    assert contract["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    error_schema = contract["errorSchema"]
    assert error_schema["$schema"] == contract["$schema"]
    assert error_schema["additionalProperties"] is False
    assert "contractVersion" in error_schema["required"]
    assert error_schema["properties"]["contractVersion"]["const"] == contract["contractVersion"]
    tools = contract["tools"]
    assert tools and len({tool["name"] for tool in tools}) == len(tools)
    checked = 0
    for tool in tools:
        assert tool["sideEffects"] is False, tool["name"]
        for schema_name in ("inputSchema", "resultSchema"):
            schema = tool[schema_name]
            assert schema["$schema"] == contract["$schema"]
            assert schema["additionalProperties"] is False
            assert "contractVersion" in schema["required"]
            assert schema["properties"]["contractVersion"]["const"] == contract["contractVersion"]
        assert tool["errorCodes"]
        assert set(tool["examples"]) == {"validInput", "invalidInput", "validResult", "error"}
        assert tool["examples"]["error"]["code"] in tool["errorCodes"]
        for key, schema in (
            ("validInput", tool["inputSchema"]),
            ("invalidInput", tool["inputSchema"]),
            ("validResult", tool["resultSchema"]),
            ("error", contract["errorSchema"]),
        ):
            result = matches(tool["examples"][key], schema)
            assert result == (key != "invalidInput"), f"{tool['name']}:{key} fixture mismatch"
            checked += 1
        if tool["name"] == "search.query":
            request = tool["examples"]["validInput"]
            required = {item["id"]: item["criterion"] for item in request["filters"] if item["required"]}
            assert "camisa branca" in request["request"].lower()
            assert required.get("category") == "camisa"
            assert required.get("color") == "branca"
            fixture = tool["examples"]["validResult"]
            assert valid_search_result(fixture, request["sort"])
            false_match = json.loads(json.dumps(fixture))
            false_match["results"][0]["filterResults"][0]["status"] = "fail"
            assert not valid_search_result(false_match, request["sort"])
            false_sort_direction = json.loads(json.dumps(fixture))
            false_sort_direction["sortAudit"]["requested"][1]["direction"] = "ascending"
            assert not valid_search_result(false_sort_direction, request["sort"])
            false_sort_status = json.loads(json.dumps(fixture))
            false_sort_status["sortAudit"]["status"] = "applied"
            assert not valid_search_result(false_sort_status, request["sort"])

    tie_break_fixture = json.loads(SORT_TIE_BREAK_FIXTURE.read_text(encoding="utf-8"))
    assert len(tie_break_fixture["sort"]) == 2
    assert tie_break_fixture["sort"][0]["direction"] != tie_break_fixture["sort"][1]["direction"]
    assert tie_break_fixture["items"][0]["attributes"][tie_break_fixture["sort"][0]["field"]] == tie_break_fixture["items"][1]["attributes"][tie_break_fixture["sort"][0]["field"]]
    assert sort_fixture_is_ordered(tie_break_fixture)
    wrong_tie_break = json.loads(json.dumps(tie_break_fixture))
    wrong_tie_break["items"][0], wrong_tie_break["items"][1] = wrong_tie_break["items"][1], wrong_tie_break["items"][0]
    assert not sort_fixture_is_ordered(wrong_tie_break)
    print(f"contract-fixtures: {checked} checked; tools: {len(tools)}; version: {contract['contractVersion']}")


if __name__ == "__main__":
    main()
