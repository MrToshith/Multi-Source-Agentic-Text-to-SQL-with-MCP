"""
Phase 4 Test Suite: Dialect-Aware Text-to-SQL, AST Safety Validation,
MCP Execution Coordinator, and Bounded Self-Correction Recovery Loop.
"""

import pytest
from src.agent.state import create_initial_state
from src.agent.nodes.text2sql import text2sql_generator_node, generate_dialect_sql_for_source
from src.agent.nodes.validator import sql_safety_validator_node
from src.agent.nodes.execution import mcp_execution_coordinator_node
from src.agent.nodes.recovery import error_recovery_node
from src.agent.graph import build_agent_graph
from src.mcp_client import MCPClient


@pytest.fixture(scope="module")
def mcp_client():
    return MCPClient()


class TestSQLSafetyValidator:
    """Tests SQLGlot AST safety validation and row limit bounding."""

    def test_ast_validator_allows_valid_select(self):
        state = create_initial_state("Show total revenue by region")
        state["generated_sql"] = {
            "sales_pg": "SELECT region_id, SUM(total_amount) FROM orders GROUP BY region_id",
            "crm_mssql": "SELECT TOP 10 region_id, COUNT(*) FROM dbo.customers GROUP BY region_id",
        }
        updates = sql_safety_validator_node(state)
        assert updates["validation_errors"] == {}
        assert updates["execution_status"] == "sql_validated"
        assert "LIMIT" in updates["generated_sql"]["sales_pg"].upper()

    def test_ast_validator_rejects_mutations(self):
        state = create_initial_state("Malicious query")
        state["generated_sql"] = {
            "sales_pg": "DROP TABLE orders CASCADE",
            "crm_mssql": "DELETE FROM dbo.customers WHERE customer_id = 201",
            "analytics_duckdb": "UPDATE products SET list_price = 0",
        }
        updates = sql_safety_validator_node(state)
        errors = updates["validation_errors"]

        assert "sales_pg" in errors
        assert "crm_mssql" in errors
        assert "analytics_duckdb" in errors
        assert updates["execution_status"] == "validation_failed"


class TestDialectGenerationAndExecution:
    """Tests dialect differences across PostgreSQL, SQL Server T-SQL, and DuckDB."""

    def test_dialect_generation(self):
        pg_sql = generate_dialect_sql_for_source("sales_pg", "Revenue by region in Q4-2025")
        mssql_sql = generate_dialect_sql_for_source("crm_mssql", "Complaints by region in Q4-2025")
        duck_sql = generate_dialect_sql_for_source("analytics_duckdb", "Products below 300 stock")

        assert "LIMIT" in pg_sql
        assert "SELECT TOP" in mssql_sql
        assert "dbo." in mssql_sql
        assert "LIMIT" in duck_sql

    def test_mcp_execution_success(self, mcp_client):
        state = create_initial_state("Compare revenue and complaints by region in Q4-2025")
        state["generated_sql"] = {
            "sales_pg": generate_dialect_sql_for_source("sales_pg", state["user_query"]),
            "crm_mssql": generate_dialect_sql_for_source("crm_mssql", state["user_query"]),
            "analytics_duckdb": generate_dialect_sql_for_source("analytics_duckdb", state["user_query"]),
        }
        updates = mcp_execution_coordinator_node(state, mcp_client=mcp_client)

        assert updates["execution_errors"] == {}
        assert updates["execution_status"] == "executed"
        assert updates["execution_results"]["sales_pg"]["row_count"] > 0
        assert updates["execution_results"]["crm_mssql"]["row_count"] > 0
        assert updates["execution_results"]["analytics_duckdb"]["row_count"] > 0


class TestSelfCorrectionLoop:
    """Tests autonomous error healing and retry bounds."""

    def test_self_correction_loop_heals_column_error(self, mcp_client):
        graph = build_agent_graph(mcp_client=mcp_client)
        state = create_initial_state("Calculate total revenue by region in Q4-2025")
        # Pre-seed an intentional column typo ('rev' instead of 'total_amount') in sales_pg
        state["generated_sql"] = {
            "sales_pg": "SELECT r.region_id, r.region_name, SUM(o.rev) AS total_revenue FROM regions r JOIN orders o ON r.region_id = o.region_id GROUP BY r.region_id, r.region_name LIMIT 50"
        }

        final_state = graph.invoke(state)

        assert final_state["retry_count"] >= 1
        assert final_state["retry_count"] <= 3
        assert final_state["execution_errors"] == {}
        assert "sales_pg" in final_state["execution_results"]
        assert final_state["execution_results"]["sales_pg"]["row_count"] > 0

    def test_self_correction_retry_exhaustion(self, mcp_client):
        graph = build_agent_graph(mcp_client=mcp_client)
        state = create_initial_state("Calculate total revenue by region in Q4-2025")
        # Inject an unrecoverable query marker so recovery cannot resolve it
        state["generated_sql"] = {
            "sales_pg": "SELECT * FROM UNRECOVERABLE_TABLE WHERE FORCE_PERSISTENT_FAILURE = 1"
        }

        final_state = graph.invoke(state)

        assert final_state["retry_count"] == 3
        assert len(final_state["execution_errors"]) > 0
