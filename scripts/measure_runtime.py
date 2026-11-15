"""Measure request planning cost without a network source or provider."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_runtime.contracts import TOOLS
from agent_runtime.search import make_search_plan


def main() -> int:
    request = TOOLS["search.query"]["examples"]["validInput"]
    iterations = 1000
    start = time.perf_counter()
    for _ in range(iterations):
        plan = make_search_plan(request)
        if len(plan.filters) != len(request["filters"]):
            raise RuntimeError("A request filter was lost while measuring the planner.")
    elapsed_ms = (time.perf_counter() - start) * 1000
    print(f"plan_calls={iterations} elapsed_ms={elapsed_ms:.2f} average_ms={elapsed_ms / iterations:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
