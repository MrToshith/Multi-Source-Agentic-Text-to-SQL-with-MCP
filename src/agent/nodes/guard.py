"""
Intent & Clarification Guard Node.
Evaluates query completeness and detects ambiguous entity mentions via MCP catalog metadata.
"""

from typing import Any, Dict
from src.agent.state import AgentState
from src.agent.intent_resolver import resolve_query_intent


AMBIGUOUS_SHORT_PHRASES = {
    "show sales",
    "sales",
    "get sales",
    "show revenue",
    "revenue",
    "show complaints",
    "complaints",
    "check complaints",
    "show orders",
    "orders",
    "show data",
    "analyze performance",
    "how are we doing",
    "give me a report",
    "show inventory",
    "show customers",
}


def intent_clarification_guard_node(state: AgentState) -> Dict[str, Any]:
    """Pauses execution with a clarification question if the user query or entity reference is ambiguous."""
    user_query = (state.get("user_query") or "").strip()
    messages = state.get("messages") or []

    user_turns = [m for m in messages if m.get("role") == "user"]
    if len(user_turns) > 1:
        combined_query = " | ".join(m.get("content", "") for m in user_turns)
        resolved = resolve_query_intent(combined_query)
        return {
            "user_query": combined_query,
            "structured_intent": resolved,
            "clarification_needed": False,
            "clarification_question": None,
            "execution_status": "intent_verified",
        }

    resolved_intent = resolve_query_intent(user_query)

    # Partial/ambiguous product entity mentions must ask for clarification instead of guessing
    if resolved_intent.get("ambiguous_entity"):
        candidates = resolved_intent.get("candidates") or []
        candidate_list = ", ".join(candidates[:4]) if candidates else "multiple products"
        question = f"Which product do you mean? Possible matches include: {candidate_list}."
        return {
            "structured_intent": resolved_intent,
            "clarification_needed": True,
            "clarification_question": question,
            "execution_status": "clarification_needed",
        }

    if resolved_intent.get("intent") in (
        "entity_attribute_lookup",
        "multi_attribute_lookup",
        "attribute_difference",
    ) and resolved_intent.get("entity"):
        return {
            "structured_intent": resolved_intent,
            "clarification_needed": False,
            "clarification_question": None,
            "execution_status": "intent_verified",
        }

    normalized = user_query.lower().strip("?.! ")
    words = normalized.split()

    has_specific_dimension = any(
        kw in normalized
        for kw in (
            "region", "quarter", "q4", "q1", "q2", "q3", "2025", "2026",
            "product", "category", "tier", "severity", "status", "warehouse",
            "top", "highest", "most", "lowest", "count", "total", "average",
            "sum", "below", "above", "greater", "less", "list all", "each", "by", "correlate",
            "cost", "price", "stock",
        )
    )

    is_ambiguous = (
        normalized in AMBIGUOUS_SHORT_PHRASES
        or (len(words) <= 3 and not has_specific_dimension)
    )

    if is_ambiguous:
        if "complaint" in normalized:
            question = (
                "Could you clarify how you would like to analyze customer complaints? "
                "For example: total count in Q4-2025, or breakdown by customer region?"
            )
        elif "sale" in normalized or "revenue" in normalized or "order" in normalized:
            question = (
                "Could you clarify which sales metric and breakdown you need? "
                "For example: total completed revenue in Q4-2025, or revenue by region?"
            )
        else:
            question = (
                "Could you specify the metric, dimension (e.g., region, product), "
                "or timeframe (e.g., Q4-2025) you would like to query?"
            )

        return {
            "structured_intent": resolved_intent,
            "clarification_needed": True,
            "clarification_question": question,
            "execution_status": "clarification_needed",
        }

    return {
        "structured_intent": resolved_intent,
        "clarification_needed": False,
        "clarification_question": None,
        "execution_status": "intent_verified",
    }
