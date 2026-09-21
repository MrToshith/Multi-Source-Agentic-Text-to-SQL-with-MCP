"""
Phase 1: Connectivity and Permission Verification Suite.
Tests connectivity across PostgreSQL, SQL Server, and DuckDB analytical file store,
and verifies strict read-only permission enforcement.
"""

import os
import pytest
from src.config import config


class TestDuckDBFileStore:
    """Tests for DuckDB local analytical storage (CSV / Parquet files)."""

    def test_duckdb_can_query_inventory_csv(self):
        import duckdb
        csv_path = os.path.join(config.duckdb.data_files_dir, "inventory.csv")
        assert os.path.exists(csv_path), f"File not found: {csv_path}"

        con = duckdb.connect(config.duckdb.database_path)
        df = con.execute(f"SELECT * FROM read_csv_auto('{csv_path}')").df()
        assert len(df) == 10
        assert "product_id" in df.columns
        assert "stock_level" in df.columns

    def test_duckdb_can_query_products_csv(self):
        import duckdb
        csv_path = os.path.join(config.duckdb.data_files_dir, "products.csv")
        assert os.path.exists(csv_path), f"File not found: {csv_path}"

        con = duckdb.connect(config.duckdb.database_path)
        df = con.execute(f"SELECT * FROM read_csv_auto('{csv_path}')").df()
        assert len(df) == 10
        assert "product_name" in df.columns
        assert "list_price" in df.columns

    def test_duckdb_in_memory_join(self):
        import duckdb
        inv_path = os.path.join(config.duckdb.data_files_dir, "inventory.csv")
        prod_path = os.path.join(config.duckdb.data_files_dir, "products.csv")

        con = duckdb.connect(config.duckdb.database_path)
        query = f"""
            SELECT p.product_name, p.category, i.warehouse_location, i.stock_level
            FROM read_csv_auto('{prod_path}') p
            JOIN read_csv_auto('{inv_path}') i ON p.product_id = i.product_id
            WHERE i.stock_level < 300
        """
        df = con.execute(query).df()
        assert len(df) > 0
        assert "warehouse_location" in df.columns


class TestPostgresStore:
    """Tests for PostgreSQL database connectivity and read-only enforcement."""

    @pytest.mark.skipif(
        os.getenv("RUN_LIVE_DB_TESTS", "0") != "1",
        reason="Live database tests disabled by default. Set RUN_LIVE_DB_TESTS=1 to run against active DB instance."
    )
    def test_postgres_connection_and_read(self):
        import psycopg2
        conn = psycopg2.connect(
            host=config.postgres.host,
            port=config.postgres.port,
            dbname=config.postgres.database,
            user=config.postgres.user,
            password=config.postgres.password
        )
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM orders;")
        count = cur.fetchone()[0]
        assert count > 0
        conn.close()

    @pytest.mark.skipif(
        os.getenv("RUN_LIVE_DB_TESTS", "0") != "1",
        reason="Live database tests disabled by default. Set RUN_LIVE_DB_TESTS=1 to run against active DB instance."
    )
    def test_postgres_readonly_enforcement(self):
        import psycopg2
        conn = psycopg2.connect(
            host=config.postgres.host,
            port=config.postgres.port,
            dbname=config.postgres.database,
            user=config.postgres.user,
            password=config.postgres.password
        )
        cur = conn.cursor()
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute("INSERT INTO regions (region_id, region_name, headquarters) VALUES (999, 'Test', 'Test');")
        conn.close()


class TestSQLServerStore:
    """Tests for SQL Server database connectivity and read-only enforcement."""

    @pytest.mark.skipif(
        os.getenv("RUN_LIVE_DB_TESTS", "0") != "1",
        reason="Live database tests disabled by default. Set RUN_LIVE_DB_TESTS=1 to run against active DB instance."
    )
    def test_sqlserver_connection_and_read(self):
        import pyodbc
        conn = pyodbc.connect(config.sqlserver.odbc_connection_string)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM dbo.complaints;")
        count = cur.fetchone()[0]
        assert count > 0
        conn.close()

    @pytest.mark.skipif(
        os.getenv("RUN_LIVE_DB_TESTS", "0") != "1",
        reason="Live database tests disabled by default. Set RUN_LIVE_DB_TESTS=1 to run against active DB instance."
    )
    def test_sqlserver_readonly_enforcement(self):
        import pyodbc
        conn = pyodbc.connect(config.sqlserver.odbc_connection_string)
        cur = conn.cursor()
        with pytest.raises(pyodbc.ProgrammingError):
            cur.execute("INSERT INTO dbo.customers (customer_id, customer_name, company_name, region_id, tier, signup_date, account_status) VALUES (999, 'Test', 'Test', 1, 'STANDARD', '2026-01-01', 'ACTIVE');")
        conn.close()
