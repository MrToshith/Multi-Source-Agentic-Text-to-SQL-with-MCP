"""
LangGraph workflow assembly for Multi-Source Agentic Text-to-SQL.
Streamlined Pipeline:
Guard -> Context Builder -> Text-to-SQL -> Execution (with self-correction recovery) -> Aggregator -> Explainer.
"""

from typing import Literal
from langgraph.graph import StateGraph, END

from src.agent.state import AgentState
from src.agent.nodes.guard import intent_clarification_guard_node
from src.agent.nodes.context import schema_context_builder_node
from src.agent.nodes.text2sql import text2sql_generator_node
from src.agent.nodes.execution import mcp_execution_coordinator_node
from src.agent.nodes.recovery import error_recovery_node, MAX_RETRIES
from src.agent.nodes.aggregator import cross_source_aggregator_node
from src.agent.nodes.explainer import result_explainer_node


def route_after_guard(state: AgentState) -> Literal["context_builder", "__end__"]:
    """Routes to END if clarification is needed, otherwise proceeds to schema context builder."""
    if state.get("clarification_needed"):
        return "__end__"
    return "context_builder"


def route_after_execution(state: AgentState) -> Literal["aggregator", "recovery", "__end__"]:
    """Routes to recovery if runtime execution errors occurred, otherwise to aggregator."""
    if state.get("execution_errors"):
        if state.get("retry_count", 0) >= MAX_RETRIES:
            return "__end__"
        return "recovery"
    return "aggregator"


def route_after_recovery(state: AgentState) -> Literal["execution", "__end__"]:
    """Retries execution of repaired SQL unless retries are exhausted."""
    if state.get("execution_status") == "retry_exhausted":
        return "__end__"
    return "execution"


def build_agent_graph(mcp_client=None):
    """Compiles and returns the simplified LangGraph StateGraph workflow."""
    workflow = StateGraph(AgentState)

    workflow.add_node("guard", intent_clarification_guard_node)
    workflow.add_node(
        "context_builder",
        lambda state: schema_context_builder_node(state, mcp_client=mcp_client),
    )
    workflow.add_node("text2sql", text2sql_generator_node)
    workflow.add_node(
        "execution",
        lambda state: mcp_execution_coordinator_node(state, mcp_client=mcp_client),
    )
    workflow.add_node("recovery", error_recovery_node)
    workflow.add_node("aggregator", cross_source_aggregator_node)
    workflow.add_node("explainer", result_explainer_node)

    workflow.set_entry_point("guard")
    workflow.add_conditional_edges(
        "guard",
        route_after_guard,
        {
            "context_builder": "context_builder",
            "__end__": END,
        },
    )
    workflow.add_edge("context_builder", "text2sql")
    workflow.add_edge("text2sql", "execution")

    workflow.add_conditional_edges(
        "execution",
        route_after_execution,
        {
            "aggregator": "aggregator",
            "recovery": "recovery",
            "__end__": END,
        },
    )

    workflow.add_conditional_edges(
        "recovery",
        route_after_recovery,
        {
            "execution": "execution",
            "__end__": END,
        },
    )

    workflow.add_edge("aggregator", "explainer")
    workflow.add_edge("explainer", END)

    return workflow.compile()


agent_graph = build_agent_graph()


