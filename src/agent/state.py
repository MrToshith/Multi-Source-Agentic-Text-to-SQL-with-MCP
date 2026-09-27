"""
State definition for the LangGraph multi-source data analyst agent.
"""

from typing import Any, Dict, List, Optional, TypedDict


class SubQueryTask(TypedDict, total=False):
    """Represents a single-source analytical sub-task planned by the agent."""
    sub_task_id: str
    source: str
    description: str
    target_tables: List[str]
    join_key: Optional[str]


class AgentState(TypedDict, total=False):
    """Comprehensive graph state tracked across multi-source reasoning turns."""
    session_id: str
    messages: List[Dict[str, str]]
    user_query: str

    # Phase 3: Intent & Clarification Guard + Planning + Schema Discovery
    clarification_needed: bool
    clarification_question: Optional[str]
    plan: List[SubQueryTask]
    join_keys: List[str]
    schema_context: Dict[str, Any]

    # Phase 4: Text-to-SQL Generation, AST Validation, Execution & Self-Correction
    generated_sql: Dict[str, str]
    validation_errors: Dict[str, str]
    execution_results: Dict[str, Any]
    execution_errors: Dict[str, str]
    retry_count: int

    # Phase 5: Cross-Source Aggregation & Natural Language Explanation
    aggregated_data: Optional[List[Dict[str, Any]]]
    final_answer: Optional[str]
    visualization_config: Optional[Dict[str, Any]]
    execution_status: str


def create_initial_state(
    user_query: str,
    session_id: str = "default-session",
    messages: Optional[List[Dict[str, str]]] = None,
) -> AgentState:
    """Creates a clean initial AgentState dictionary for a workflow turn."""
    history = list(messages) if messages else []
    if not history or history[-1].get("content") != user_query:
        history.append({"role": "user", "content": user_query})

    return AgentState(
        session_id=session_id,
        messages=history,
        user_query=user_query,
        clarification_needed=False,
        clarification_question=None,
        plan=[],
        join_keys=[],
        schema_context={},
        generated_sql={},
        validation_errors={},
        execution_results={},
        execution_errors={},
        retry_count=0,
        aggregated_data=None,
        final_answer=None,
        visualization_config=None,
        execution_status="initialized",
    )
