"""
LangGraph workflow assembly for Multi-Source Agentic Text-to-SQL.
Complete End-to-End Pipeline (Phases 3, 4, 5):
Guard -> Planner -> Context Builder -> Text-to-SQL -> Validator -> Execution / Self-Correction -> Aggregator -> Explainer.
"""

from typing import Literal
from langgraph.graph import StateGraph, END

from src.agent.state import AgentState
from src.agent.nodes.guard import intent_clarification_guard_node
from src.agent.nodes.planner import query_planner_node
from src.agent.nodes.context import schema_context_builder_node
from src.agent.nodes.text2sql import text2sql_generator_node
from src.agent.nodes.validator import sql_safety_validator_node
from src.agent.nodes.execution import mcp_execution_coordinator_node
from src.agent.nodes.recovery import error_recovery_node, MAX_RETRIES
from src.agent.nodes.aggregator import cross_source_aggregator_node
from src.agent.nodes.explainer import result_explainer_node


def route_after_guard(state: AgentState) -> Literal["planner", "__end__"]:
    """Routes to END if clarification is needed, otherwise proceeds to query planner."""
    if state.get("clarification_needed"):
        return "__end__"
    return "planner"


def route_after_validator(state: AgentState) -> Literal["execution", "recovery", "__end__"]:
    """Routes to recovery if AST validation errors exist, otherwise to MCP execution."""
    if state.get("validation_errors"):
        if state.get("retry_count", 0) >= MAX_RETRIES:
            return "__end__"
        return "recovery"
    return "execution"


def route_after_execution(state: AgentState) -> Literal["aggregator", "recovery", "__end__"]:
    """Routes to recovery if runtime execution errors occurred, otherwise to cross-source aggregator."""
    if state.get("execution_errors"):
        if state.get("retry_count", 0) >= MAX_RETRIES:
            return "__end__"
        return "recovery"
    return "aggregator"


def route_after_recovery(state: AgentState) -> Literal["validator", "__end__"]:
    """Re-validates self-corrected SQL before execution unless retries are exhausted."""
    if state.get("execution_status") == "retry_exhausted":
        return "__end__"
    return "validator"


def build_agent_graph(mcp_client=None):
    """Compiles and returns the complete LangGraph StateGraph workflow."""
    workflow = StateGraph(AgentState)

    workflow.add_node("guard", intent_clarification_guard_node)
    workflow.add_node(
        "planner",
        lambda state: query_planner_node(state, mcp_client=mcp_client),
    )
    workflow.add_node(
        "context_builder",
        lambda state: schema_context_builder_node(state, mcp_client=mcp_client),
    )
    workflow.add_node("text2sql", text2sql_generator_node)
    workflow.add_node("validator", sql_safety_validator_node)
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
            "planner": "planner",
            "__end__": END,
        },
    )
    workflow.add_edge("planner", "context_builder")
    workflow.add_edge("context_builder", "text2sql")
    workflow.add_edge("text2sql", "validator")

    workflow.add_conditional_edges(
        "validator",
        route_after_validator,
        {
            "execution": "execution",
            "recovery": "recovery",
            "__end__": END,
        },
    )

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
            "validator": "validator",
            "__end__": END,
        },
    )

    workflow.add_edge("aggregator", "explainer")
    workflow.add_edge("explainer", END)

    return workflow.compile()


agent_graph = build_agent_graph()
