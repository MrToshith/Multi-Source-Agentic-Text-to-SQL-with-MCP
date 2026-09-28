"""
Intent & Clarification Guard Node.
Assesses user query completeness, detects ambiguous entity references using MCP catalog metadata,
and pauses execution with a clarification prompt when ambiguous.
"""

from typing import Any, Dict
from src.agent.state import AgentState
from src.agent.llm import default_llm_client
from src.agent.prompts.guard import GUARD_SYSTEM_PROMPT, format_guard_prompt
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
    """
    Evaluates whether the user's natural language query is unambiguous or requires clarification.
    Also verifies entity resolution so partial/ambiguous product mentions trigger clarification.
    """
    user_query = (state.get("user_query") or "").strip()
    messages = state.get("messages") or []

    # Count how many user messages exist in conversation history
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

    # Resolve structured intent and entity matches against MCP catalog first
    resolved_intent = resolve_query_intent(user_query)

    # 1. If user referenced an ambiguous or incomplete product entity (e.g., "What's the price of the database agent?")
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

    # 2. If an exact entity lookup was matched (e.g. "Database Replica Agent cost?"), it is unambiguous
    if resolved_intent.get("intent") == "entity_attribute_lookup" and resolved_intent.get("entity"):
        return {
            "structured_intent": resolved_intent,
            "clarification_needed": False,
            "clarification_question": None,
            "execution_status": "intent_verified",
        }

    # 3. Check short phrase / broad query ambiguity
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
            "structured_intent": resolved_intent,
            "clarification_needed": True,
            "clarification_question": question,
            "execution_status": "clarification_needed",
        }

    # Optional LLM guard check when local Ollama is running
    llm_result = default_llm_client.generate_json(
        prompt=format_guard_prompt(user_query, messages),
        system_prompt=GUARD_SYSTEM_PROMPT,
    )
    if llm_result and isinstance(llm_result.get("clarification_needed"), bool):
        if llm_result["clarification_needed"]:
            question = llm_result.get("clarification_question") or (
                "Could you please clarify the specific metric, breakdown dimension, or time period you want to analyze?"
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
