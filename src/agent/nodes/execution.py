"""
MCP Execution Coordinator Node (Deterministic Service).
Dispatches validated read-only SQL queries through the MCP Client, chains cross-source entity keys
(e.g., PostgreSQL order.customer_id -> SQL Server customers lookup), and performs strict Result-Shape Validation.
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
    generated_sql = dict(state.get("generated_sql") or {})
    structured_intent = dict(state.get("structured_intent") or {})
    execution_results: Dict[str, Any] = dict(state.get("execution_results") or {})
    execution_errors: Dict[str, str] = {}

    intent_type = structured_intent.get("intent")
    expected_attr = structured_intent.get("attribute")
    expected_attrs = structured_intent.get("attributes") or ([expected_attr] if expected_attr else [])
    expected_entity = structured_intent.get("entity")
    expected_limit = int(structured_intent.get("limit") or 1)

    # Ensure sales_pg executes before crm_mssql for cross-source entity lookup chaining
    ordered_sources = [
        s for s in ("sales_pg", "crm_mssql", "analytics_duckdb") if s in generated_sql
    ] + [s for s in generated_sql if s not in ("sales_pg", "crm_mssql", "analytics_duckdb")]

    for source in ordered_sources:
        sql = generated_sql[source]

        # Dynamic cross-source key chaining: if sales_pg found customer_id, filter crm_mssql by that customer_id
        if (
            intent_type == "cross_source_entity_lookup"
            and source == "crm_mssql"
            and "sales_pg" in execution_results
        ):
            pg_res = execution_results["sales_pg"]
            pg_cols = pg_res.get("columns") or []
            pg_rows = pg_res.get("rows") or []
            if pg_rows and "customer_id" in pg_cols:
                cid_idx = pg_cols.index("customer_id")
                cid_val = pg_rows[0][cid_idx] if isinstance(pg_rows[0], (list, tuple)) else pg_rows[0].get("customer_id")
                if cid_val is not None:
                    sql = (
                        f"SELECT TOP 1 customer_id, customer_name, company_name, tier, region_id "
                        f"FROM dbo.customers "
                        f"WHERE customer_id = {int(cid_val)}"
                    )
                    generated_sql["crm_mssql"] = sql

        try:
            result = client.execute_read_query(source, sql)
            columns = result.get("columns") or []
            rows = result.get("rows") or []

            # =================================================================
            # RESULT-SHAPE VALIDATION
            # =================================================================

            # 1. Single Entity Attribute Lookup
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

            # 2. Multi-Attribute Lookup & Attribute Difference
            elif intent_type in ("multi_attribute_lookup", "attribute_difference") and source == structured_intent.get("source"):
                missing_attrs = [a for a in expected_attrs if a not in columns]
                if missing_attrs:
                    execution_errors[source] = (
                        f"Result validation failed: missing requested attributes {missing_attrs} in columns {columns}"
                    )
                    continue
                if intent_type == "attribute_difference" and "price_difference" not in columns:
                    execution_errors[source] = (
                        f"Result validation failed: missing arithmetic column 'price_difference' in columns {columns}"
                    )
                    continue
                if len(rows) > 1:
                    execution_errors[source] = (
                        f"Result validation failed: expected 1 row for entity '{expected_entity}', got {len(rows)} rows"
                    )
                    continue

            # 3. Total / Count Scalar Aggregation (Must be 1 scalar row without regional grouping)
            elif intent_type in ("total_aggregation", "count_aggregation"):
                if "region_id" in columns or "region_name" in columns or len(rows) > 1:
                    execution_errors[source] = (
                        f"Result validation failed: expected 1 ungrouped scalar row, got {len(rows)} rows with columns {columns}"
                    )
                    continue

            # 4. Top / Max / Min Ranking
            elif intent_type == "top_max_min":
                if len(rows) > expected_limit:
                    execution_errors[source] = (
                        f"Result validation failed: expected at most {expected_limit} top row(s), got {len(rows)} rows"
                    )
                    continue

            execution_results[source] = result
        except Exception as e:
            execution_errors[source] = str(e)

    status = "execution_failed" if execution_errors else "executed"
    return {
        "generated_sql": generated_sql,
        "execution_results": execution_results,
        "execution_errors": execution_errors,
        "execution_status": status,
    }
