"""
Result Explainer Node.
Synthesizes natural-language business takeaways and chart visualization specifications from aggregated data.
"""

from typing import Any, Dict, List
from src.agent.state import AgentState
from src.agent.llm import default_llm_client
from src.agent.prompts.explainer import EXPLAINER_SYSTEM_PROMPT, format_explainer_prompt


def result_explainer_node(state: AgentState) -> Dict[str, Any]:
    """
    Produces a natural-language business answer and optional chart config from aggregated_data.
    """
    user_query = state.get("user_query") or ""
    aggregated_data: List[Dict[str, Any]] = state.get("aggregated_data") or []

    if not aggregated_data:
        return {
            "final_answer": "The query executed successfully, but no matching records were found.",
            "visualization_config": None,
            "execution_status": "completed",
        }

    # Try local LLM if enabled
    llm_result = default_llm_client.generate_json(
        prompt=format_explainer_prompt(user_query, aggregated_data[:20]),
        system_prompt=EXPLAINER_SYSTEM_PROMPT,
    )
    if llm_result and isinstance(llm_result.get("final_answer"), str) and llm_result["final_answer"].strip():
        return {
            "final_answer": llm_result["final_answer"],
            "visualization_config": llm_result.get("visualization_config"),
            "execution_status": "completed",
        }

    # Deterministic analytical narrative synthesis
    sample = aggregated_data[0]
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
        summary_parts.append(f"Successfully retrieved and synthesized **{len(aggregated_data)} records** across the target data sources.")

    final_answer = " ".join(summary_parts)

    # Build chart specification
    x_axis = "region_name" if "region_name" in sample else ("product_name" if "product_name" in sample else list(sample.keys())[0])
    y_axes = [k for k in ("total_revenue", "complaint_count", "order_count", "stock_level", "list_price") if k in sample]

    visualization_config = {
        "chart_type": "bar" if len(y_axes) == 1 else "grouped_bar",
        "title": f"Analysis: {user_query[:60]}",
        "x_axis": x_axis,
        "y_axes": y_axes,
        "data": aggregated_data[:20],
    }

    return {
        "final_answer": final_answer,
        "visualization_config": visualization_config,
        "execution_status": "completed",
    }
