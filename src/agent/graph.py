"""
LangGraph workflow assembly for Multi-Source Agentic Text-to-SQL.
Simplified Architecture:
Single, focused Text-to-SQL Node responsible for understanding user intent,
generating dialect-aware SQL queries, and executing through MCP.
"""

from typing import Any, Dict
from langgraph.graph import StateGraph, END

from src.agent.state import AgentState
from src.agent.nodes.guard import intent_clarification_guard_node
from src.agent.nodes.context import schema_context_builder_node
from src.agent.nodes.text2sql import text2sql_generator_node
from src.agent.nodes.execution import mcp_execution_coordinator_node
from src.agent.nodes.recovery import error_recovery_node
from src.agent.nodes.aggregator import cross_source_aggregator_node
from src.agent.nodes.explainer import result_explainer_node
from src.mcp_client import default_mcp_client


def text2sql_node(state: AgentState, mcp_client=None) -> Dict[str, Any]:
    """
    Single, unified Text-to-SQL Agent Node.
    Responsible for:
    1. Ambiguity check (pauses for clarification if query is ambiguous).
    2. Targeted schema context discovery via MCP.
    3. Generating dialect-aware read-only SQL queries across target data sources.
    4. Executing queries through the MCP client and aggregating results.
    """
    client = mcp_client or default_mcp_client

    # 1. Ambiguity & Clarification Check
    guard_update = intent_clarification_guard_node(state)
    if guard_update.get("clarification_needed"):
        return guard_update

    current_state = {**state, **guard_update}

    # 2. Schema Context Discovery
    ctx_update = schema_context_builder_node(current_state, mcp_client=client)
    current_state.update(ctx_update)

    # 3. Dialect-Aware Text-to-SQL Generation (Core Responsibility)
    t2sql_update = text2sql_generator_node(current_state)
    current_state.update(t2sql_update)

    # 4. MCP Query Execution
    exec_update = mcp_execution_coordinator_node(current_state, mcp_client=client)
    current_state.update(exec_update)

    # 5. Autonomous Error Self-Correction (if runtime typo/syntax error occurs)
    while current_state.get("execution_errors") and current_state.get("retry_count", 0) < 3:
        rec_update = error_recovery_node(current_state)
        current_state.update(rec_update)
        if current_state.get("execution_status") == "retry_exhausted":
            break
        exec_retry = mcp_execution_coordinator_node(current_state, mcp_client=client)
        current_state.update(exec_retry)


    # 6. Cross-Source Aggregation & Result Formatting
    agg_update = cross_source_aggregator_node(current_state)
    current_state.update(agg_update)

    exp_update = result_explainer_node(current_state)
    current_state.update(exp_update)

    current_state["execution_status"] = "completed"
    return current_state


def build_agent_graph(mcp_client=None):
    """Compiles and returns the simplified single-node Text-to-SQL StateGraph workflow."""
    workflow = StateGraph(AgentState)

    workflow.add_node(
        "text2sql",
        lambda state: text2sql_node(state, mcp_client=mcp_client),
    )
    workflow.set_entry_point("text2sql")
    workflow.add_edge("text2sql", END)

    return workflow.compile()


agent_graph = build_agent_graph()



