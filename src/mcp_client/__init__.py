"""
MCP Client connector wrapping the custom Multi-Source MCP Server.
"""

from src.mcp_client.client import MCPClient, default_mcp_client

__all__ = ["MCPClient", "default_mcp_client"]
