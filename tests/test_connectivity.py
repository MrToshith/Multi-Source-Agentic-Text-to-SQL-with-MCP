"""
Phase 1: Connectivity, Permission, and Cross-Source Relational Verification Suite.
Tests connectivity across PostgreSQL, SQL Server, and DuckDB analytical file store,
validates cross-source logical foreign keys, and verifies strict read-only permissions.
"""

import os
import re
import socket
import pytest
import duckdb
from src.config import config


def is_service_listening(host: str, port: int, timeout: float = 0.5) -> bool:
    """Helper to detect if a database port is open and listening."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        res = sock.connect_ex((host, port))
        return res == 0
    except OSError:
        return False
    finally:
        sock.close()


# ------------------------------------------------------------------------------
# Module-level fixtures for parsed datasets and cross-source keys
# ------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def products_data():
    csv_path = os.path.join(config.duckdb.data_files_dir, "products.csv")
    con = duckdb.connect()
    df = con.execute("SELECT * FROM read_csv_auto(?)", [csv_path]).df()
    return df


@pytest.fixture(scope="module")
def inventory_data():
    csv_path = os.path.join(config.duckdb.data_files_dir, "inventory.csv")
    con = duckdb.connect()
    df = con.execute("SELECT * FROM read_csv_auto(?)", [csv_path]).df()
    return df


@pytest.fixture(scope="module")
def postgres_seed_parsed():
    seed_path = os.path.join("data", "postgres", "seed.sql")
    with open(seed_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract orders: (order_id, customer_id, rep_id, region_id, ...)
    orders = re.findall(
        r"\((\d{4}),\s*(\d+),\s*(\d+),\s*(\d+),\s*'(\d{4}-\d{2}-\d{2})',\s*'([^']+)',\s*([\d\.]+),\s*'([^']+)'\)",
        content
    )
    # Extract order_items: (item_id, order_id, product_id, quantity, unit_price, subtotal)
    items = re.findall(
        r"\((\d+),\s*(\d{4}),\s*(\d+),\s*(\d+),\s*([\d\.]+),\s*([\d\.]+)\)",
        content
    )
    return {"orders": orders, "items": items}


@pytest.fixture(scope="module")
def sqlserver_seed_parsed():
    seed_path = os.path.join("data", "sqlserver", "seed.sql")
    with open(seed_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract customers: (customer_id, customer_name, company_name, region_id, tier, signup_date, account_status)
    customers = re.findall(
        r"\((\d{3}),\s*'([^']+)',\s*'([^']+)',\s*(\d+),\s*'([^']+)',\s*'(\d{4}-\d{2}-\d{2})',\s*'([^']+)'\)",
        content
    )
    # Extract complaints: (complaint_id, customer_id, complaint_date, quarter, category, severity, status, ...)
    complaints = re.findall(
        r"\((\d{4}),\s*(\d+),\s*'(\d{4}-\d{2}-\d{2})',\s*'([^']+)',\s*'([^']+)',\s*'([^']+)',\s*'([^']+)'",
        content
    )
    return {"customers": customers, "complaints": complaints}


# ------------------------------------------------------------------------------
# 1. DuckDB Analytical File Store Tests
# ------------------------------------------------------------------------------

class TestDuckDBAnalyticalFiles:
    """Tests for DuckDB analytical storage querying products.csv and inventory.csv."""

    def test_duckdb_can_query_inventory_csv(self):
        csv_path = os.path.join(config.duckdb.data_files_dir, "inventory.csv")
        assert os.path.exists(csv_path), f"File not found: {csv_path}"

        con = duckdb.connect(config.duckdb.database_path)
        df = con.execute("SELECT * FROM read_csv_auto(?)", [csv_path]).df()
        assert len(df) == 10
        expected_cols = {"product_id", "warehouse_id", "warehouse_location", "stock_level", "reorder_point", "safety_stock"}
        assert expected_cols.issubset(set(df.columns))
        assert df["product_id"].dtype in ("int64", "int32")

    def test_duckdb_can_query_products_csv(self):
        csv_path = os.path.join(config.duckdb.data_files_dir, "products.csv")
        assert os.path.exists(csv_path), f"File not found: {csv_path}"

        con = duckdb.connect(config.duckdb.database_path)
        df = con.execute("SELECT * FROM read_csv_auto(?)", [csv_path]).df()
        assert len(df) == 10
        expected_cols = {"product_id", "product_name", "category", "cost_price", "list_price", "is_active"}
        assert expected_cols.issubset(set(df.columns))
        assert df["product_id"].dtype in ("int64", "int32")

    def test_duckdb_csv_join(self):
        prod_path = os.path.join(config.duckdb.data_files_dir, "products.csv")
        inv_path = os.path.join(config.duckdb.data_files_dir, "inventory.csv")

        con = duckdb.connect(config.duckdb.database_path)
        query = """
            SELECT
                p.product_id,
                p.product_name,
                p.category,
                p.list_price,
                i.warehouse_location,
                i.stock_level
            FROM read_csv_auto(?) p
            JOIN read_csv_auto(?) i ON p.product_id = i.product_id
            WHERE i.stock_level < 300
        """
        df = con.execute(query, [prod_path, inv_path]).df()
        assert len(df) > 0
        assert "warehouse_location" in df.columns
        assert "product_name" in df.columns


# ------------------------------------------------------------------------------
# 2. Cross-Source Relational Verification
# ------------------------------------------------------------------------------

class TestCrossSourceKeys:
    """
    Validates logical cross-source relationships across heterogeneous stores:
    - inventory.csv -> products.csv (product_id)
    - PostgreSQL order_items -> products.csv (product_id)
    - PostgreSQL orders -> SQL Server customers (customer_id)
    - SQL Server customers -> PostgreSQL regions (region_id)
    - SQL Server complaints -> SQL Server customers (customer_id)
    """

    def test_inventory_and_products_cross_keys(self, inventory_data, products_data):
        inv_prod_ids = set(inventory_data["product_id"])
        prod_ids = set(products_data["product_id"])
        assert inv_prod_ids == prod_ids, "Inventory product IDs do not match products.csv IDs"

    def test_postgres_order_items_product_keys(self, postgres_seed_parsed, products_data):
        items = postgres_seed_parsed["items"]
        assert len(items) > 0
        referenced_product_ids = {int(item[2]) for item in items}
        valid_product_ids = set(products_data["product_id"])
        assert referenced_product_ids.issubset(valid_product_ids), (
            f"Postgres order_items reference invalid product IDs: {referenced_product_ids - valid_product_ids}"
        )

    def test_postgres_orders_customer_keys(self, postgres_seed_parsed, sqlserver_seed_parsed):
        orders = postgres_seed_parsed["orders"]
        customers = sqlserver_seed_parsed["customers"]
        assert len(orders) == 50, f"Expected 50 orders in seed, found {len(orders)}"
        assert len(customers) == 30, f"Expected 30 customers in seed, found {len(customers)}"

        order_customer_ids = {int(o[1]) for o in orders}
        valid_customer_ids = {int(c[0]) for c in customers}
        assert order_customer_ids.issubset(valid_customer_ids), (
            f"Postgres orders reference invalid customer IDs: {order_customer_ids - valid_customer_ids}"
        )

    def test_sqlserver_customers_region_keys(self, sqlserver_seed_parsed):
        customers = sqlserver_seed_parsed["customers"]
        assert len(customers) == 30
        valid_regions = {1, 2, 3, 4}  # 1=East, 2=West, 3=Europe, 4=APAC
        customer_region_ids = {int(c[3]) for c in customers}
        assert customer_region_ids.issubset(valid_regions), (
            f"SQL Server customers reference invalid region IDs: {customer_region_ids - valid_regions}"
        )

    def test_sqlserver_complaints_customer_keys(self, sqlserver_seed_parsed):
        complaints = sqlserver_seed_parsed["complaints"]
        customers = sqlserver_seed_parsed["customers"]
        assert len(complaints) == 60, f"Expected 60 complaints in seed, found {len(complaints)}"

        complaint_customer_ids = {int(c[1]) for c in complaints}
        valid_customer_ids = {int(c[0]) for c in customers}
        assert complaint_customer_ids.issubset(valid_customer_ids), (
            f"Complaints reference invalid customer IDs: {complaint_customer_ids - valid_customer_ids}"
        )


# ------------------------------------------------------------------------------
# 3. PostgreSQL Store: Connectivity & Read-Only Permission Enforcement
# ------------------------------------------------------------------------------

class TestPostgresStore:
    """Tests for PostgreSQL database connectivity and read-only enforcement."""

    @pytest.fixture(autouse=True)
    def check_postgres_availability(self):
        if not is_service_listening(config.postgres.host, config.postgres.port):
            pytest.skip(
                f"PostgreSQL service is not listening on {config.postgres.host}:{config.postgres.port}. "
                "Start the PostgreSQL service to run live database connectivity tests."
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
        assert count == 50
        conn.close()

    def test_postgres_readonly_enforcement_insert(self):
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
        conn.rollback()
        conn.close()

    def test_postgres_readonly_enforcement_update(self):
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
            cur.execute("UPDATE orders SET total_amount = 0 WHERE order_id = 1001;")
        conn.rollback()
        conn.close()

    def test_postgres_readonly_enforcement_delete(self):
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
            cur.execute("DELETE FROM orders WHERE order_id = 1001;")
        conn.rollback()
        conn.close()

    def test_postgres_readonly_enforcement_drop(self):
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
            cur.execute("DROP TABLE orders CASCADE;")
        conn.rollback()
        conn.close()

    def test_postgres_readonly_enforcement_alter(self):
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
            cur.execute("ALTER TABLE orders ADD COLUMN test_col INT;")
        conn.rollback()
        conn.close()


# ------------------------------------------------------------------------------
# 4. SQL Server Store: Connectivity & Read-Only Permission Enforcement
# ------------------------------------------------------------------------------

class TestSQLServerStore:
    """Tests for SQL Server database connectivity and read-only enforcement."""

    @pytest.fixture(autouse=True)
    def check_sqlserver_availability(self):
        if not is_service_listening(config.sqlserver.host, config.sqlserver.port):
            pytest.skip(
                f"SQL Server service is not listening on {config.sqlserver.host}:{config.sqlserver.port}. "
                "Start the SQL Server service to run live database connectivity tests."
            )

    def test_sqlserver_connection_and_read(self):
        import pyodbc
        conn = pyodbc.connect(config.sqlserver.odbc_connection_string)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM dbo.complaints;")
        count = cur.fetchone()[0]
        assert count == 60

        cur.execute("SELECT COUNT(*) FROM dbo.customers;")
        cust_count = cur.fetchone()[0]
        assert cust_count == 30
        conn.close()

    def test_sqlserver_readonly_enforcement_insert(self):
        import pyodbc
        conn = pyodbc.connect(config.sqlserver.odbc_connection_string)
        cur = conn.cursor()
        with pytest.raises(pyodbc.Error):
            cur.execute("INSERT INTO dbo.customers (customer_id, customer_name, company_name, region_id, tier, signup_date, account_status) VALUES (999, 'T', 'T', 1, 'STANDARD', '2026-01-01', 'ACTIVE');")
        conn.rollback()
        conn.close()

    def test_sqlserver_readonly_enforcement_update(self):
        import pyodbc
        conn = pyodbc.connect(config.sqlserver.odbc_connection_string)
        cur = conn.cursor()
        with pytest.raises(pyodbc.Error):
            cur.execute("UPDATE dbo.customers SET customer_name = 'Changed' WHERE customer_id = 201;")
        conn.rollback()
        conn.close()

    def test_sqlserver_readonly_enforcement_delete(self):
        import pyodbc
        conn = pyodbc.connect(config.sqlserver.odbc_connection_string)
        cur = conn.cursor()
        with pytest.raises(pyodbc.Error):
            cur.execute("DELETE FROM dbo.customers WHERE customer_id = 201;")
        conn.rollback()
        conn.close()

    def test_sqlserver_readonly_enforcement_drop(self):
        import pyodbc
        conn = pyodbc.connect(config.sqlserver.odbc_connection_string)
        cur = conn.cursor()
        with pytest.raises(pyodbc.Error):
            cur.execute("DROP TABLE dbo.complaints;")
        conn.rollback()
        conn.close()

    def test_sqlserver_readonly_enforcement_alter(self):
        import pyodbc
        conn = pyodbc.connect(config.sqlserver.odbc_connection_string)
        cur = conn.cursor()
        with pytest.raises(pyodbc.Error):
            cur.execute("ALTER TABLE dbo.customers ADD test_col INT;")
        conn.rollback()
        conn.close()


# ------------------------------------------------------------------------------
# 5. Seed Script Permission & Configuration Declarations
# ------------------------------------------------------------------------------

class TestSeedPermissionDeclarations:
    """Verifies that seed SQL scripts properly configure read-only users and explicit restrictions."""

    def test_postgres_seed_permission_declarations(self):
        seed_path = os.path.join("data", "postgres", "seed.sql")
        with open(seed_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "CREATE ROLE readonly_pg_user" in content
        assert "GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_pg_user;" in content
        assert "REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM readonly_pg_user;" in content
        assert "REVOKE CREATE ON SCHEMA public FROM readonly_pg_user;" in content
        assert "REVOKE CREATE ON DATABASE sales_db FROM readonly_pg_user;" in content

    def test_sqlserver_seed_permission_declarations(self):
        seed_path = os.path.join("data", "sqlserver", "seed.sql")
        with open(seed_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "CREATE LOGIN readonly_mssql_user" in content
        assert "CREATE USER readonly_mssql_user" in content
        assert "ALTER ROLE db_datareader ADD MEMBER readonly_mssql_user;" in content
        assert "DENY INSERT, UPDATE, DELETE ON SCHEMA::dbo TO readonly_mssql_user;" in content
        assert "DENY ALTER ON SCHEMA::dbo TO readonly_mssql_user;" in content
        assert "DENY CONTROL ON SCHEMA::dbo TO readonly_mssql_user;" in content

