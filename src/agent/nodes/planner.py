"""
Query Planner & Source Selector Node.
Decomposes user questions into single-source sub-tasks and identifies cross-source join keys.
"""

from typing import Any, Dict, List
from src.agent.state import AgentState, SubQueryTask
from src.agent.llm import default_llm_client
from src.agent.prompts.planner import PLANNER_SYSTEM_PROMPT, format_planner_prompt
from src.mcp_client import default_mcp_client


def query_planner_node(state: AgentState, mcp_client=None) -> Dict[str, Any]:
    """
    Analyzes the user query and produces a structured multi-source execution plan.
    """
    client = mcp_client or default_mcp_client
    user_query = (state.get("user_query") or "").strip()
    q_lower = user_query.lower()

    available_sources = client.list_data_sources()

    # Try local LLM if enabled
    llm_result = default_llm_client.generate_json(
        prompt=format_planner_prompt(user_query, available_sources),
        system_prompt=PLANNER_SYSTEM_PROMPT,
    )
    if llm_result and isinstance(llm_result.get("plan"), list) and len(llm_result["plan"]) > 0:
        return {
            "plan": llm_result["plan"],
            "join_keys": llm_result.get("join_keys", []),
            "execution_status": "planned",
        }

    # Deterministic domain analysis & source decomposition
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
        for kw in ("product", "inventory", "stock", "warehouse", "reorder", "catalog", "price")
    )

    # Refine: if the user only asks about complaints by region, we need both crm_mssql and sales_pg (for region_name)
    if needs_crm and "region" in q_lower:
        needs_sales = True

    # If only asking about products/inventory, don't pull sales unless orders/revenue mentioned
    if needs_analytics and not any(kw in q_lower for kw in ("sale", "revenue", "order", "complaint", "customer")):
        needs_sales = False
        needs_crm = False

    # Default to sales_pg if no specific keyword matched
    if not (needs_sales or needs_crm or needs_analytics):
        needs_sales = True

    plan: List[SubQueryTask] = []
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
        "plan": plan,
        "join_keys": join_keys,
        "execution_status": "planned",
    }
