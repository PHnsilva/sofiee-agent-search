"""One-shot JSON interface for the local search runtime."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_runtime import execute
from agent_runtime.contracts import error_result


def main() -> int:
    raw = sys.stdin.buffer.read(80_001)
    if len(raw) > 80_000:
        print(json.dumps(error_result("limit_exceeded", "Request exceeds 80000 bytes.")))
        return 2
    try:
        request = json.loads(raw.decode("utf-8"))
        if not isinstance(request, dict) or set(request) != {"tool", "input"}:
            raise ValueError
        result = execute(request["tool"], request["input"])
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
        print(json.dumps(error_result("invalid_request", "Expected JSON with tool and input.")))
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if "code" not in result else 2


if __name__ == "__main__":
    raise SystemExit(main())
