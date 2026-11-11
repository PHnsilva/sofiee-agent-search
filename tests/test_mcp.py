"""Exercise discovery and a real MCP call against the local stdio process."""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
SERVER = StdioServerParameters(
    command=sys.executable,
    args=["-m", "agent_runtime.mcp_server"],
    cwd=ROOT,
)
EXPECTED_NAMES = {'search.query'}
PAYLOAD = {'contractVersion': '1.0.0',
 'request': 'find a white shirt size M',
 'query': 'white shirt',
 'filters': [{'id': 'category', 'criterion': 'shirt', 'required': True},
             {'id': 'color', 'criterion': 'white', 'required': True},
             {'id': 'size', 'criterion': 'M', 'required': True}],
 'sourceHints': [],
 'sort': [],
 'pageLimit': 10,
 'cursor': ''}


async def discover_and_call():
    async with Client(SERVER) as client:
        listing = await client.list_tools()
        names = {item.name for item in listing.tools}
        tools = {item.name: item for item in listing.tools}
        result = await client.call_tool("search.query", PAYLOAD)
        return names, tools, result


class McpTransportTests(unittest.TestCase):
    def test_real_client_discovers_contract_tools_and_calls_domain_operation(self):
        names, tools, result = asyncio.run(discover_and_call())
        self.assertSetEqual(names, EXPECTED_NAMES)
        self.assertEqual(tools["search.query"].input_schema["$id"], "https://sofiee-agent-search.local/contracts/v1/query.input.schema.json")
        self.assertIsInstance(result.structured_content, dict)
        self.assertEqual(result.structured_content.get("contractVersion"), "1.0.0")
        self.assertTrue(result.is_error)
        self.assertEqual(result.structured_content.get("code"), "source_unavailable")


if __name__ == "__main__":
    unittest.main()
