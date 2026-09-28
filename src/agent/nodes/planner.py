"""
Query Planner & Source Selector Node.
Produces a structured intent and decomposes user questions into single-source sub-tasks and cross-source join keys.
"""

from typing import Any, Dict, List
from src.agent.state import AgentState, SubQueryTask
from src.agent.llm import default_llm_client
from src.agent.prompts.planner import PLANNER_SYSTEM_PROMPT, format_planner_prompt
from src.agent.intent_resolver import resolve_query_intent
from src.mcp_client import default_mcp_client


def query_planner_node(state: AgentState, mcp_client=None) -> Dict[str, Any]:
    """
    Analyzes the user query and produces both a structured_intent and a multi-source execution plan.
    """
    client = mcp_client or default_mcp_client
    user_query = (state.get("user_query") or "").strip()
    q_lower = user_query.lower()

    structured_intent = state.get("structured_intent") or resolve_query_intent(user_query, client)
    intent_type = structured_intent.get("intent")

    # 1. Exact Entity Attribute Lookup or Single-Source DuckDB Filtering/Aggregation
    if intent_type in ("entity_attribute_lookup", "filtering", "aggregation") and structured_intent.get("source") == "analytics_duckdb":
        primary_table = structured_intent.get("table") or "products"
        if primary_table == "products":
            target_tables = ["products"]
        else:
            target_tables = ["inventory", "products"]

        plan: List[SubQueryTask] = [
            SubQueryTask(
                sub_task_id="sub_analytics_duckdb",
                source="analytics_duckdb",
                description=f"Execute {intent_type} on {primary_table} for: {user_query}",
                target_tables=target_tables,
                join_key="product_id",
            )
        ]
        return {
            "structured_intent": structured_intent,
            "plan": plan,
            "join_keys": ["product_id"],
            "execution_status": "planned",
        }

    available_sources = client.list_data_sources()

    # Deterministic domain analysis & source decomposition for grouping and cross-source queries
    needs_sales = any(
        kw in q_lower
        for kw in ("sale", "revenue", "order", "rep", "amount", "subtotal", "quarter", "region")
    )
    needs_crm = any(
        kw in q_lower
        for kw in ("complaint", "ticket", "customer", "tier", "churn", "severity", "support", "crm")
    )
    needs_analytics = any(
        kw in q_lower
        for kw in ("product", "inventory", "stock", "warehouse", "reorder", "catalog", "price", "cost")
    )

    # Refine: if the user asks about complaints by region, we need both crm_mssql and sales_pg (for region_name)
    if needs_crm and "region" in q_lower:
        needs_sales = True

    # If only asking about products/inventory, don't pull sales unless orders/revenue mentioned
    if needs_analytics and not any(kw in q_lower for kw in ("sale", "revenue", "order", "complaint", "customer")):
        needs_sales = False
        needs_crm = False

    if not (needs_sales or needs_crm or needs_analytics):
        needs_sales = True

    plan = []
    join_keys: List[str] = []

    if needs_sales and needs_crm:
        if "customer" in q_lower and "region" not in q_lower:
            join_keys.append("customer_id")
        else:
            join_keys.append("region_id")

    if needs_sales and needs_analytics:
        if "product_id" not in join_keys:
            join_keys.append("product_id")

    primary_join_key = join_keys[0] if join_keys else None

    if needs_sales:
        sales_tables = ["regions", "orders"]
        if "product" in q_lower or "item" in q_lower or primary_join_key == "product_id":
            sales_tables.append("order_items")
        if "rep" in q_lower:
            sales_tables.append("sales_reps")

        plan.append(
            SubQueryTask(
                sub_task_id="sub_sales_pg",
                source="sales_pg",
                description=f"Retrieve sales and order metrics for: {user_query}",
                target_tables=sales_tables,
                join_key=primary_join_key or "region_id",
            )
        )

    if needs_crm:
        crm_tables = ["customers", "complaints"]
        plan.append(
            SubQueryTask(
                sub_task_id="sub_crm_mssql",
                source="crm_mssql",
                description=f"Retrieve customer and complaint metrics for: {user_query}",
                target_tables=crm_tables,
                join_key=primary_join_key or "region_id",
            )
        )

    if needs_analytics:
        analytics_tables = ["products", "inventory"]
        plan.append(
            SubQueryTask(
                sub_task_id="sub_analytics_duckdb",
                source="analytics_duckdb",
                description=f"Retrieve product catalog and inventory levels for: {user_query}",
                target_tables=analytics_tables,
                join_key="product_id",
            )
        )

    return {
        "structured_intent": structured_intent,
        "plan": plan,
        "join_keys": join_keys,
        "execution_status": "planned",
    }
