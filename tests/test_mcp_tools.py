"""
Phase 2 Test Suite: Custom Multi-Source MCP Server.
Validates tool registration, source routing, schema discovery,
read-only query execution, and server-side safety guardrails.
"""

import pytest
import asyncio
from src.mcp_server.server import create_mcp_server
from src.mcp_server.router import SourceRouter
from src.mcp_server.guardrails import (
    validate_read_only_sql,
    apply_query_limit,
    SQLSecurityError,
)
from src.mcp_server.adapters.duckdb_file import DuckDBFileAdapter
from tests.test_connectivity import is_service_listening
from src.config import config


# ------------------------------------------------------------------------------
# Module-level fixtures
# ------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def duckdb_adapter():
    return DuckDBFileAdapter()


@pytest.fixture(scope="module")
def mcp_server():
    return create_mcp_server()


# ------------------------------------------------------------------------------
# 1. Server Guardrails Unit Tests
# ------------------------------------------------------------------------------

class TestServerGuardrails:
    """Validates server-side AST analysis and query bounding."""

    def test_valid_select_allowed(self):
        valid_queries = [
            "SELECT * FROM products",
            "SELECT product_id, product_name FROM products WHERE list_price > 1000",
            "SELECT category, COUNT(*) FROM products GROUP BY category HAVING COUNT(*) > 1",
            "WITH high_price AS (SELECT * FROM products WHERE list_price > 2000) SELECT * FROM high_price",
            "SELECT p.product_name, i.stock_level FROM products p JOIN inventory i ON p.product_id = i.product_id",
        ]
        for query in valid_queries:
            is_valid, msg = validate_read_only_sql(query)
            assert is_valid is True, f"Expected '{query}' to be valid, but got: {msg}"

    def test_mutations_strictly_blocked(self):
        blocked_queries = [
            "DELETE FROM products WHERE product_id = 301",
            "DROP TABLE inventory",
            "UPDATE products SET list_price = 0",
            "INSERT INTO regions (region_id, region_name) VALUES (99, 'Invalid')",
            "TRUNCATE TABLE orders",
            "ALTER TABLE customers ADD COLUMN hack VARCHAR(100)",
            "CREATE TABLE hack (id INT)",
        ]
        for query in blocked_queries:
            is_valid, msg = validate_read_only_sql(query)
            assert is_valid is False, f"Expected '{query}' to be blocked, but was marked valid."
            assert ("Forbidden" in msg) or ("Only read-only" in msg) or ("syntax" in msg)

    def test_multi_statement_injection_blocked(self):
        injections = [
            "SELECT * FROM products; DROP TABLE products",
            "SELECT 1; DELETE FROM customers",
            "SELECT * FROM inventory; UPDATE products SET list_price = 0;",
        ]
        for injection in injections:
            is_valid, msg = validate_read_only_sql(injection)
            assert is_valid is False, f"Expected injection '{injection}' to be blocked."
            assert "Multiple statements" in msg or "Forbidden" in msg

    def test_apply_query_limit(self):
        # When no limit is present, append limit
        q1 = apply_query_limit("SELECT * FROM products", max_rows=50)
        assert "50" in q1

        # When higher limit is present, clamp to max_rows
        q2 = apply_query_limit("SELECT * FROM products LIMIT 500", max_rows=100)
        assert "100" in q2
        assert "500" not in q2

        # When lower limit is present, preserve it
        q3 = apply_query_limit("SELECT * FROM products LIMIT 10", max_rows=100)
        assert "10" in q3


# ------------------------------------------------------------------------------
# 2. Source Router Tests
# ------------------------------------------------------------------------------

class TestSourceRouter:
    """Validates source dispatcher resolution and error handling."""

    def test_list_data_sources(self):
        router = SourceRouter()
        sources = router.list_data_sources()
        source_ids = {s.id for s in sources}
        assert source_ids == {"sales_pg", "crm_mssql", "analytics_duckdb"}

        # Verify technology metadata
        source_map = {s.id: s for s in sources}
        assert source_map["sales_pg"].type == "postgresql"
        assert source_map["crm_mssql"].type == "sqlserver"
        assert source_map["analytics_duckdb"].type == "duckdb"

    def test_get_adapter_valid(self):
        router = SourceRouter()
        pg_adapter = router.get_adapter("sales_pg")
        assert pg_adapter.source_id == "sales_pg"

        mssql_adapter = router.get_adapter("crm_mssql")
        assert mssql_adapter.source_id == "crm_mssql"

        duck_adapter = router.get_adapter("analytics_duckdb")
        assert duck_adapter.source_id == "analytics_duckdb"

    def test_get_adapter_unknown_source_raises(self):
        router = SourceRouter()
        with pytest.raises(ValueError) as exc:
            router.get_adapter("unknown_db")
        assert "Unknown data source 'unknown_db'" in str(exc.value)


# ------------------------------------------------------------------------------
# 3. DuckDB File Adapter Tests
# ------------------------------------------------------------------------------

class TestDuckDBFileAdapter:
    """Tests for the analytical DuckDB CSV file adapter."""

    def test_list_tables(self, duckdb_adapter):
        tables = duckdb_adapter.list_tables()
        assert "products" in tables
        assert "inventory" in tables

    def test_describe_table_products(self, duckdb_adapter):
        schema = duckdb_adapter.describe_table("products")
        assert schema.table_name == "products"
        col_names = {c.name for c in schema.columns}
        assert {"product_id", "product_name", "category", "cost_price", "list_price", "is_active"}.issubset(col_names)
        # Check product_id is primary key
        pk_col = next(c for c in schema.columns if c.name == "product_id")
        assert pk_col.is_primary_key is True

    def test_describe_table_inventory(self, duckdb_adapter):
        schema = duckdb_adapter.describe_table("inventory")
        assert schema.table_name == "inventory"
        col_names = {c.name for c in schema.columns}
        assert {"product_id", "warehouse_id", "stock_level", "reorder_point"}.issubset(col_names)

    def test_describe_table_unknown_raises(self, duckdb_adapter):
        with pytest.raises(ValueError) as exc:
            duckdb_adapter.describe_table("non_existent_table")
        assert "does not exist" in str(exc.value)

    def test_get_relationships(self, duckdb_adapter):
        rels = duckdb_adapter.get_relationships()
        assert len(rels) >= 1
        rel = rels[0]
        assert rel.source_table == "inventory"
        assert rel.source_column == "product_id"
        assert rel.target_table == "products"
        assert rel.target_column == "product_id"

    def test_get_sample_rows(self, duckdb_adapter):
        samples = duckdb_adapter.get_sample_rows("products", limit=3)
        assert len(samples) == 3
        assert "product_name" in samples[0]
        assert "list_price" in samples[0]

    def test_execute_read_query_success(self, duckdb_adapter):
        query = "SELECT product_name, category, list_price FROM products WHERE category = 'Software'"
        result = duckdb_adapter.execute_read_query(query)
        assert result.row_count > 0
        assert result.columns == ["product_name", "category", "list_price"]
        assert result.truncated is False
        assert result.execution_time_ms is not None
        assert result.execution_time_ms >= 0


# ------------------------------------------------------------------------------
# 4. MCP Protocol Server Tool Invocations
# ------------------------------------------------------------------------------

class TestMCPServerProtocol:
    """Tests async tool invocations through the official MCP server interface."""

    def test_all_six_tools_registered(self, mcp_server):
        tools = asyncio.run(mcp_server.list_tools())
        tool_names = {t.name for t in tools}
        expected_tools = {
            "list_data_sources",
            "list_tables",
            "describe_table",
            "get_relationships",
            "get_sample_rows",
            "execute_read_query",
        }
        assert expected_tools == tool_names

    def test_tool_list_data_sources(self, mcp_server):
        res = asyncio.run(mcp_server.call_tool("list_data_sources", {}))
        assert not res.is_error
        combined_text = " ".join(c.text for c in res.content)
        assert "sales_pg" in combined_text
        assert "crm_mssql" in combined_text
        assert "analytics_duckdb" in combined_text

    def test_tool_list_tables_analytics(self, mcp_server):
        res = asyncio.run(mcp_server.call_tool("list_tables", {"source": "analytics_duckdb"}))
        assert not res.is_error
        table_names = [c.text for c in res.content]
        assert "products" in table_names
        assert "inventory" in table_names

    def test_tool_describe_table_analytics(self, mcp_server):
        res = asyncio.run(mcp_server.call_tool("describe_table", {"source": "analytics_duckdb", "table": "products"}))
        assert not res.is_error
        combined_text = " ".join(c.text for c in res.content)
        assert "product_id" in combined_text
        assert "product_name" in combined_text

    def test_tool_get_relationships_analytics(self, mcp_server):
        res = asyncio.run(mcp_server.call_tool("get_relationships", {"source": "analytics_duckdb"}))
        assert not res.is_error
        combined_text = " ".join(c.text for c in res.content)
        assert "inventory" in combined_text
        assert "products" in combined_text

    def test_tool_get_sample_rows_analytics(self, mcp_server):
        res = asyncio.run(mcp_server.call_tool("get_sample_rows", {"source": "analytics_duckdb", "table": "products", "limit": 2}))
        assert not res.is_error
        combined_text = " ".join(c.text for c in res.content)
        assert "Enterprise Cloud Suite" in combined_text

    def test_tool_execute_read_query_analytics(self, mcp_server):
        res = asyncio.run(mcp_server.call_tool(
            "execute_read_query",
            {
                "source": "analytics_duckdb",
                "validated_sql": "SELECT product_id, product_name, list_price FROM products WHERE list_price > 2000"
            }
        ))
        assert not res.is_error
        combined_text = " ".join(c.text for c in res.content)
        assert "columns" in combined_text
        assert "rows" in combined_text
        assert "Enterprise Cloud Suite" in combined_text

    def test_tool_execute_read_query_guardrail_rejection(self, mcp_server):
        with pytest.raises(Exception):
            asyncio.run(mcp_server.call_tool(
                "execute_read_query",
                {
                    "source": "analytics_duckdb",
                    "validated_sql": "DELETE FROM products WHERE product_id = 301"
                }
            ))


# ------------------------------------------------------------------------------
# 5. Live Database Adapter Tests (PostgreSQL & SQL Server)
# ------------------------------------------------------------------------------

class TestLiveDatabaseAdapters:
    """Tests live database metadata and queries when service daemons are running."""

    def test_postgres_adapter_live(self):
        if not is_service_listening(config.postgres.host, config.postgres.port):
            pytest.skip(f"PostgreSQL not listening on {config.postgres.host}:{config.postgres.port}")

        from src.mcp_server.adapters.postgres import PostgresAdapter
        adapter = PostgresAdapter()
        tables = adapter.list_tables()
        assert "orders" in tables
        assert "order_items" in tables

        schema = adapter.describe_table("orders")
        assert schema.table_name == "orders"
        assert any(c.name == "order_id" and c.is_primary_key for c in schema.columns)

        rels = adapter.get_relationships()
        assert len(rels) > 0

        res = adapter.execute_read_query("SELECT COUNT(*) AS count FROM orders")
        assert res.rows[0][0] == 50

    def test_sqlserver_adapter_live(self):
        if not is_service_listening(config.sqlserver.host, config.sqlserver.port):
            pytest.skip(f"SQL Server not listening on {config.sqlserver.host}:{config.sqlserver.port}")

        from src.mcp_server.adapters.sqlserver import SQLServerAdapter
        adapter = SQLServerAdapter()
        tables = adapter.list_tables()
        assert "complaints" in [t.lower() for t in tables]
        assert "customers" in [t.lower() for t in tables]

        schema = adapter.describe_table("customers")
        assert any(c.name == "customer_id" and c.is_primary_key for c in schema.columns)

        rels = adapter.get_relationships()
        assert len(rels) > 0

        res = adapter.execute_read_query("SELECT COUNT(*) AS count FROM dbo.complaints")
        assert res.rows[0][0] == 60
