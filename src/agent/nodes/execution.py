"""
MCP Execution Coordinator Node (Deterministic Service).
Dispatches validated read-only SQL queries through the MCP Client, captures tabular results or runtime errors,
and performs post-execution Result Validation against the Planner's structured_intent.
"""

from typing import Any, Dict
from src.agent.state import AgentState
from src.mcp_client import default_mcp_client


def mcp_execution_coordinator_node(state: AgentState, mcp_client=None) -> Dict[str, Any]:
    """
    Executes all validated SQL statements through the custom MCP Server.
    Validates that the returned columns and row cardinality match the structured intent.
    """
    client = mcp_client or default_mcp_client
    generated_sql = state.get("generated_sql") or {}
    structured_intent = state.get("structured_intent") or {}
    execution_results: Dict[str, Any] = dict(state.get("execution_results") or {})
    execution_errors: Dict[str, str] = {}

    intent_type = structured_intent.get("intent")
    expected_attr = structured_intent.get("attribute")
    expected_entity = structured_intent.get("entity")

    for source, sql in generated_sql.items():
        try:
            result = client.execute_read_query(source, sql)
            columns = result.get("columns") or []
            rows = result.get("rows") or []

            # Post-Execution Result Validation for exact entity lookups
            if intent_type == "entity_attribute_lookup" and source == structured_intent.get("source"):
                if expected_attr and expected_attr not in columns:
                    execution_errors[source] = (
                        f"Result validation failed: expected attribute '{expected_attr}' in columns, got {columns}"
                    )
                    continue
                if expected_attr != "stock_level" and "stock_level" in columns:
                    execution_errors[source] = (
                        f"Result validation failed: query returned unrelated 'stock_level' column for '{expected_attr}' lookup"
                    )
                    continue
                if len(rows) > 1:
                    execution_errors[source] = (
                        f"Result validation failed: expected 1 row for entity '{expected_entity}', but returned {len(rows)} rows"
                    )
                    continue

            execution_results[source] = result
        except Exception as e:
            execution_errors[source] = str(e)

    status = "execution_failed" if execution_errors else "executed"
    return {
        "execution_results": execution_results,
        "execution_errors": execution_errors,
        "execution_status": status,
    }
