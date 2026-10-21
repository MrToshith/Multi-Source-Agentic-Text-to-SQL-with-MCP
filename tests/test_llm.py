"""
Tests for LLM Client, MCP Schema Injection, and Dynamic SQL Generation.
"""

import pytest
from unittest.mock import MagicMock
from src.agent.llm import clean_sql, LLMClient
from src.agent.graph import get_mcp_schema_context, build_agent_graph
from src.agent.state import create_initial_state
from src.mcp_client import MCPClient


class TestLLMText2SQL:
    """Verifies LLM cleaning, MCP schema discovery, and LLM-driven query execution."""

    def test_clean_sql_strips_markdown_and_prefixes(self):
        raw = "```sql\nSELECT product_name, cost_price FROM products WHERE product_name = 'Database Replica Agent';\n```"
        cleaned = clean_sql(raw)
        assert cleaned == "SELECT product_name, cost_price FROM products WHERE product_name = 'Database Replica Agent'"

        raw_with_prefix = "Here is the SQL query:\nSELECT region_id, SUM(total_amount) FROM orders GROUP BY region_id;"
        cleaned_prefix = clean_sql(raw_with_prefix)
        assert cleaned_prefix == "SELECT region_id, SUM(total_amount) FROM orders GROUP BY region_id"

    def test_get_mcp_schema_context_fetches_tables_and_columns(self):
        mcp = MCPClient()
        schema_text = get_mcp_schema_context(mcp, "analytics_duckdb")
        assert "Source: analytics_duckdb" in schema_text
        assert "products" in schema_text
        assert "cost_price" in schema_text

    def test_llm_generated_sql_is_used_when_available(self):
        """When an LLM provides valid SQL, the agent executes the LLM's SQL."""
        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.is_available.return_value = True
        mock_llm.generate_sql.return_value = (
            "SELECT product_name, cost_price FROM products WHERE product_name = 'Database Replica Agent' LIMIT 1"
        )

        mcp = MCPClient()
        graph = build_agent_graph(mcp_client=mcp, llm_client=mock_llm)

        state = create_initial_state("What is the cost price of Database Replica Agent?")
        final = graph.invoke(state)

        # Assert LLM was called with MCP discovered schema in the prompt
        assert mock_llm.generate_sql.called
        call_prompt = mock_llm.generate_sql.call_args[0][0]
        assert "MCP Discovered Schema:" in call_prompt
        assert "products" in call_prompt

        # Assert the LLM's SQL was recorded and executed
        assert "analytics_duckdb" in final["generated_sql"]
        assert "SELECT product_name, cost_price" in final["generated_sql"]["analytics_duckdb"]
        assert len(final["aggregated_data"]) == 1
        assert float(final["aggregated_data"][0]["cost_price"]) == 1100.0
