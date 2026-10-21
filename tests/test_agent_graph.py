"""
Test suite for Streamlined LangGraph Agent Graph.
Tests ambiguity detection, source determination, and agent workflow routing.
"""

import pytest
from src.agent.state import create_initial_state
from src.agent.graph import (
    build_agent_graph,
    check_query_ambiguity,
    determine_sources,
)
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
        ambiguous, question = check_query_ambiguity("Show sales")
        assert ambiguous is True
        assert question is not None
        assert len(question) > 15

    def test_clarification_guard_clear(self):
        ambiguous, question = check_query_ambiguity(
            "Which region had the highest revenue and most customer complaints in Q4-2025?"
        )
        assert ambiguous is False
        assert question is None

    def test_clarification_resumes_after_user_follow_up(self, compiled_graph):
        messages = [
            {"role": "user", "content": "Show sales"},
            {"role": "assistant", "content": "Could you clarify which metric and breakdown you need?"},
            {"role": "user", "content": "Total revenue by region for Q4-2025"},
        ]
        state = create_initial_state(
            user_query="Total revenue by region for Q4-2025",
            messages=messages,
        )
        final_state = compiled_graph.invoke(state)
        assert final_state["clarification_needed"] is False
        assert len(final_state.get("aggregated_data") or []) > 0


class TestQueryPlanner:
    """Tests cross-source source determination."""

    def test_query_planner_decomposition_cross_source(self):
        sources = determine_sources(
            "Which region had the highest revenue and most customer complaints last quarter?"
        )
        assert "sales_pg" in sources
        assert "crm_mssql" in sources

    def test_query_planner_analytics_source(self):
        sources = determine_sources(
            "List all products with warehouse stock level below 300"
        )
        assert sources == ["analytics_duckdb"]


class TestSchemaContextBuilder:
    """Tests schema discovery via MCP client."""

    def test_schema_context_builder_mcp_call(self, mcp_client):
        sources = determine_sources("Which region had the highest revenue?")
        assert "sales_pg" in sources
        tables = mcp_client.list_tables("sales_pg")
        assert "orders" in tables
        assert "regions" in tables
        schema = mcp_client.describe_table("sales_pg", "orders")
        assert len(schema["columns"]) > 0


class TestCompiledGraphRouting:
    """Tests end-to-end LangGraph state transitions."""

    def test_graph_pauses_on_ambiguous_query(self, compiled_graph):
        initial = create_initial_state("complaints")
        final_state = compiled_graph.invoke(initial)

        assert final_state["clarification_needed"] is True
        assert final_state["clarification_question"] is not None

    def test_graph_completes_planning_and_context_for_clear_query(self, compiled_graph):
        initial = create_initial_state(
            "Compare total order revenue and customer complaint count by region in Q4-2025"
        )
        final_state = compiled_graph.invoke(initial)

        assert final_state["clarification_needed"] is False
        assert len(final_state.get("aggregated_data") or []) > 0
        assert "sales_pg" in final_state.get("generated_sql", {})
        assert "crm_mssql" in final_state.get("generated_sql", {})
