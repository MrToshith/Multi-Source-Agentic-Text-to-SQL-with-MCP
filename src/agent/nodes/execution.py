"""
MCP Execution Coordinator Node (Deterministic Service).
Dispatches generated read-only SQL queries through the MCP Client and dynamically
chains cross-source entity keys (e.g. PostgreSQL order.customer_id -> SQL Server customers lookup).
"""

from typing import Any, Dict
from src.agent.state import AgentState
from src.mcp_client import default_mcp_client


def mcp_execution_coordinator_node(state: AgentState, mcp_client=None) -> Dict[str, Any]:
    """
    Executes all generated SQL statements through the MCP Client.
    Handles dynamic entity key propagation across distributed data sources.
    """
    client = mcp_client or default_mcp_client
    generated_sql = dict(state.get("generated_sql") or {})
    structured_intent = dict(state.get("structured_intent") or {})
    execution_results: Dict[str, Any] = dict(state.get("execution_results") or {})
    execution_errors: Dict[str, str] = {}

    intent_type = structured_intent.get("intent")

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

