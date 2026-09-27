"""
Schema & Source Context Builder Node (Deterministic Service).
Retrieves table schemas, foreign keys, and sample rows dynamically via MCP tool calls.
"""

from typing import Any, Dict
from src.agent.state import AgentState
from src.mcp_client import default_mcp_client


def schema_context_builder_node(state: AgentState, mcp_client=None) -> Dict[str, Any]:
    """
    Executes just-in-time schema discovery through the MCP Client strictly for
    the sources and tables selected by the Query Planner.
    """
    client = mcp_client or default_mcp_client
    plan = state.get("plan") or []

    schema_context: Dict[str, Any] = {}

    for task in plan:
        source = task.get("source")
        target_tables = task.get("target_tables") or []
        if not source:
            continue

        if source not in schema_context:
            relationships = client.get_relationships(source)
            schema_context[source] = {
                "tables": {},
                "relationships": relationships,
            }

        for table in target_tables:
            if table not in schema_context[source]["tables"]:
                table_schema = client.describe_table(source, table)
                sample_rows = client.get_sample_rows(source, table, limit=3)
                schema_context[source]["tables"][table] = {
                    "schema": table_schema,
                    "sample_rows": sample_rows,
                }

    return {
        "schema_context": schema_context,
        "execution_status": "context_built",
    }
