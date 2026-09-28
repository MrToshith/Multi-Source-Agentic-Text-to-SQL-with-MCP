"""
Result Explainer Node.
Synthesizes natural-language business answers and optional chart configurations strictly from
the actual database result (aggregated_data) and the Planner's structured_intent.
Never invents facts or applies regional templates to ungrouped scalar queries.
"""

from typing import Any, Dict, List
from src.agent.state import AgentState
from src.agent.intent_resolver import resolve_query_intent


ATTRIBUTE_LABELS = {
    "cost_price": "cost price",
    "list_price": "list price",
    "stock_level": "stock level",
    "warehouse_location": "warehouse location",
    "reorder_point": "reorder point",
    "safety_stock": "safety stock",
    "category": "category",
    "total_revenue": "total revenue",
    "complaint_count": "complaint count",
}


def _fmt_num(val: Any) -> str:
    """Formats numbers with both comma-formatted and raw representations (e.g., '2,400 (2400)')."""
    if isinstance(val, (int, float)):
        fval = float(val)
        if fval.is_integer():
            ival = int(fval)
            return f"{ival:,} ({ival})" if abs(ival) >= 1000 else str(ival)
        return f"{fval:,.2f} ({fval})"
    return str(val)


def result_explainer_node(state: AgentState) -> Dict[str, Any]:
    """
    Produces a natural-language business answer and optional chart config strictly from aggregated_data.
    """
    user_query = state.get("user_query") or ""
    aggregated_data: List[Dict[str, Any]] = state.get("aggregated_data") or []
    structured_intent = state.get("structured_intent") or resolve_query_intent(user_query)

    if not aggregated_data:
        return {
            "final_answer": "The query executed successfully, but no matching records were found.",
            "visualization_config": None,
            "execution_status": "completed",
        }

    intent_type = structured_intent.get("intent")
    filters = structured_intent.get("filters") or {}
    q_str = f" in {filters['quarter']}" if filters.get("quarter") else ""
    sample = aggregated_data[0]

    # -------------------------------------------------------------------------
    # 3. ATTRIBUTE DIFFERENCE / ARITHMETIC LOOKUP
    # -------------------------------------------------------------------------
    if intent_type == "attribute_difference":
        entity_name = sample.get("product_name") or structured_intent.get("entity") or "The product"
        attrs = structured_intent.get("attributes") or ["list_price", "cost_price"]
        col_a = attrs[0] if len(attrs) >= 1 else "list_price"
        col_b = attrs[1] if len(attrs) >= 2 else "cost_price"
        label_a = ATTRIBUTE_LABELS.get(col_a, col_a.replace("_", " "))
        label_b = ATTRIBUTE_LABELS.get(col_b, col_b.replace("_", " "))
        val_a = float(sample.get(col_a) or 0)
        val_b = float(sample.get(col_b) or 0)
        diff_val = float(sample.get("price_difference") if "price_difference" in sample else (val_a - val_b))

        final_answer = (
            f"{entity_name} has a {label_a} of {_fmt_num(val_a)} and a {label_b} of {_fmt_num(val_b)}, "
            f"giving a difference of {_fmt_num(diff_val)}."
        )
        return {
            "final_answer": final_answer,
            "visualization_config": None,
            "execution_status": "completed",
        }

    # -------------------------------------------------------------------------
    # 2. MULTI-ATTRIBUTE ENTITY LOOKUP
    # -------------------------------------------------------------------------
    if intent_type == "multi_attribute_lookup":
        entity_name = sample.get("product_name") or structured_intent.get("entity") or "The product"
        attrs = structured_intent.get("attributes") or ["list_price", "cost_price"]
        parts = []
        for attr in attrs:
            lbl = ATTRIBUTE_LABELS.get(attr, attr.replace("_", " "))
            v = sample.get(attr)
            parts.append(f"a {lbl} of {_fmt_num(v)}")
        joined_parts = " and ".join(parts)
        return {
            "final_answer": f"{entity_name} has {joined_parts}.",
            "visualization_config": None,
            "execution_status": "completed",
        }

    # -------------------------------------------------------------------------
    # 1. SINGLE ENTITY ATTRIBUTE LOOKUP
    # -------------------------------------------------------------------------
    if intent_type == "entity_attribute_lookup":
        attr = structured_intent.get("attribute") or "cost_price"
        attr_label = ATTRIBUTE_LABELS.get(attr, attr.replace("_", " "))
        entity_name = sample.get("product_name") or structured_intent.get("entity") or "The requested item"
        val = sample.get(attr)

        if attr in ("cost_price", "list_price") and isinstance(val, (int, float)):
            final_answer = f"{entity_name} has a {attr_label} of {_fmt_num(val)}."
        elif attr == "stock_level" and isinstance(val, (int, float)):
            final_answer = f"{entity_name} has a {attr_label} of {int(val)} units."
        else:
            final_answer = f"{entity_name} has a {attr_label} of {val}."

        return {
            "final_answer": final_answer,
            "visualization_config": None,
            "execution_status": "completed",
        }

    # -------------------------------------------------------------------------
    # 8. CROSS-SOURCE ENTITY LOOKUP (Order in PostgreSQL + Customer in SQL Server)
    # -------------------------------------------------------------------------
    if intent_type == "cross_source_entity_lookup":
        cust_name = sample.get("customer_name") or f"Customer {sample.get('customer_id')}"
        comp_name = sample.get("company_name") or "Unknown Company"
        cid = sample.get("customer_id")
        oid = sample.get("order_id")
        amt = float(sample.get("total_amount") or 0)
        final_answer = (
            f"{cust_name} of {comp_name} (customer_id = {cid}) placed the highest-value completed order "
            f"(order_id = {oid}){q_str}, worth {_fmt_num(amt)}."
        )
        return {
            "final_answer": final_answer,
            "visualization_config": None,
            "execution_status": "completed",
        }

    # -------------------------------------------------------------------------
    # 4. TOTAL / SCALAR AGGREGATION (Ungrouped SUM / AVG)
    # -------------------------------------------------------------------------
    if intent_type == "total_aggregation":
        if "total_revenue" in sample:
            rev_val = float(sample.get("total_revenue") or 0)
            status_word = " completed" if filters.get("status") == "COMPLETED" else ""
            return {
                "final_answer": f"Total{status_word} revenue{q_str} was {_fmt_num(rev_val)}.",
                "visualization_config": None,
                "execution_status": "completed",
            }
        agg_spec = structured_intent.get("aggregation_spec") or {}
        fn = agg_spec.get("function", structured_intent.get("aggregation") or "AVG")
        col = agg_spec.get("column", structured_intent.get("metric") or "cost_price")
        col_label = ATTRIBUTE_LABELS.get(col, col.replace("_", " "))
        val = next(iter(sample.values()), 0)
        fn_word = "average" if fn == "AVG" else "total"
        return {
            "final_answer": f"The {fn_word} {col_label}{q_str} is {_fmt_num(val)}.",
            "visualization_config": None,
            "execution_status": "completed",
        }

    # -------------------------------------------------------------------------
    # 5. COUNT AGGREGATION (Ungrouped COUNT)
    # -------------------------------------------------------------------------
    if intent_type == "count_aggregation":
        if "complaint_count" in sample:
            cnt = int(sample.get("complaint_count") or 0)
            return {
                "final_answer": f"There were {cnt} complaints recorded{q_str}.",
                "visualization_config": None,
                "execution_status": "completed",
            }
        cnt = int(next(iter(sample.values()), 0))
        return {
            "final_answer": f"There were {cnt} records found{q_str}.",
            "visualization_config": None,
            "execution_status": "completed",
        }

    # -------------------------------------------------------------------------
    # 7. TOP / MAX / MIN RANKING
    # -------------------------------------------------------------------------
    if intent_type == "top_max_min":
        order_spec = structured_intent.get("order_by") or {}
        col = order_spec.get("column") or structured_intent.get("attribute") or "total_revenue"
        col_label = ATTRIBUTE_LABELS.get(col, col.replace("_", " "))
        direction = order_spec.get("direction", "DESC")
        superlative = "highest" if direction == "DESC" else "lowest"
        entity_name = sample.get("region_name") or sample.get("product_name") or f"Region {sample.get('region_id')}"
        val = float(sample.get(col) or 0)

        if col == "total_revenue":
            status_word = " completed" if filters.get("status") == "COMPLETED" else ""
            answer_text = f"{entity_name} generated the {superlative}{status_word} revenue{q_str} at {_fmt_num(val)}."
        else:
            answer_text = f"{entity_name} has the {superlative} {col_label}{q_str} at {_fmt_num(val)}."

        return {
            "final_answer": answer_text,
            "visualization_config": None,
            "execution_status": "completed",
        }

    # -------------------------------------------------------------------------
    # 10. FILTERING / LISTING
    # -------------------------------------------------------------------------
    if intent_type == "filtering":
        f_cond = structured_intent.get("filter_condition") or {}
        if f_cond.get("column") == "category":
            names = ", ".join(str(r.get("product_name")) for r in aggregated_data if r.get("product_name"))
            return {
                "final_answer": f"Found {len(aggregated_data)} product(s) in the {f_cond.get('value')} category: {names}.",
                "visualization_config": None,
                "execution_status": "completed",
            }

    # -------------------------------------------------------------------------
    # 6 & 9. GROUPED AGGREGATION & CROSS-SOURCE AGGREGATION
    # -------------------------------------------------------------------------
    summary_parts: List[str] = []

    if "total_revenue" in sample:
        top_rev_row = max(aggregated_data, key=lambda r: float(r.get("total_revenue") or 0))
        label = top_rev_row.get("region_name") or top_rev_row.get("product_name") or f"ID {top_rev_row.get('region_id') or top_rev_row.get('product_id')}"
        rev_val = float(top_rev_row.get("total_revenue") or 0)
        summary_parts.append(f"**{label}** generated the highest revenue{q_str} at **${rev_val:,.2f}**.")

    if "complaint_count" in sample:
        top_comp_row = max(aggregated_data, key=lambda r: int(r.get("complaint_count") or 0))
        label = top_comp_row.get("region_name") or top_comp_row.get("customer_name") or f"Region {top_comp_row.get('region_id')}"
        comp_val = int(top_comp_row.get("complaint_count") or 0)
        summary_parts.append(f"**{label}** recorded the highest volume of customer complaints{q_str} with **{comp_val} tickets**.")

    if "stock_level" in sample:
        low_stock_row = min(aggregated_data, key=lambda r: int(r.get("stock_level") or 0))
        prod_label = low_stock_row.get("product_name") or f"Product {low_stock_row.get('product_id')}"
        stock_val = int(low_stock_row.get("stock_level") or 0)
        summary_parts.append(
            f"Found **{len(aggregated_data)} products** matching the inventory filter; "
            f"**{prod_label}** has the lowest stock level at **{stock_val} units**."
        )

    if not summary_parts:
        summary_parts.append(f"Successfully retrieved **{len(aggregated_data)} records**.")

    final_answer = " ".join(summary_parts)

    x_axis = "region_name" if "region_name" in sample else ("product_name" if "product_name" in sample else list(sample.keys())[0])
    y_axes = [k for k in ("total_revenue", "complaint_count", "order_count", "stock_level", "list_price") if k in sample]

    visualization_config = {
        "chart_type": "bar" if len(y_axes) == 1 else "grouped_bar",
        "title": f"Analysis: {user_query[:60]}",
        "x_axis": x_axis,
        "y_axes": y_axes,
        "data": aggregated_data[:20],
    } if len(aggregated_data) > 1 and y_axes else None

    return {
        "final_answer": final_answer,
        "visualization_config": visualization_config,
        "execution_status": "completed",
    }
