"""
Test suite for Dialect-Aware Text-to-SQL and MCP Execution.
"""

import pytest
from src.agent.state import create_initial_state
from src.agent.graph import generate_dialect_sql, build_agent_graph
from src.mcp_server.guardrails import validate_read_only_sql, apply_query_limit
from src.mcp_client import MCPClient


@pytest.fixture(scope="module")
def mcp_client():
    return MCPClient()


class TestSQLSafetyValidator:
    """Tests SQLGlot AST safety validation and row limit bounding."""

    def test_ast_validator_allows_valid_select(self):
        sql_pg = "SELECT region_id, SUM(total_amount) FROM orders GROUP BY region_id"
        is_valid, err = validate_read_only_sql(sql_pg)
        assert is_valid is True
        limited = apply_query_limit(sql_pg, max_rows=200)
        assert "LIMIT" in limited.upper()

    def test_ast_validator_rejects_mutations(self):
        for bad_sql in [
            "DROP TABLE orders CASCADE",
            "DELETE FROM dbo.customers WHERE customer_id = 201",
            "UPDATE products SET list_price = 0",
        ]:
            is_valid, err = validate_read_only_sql(bad_sql)
            assert is_valid is False
            assert "Forbidden statement type" in err or "SELECT" in err


class TestDialectGenerationAndExecution:
    """Tests dialect differences across PostgreSQL, SQL Server T-SQL, and DuckDB."""

    def test_dialect_generation(self):
        pg_sql = generate_dialect_sql("sales_pg", "Revenue by region in Q4-2025")
        mssql_sql = generate_dialect_sql("crm_mssql", "Complaints by region in Q4-2025")
        duck_sql = generate_dialect_sql("analytics_duckdb", "Products below 300 stock")

        assert "LIMIT" in pg_sql
        assert "SELECT TOP" in mssql_sql
        assert "dbo." in mssql_sql
        assert "LIMIT" in duck_sql

    def test_mcp_execution_success(self, mcp_client):
        graph = build_agent_graph(mcp_client=mcp_client)
        state = create_initial_state("Compare revenue and complaints by region in Q4-2025")
        final_state = graph.invoke(state)

        assert final_state["clarification_needed"] is False
        assert len(final_state["execution_results"]) >= 2
        assert len(final_state["aggregated_data"]) > 0


class TestSelfCorrectionLoop:
    """Tests autonomous error healing."""

    def test_self_correction_loop_heals_column_error(self, mcp_client):
        graph = build_agent_graph(mcp_client=mcp_client)
        state = create_initial_state("Calculate total revenue by region in Q4-2025")
        # Pre-seed an intentional column typo ('rev' instead of 'total_amount') in sales_pg
        state["generated_sql"] = {
            "sales_pg": "SELECT r.region_id, r.region_name, SUM(o.rev) AS total_revenue FROM regions r JOIN orders o ON r.region_id = o.region_id GROUP BY r.region_id, r.region_name LIMIT 50"
        }

        final_state = graph.invoke(state)
        assert "total_amount" in final_state["generated_sql"]["sales_pg"]
        assert len(final_state["aggregated_data"]) > 0
