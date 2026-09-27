"""
MCP Client connector wrapping official MCP SDK server tool invocations.
Provides the strict tool boundary between the LangGraph reasoning engine and the custom MCP Server.
"""

import asyncio
import concurrent.futures
import json
from typing import Any, Dict, List, Optional
from mcp.server.mcpserver import MCPServer

from src.mcp_server.server import create_mcp_server


class MCPClient:
    """Client interface for invoking tools on the custom Multi-Source MCP Server."""

    def __init__(self, server: Optional[MCPServer] = None):
        self._server = server or create_mcp_server()

    def _run_async(self, coro):
        """Executes an async MCP tool call safely whether inside or outside an event loop."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        return asyncio.run(coro)

    def _extract_payload(self, call_result) -> Any:
        """Extracts structured Python objects from MCP CallToolResult."""
        if getattr(call_result, "is_error", False):
            err_text = " ".join(getattr(c, "text", str(c)) for c in call_result.content)
            raise RuntimeError(f"MCP Tool Error: {err_text}")

        if getattr(call_result, "structured_content", None) is not None:
            sc = call_result.structured_content
            if isinstance(sc, dict) and "result" in sc:
                return sc["result"]
            return sc

        items = []
        for content in call_result.content:
            text = getattr(content, "text", "")
            try:
                items.append(json.loads(text))
            except Exception:
                items.append(text)

        if len(items) == 1:
            return items[0]
        return items

    def list_data_sources(self) -> List[Dict[str, Any]]:
        res = self._run_async(self._server.call_tool("list_data_sources", {}))
        payload = self._extract_payload(res)
        return payload if isinstance(payload, list) else [payload]

    def list_tables(self, source: str) -> List[str]:
        res = self._run_async(self._server.call_tool("list_tables", {"source": source}))
        payload = self._extract_payload(res)
        return payload if isinstance(payload, list) else [str(payload)]

    def describe_table(self, source: str, table: str) -> Dict[str, Any]:
        res = self._run_async(self._server.call_tool("describe_table", {"source": source, "table": table}))
        payload = self._extract_payload(res)
        return payload if isinstance(payload, dict) else {"table_name": table, "raw": payload}

    def get_relationships(self, source: str) -> List[Dict[str, Any]]:
        res = self._run_async(self._server.call_tool("get_relationships", {"source": source}))
        payload = self._extract_payload(res)
        return payload if isinstance(payload, list) else [payload]

    def get_sample_rows(self, source: str, table: str, limit: int = 3) -> List[Dict[str, Any]]:
        res = self._run_async(
            self._server.call_tool("get_sample_rows", {"source": source, "table": table, "limit": limit})
        )
        payload = self._extract_payload(res)
        return payload if isinstance(payload, list) else [payload]

    def execute_read_query(self, source: str, validated_sql: str) -> Dict[str, Any]:
        res = self._run_async(
            self._server.call_tool("execute_read_query", {"source": source, "validated_sql": validated_sql})
        )
        payload = self._extract_payload(res)
        return payload if isinstance(payload, dict) else {"raw": payload}


default_mcp_client = MCPClient()
