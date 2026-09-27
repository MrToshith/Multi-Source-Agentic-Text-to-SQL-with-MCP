"""
LangGraph workflow assembly for Multi-Source Agentic Text-to-SQL.
Phase 3 Core: Intent & Clarification Guard -> Query Planner -> Schema & Source Context Builder.
"""

from typing import Literal
from langgraph.graph import StateGraph, END

from src.agent.state import AgentState
from src.agent.nodes.guard import intent_clarification_guard_node
from src.agent.nodes.planner import query_planner_node
from src.agent.nodes.context import schema_context_builder_node


def route_after_guard(state: AgentState) -> Literal["planner", "__end__"]:
    """Routes to END if clarification is needed, otherwise proceeds to query planner."""
    if state.get("clarification_needed"):
        return "__end__"
    return "planner"


def build_agent_graph(mcp_client=None):
    """Compiles and returns the LangGraph StateGraph workflow."""
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
    workflow.add_edge("context_builder", END)

    return workflow.compile()


agent_graph = build_agent_graph()
