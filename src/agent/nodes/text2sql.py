"""
Dialect-Aware Text-to-SQL Generator Node.
Generates native read-only SQL strictly from the Planner's structured_intent for:
  1. entity_attribute_lookup
  2. multi_attribute_lookup
  3. attribute_difference
  4. total_aggregation (NO GROUP BY)
  5. count_aggregation (NO GROUP BY)
  6. grouped_aggregation (WITH GROUP BY)
  7. top_max_min (WITH ORDER BY & LIMIT)
  8. cross_source_entity_lookup
  9. cross_source_aggregation
  10. filtering
"""

from typing import Any, Dict, List, Optional
from src.agent.state import AgentState
from src.agent.intent_resolver import (
    INVENTORY_TABLE_ATTRIBUTES,
    PRODUCT_TABLE_ATTRIBUTES,
    resolve_query_intent,
)


def _build_pg_where(filters: Dict[str, Any], table_alias: str = "") -> str:
    prefix = f"{table_alias}." if table_alias else ""
    clauses: List[str] = []
    if filters.get("status"):
        clauses.append(f"{prefix}status = '{filters['status']}'")
    if filters.get("quarter"):
        clauses.append(f"{prefix}quarter = '{filters['quarter']}'")
    return f"WHERE {' AND '.join(clauses)}" if clauses else ""


def _build_mssql_complaint_where(filters: Dict[str, Any], table_alias: str = "") -> str:
    prefix = f"{table_alias}." if table_alias else ""
    clauses: List[str] = []
    if filters.get("quarter"):
        clauses.append(f"{prefix}quarter = '{filters['quarter']}'")
    if filters.get("complaint_status"):
        clauses.append(f"{prefix}status = '{filters['complaint_status']}'")
    return f"WHERE {' AND '.join(clauses)}" if clauses else ""


def generate_dialect_sql_for_source(
    source: str,
    user_query: str,
    join_key: str = "region_id",
    structured_intent: Optional[Dict[str, Any]] = None,
) -> str:
    """Produces dialect-specific SQL for a given target source and structured intent."""
    intent_obj = structured_intent or resolve_query_intent(user_query)
    intent_type = intent_obj.get("intent")
    filters = intent_obj.get("filters") or {}

    # =========================================================================
    # SOURCE 1: PostgreSQL (sales_pg)
    # =========================================================================
    if source == "sales_pg":
        # 8. Cross-Source Entity Lookup (e.g. Highest-value completed order in Q4-2025 -> customer_id)
        if intent_type == "cross_source_entity_lookup":
            where_sql = _build_pg_where(filters)
            direction = (intent_obj.get("order_by") or {}).get("direction", "DESC")
            limit_val = int(intent_obj.get("limit") or 1)
            return (
                f"SELECT order_id, customer_id, total_amount, quarter, status "
                f"FROM orders "
                f"{where_sql} "
                f"ORDER BY total_amount {direction} "
                f"LIMIT {limit_val}"
            ).replace("  ", " ").strip()

        # 4. Total Aggregation (Ungrouped SUM / AVG across matching orders)
        if intent_type == "total_aggregation":
            where_sql = _build_pg_where(filters)
            agg_fn = intent_obj.get("aggregation") or "SUM"
            return (
                f"SELECT COALESCE({agg_fn}(total_amount), 0) AS total_revenue "
                f"FROM orders "
                f"{where_sql}"
            ).replace("  ", " ").strip()

        # 5. Count Aggregation (Ungrouped COUNT across matching orders)
        if intent_type == "count_aggregation":
            where_sql = _build_pg_where(filters)
            return (
                f"SELECT COUNT(order_id) AS order_count "
                f"FROM orders "
                f"{where_sql}"
            ).replace("  ", " ").strip()

        # 7. Top / Max / Min Regional Revenue Ranking
        if intent_type == "top_max_min":
            where_sql = _build_pg_where(filters, table_alias="o")
            direction = (intent_obj.get("order_by") or {}).get("direction", "DESC")
            limit_val = int(intent_obj.get("limit") or 1)
            return (
                f"SELECT r.region_id, r.region_name, COUNT(o.order_id) AS order_count, "
                f"SUM(o.total_amount) AS total_revenue "
                f"FROM regions r "
                f"JOIN orders o ON r.region_id = o.region_id "
                f"{where_sql} "
                f"GROUP BY r.region_id, r.region_name "
                f"ORDER BY total_revenue {direction} "
                f"LIMIT {limit_val}"
            ).replace("  ", " ").strip()

        # 6 & 9. Grouped Aggregation / Cross-Source Aggregation by Region
        where_sql = _build_pg_where(filters, table_alias="o")
        return (
            f"SELECT r.region_id, r.region_name, COUNT(o.order_id) AS order_count, "
            f"SUM(o.total_amount) AS total_revenue "
            f"FROM regions r "
            f"JOIN orders o ON r.region_id = o.region_id "
            f"{where_sql} "
            f"GROUP BY r.region_id, r.region_name "
            f"ORDER BY total_revenue DESC "
            f"LIMIT 50"
        ).replace("  ", " ").strip()

    # =========================================================================
    # SOURCE 2: SQL Server (crm_mssql)
    # =========================================================================
    if source == "crm_mssql":
        # 8. Cross-Source Entity Lookup (Lookup customer name and company by customer_id)
        if intent_type == "cross_source_entity_lookup":
            target_cid = intent_obj.get("target_customer_id")
            if target_cid is not None:
                return (
                    f"SELECT TOP 1 customer_id, customer_name, company_name, tier, region_id "
                    f"FROM dbo.customers "
                    f"WHERE customer_id = {int(target_cid)}"
                )
            return (
                "SELECT TOP 50 customer_id, customer_name, company_name, tier, region_id "
                "FROM dbo.customers"
            )

        # 5. Count Aggregation (Ungrouped COUNT of complaints, e.g., "How many complaints were recorded in Q4-2025?")
        if intent_type in ("count_aggregation", "total_aggregation"):
            where_sql = _build_mssql_complaint_where(filters)
            return (
                f"SELECT COUNT(complaint_id) AS complaint_count "
                f"FROM dbo.complaints "
                f"{where_sql}"
            ).replace("  ", " ").strip()

        # 7. Top / Max / Min Regional Complaint Ranking
        if intent_type == "top_max_min":
            where_sql = _build_mssql_complaint_where(filters, table_alias="comp")
            direction = (intent_obj.get("order_by") or {}).get("direction", "DESC")
            limit_val = int(intent_obj.get("limit") or 1)
            return (
                f"SELECT TOP {limit_val} c.region_id, COUNT(comp.complaint_id) AS complaint_count "
                f"FROM dbo.customers c "
                f"JOIN dbo.complaints comp ON c.customer_id = comp.customer_id "
                f"{where_sql} "
                f"GROUP BY c.region_id "
                f"ORDER BY complaint_count {direction}"
            ).replace("  ", " ").strip()

        # 6 & 9. Grouped Aggregation / Cross-Source Aggregation by Region
        where_sql = _build_mssql_complaint_where(filters, table_alias="comp")
        return (
            f"SELECT TOP 50 c.region_id, COUNT(comp.complaint_id) AS complaint_count, "
            f"COUNT(DISTINCT c.customer_id) AS affected_customers "
            f"FROM dbo.customers c "
            f"JOIN dbo.complaints comp ON c.customer_id = comp.customer_id "
            f"{where_sql} "
            f"GROUP BY c.region_id "
            f"ORDER BY complaint_count DESC"
        ).replace("  ", " ").strip()

    # =========================================================================
    # SOURCE 3: DuckDB (analytics_duckdb)
    # =========================================================================
    if source == "analytics_duckdb":
        # 3. Attribute Difference / Arithmetic Lookup (e.g. list_price - cost_price)
        if intent_type == "attribute_difference" and intent_obj.get("entity"):
            entity_val = str(intent_obj["entity"]).replace("'", "''")
            attrs = intent_obj.get("attributes") or ["list_price", "cost_price"]
            col_a = attrs[0] if len(attrs) >= 1 else "list_price"
            col_b = attrs[1] if len(attrs) >= 2 else "cost_price"
            return (
                f"SELECT product_name, {col_a}, {col_b}, ({col_a} - {col_b}) AS price_difference "
                f"FROM products "
                f"WHERE product_name = '{entity_val}' "
                f"LIMIT 1"
            )

        # 2. Multi-Attribute Entity Lookup
        if intent_type == "multi_attribute_lookup" and intent_obj.get("entity"):
            entity_val = str(intent_obj["entity"]).replace("'", "''")
            attrs = intent_obj.get("attributes") or ["list_price", "cost_price"]
            needs_inv = any(a in INVENTORY_TABLE_ATTRIBUTES for a in attrs)
            if needs_inv:
                select_cols = ["p.product_name"] + [
                    f"i.{a}" if a in INVENTORY_TABLE_ATTRIBUTES else f"p.{a}" for a in attrs
                ]
                return (
                    f"SELECT {', '.join(select_cols)} "
                    f"FROM products p "
                    f"JOIN inventory i ON p.product_id = i.product_id "
                    f"WHERE p.product_name = '{entity_val}' "
                    f"LIMIT 1"
                )
            select_cols = ["product_name"] + [a for a in attrs if a != "product_name"]
            return (
                f"SELECT {', '.join(select_cols)} "
                f"FROM products "
                f"WHERE product_name = '{entity_val}' "
                f"LIMIT 1"
            )

        # 1. Single Entity Attribute Lookup
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

        # 10. Filtering / Listing
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

        # 4 & 7. Total Aggregation or Top / Max / Min Ranking on DuckDB
        if intent_type in ("total_aggregation", "top_max_min", "aggregation"):
            agg_spec = intent_obj.get("aggregation_spec") or intent_obj.get("aggregation")
            order_spec = intent_obj.get("order_by")
            table = intent_obj.get("table") or "products"

            if isinstance(agg_spec, dict):
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
