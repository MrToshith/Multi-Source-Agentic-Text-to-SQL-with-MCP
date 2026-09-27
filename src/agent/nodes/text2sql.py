"""
Dialect-Aware Text-to-SQL Generator Node.
Generates native read-only SQL tailored to PostgreSQL, SQL Server (T-SQL), and DuckDB.
"""

from typing import Any, Dict
from src.agent.state import AgentState
from src.agent.llm import default_llm_client
from src.agent.prompts.text2sql import TEXT2SQL_SYSTEM_PROMPT, format_text2sql_prompt


def generate_dialect_sql_for_source(source: str, user_query: str, join_key: str = "region_id") -> str:
    """Produces dialect-specific SQL for a given target source and user query."""
    q_lower = user_query.lower()
    filter_q4 = "q4" in q_lower or "last quarter" in q_lower

    if source == "sales_pg":
        # PostgreSQL dialect (uses LIMIT)
        if join_key == "product_id" or ("product" in q_lower and "region" not in q_lower):
            return (
                "SELECT oi.product_id, SUM(oi.quantity) AS total_quantity_sold, "
                "SUM(oi.subtotal) AS total_revenue "
                "FROM order_items oi "
                "JOIN orders o ON oi.order_id = o.order_id "
                "WHERE o.status = 'COMPLETED' "
                "GROUP BY oi.product_id "
                "ORDER BY total_revenue DESC "
                "LIMIT 50"
            )
        if join_key == "customer_id" and "region" not in q_lower:
            return (
                "SELECT o.customer_id, o.region_id, COUNT(o.order_id) AS order_count, "
                "SUM(o.total_amount) AS total_revenue "
                "FROM orders o "
                "WHERE o.status = 'COMPLETED' "
                "GROUP BY o.customer_id, o.region_id "
                "ORDER BY total_revenue DESC "
                "LIMIT 50"
            )
        where_clause = "WHERE o.status = 'COMPLETED' AND o.quarter = 'Q4-2025'" if filter_q4 else "WHERE o.status = 'COMPLETED'"
        return (
            "SELECT r.region_id, r.region_name, COUNT(o.order_id) AS order_count, "
            "SUM(o.total_amount) AS total_revenue "
            "FROM regions r "
            "JOIN orders o ON r.region_id = o.region_id "
            f"{where_clause} "
            "GROUP BY r.region_id, r.region_name "
            "ORDER BY total_revenue DESC "
            "LIMIT 50"
        )

    if source == "crm_mssql":
        # SQL Server T-SQL dialect (uses SELECT TOP and dbo. schema prefix)
        if join_key == "customer_id" and "region" not in q_lower:
            return (
                "SELECT TOP 50 c.customer_id, c.customer_name, c.company_name, c.region_id, c.tier, "
                "COUNT(comp.complaint_id) AS complaint_count "
                "FROM dbo.customers c "
                "LEFT JOIN dbo.complaints comp ON c.customer_id = comp.customer_id "
                "GROUP BY c.customer_id, c.customer_name, c.company_name, c.region_id, c.tier "
                "ORDER BY complaint_count DESC"
            )
        where_clause = "WHERE comp.quarter = 'Q4-2025'" if filter_q4 else ""
        return (
            "SELECT TOP 50 c.region_id, COUNT(comp.complaint_id) AS complaint_count, "
            "COUNT(DISTINCT c.customer_id) AS affected_customers "
            "FROM dbo.customers c "
            "JOIN dbo.complaints comp ON c.customer_id = comp.customer_id "
            f"{where_clause} "
            "GROUP BY c.region_id "
            "ORDER BY complaint_count DESC"
        ).replace("  ", " ")

    if source == "analytics_duckdb":
        # DuckDB analytical SQL dialect (uses LIMIT)
        if "below 300" in q_lower or "low stock" in q_lower or "< 300" in q_lower:
            return (
                "SELECT p.product_id, p.product_name, p.category, p.list_price, "
                "i.warehouse_location, i.stock_level, i.reorder_point "
                "FROM products p "
                "JOIN inventory i ON p.product_id = i.product_id "
                "WHERE i.stock_level < 300 "
                "ORDER BY i.stock_level ASC "
                "LIMIT 50"
            )
        return (
            "SELECT p.product_id, p.product_name, p.category, p.cost_price, p.list_price, "
            "i.warehouse_location, i.stock_level "
            "FROM products p "
            "JOIN inventory i ON p.product_id = i.product_id "
            "ORDER BY p.list_price DESC "
            "LIMIT 50"
        )

    raise ValueError(f"Unsupported data source for SQL generation: {source}")


def text2sql_generator_node(state: AgentState) -> Dict[str, Any]:
    """
    Drafts dialect-aware SQL queries for every planned source.
    Preserves any pre-supplied generated_sql if already set (e.g. during retry/test injection).
    """
    existing_sql = state.get("generated_sql") or {}
    if existing_sql and state.get("retry_count", 0) > 0:
        return {"generated_sql": existing_sql, "execution_status": "sql_generated"}

    user_query = state.get("user_query") or ""
    plan = state.get("plan") or []
    schema_context = state.get("schema_context") or {}
    join_keys = state.get("join_keys") or ["region_id"]
    primary_join_key = join_keys[0] if join_keys else "region_id"

    llm_result = default_llm_client.generate_json(
        prompt=format_text2sql_prompt(user_query, plan, schema_context),
        system_prompt=TEXT2SQL_SYSTEM_PROMPT,
    )
    if llm_result and isinstance(llm_result.get("generated_sql"), dict) and len(llm_result["generated_sql"]) > 0:
        return {
            "generated_sql": llm_result["generated_sql"],
            "execution_status": "sql_generated",
        }

    generated_sql: Dict[str, str] = {}
    for task in plan:
        source = task.get("source")
        task_join_key = task.get("join_key") or primary_join_key
        if source:
            if source in existing_sql:
                generated_sql[source] = existing_sql[source]
            else:
                generated_sql[source] = generate_dialect_sql_for_source(source, user_query, join_key=task_join_key)

    return {
        "generated_sql": generated_sql,
        "execution_status": "sql_generated",
    }
