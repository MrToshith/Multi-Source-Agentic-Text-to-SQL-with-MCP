"""
MCP Execution Coordinator Node (Deterministic Service).
Dispatches validated read-only SQL queries through the MCP Client and captures tabular results or runtime errors.
"""

from typing import Any, Dict
from src.agent.state import AgentState
from src.mcp_client import default_mcp_client


def mcp_execution_coordinator_node(state: AgentState, mcp_client=None) -> Dict[str, Any]:
    """
    Executes all validated SQL statements through the custom MCP Server.
    Captures structured results in execution_results or runtime traces in execution_errors.
    """
    client = mcp_client or default_mcp_client
    generated_sql = state.get("generated_sql") or {}
    execution_results: Dict[str, Any] = dict(state.get("execution_results") or {})
    execution_errors: Dict[str, str] = {}

    for source, sql in generated_sql.items():
        try:
            result = client.execute_read_query(source, sql)
            execution_results[source] = result
        except Exception as e:
            execution_errors[source] = str(e)

    status = "execution_failed" if execution_errors else "executed"
    return {
        "execution_results": execution_results,
        "execution_errors": execution_errors,
        "execution_status": status,
    }
