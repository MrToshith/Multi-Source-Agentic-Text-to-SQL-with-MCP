"""
Schema & Source Context Builder Node (Deterministic Service).
Retrieves table schemas, foreign keys, and sample rows dynamically via MCP tool calls.
"""

from typing import Any, Dict, List
from src.agent.state import AgentState, SubQueryTask
from src.agent.intent_resolver import resolve_query_intent
from src.mcp_client import default_mcp_client


def schema_context_builder_node(state: AgentState, mcp_client=None) -> Dict[str, Any]:
    """
    Executes just-in-time schema discovery through the MCP Client for
    the sources and tables identified by structured_intent or pre-supplied plan.
    """
    client = mcp_client or default_mcp_client
    user_query = state.get("user_query") or ""
    structured_intent = state.get("structured_intent") or resolve_query_intent(user_query, client)
    plan: List[SubQueryTask] = list(state.get("plan") or [])

    # If plan was not pre-set, derive source tasks directly from structured_intent
    if not plan:
        sources = structured_intent.get("sources")
        primary_source = structured_intent.get("source")
        group_by = structured_intent.get("group_by")
        intent_type = structured_intent.get("intent")
        join_key = structured_intent.get("join_key") or "region_id"

        if sources:
            for s in sources:
                if s == "sales_pg":
                    plan.append(
                        SubQueryTask(
                            sub_task_id="sub_sales_pg",
                            source="sales_pg",
                            description=f"Sales metrics for: {user_query}",
                            target_tables=["orders", "regions"],
                            join_key=join_key,
                        )
                    )
                elif s == "crm_mssql":
                    plan.append(
                        SubQueryTask(
                            sub_task_id="sub_crm_mssql",
                            source="crm_mssql",
                            description=f"CRM metrics for: {user_query}",
                            target_tables=["customers", "complaints"],
                            join_key=join_key,
                        )
                    )
        elif primary_source == "analytics_duckdb":
            tbl = structured_intent.get("table") or "products"
            tables = (
                ["products", "inventory"]
                if (
                    tbl == "inventory"
                    or intent_type in ("stock_level", "inventory_filtering")
                    or "stock" in user_query.lower()
                    or "warehouse" in user_query.lower()
                )
                else ["products"]
            )
            plan.append(
                SubQueryTask(
                    sub_task_id="sub_analytics_duckdb",
                    source="analytics_duckdb",
                    description=f"Analytics for: {user_query}",
                    target_tables=tables,
                    join_key="product_id",
                )
            )
        elif primary_source == "crm_mssql":
            tables = ["customers", "complaints"] if group_by else ["complaints"]
            plan.append(
                SubQueryTask(
                    sub_task_id="sub_crm_mssql",
                    source="crm_mssql",
                    description=f"CRM metrics for: {user_query}",
                    target_tables=tables,
                    join_key="customer_id",
                )
            )
        else:  # default sales_pg
            tables = (
                ["orders", "regions"]
                if (
                    group_by
                    or intent_type in ("top_max_min", "grouped_aggregation")
                    or "region" in user_query.lower()
                )
                else ["orders"]
            )
            plan.append(
                SubQueryTask(
                    sub_task_id="sub_sales_pg",
                    source="sales_pg",
                    description=f"Sales metrics for: {user_query}",
                    target_tables=tables,
                    join_key="region_id",
                )
            )

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

    join_keys = state.get("join_keys") or [structured_intent.get("join_key") or "region_id"]
    return {
        "structured_intent": structured_intent,
        "plan": plan,
        "join_keys": join_keys,
        "schema_context": schema_context,
        "execution_status": "context_built",
    }

