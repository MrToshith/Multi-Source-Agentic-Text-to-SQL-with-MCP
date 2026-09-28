"""
Structured Intent, Entity, Multi-Attribute, Arithmetic, and Cross-Source Resolver.
Classifies user queries into explicit intent types BEFORE SQL generation:
  1. entity_attribute_lookup
  2. multi_attribute_lookup
  3. attribute_difference
  4. total_aggregation
  5. count_aggregation
  6. grouped_aggregation
  7. top_max_min
  8. cross_source_entity_lookup
  9. cross_source_aggregation
  10. filtering
"""

import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from src.mcp_client import default_mcp_client


STOP_AND_QUERY_WORDS = {
    "what", "is", "are", "was", "were", "the", "a", "an", "of", "for", "in", "on", "at",
    "to", "from", "by", "with", "tell", "me", "show", "list", "get", "give", "find",
    "how", "much", "many", "does", "do", "has", "have", "had", "can", "you", "please",
    "cost", "price", "unit", "list", "retail", "selling", "stock", "level", "levels",
    "inventory", "warehouse", "location", "category", "reorder", "point", "threshold",
    "safety", "product", "products", "item", "items", "all", "below", "above", "under",
    "over", "less", "greater", "than", "highest", "lowest", "most", "least", "top",
    "average", "avg", "total", "sum", "count", "revenue", "sales", "order", "orders",
    "complaint", "complaints", "customer", "customers", "region", "regions", "quarter",
    "last", "q1", "q2", "q3", "q4", "2025", "2026", "which", "who", "where", "between",
    "difference", "and", "compare", "recorded", "completed", "placed", "value", "company",
    "belong", "they", "their", "generated",
}

PRODUCT_TABLE_ATTRIBUTES = {"cost_price", "list_price", "category", "is_active", "product_id", "product_name"}
INVENTORY_TABLE_ATTRIBUTES = {"stock_level", "warehouse_location", "warehouse_id", "reorder_point", "safety_stock"}


def _tokenize(text: str) -> List[str]:
    """Normalizes possessives and punctuation into lowercase alphanumeric tokens."""
    cleaned = re.sub(r"'s\b", "", text.lower())
    cleaned = re.sub(r"[^a-z0-9\s-]", " ", cleaned)
    cleaned = cleaned.replace("-", " ")
    return [t for t in cleaned.split() if t]


def get_catalog_products(mcp_client=None) -> List[Dict[str, Any]]:
    """Retrieves the product catalog dynamically via the MCP Server."""
    client = mcp_client or default_mcp_client
    try:
        rows = client.get_sample_rows("analytics_duckdb", "products", limit=50)
        if rows:
            return rows
    except Exception:
        pass
    return []


def extract_all_requested_attributes(user_query: str) -> Tuple[List[str], Optional[str]]:
    """
    Extracts ALL requested product/inventory attributes in order of appearance.
    Returns (attributes_list, primary_table).
    """
    q_lower = user_query.lower()
    found: List[Tuple[int, str, str]] = []

    patterns = [
        (r"\blist price\b|\bselling price\b|\bretail price\b|\bcatalog price\b", "list_price", "products"),
        (r"\bcost price\b|\bunit cost\b|\bhow much does\b|\bcost of\b|\bcost for\b|\bcost\b", "cost_price", "products"),
        (r"\bstock level\b|\binventory level\b|\bin stock\b|\bunits in stock\b|\bstock\b", "stock_level", "inventory"),
        (r"\bwarehouse location\b|\bwarehouse\b|\bwhere is\b|\bstored\b", "warehouse_location", "inventory"),
        (r"\breorder point\b|\breorder threshold\b|\breorder\b", "reorder_point", "inventory"),
        (r"\bsafety stock\b", "safety_stock", "inventory"),
        (r"\bcategory\b", "category", "products"),
    ]

    for pat, col, tbl in patterns:
        m = re.search(pat, q_lower)
        if m:
            found.append((m.start(), col, tbl))

    found.sort(key=lambda x: x[0])
    attrs: List[str] = []
    tables: List[str] = []
    for _, col, tbl in found:
        if col not in attrs:
            attrs.append(col)
            tables.append(tbl)

    if not attrs and "price" in q_lower:
        attrs = ["cost_price"]
        tables = ["products"]

    primary_table = "inventory" if "inventory" in tables else ("products" if tables else None)
    return attrs, primary_table


def extract_requested_attribute(user_query: str) -> Tuple[Optional[str], Optional[str]]:
    """Returns (primary_attribute, primary_table) for backwards compatibility."""
    attrs, tbl = extract_all_requested_attributes(user_query)
    return (attrs[0] if attrs else None), tbl


def extract_query_filters(user_query: str) -> Dict[str, Any]:
    """Extracts explicit quarter, order status, complaint status, or severity filters from the user query."""
    q_lower = user_query.lower()
    filters: Dict[str, Any] = {}

    q_match = re.search(r"\b(q[1-4])[-\s]?(202[56])\b", q_lower)
    if q_match:
        filters["quarter"] = f"{q_match.group(1).upper()}-{q_match.group(2)}"
    elif "last quarter" in q_lower:
        filters["quarter"] = "Q4-2025"

    if "completed" in q_lower:
        filters["status"] = "COMPLETED"
    elif "pending" in q_lower:
        filters["status"] = "PENDING"
    elif "cancelled" in q_lower or "canceled" in q_lower:
        filters["status"] = "CANCELLED"

    if "open complaint" in q_lower or ("open" in q_lower and "complaint" in q_lower):
        filters["complaint_status"] = "OPEN"

    return filters


def has_explicit_region_grouping(user_query: str) -> bool:
    """
    Returns True ONLY if the user explicitly asked to group or break down by region.
    Does NOT return True for 'total revenue in Q4-2025' or 'how many complaints in Q4-2025'.
    """
    q_lower = user_query.lower()
    explicit_phrases = (
        "by region",
        "per region",
        "each region",
        "across regions",
        "regional",
        "for each region",
        "in each region",
        "region breakdown",
        "breakdown by region",
    )
    return any(p in q_lower for p in explicit_phrases)


def match_product_entity(
    user_query: str,
    products: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Matches a product entity from the user query against the MCP product catalog.
    Supports exact case-insensitive matching, token-based matching, and typo fuzzy matching.
    Detects ambiguous partial references and requests clarification instead of guessing.
    """
    q_tokens = _tokenize(user_query)
    q_joined = " ".join(q_tokens)

    exact_matches: List[str] = []
    fuzzy_full_matches: List[Tuple[str, float]] = []
    partial_matches: List[Tuple[str, int, int]] = []

    for row in products:
        prod_name = str(row.get("product_name") or "").strip()
        if not prod_name:
            continue
        p_tokens = _tokenize(prod_name)
        if not p_tokens:
            continue
        p_joined = " ".join(p_tokens)

        if p_joined in q_joined or all(pt in q_tokens for pt in p_tokens):
            exact_matches.append(prod_name)
            continue

        n = len(p_tokens)
        if len(q_tokens) >= n:
            best_ratio = 0.0
            for i in range(len(q_tokens) - n + 1):
                window_str = " ".join(q_tokens[i : i + n])
                ratio = SequenceMatcher(None, window_str, p_joined).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
            if best_ratio >= 0.86:
                fuzzy_full_matches.append((prod_name, best_ratio))
                continue

        matched_token_count = sum(1 for pt in p_tokens if pt in q_tokens)
        if matched_token_count > 0:
            partial_matches.append((prod_name, matched_token_count, len(p_tokens)))

    if len(exact_matches) == 1:
        return {"status": "matched", "entity": exact_matches[0], "candidates": exact_matches}
    if len(exact_matches) > 1:
        return {"status": "ambiguous", "entity": None, "candidates": exact_matches}
    if len(fuzzy_full_matches) == 1:
        return {"status": "matched", "entity": fuzzy_full_matches[0][0], "candidates": [fuzzy_full_matches[0][0]]}
    if len(fuzzy_full_matches) > 1:
        return {"status": "ambiguous", "entity": None, "candidates": [m[0] for m in fuzzy_full_matches]}

    non_stop_tokens = [t for t in q_tokens if t not in STOP_AND_QUERY_WORDS and not t.isdigit()]
    if non_stop_tokens and partial_matches:
        partial_matches.sort(key=lambda item: (item[1] / item[2], item[1]), reverse=True)
        candidates = [m[0] for m in partial_matches]
        return {"status": "ambiguous", "entity": None, "candidates": candidates}

    return {"status": "none", "entity": None, "candidates": []}


def resolve_query_intent(user_query: str, mcp_client=None) -> Dict[str, Any]:
    """
    Analyzes the user query using live MCP metadata to produce a rich structured intent.
    Never defaults to regional GROUP BY unless the user explicitly asks for regional breakdown or ranking.
    """
    q_lower = user_query.lower().strip()
    products = get_catalog_products(mcp_client)
    categories = sorted({str(r.get("category", "")).strip() for r in products if r.get("category")})

    entity_match = match_product_entity(user_query, products)
    attributes, attr_table = extract_all_requested_attributes(user_query)
    primary_attr = attributes[0] if attributes else None
    filters = extract_query_filters(user_query)
    explicit_region_group = has_explicit_region_grouping(user_query)

    # -------------------------------------------------------------------------
    # 8. CROSS-SOURCE ENTITY LOOKUP
    # Example: "Who placed the highest-value completed order in Q4-2025, and which company do they belong to?"
    # -------------------------------------------------------------------------
    asks_who_or_company = any(w in q_lower for w in ("who placed", "who ordered", "which customer", "which company", "company do they belong", "customer name"))
    asks_order = any(w in q_lower for w in ("order", "purchase", "bought", "placed"))
    if asks_who_or_company and asks_order:
        if "status" not in filters:
            filters["status"] = "COMPLETED"
        direction = "ASC" if any(w in q_lower for w in ("lowest", "smallest", "minimum")) else "DESC"
        return {
            "intent": "cross_source_entity_lookup",
            "operation": "cross_source_lookup",
            "aggregation": "MAX" if direction == "DESC" else "MIN",
            "metric": "total_amount",
            "entity": None,
            "entity_type": "customer_order",
            "attribute": "total_amount",
            "attributes": ["order_id", "customer_id", "customer_name", "company_name", "total_amount"],
            "filters": filters,
            "group_by": None,
            "order_by": {"column": "total_amount", "direction": direction, "limit": 1},
            "limit": 1,
            "source": "multi",
            "sources": ["sales_pg", "crm_mssql"],
            "table": "orders",
            "join_key": "customer_id",
            "ambiguous_entity": False,
            "candidates": [],
        }

    # -------------------------------------------------------------------------
    # 9. CROSS-SOURCE AGGREGATION
    # Example: "Compare Q4-2025 revenue and complaint counts by region."
    # Example: "Which region had the highest revenue and most customer complaints last quarter?"
    # -------------------------------------------------------------------------
    has_sales_kw = any(kw in q_lower for kw in ("revenue", "sale", "sales", "order", "orders"))
    has_crm_kw = any(kw in q_lower for kw in ("complaint", "complaints", "ticket", "tickets", "crm")) or (
        "customer" in q_lower and "complaint" in q_lower
    )
    has_analytics_kw = any(kw in q_lower for kw in ("product", "products", "inventory", "stock", "warehouse", "cost_price", "list_price"))

    if (has_sales_kw and has_crm_kw) or (has_sales_kw and has_analytics_kw and "region" in q_lower):
        if "status" not in filters:
            filters["status"] = "COMPLETED"
        return {
            "intent": "cross_source_aggregation",
            "operation": "cross_source_aggregate",
            "aggregation": "SUM_AND_COUNT",
            "metric": "revenue_and_complaints",
            "entity": None,
            "entity_type": "region",
            "attribute": "total_revenue",
            "attributes": ["region_id", "region_name", "total_revenue", "complaint_count"],
            "filters": filters,
            "group_by": ["region"],
            "order_by": {"column": "total_revenue", "direction": "DESC"},
            "limit": 50,
            "source": "multi",
            "sources": ["sales_pg", "crm_mssql"],
            "table": None,
            "join_key": "region_id",
            "ambiguous_entity": False,
            "candidates": [],
        }

    # -------------------------------------------------------------------------
    # AMBIGUOUS PRODUCT ENTITY GUARD
    # -------------------------------------------------------------------------
    if entity_match["status"] == "ambiguous":
        return {
            "intent": "entity_attribute_lookup",
            "operation": "lookup",
            "entity": None,
            "entity_type": "product",
            "attribute": primary_attr or "cost_price",
            "attributes": attributes or ["cost_price"],
            "filters": filters,
            "group_by": None,
            "order_by": None,
            "limit": 1,
            "source": "analytics_duckdb",
            "table": attr_table or "products",
            "ambiguous_entity": True,
            "candidates": entity_match["candidates"],
        }

    # -------------------------------------------------------------------------
    # 1, 2, 3. PRODUCT ENTITY LOOKUP (SINGLE ATTRIBUTE, MULTI-ATTRIBUTE, OR DIFFERENCE/ARITHMETIC)
    # -------------------------------------------------------------------------
    if entity_match["status"] == "matched":
        entity_name = entity_match["entity"]
        is_difference = any(w in q_lower for w in ("difference", "diff", "margin", "markup", "minus"))

        if is_difference:
            req_attrs = attributes if len(attributes) >= 2 else ["list_price", "cost_price"]
            return {
                "intent": "attribute_difference",
                "operation": "arithmetic_lookup",
                "aggregation": "DIFF",
                "metric": "price_difference",
                "entity": entity_name,
                "entity_type": "product",
                "entity_column": "product_name",
                "attribute": "price_difference",
                "attributes": req_attrs,
                "filters": {"product_name": entity_name},
                "group_by": None,
                "order_by": None,
                "limit": 1,
                "source": "analytics_duckdb",
                "table": "products",
                "ambiguous_entity": False,
                "candidates": [entity_name],
            }

        if len(attributes) > 1:
            resolved_table = "inventory" if any(a in INVENTORY_TABLE_ATTRIBUTES for a in attributes) else "products"
            return {
                "intent": "multi_attribute_lookup",
                "operation": "lookup",
                "aggregation": None,
                "metric": None,
                "entity": entity_name,
                "entity_type": "product",
                "entity_column": "product_name",
                "attribute": attributes[0],
                "attributes": attributes,
                "filters": {"product_name": entity_name},
                "group_by": None,
                "order_by": None,
                "limit": 1,
                "source": "analytics_duckdb",
                "table": resolved_table,
                "ambiguous_entity": False,
                "candidates": [entity_name],
            }

        resolved_attr = primary_attr or "cost_price"
        resolved_table = attr_table or ("inventory" if resolved_attr in INVENTORY_TABLE_ATTRIBUTES else "products")
        return {
            "intent": "entity_attribute_lookup",
            "operation": "lookup",
            "aggregation": None,
            "metric": resolved_attr,
            "entity": entity_name,
            "entity_type": "product",
            "entity_column": "product_name",
            "attribute": resolved_attr,
            "attributes": [resolved_attr],
            "filters": {"product_name": entity_name},
            "group_by": None,
            "order_by": None,
            "limit": 1,
            "source": "analytics_duckdb",
            "table": resolved_table,
            "ambiguous_entity": False,
            "candidates": [entity_name],
        }

    # -------------------------------------------------------------------------
    # 10. FILTERING / LISTING (DuckDB Products / Inventory)
    # -------------------------------------------------------------------------
    below_match = re.search(r"(?:below|under|less than|<)\s*(\d+)", q_lower)
    above_match = re.search(r"(?:above|over|greater than|>)\s*(\d+)", q_lower)
    matched_category = next((cat for cat in categories if cat.lower() in q_lower), None)

    if below_match or above_match or "low stock" in q_lower:
        threshold = int(below_match.group(1)) if below_match else (int(above_match.group(1)) if above_match else 300)
        operator = ">" if above_match else "<"
        filter_col = primary_attr if primary_attr in ("cost_price", "list_price", "stock_level", "reorder_point") else "stock_level"
        target_table = "inventory" if filter_col in INVENTORY_TABLE_ATTRIBUTES else "products"
        return {
            "intent": "filtering",
            "operation": "filter",
            "entity": None,
            "entity_type": "product",
            "attribute": filter_col,
            "attributes": [filter_col],
            "filters": {filter_col: f"{operator} {threshold}"},
            "filter_condition": {"column": filter_col, "operator": operator, "value": threshold},
            "group_by": None,
            "order_by": {"column": filter_col, "direction": "ASC"},
            "limit": 50,
            "source": "analytics_duckdb",
            "table": target_table,
            "ambiguous_entity": False,
            "candidates": [],
        }

    if matched_category and ("product" in q_lower or "category" in q_lower or "list" in q_lower or "show" in q_lower):
        return {
            "intent": "filtering",
            "operation": "filter",
            "entity": matched_category,
            "entity_type": "category",
            "attribute": "category",
            "attributes": ["product_id", "product_name", "category", "cost_price", "list_price"],
            "filters": {"category": matched_category},
            "filter_condition": {"column": "category", "operator": "=", "value": matched_category},
            "group_by": None,
            "order_by": None,
            "limit": 50,
            "source": "analytics_duckdb",
            "table": "products",
            "ambiguous_entity": False,
            "candidates": [],
        }

    # -------------------------------------------------------------------------
    # 7. TOP / MAX / MIN RANKING (Regions or Products)
    # Example: "Which region generated the highest completed revenue in Q4-2025?"
    # Example: "Which product has the highest list price?"
    # -------------------------------------------------------------------------
    is_ranking = any(w in q_lower for w in ("highest", "lowest", "most expensive", "cheapest", "most", "least", "top", "maximum", "minimum"))
    direction = "ASC" if any(w in q_lower for w in ("lowest", "cheapest", "least", "minimum")) else "DESC"
    limit_match = re.search(r"\btop\s+(\d+)\b", q_lower)
    limit_val = int(limit_match.group(1)) if limit_match else 1

    if is_ranking and ("which region" in q_lower or "what region" in q_lower or "top region" in q_lower or ("region" in q_lower and not explicit_region_group)):
        if has_crm_kw and not has_sales_kw:
            return {
                "intent": "top_max_min",
                "operation": "rank",
                "aggregation": "COUNT",
                "metric": "complaints",
                "entity": None,
                "entity_type": "region",
                "attribute": "complaint_count",
                "attributes": ["region_id", "complaint_count"],
                "filters": filters,
                "group_by": ["region"],
                "order_by": {"column": "complaint_count", "direction": direction, "limit": limit_val},
                "limit": limit_val,
                "source": "crm_mssql",
                "table": "complaints",
                "ambiguous_entity": False,
                "candidates": [],
            }
        if "status" not in filters:
            filters["status"] = "COMPLETED"
        return {
            "intent": "top_max_min",
            "operation": "rank",
            "aggregation": "SUM",
            "metric": "revenue",
            "entity": None,
            "entity_type": "region",
            "attribute": "total_revenue",
            "attributes": ["region_id", "region_name", "total_revenue"],
            "filters": filters,
            "group_by": ["region"],
            "order_by": {"column": "total_revenue", "direction": direction, "limit": limit_val},
            "limit": limit_val,
            "source": "sales_pg",
            "table": "orders",
            "ambiguous_entity": False,
            "candidates": [],
        }

    if is_ranking and (has_analytics_kw or primary_attr in PRODUCT_TABLE_ATTRIBUTES or primary_attr in INVENTORY_TABLE_ATTRIBUTES):
        target_attr = primary_attr or ("list_price" if "price" in q_lower else "cost_price")
        target_table = "inventory" if target_attr in INVENTORY_TABLE_ATTRIBUTES else "products"
        return {
            "intent": "top_max_min",
            "operation": "rank",
            "aggregation": "MAX" if direction == "DESC" else "MIN",
            "metric": target_attr,
            "entity": None,
            "entity_type": "product",
            "attribute": target_attr,
            "attributes": ["product_name", target_attr],
            "filters": filters,
            "group_by": None,
            "order_by": {"column": target_attr, "direction": direction, "limit": limit_val},
            "limit": limit_val,
            "source": "analytics_duckdb",
            "table": target_table,
            "ambiguous_entity": False,
            "candidates": [],
        }

    # -------------------------------------------------------------------------
    # 5. COUNT AGGREGATION (Ungrouped Scalar Count)
    # Example: "How many complaints were recorded in Q4-2025?"
    # Example: "How many orders were completed in Q4-2025?"
    # -------------------------------------------------------------------------
    is_count_question = any(p in q_lower for p in ("how many", "number of", "count of", "total complaints", "total number of"))
    if is_count_question and not explicit_region_group:
        if has_crm_kw:
            return {
                "intent": "count_aggregation",
                "operation": "aggregate",
                "aggregation": "COUNT",
                "metric": "complaints",
                "entity": None,
                "entity_type": "complaint",
                "attribute": "complaint_count",
                "attributes": ["complaint_count"],
                "filters": filters,
                "group_by": None,
                "order_by": None,
                "limit": 1,
                "source": "crm_mssql",
                "table": "complaints",
                "ambiguous_entity": False,
                "candidates": [],
            }
        if has_sales_kw:
            return {
                "intent": "count_aggregation",
                "operation": "aggregate",
                "aggregation": "COUNT",
                "metric": "orders",
                "entity": None,
                "entity_type": "order",
                "attribute": "order_count",
                "attributes": ["order_count"],
                "filters": filters,
                "group_by": None,
                "order_by": None,
                "limit": 1,
                "source": "sales_pg",
                "table": "orders",
                "ambiguous_entity": False,
                "candidates": [],
            }

    # -------------------------------------------------------------------------
    # 4. TOTAL / SCALAR AGGREGATION (Ungrouped SUM / AVG)
    # Example: "What was the total completed revenue in Q4-2025?"
    # Example: "What was the total completed revenue in Q1-2026?"
    # Example: "What is the average cost price of products?"
    # -------------------------------------------------------------------------
    is_scalar_agg = any(w in q_lower for w in ("total", "sum", "average", "avg"))
    if is_scalar_agg and not explicit_region_group:
        if has_analytics_kw or primary_attr in PRODUCT_TABLE_ATTRIBUTES or primary_attr in INVENTORY_TABLE_ATTRIBUTES:
            target_attr = primary_attr or "cost_price"
            target_table = "inventory" if target_attr in INVENTORY_TABLE_ATTRIBUTES else "products"
            agg_fn = "AVG" if ("average" in q_lower or "avg" in q_lower) else "SUM"
            return {
                "intent": "total_aggregation",
                "operation": "aggregate",
                "aggregation": agg_fn,
                "metric": target_attr,
                "entity": None,
                "entity_type": "product",
                "attribute": f"{agg_fn.lower()}_{target_attr}",
                "attributes": [f"{agg_fn.lower()}_{target_attr}"],
                "filters": filters,
                "aggregation_spec": {"function": agg_fn, "column": target_attr},
                "group_by": None,
                "order_by": None,
                "limit": 1,
                "source": "analytics_duckdb",
                "table": target_table,
                "ambiguous_entity": False,
                "candidates": [],
            }

        if has_sales_kw:
            if "status" not in filters:
                filters["status"] = "COMPLETED"
            agg_fn = "AVG" if ("average" in q_lower or "avg" in q_lower) else "SUM"
            return {
                "intent": "total_aggregation",
                "operation": "aggregate",
                "aggregation": agg_fn,
                "metric": "revenue",
                "entity": None,
                "entity_type": "order",
                "attribute": "total_revenue",
                "attributes": ["total_revenue"],
                "filters": filters,
                "group_by": None,
                "order_by": None,
                "limit": 1,
                "source": "sales_pg",
                "table": "orders",
                "ambiguous_entity": False,
                "candidates": [],
            }

        if has_crm_kw:
            return {
                "intent": "count_aggregation",
                "operation": "aggregate",
                "aggregation": "COUNT",
                "metric": "complaints",
                "entity": None,
                "entity_type": "complaint",
                "attribute": "complaint_count",
                "attributes": ["complaint_count"],
                "filters": filters,
                "group_by": None,
                "order_by": None,
                "limit": 1,
                "source": "crm_mssql",
                "table": "complaints",
                "ambiguous_entity": False,
                "candidates": [],
            }

    # -------------------------------------------------------------------------
    # 6. GROUPED AGGREGATION (When user explicitly requests grouping, e.g., "by region")
    # Example: "Show completed revenue by region in Q4-2025."
    # Example: "Show open complaint count by region"
    # -------------------------------------------------------------------------
    if has_crm_kw and not has_sales_kw:
        if explicit_region_group:
            return {
                "intent": "grouped_aggregation",
                "operation": "aggregate",
                "aggregation": "COUNT",
                "metric": "complaints",
                "entity": None,
                "entity_type": "region",
                "attribute": "complaint_count",
                "attributes": ["region_id", "complaint_count"],
                "filters": filters,
                "group_by": ["region"],
                "order_by": {"column": "complaint_count", "direction": "DESC"},
                "limit": 50,
                "source": "crm_mssql",
                "table": "complaints",
                "ambiguous_entity": False,
                "candidates": [],
            }
        # Default ungrouped count if region was not mentioned
        return {
            "intent": "count_aggregation",
            "operation": "aggregate",
            "aggregation": "COUNT",
            "metric": "complaints",
            "entity": None,
            "entity_type": "complaint",
            "attribute": "complaint_count",
            "attributes": ["complaint_count"],
            "filters": filters,
            "group_by": None,
            "order_by": None,
            "limit": 1,
            "source": "crm_mssql",
            "table": "complaints",
            "ambiguous_entity": False,
            "candidates": [],
        }

    if explicit_region_group:
        if "status" not in filters:
            filters["status"] = "COMPLETED"
        return {
            "intent": "grouped_aggregation",
            "operation": "aggregate",
            "aggregation": "SUM",
            "metric": "revenue",
            "entity": None,
            "entity_type": "region",
            "attribute": "total_revenue",
            "attributes": ["region_id", "region_name", "order_count", "total_revenue"],
            "filters": filters,
            "group_by": ["region"],
            "order_by": {"column": "total_revenue", "direction": "DESC"},
            "limit": 50,
            "source": "sales_pg",
            "table": "orders",
            "ambiguous_entity": False,
            "candidates": [],
        }

    # If user asked about revenue/sales with a quarter filter (e.g. "What was the revenue in Q4-2025?") without "by region"
    if has_sales_kw:
        if "status" not in filters:
            filters["status"] = "COMPLETED"
        return {
            "intent": "total_aggregation",
            "operation": "aggregate",
            "aggregation": "SUM",
            "metric": "revenue",
            "entity": None,
            "entity_type": "order",
            "attribute": "total_revenue",
            "attributes": ["total_revenue"],
            "filters": filters,
            "group_by": None,
            "order_by": None,
            "limit": 1,
            "source": "sales_pg",
            "table": "orders",
            "ambiguous_entity": False,
            "candidates": [],
        }

    # Fallback
    return {
        "intent": "grouped_aggregation",
        "operation": "aggregate",
        "aggregation": "SUM",
        "metric": "revenue",
        "entity": None,
        "entity_type": "region",
        "attribute": "total_revenue",
        "attributes": ["region_id", "region_name", "total_revenue"],
        "filters": {"status": "COMPLETED"},
        "group_by": ["region"],
        "order_by": {"column": "total_revenue", "direction": "DESC"},
        "limit": 50,
        "source": "sales_pg",
        "table": "orders",
        "ambiguous_entity": False,
        "candidates": [],
    }
