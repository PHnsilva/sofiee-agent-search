from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from agent_runtime.contracts import TOOLS


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "run_runtime.py"


class SearchRuntimeTaskCliTests(unittest.TestCase):
    def test_cli_returns_missing_source_dependency_without_relaxing_filters(self):
        task = {
            "contractVersion": "1.0.0",
            "objective": "Buscar uma camisa e preservar filtros",
            "stages": [
                {"id": "query", "tool": "search.query", "input": TOOLS["search.query"]["examples"]["validInput"]},
                {"id": "audit", "tool": "search.audit", "dependsOn": ["query"], "input": {"sourceStage": "query"}},
            ],
        }
        completed = subprocess.run(
            [sys.executable, str(CLI)], input=json.dumps({"task": task}), text=True, capture_output=True, cwd=ROOT, timeout=10, check=False
        )
        self.assertEqual(completed.returncode, 2, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["stages"][0]["error"]["code"], "source_unavailable")
        self.assertEqual(result["stages"][1]["blockedBy"], ["query"])


if __name__ == "__main__":
    unittest.main()
