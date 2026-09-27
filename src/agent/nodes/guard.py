"""
Intent & Clarification Guard Node.
Assesses user query completeness and pauses execution with a clarification prompt when ambiguous.
"""

from typing import Any, Dict
from src.agent.state import AgentState
from src.agent.llm import default_llm_client
from src.agent.prompts.guard import GUARD_SYSTEM_PROMPT, format_guard_prompt


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
    """
    Evaluates whether the user's natural language query is unambiguous or requires clarification.
    If the session already has prior turns answering a clarification, proceeds directly to planning.
    """
    user_query = (state.get("user_query") or "").strip()
    messages = state.get("messages") or []

    # Count how many user messages exist in conversation history
    user_turns = [m for m in messages if m.get("role") == "user"]
    if len(user_turns) > 1:
        # Combine prior query context with clarification response
        combined_query = " | ".join(m.get("content", "") for m in user_turns)
        return {
            "user_query": combined_query,
            "clarification_needed": False,
            "clarification_question": None,
            "execution_status": "intent_verified",
        }

    # Try local LLM if enabled
    llm_result = default_llm_client.generate_json(
        prompt=format_guard_prompt(user_query, messages),
        system_prompt=GUARD_SYSTEM_PROMPT,
    )
    if llm_result and isinstance(llm_result.get("clarification_needed"), bool):
        if llm_result["clarification_needed"]:
            question = llm_result.get("clarification_question") or (
                "Could you please clarify the specific metric, breakdown dimension (e.g., by region or product), "
                "or time period (e.g., Q4-2025 or Q1-2026) you want to analyze?"
            )
            return {
                "clarification_needed": True,
                "clarification_question": question,
                "execution_status": "clarification_needed",
            }
        return {
            "clarification_needed": False,
            "clarification_question": None,
            "execution_status": "intent_verified",
        }

    # Deterministic ambiguity evaluation
    normalized = user_query.lower().strip("?.! ")
    words = normalized.split()

    has_specific_dimension = any(
        kw in normalized
        for kw in (
            "region", "quarter", "q4", "q1", "q2", "q3", "2025", "2026",
            "product", "category", "tier", "severity", "status", "warehouse",
            "top", "highest", "most", "lowest", "count", "total", "average",
            "sum", "below", "above", "greater", "less", "list all", "each", "by", "correlate",
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
                "For example: by severity, by customer region, or for a specific quarter (Q4-2025 vs Q1-2026)?"
            )
        elif "sale" in normalized or "revenue" in normalized or "order" in normalized:
            question = (
                "Could you clarify which sales metric and breakdown you need? "
                "For example: total revenue by region, completed order volume in Q4-2025, or top products sold?"
            )
        else:
            question = (
                "Your request is a bit broad. Could you specify the metric, dimension (e.g., region, product, customer tier), "
                "or timeframe (e.g., Q4-2025) you would like to query?"
            )

        return {
            "clarification_needed": True,
            "clarification_question": question,
            "execution_status": "clarification_needed",
        }

    return {
        "clarification_needed": False,
        "clarification_question": None,
        "execution_status": "intent_verified",
    }
