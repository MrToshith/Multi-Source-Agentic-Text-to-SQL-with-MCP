"""
Result Explainer Node.
Synthesizes natural-language business answers and optional chart configurations strictly from
the actual database result (aggregated_data) and the Planner's structured_intent.
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
}


def _format_number_str(val: Any) -> str:
    """Formats numeric values so both raw integer (1100) and formatted currency ($1,100.00) are clear."""
    if isinstance(val, (int, float)):
        fval = float(val)
        if fval.is_integer():
            ival = int(fval)
            return f"{ival} (${fval:,.2f})" if ival >= 100 else str(ival)
        return f"{fval:.2f} (${fval:,.2f})"
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
    sample = aggregated_data[0]

    # A) Exact Entity Attribute Lookup (e.g., "What is the cost price of Database Replica Agent?")
    if intent_type == "entity_attribute_lookup":
        attr = structured_intent.get("attribute") or "cost_price"
        attr_label = ATTRIBUTE_LABELS.get(attr, attr.replace("_", " "))
        entity_name = sample.get("product_name") or structured_intent.get("entity") or "The requested item"
        val = sample.get(attr)

        if attr in ("cost_price", "list_price") and isinstance(val, (int, float)):
            fval = float(val)
            raw_str = str(int(fval)) if fval.is_integer() else f"{fval:.2f}"
            final_answer = f"{entity_name} has a {attr_label} of {raw_str} (${fval:,.2f})."
        elif attr == "stock_level" and isinstance(val, (int, float)):
            final_answer = f"{entity_name} has a {attr_label} of {int(val)} units."
        else:
            final_answer = f"{entity_name} has a {attr_label} of {val}."

        return {
            "final_answer": final_answer,
            "visualization_config": None,
            "execution_status": "completed",
        }

    # C) Aggregation / Ranking (e.g., "Which product has the highest list price?", "What is the average cost price of products?")
    if intent_type == "aggregation":
        agg_spec = structured_intent.get("aggregation")
        order_spec = structured_intent.get("order_by")

        if agg_spec:
            fn = agg_spec.get("function", "AVG")
            col = agg_spec.get("column", "cost_price")
            col_label = ATTRIBUTE_LABELS.get(col, col.replace("_", " "))
            alias = f"{fn.lower()}_{col}"
            val = sample.get(alias, next(iter(sample.values()), 0))
            fn_word = "average" if fn == "AVG" else ("total" if fn == "SUM" else "count of")
            return {
                "final_answer": f"The {fn_word} {col_label} is {_format_number_str(val)}.",
                "visualization_config": None,
                "execution_status": "completed",
            }

        if order_spec:
            col = order_spec.get("column", "list_price")
            col_label = ATTRIBUTE_LABELS.get(col, col.replace("_", " "))
            direction = order_spec.get("direction", "DESC")
            superlative = "highest" if direction == "DESC" else "lowest"
            entity_name = sample.get("product_name") or sample.get("region_name") or "The top record"
            val = sample.get(col)
            if col in ("cost_price", "list_price") and isinstance(val, (int, float)):
                fval = float(val)
                raw_str = str(int(fval)) if fval.is_integer() else f"{fval:.2f}"
                answer_text = f"{entity_name} has the {superlative} {col_label} at {raw_str} (${fval:,.2f})."
            else:
                answer_text = f"{entity_name} has the {superlative} {col_label} at {val}."
            return {
                "final_answer": answer_text,
                "visualization_config": None if len(aggregated_data) == 1 else {
                    "chart_type": "bar",
                    "title": f"Analysis: {user_query[:60]}",
                    "x_axis": "product_name",
                    "y_axes": [col],
                    "data": aggregated_data[:20],
                },
                "execution_status": "completed",
            }

    # B) Filtering / Listing
    if intent_type == "filtering":
        f_cond = structured_intent.get("filter_condition") or {}
        if f_cond.get("column") == "category":
            names = ", ".join(str(r.get("product_name")) for r in aggregated_data if r.get("product_name"))
            return {
                "final_answer": f"Found {len(aggregated_data)} product(s) in the {f_cond.get('value')} category: {names}.",
                "visualization_config": None,
                "execution_status": "completed",
            }

    # D & E) Grouping and Cross-Source synthesis
    summary_parts: List[str] = []

    if "total_revenue" in sample:
        top_rev_row = max(aggregated_data, key=lambda r: float(r.get("total_revenue") or 0))
        label = top_rev_row.get("region_name") or top_rev_row.get("product_name") or f"ID {top_rev_row.get('region_id') or top_rev_row.get('product_id')}"
        rev_val = float(top_rev_row.get("total_revenue") or 0)
        summary_parts.append(f"**{label}** generated the highest revenue at **${rev_val:,.2f}**.")

    if "complaint_count" in sample:
        top_comp_row = max(aggregated_data, key=lambda r: int(r.get("complaint_count") or 0))
        label = top_comp_row.get("region_name") or top_comp_row.get("customer_name") or f"Region {top_comp_row.get('region_id')}"
        comp_val = int(top_comp_row.get("complaint_count") or 0)
        summary_parts.append(f"**{label}** recorded the highest volume of customer complaints with **{comp_val} tickets**.")

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
