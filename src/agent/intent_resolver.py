"""
Structured Intent, Entity, and Attribute Resolver.
Uses MCP schema metadata and sample rows to resolve entities (with fuzzy matching and ambiguity detection),
extract requested attributes, and classify analytical intent into:
  A) entity_attribute_lookup
  B) filtering
  C) aggregation
  D) grouping
  E) cross_source
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
    "last", "q1", "q2", "q3", "q4", "2025", "2026", "which", "who", "where",
}

PRODUCT_TABLE_ATTRIBUTES = {"cost_price", "list_price", "category", "is_active", "product_id", "product_name"}
INVENTORY_TABLE_ATTRIBUTES = {"stock_level", "warehouse_location", "warehouse_id", "reorder_point", "safety_stock"}


def _tokenize(text: str) -> List[str]:
    """Normalizes possessives and punctuation into lowercase alphanumeric tokens."""
    cleaned = re.sub(r"'s\b", "", text.lower())
    cleaned = re.sub(r"[^a-z0-9\s-]", " ", cleaned)
    # Split hyphens as separate tokens as well so 'real-time' matches 'real time'
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


def extract_requested_attribute(user_query: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Determines the specific database attribute and target table requested by the user.
    Returns (attribute_column, table_name).
    """
    q_lower = user_query.lower()

    if any(p in q_lower for p in ("cost price", "unit cost", "how much does", "cost of", "cost for")) or re.search(r"\bcost\b", q_lower):
        return "cost_price", "products"

    if any(p in q_lower for p in ("list price", "selling price", "retail price", "catalog price")):
        return "list_price", "products"

    if any(p in q_lower for p in ("stock level", "inventory level", "in stock", "units in stock")) or re.search(r"\bstock\b", q_lower):
        return "stock_level", "inventory"

    if any(p in q_lower for p in ("warehouse location", "warehouse", "where is", "stored")):
        return "warehouse_location", "inventory"

    if any(p in q_lower for p in ("reorder point", "reorder threshold", "reorder")):
        return "reorder_point", "inventory"

    if "safety stock" in q_lower:
        return "safety_stock", "inventory"

    if "category" in q_lower:
        return "category", "products"

    if "price" in q_lower:
        return "cost_price", "products"

    return None, None


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

        # 1. Exact phrase or 100% token presence in query
        if p_joined in q_joined or all(pt in q_tokens for pt in p_tokens):
            exact_matches.append(prod_name)
            continue

        # 2. Sliding window fuzzy match for minor spelling typos across full N-gram
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

        # 3. Partial significant token overlap (e.g., "database agent" matching 2/3 of "Database Replica Agent")
        matched_token_count = sum(1 for pt in p_tokens if pt in q_tokens)
        if matched_token_count > 0:
            partial_matches.append((prod_name, matched_token_count, len(p_tokens)))

    if len(exact_matches) == 1:
        return {
            "status": "matched",
            "entity": exact_matches[0],
            "candidates": exact_matches,
        }

    if len(exact_matches) > 1:
        return {
            "status": "ambiguous",
            "entity": None,
            "candidates": exact_matches,
        }

    if len(fuzzy_full_matches) == 1:
        return {
            "status": "matched",
            "entity": fuzzy_full_matches[0][0],
            "candidates": [fuzzy_full_matches[0][0]],
        }

    if len(fuzzy_full_matches) > 1:
        return {
            "status": "ambiguous",
            "entity": None,
            "candidates": [m[0] for m in fuzzy_full_matches],
        }

    # Check if user had candidate entity tokens that partially matched one or more products
    non_stop_tokens = [t for t in q_tokens if t not in STOP_AND_QUERY_WORDS and not t.isdigit()]
    if non_stop_tokens and partial_matches:
        # Sort partial matches by number of matched tokens descending
        partial_matches.sort(key=lambda item: (item[1] / item[2], item[1]), reverse=True)
        candidates = [m[0] for m in partial_matches]
        return {
            "status": "ambiguous",
            "entity": None,
            "candidates": candidates,
        }

    return {
        "status": "none",
        "entity": None,
        "candidates": [],
    }


def resolve_query_intent(user_query: str, mcp_client=None) -> Dict[str, Any]:
    """
    Analyzes the user query using live MCP metadata to produce a structured intent:
    - intent: 'entity_attribute_lookup' | 'filtering' | 'aggregation' | 'grouping' | 'cross_source'
    - entity, entity_type, attribute, source, table, filter_condition, order_by, ambiguous_entity
    """
    q_lower = user_query.lower().strip()
    products = get_catalog_products(mcp_client)
    categories = sorted({str(r.get("category", "")).strip() for r in products if r.get("category")})

    entity_match = match_product_entity(user_query, products)
    attribute, attr_table = extract_requested_attribute(user_query)

    # Check if multiple sources are involved (Cross-Source intent)
    has_sales_kw = any(kw in q_lower for kw in ("revenue", "sale", "sales", "order", "orders"))
    has_crm_kw = any(kw in q_lower for kw in ("complaint", "complaints", "ticket", "tickets", "customer", "customers", "crm"))
    has_analytics_kw = any(kw in q_lower for kw in ("product", "products", "inventory", "stock", "warehouse", "cost_price", "list_price"))

    if (has_sales_kw and has_crm_kw) or (has_sales_kw and has_analytics_kw and "region" in q_lower):
        return {
            "intent": "cross_source",
            "entity": None,
            "entity_type": None,
            "attribute": attribute,
            "source": "multi",
            "table": None,
            "ambiguous_entity": False,
            "candidates": [],
        }

    # If an ambiguous partial product entity was referenced (e.g., "What's the price of the database agent?")
    if entity_match["status"] == "ambiguous":
        return {
            "intent": "entity_attribute_lookup",
            "entity": None,
            "entity_type": "product",
            "attribute": attribute or "cost_price",
            "source": "analytics_duckdb",
            "table": attr_table or "products",
            "ambiguous_entity": True,
            "candidates": entity_match["candidates"],
        }

    # A) Exact Entity Lookup (e.g. "What is the cost price of Database Replica Agent?")
    if entity_match["status"] == "matched":
        resolved_attr = attribute or "cost_price"
        resolved_table = attr_table or ("inventory" if resolved_attr in INVENTORY_TABLE_ATTRIBUTES else "products")
        return {
            "intent": "entity_attribute_lookup",
            "entity": entity_match["entity"],
            "entity_type": "product",
            "entity_column": "product_name",
            "attribute": resolved_attr,
            "source": "analytics_duckdb",
            "table": resolved_table,
            "ambiguous_entity": False,
            "candidates": [entity_match["entity"]],
        }

    # B) Filtering / Listing queries (e.g., "Show products with stock below 300", "List all products in the Security category")
    below_match = re.search(r"(?:below|under|less than|<)\s*(\d+)", q_lower)
    above_match = re.search(r"(?:above|over|greater than|>)\s*(\d+)", q_lower)
    matched_category = next((cat for cat in categories if cat.lower() in q_lower), None)

    if below_match or above_match or "low stock" in q_lower:
        threshold = int(below_match.group(1)) if below_match else (int(above_match.group(1)) if above_match else 300)
        operator = ">" if above_match else "<"
        filter_col = attribute if attribute in ("cost_price", "list_price", "stock_level", "reorder_point") else "stock_level"
        target_table = "inventory" if filter_col in INVENTORY_TABLE_ATTRIBUTES else "products"
        return {
            "intent": "filtering",
            "entity": None,
            "entity_type": "product",
            "attribute": filter_col,
            "source": "analytics_duckdb",
            "table": target_table,
            "filter_condition": {"column": filter_col, "operator": operator, "value": threshold},
            "ambiguous_entity": False,
            "candidates": [],
        }

    if matched_category and ("product" in q_lower or "category" in q_lower or "list" in q_lower or "show" in q_lower):
        return {
            "intent": "filtering",
            "entity": matched_category,
            "entity_type": "category",
            "attribute": "category",
            "source": "analytics_duckdb",
            "table": "products",
            "filter_condition": {"column": "category", "operator": "=", "value": matched_category},
            "ambiguous_entity": False,
            "candidates": [],
        }

    # C) Aggregation / Ranking on Products or Inventory (e.g., "Which product has the highest list price?", "What is the average cost price of products?")
    is_ranking = any(w in q_lower for w in ("highest", "lowest", "most expensive", "cheapest", "top", "maximum", "minimum"))
    is_scalar_agg = any(w in q_lower for w in ("average", "avg", "sum", "total", "count"))

    if (is_ranking or is_scalar_agg) and (has_analytics_kw or attribute in PRODUCT_TABLE_ATTRIBUTES or attribute in INVENTORY_TABLE_ATTRIBUTES):
        target_attr = attribute or ("list_price" if "price" in q_lower else "cost_price")
        target_table = "inventory" if target_attr in INVENTORY_TABLE_ATTRIBUTES else "products"
        if is_scalar_agg and not is_ranking:
            agg_fn = "AVG" if ("average" in q_lower or "avg" in q_lower) else ("SUM" if ("sum" in q_lower or "total" in q_lower) else "COUNT")
            return {
                "intent": "aggregation",
                "entity": None,
                "entity_type": "product",
                "attribute": target_attr,
                "source": "analytics_duckdb",
                "table": target_table,
                "aggregation": {"function": agg_fn, "column": target_attr},
                "ambiguous_entity": False,
                "candidates": [],
            }
        direction = "ASC" if any(w in q_lower for w in ("lowest", "cheapest", "least", "minimum")) else "DESC"
        limit_match = re.search(r"\btop\s+(\d+)\b", q_lower)
        limit_val = int(limit_match.group(1)) if limit_match else 1
        return {
            "intent": "aggregation",
            "entity": None,
            "entity_type": "product",
            "attribute": target_attr,
            "source": "analytics_duckdb",
            "table": target_table,
            "order_by": {"column": target_attr, "direction": direction, "limit": limit_val},
            "ambiguous_entity": False,
            "candidates": [],
        }

    # D) Grouping queries (e.g., "Show total revenue by region", "Show open complaint count by region")
    if has_crm_kw and not has_sales_kw:
        return {
            "intent": "grouping",
            "entity": None,
            "entity_type": "complaint",
            "attribute": "complaint_count",
            "source": "crm_mssql",
            "table": "complaints",
            "ambiguous_entity": False,
            "candidates": [],
        }

    return {
        "intent": "grouping",
        "entity": None,
        "entity_type": "region",
        "attribute": "total_revenue",
        "source": "sales_pg",
        "table": "orders",
        "ambiguous_entity": False,
        "candidates": [],
    }
