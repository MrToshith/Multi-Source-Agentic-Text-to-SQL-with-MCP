"""
Dialect-Aware Text-to-SQL Generator Node.
Uses the Planner's structured_intent to generate native read-only SQL tailored to
PostgreSQL, SQL Server (T-SQL), and DuckDB without reinterpreting exact entity lookups into broad inventory queries.
"""

from typing import Any, Dict, Optional
from src.agent.state import AgentState
from src.agent.intent_resolver import resolve_query_intent


def generate_dialect_sql_for_source(
    source: str,
    user_query: str,
    join_key: str = "region_id",
    structured_intent: Optional[Dict[str, Any]] = None,
) -> str:
    """Produces dialect-specific SQL for a given target source and structured intent."""
    q_lower = user_query.lower()
    filter_q4 = "q4" in q_lower or "last quarter" in q_lower
    intent_obj = structured_intent or resolve_query_intent(user_query)
    intent_type = intent_obj.get("intent")

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
        # A) Exact Entity Attribute Lookup
        if intent_type == "entity_attribute_lookup" and intent_obj.get("entity"):
            entity_val = str(intent_obj["entity"]).replace("'", "''")
            attr = intent_obj.get("attribute") or "cost_price"
            table = intent_obj.get("table") or "products"

            if table == "inventory":
                return (
                    f"SELECT p.product_name, i.{attr} "
                    f"FROM inventory i "
                    f"JOIN products p ON i.product_id = p.product_id "
                    f"WHERE p.product_name = '{entity_val}' "
                    f"LIMIT 1"
                )
            return (
                f"SELECT product_name, {attr} "
                f"FROM products "
                f"WHERE product_name = '{entity_val}' "
                f"LIMIT 1"
            )

        # B) Filtering / Listing
        if intent_type == "filtering":
            f_cond = intent_obj.get("filter_condition") or {}
            col = f_cond.get("column") or "stock_level"
            op = f_cond.get("operator") or "<"
            val = f_cond.get("value", 300)
            table = intent_obj.get("table") or "inventory"

            if table == "products" and col == "category":
                safe_val = str(val).replace("'", "''")
                return (
                    f"SELECT product_id, product_name, category, cost_price, list_price "
                    f"FROM products "
                    f"WHERE LOWER(category) = LOWER('{safe_val}') "
                    f"LIMIT 50"
                )
            return (
                f"SELECT p.product_id, p.product_name, p.category, p.list_price, "
                f"i.warehouse_location, i.stock_level, i.reorder_point "
                f"FROM products p "
                f"JOIN inventory i ON p.product_id = i.product_id "
                f"WHERE i.{col} {op} {val} "
                f"ORDER BY i.{col} ASC "
                f"LIMIT 50"
            )

        # C) Aggregation / Ranking
        if intent_type == "aggregation":
            agg_spec = intent_obj.get("aggregation")
            order_spec = intent_obj.get("order_by")
            table = intent_obj.get("table") or "products"

            if agg_spec:
                fn = agg_spec.get("function", "AVG")
                col = agg_spec.get("column", "cost_price")
                alias = f"{fn.lower()}_{col}"
                return f"SELECT ROUND({fn}({col}), 2) AS {alias} FROM {table}"

            if order_spec:
                col = order_spec.get("column", "list_price")
                direction = order_spec.get("direction", "DESC")
                limit_val = int(order_spec.get("limit", 1))
                if table == "inventory":
                    return (
                        f"SELECT p.product_name, i.{col} "
                        f"FROM inventory i "
                        f"JOIN products p ON i.product_id = p.product_id "
                        f"ORDER BY i.{col} {direction} "
                        f"LIMIT {limit_val}"
                    )
                return (
                    f"SELECT product_name, {col} "
                    f"FROM products "
                    f"ORDER BY {col} {direction} "
                    f"LIMIT {limit_val}"
                )

        # Fallback for general cross-source product/inventory joins
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
    Drafts dialect-aware SQL queries for every planned source using the Planner's structured_intent.
    Preserves any pre-supplied generated_sql if already set (e.g. during retry/test injection).
    """
    existing_sql = state.get("generated_sql") or {}
    if existing_sql and state.get("retry_count", 0) > 0:
        return {"generated_sql": existing_sql, "execution_status": "sql_generated"}

    user_query = state.get("user_query") or ""
    plan = state.get("plan") or []
    structured_intent = state.get("structured_intent") or resolve_query_intent(user_query)
    join_keys = state.get("join_keys") or ["region_id"]
    primary_join_key = join_keys[0] if join_keys else "region_id"

    generated_sql: Dict[str, str] = {}
    for task in plan:
        source = task.get("source")
        task_join_key = task.get("join_key") or primary_join_key
        if source:
            if source in existing_sql:
                generated_sql[source] = existing_sql[source]
            else:
                generated_sql[source] = generate_dialect_sql_for_source(
                    source,
                    user_query,
                    join_key=task_join_key,
                    structured_intent=structured_intent,
                )

    return {
        "structured_intent": structured_intent,
        "generated_sql": generated_sql,
        "execution_status": "sql_generated",
    }
