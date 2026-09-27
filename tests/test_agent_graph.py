"""
Phase 3 Test Suite: LangGraph Agent Core.
Tests Intent & Clarification Guard, Query Planner & Source Selector,
Schema & Source Context Builder via MCP Client, and LangGraph workflow routing.
"""

import pytest
from src.agent.state import create_initial_state
from src.agent.nodes.guard import intent_clarification_guard_node
from src.agent.nodes.planner import query_planner_node
from src.agent.nodes.context import schema_context_builder_node
from src.agent.graph import build_agent_graph
from src.mcp_client import MCPClient


@pytest.fixture(scope="module")
def mcp_client():
    return MCPClient()


@pytest.fixture(scope="module")
def compiled_graph(mcp_client):
    return build_agent_graph(mcp_client=mcp_client)


class TestClarificationGuard:
    """Tests ambiguity detection and conversational clarification interrupts."""

    def test_clarification_guard_ambiguous(self):
        state = create_initial_state("Show sales")
        updates = intent_clarification_guard_node(state)
        assert updates["clarification_needed"] is True
        assert updates["clarification_question"] is not None
        assert len(updates["clarification_question"]) > 15
        assert updates["execution_status"] == "clarification_needed"

    def test_clarification_guard_clear(self):
        state = create_initial_state(
            "Which region had the highest revenue and most customer complaints in Q4-2025?"
        )
        updates = intent_clarification_guard_node(state)
        assert updates["clarification_needed"] is False
        assert updates["clarification_question"] is None
        assert updates["execution_status"] == "intent_verified"

    def test_clarification_resumes_after_user_follow_up(self):
        messages = [
            {"role": "user", "content": "Show sales"},
            {"role": "assistant", "content": "Could you clarify which metric and breakdown you need?"},
            {"role": "user", "content": "Total revenue by region for Q4-2025"},
        ]
        state = create_initial_state(
            user_query="Total revenue by region for Q4-2025",
            messages=messages,
        )
        updates = intent_clarification_guard_node(state)
        assert updates["clarification_needed"] is False
        assert "Show sales" in updates["user_query"]
        assert "Total revenue by region" in updates["user_query"]


class TestQueryPlanner:
    """Tests cross-source decomposition and join key identification."""

    def test_query_planner_decomposition_cross_source(self, mcp_client):
        state = create_initial_state(
            "Which region had the highest revenue and most customer complaints last quarter?"
        )
        updates = query_planner_node(state, mcp_client=mcp_client)
        plan = updates["plan"]
        sources = {task["source"] for task in plan}

        assert "sales_pg" in sources
        assert "crm_mssql" in sources
        assert "region_id" in updates["join_keys"]
        assert updates["execution_status"] == "planned"

    def test_query_planner_analytics_source(self, mcp_client):
        state = create_initial_state(
            "List all products with warehouse stock level below 300"
        )
        updates = query_planner_node(state, mcp_client=mcp_client)
        plan = updates["plan"]
        sources = {task["source"] for task in plan}

        assert sources == {"analytics_duckdb"}


class TestSchemaContextBuilder:
    """Tests dynamic schema, foreign key, and sample row retrieval through MCP."""

    def test_schema_context_builder_mcp_call(self, mcp_client):
        state = create_initial_state(
            "Which region had the highest revenue and most customer complaints last quarter?"
        )
        plan_updates = query_planner_node(state, mcp_client=mcp_client)
        state.update(plan_updates)

        ctx_updates = schema_context_builder_node(state, mcp_client=mcp_client)
        schema_context = ctx_updates["schema_context"]

        assert "sales_pg" in schema_context
        assert "crm_mssql" in schema_context
        assert "orders" in schema_context["sales_pg"]["tables"]
        assert "regions" in schema_context["sales_pg"]["tables"]
        assert "complaints" in schema_context["crm_mssql"]["tables"]
        assert len(schema_context["sales_pg"]["tables"]["orders"]["sample_rows"]) > 0
        assert len(schema_context["sales_pg"]["relationships"]) > 0


class TestCompiledGraphRouting:
    """Tests end-to-end LangGraph state transitions for Phase 3."""

    def test_graph_pauses_on_ambiguous_query(self, compiled_graph):
        initial = create_initial_state("complaints")
        final_state = compiled_graph.invoke(initial)

        assert final_state["clarification_needed"] is True
        assert final_state["clarification_question"] is not None
        assert final_state["plan"] == []

    def test_graph_completes_planning_and_context_for_clear_query(self, compiled_graph):
        initial = create_initial_state(
            "Compare total order revenue and customer complaint count by region in Q4-2025"
        )
        final_state = compiled_graph.invoke(initial)

        assert final_state["clarification_needed"] is False
        assert len(final_state["plan"]) >= 2
        assert "sales_pg" in final_state["schema_context"]
        assert "crm_mssql" in final_state["schema_context"]
