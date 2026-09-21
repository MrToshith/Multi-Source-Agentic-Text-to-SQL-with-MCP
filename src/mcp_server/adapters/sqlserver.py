"""
SQL Server database adapter for the crm_db domain.
Connects with readonly_mssql_user and inspects INFORMATION_SCHEMA and sys.foreign_keys metadata.
"""

import time
from typing import Any, Optional
import pyodbc

from src.config import config
from src.mcp_server.adapters.base import BaseSourceAdapter
from src.mcp_server.schemas import TableSchema, ColumnInfo, RelationshipInfo, QueryResult
from src.mcp_server.guardrails import apply_query_limit


class SQLServerAdapter(BaseSourceAdapter):
    """Adapter for querying Microsoft SQL Server CRM and complaints domain."""

    def __init__(self, connection_string: Optional[str] = None):
        self.connection_string = connection_string or config.sqlserver.odbc_connection_string

    @property
    def source_id(self) -> str:
        return "crm_mssql"

    @property
    def dialect(self) -> str:
        return "tsql"

    def _get_connection(self):
        try:
            return pyodbc.connect(self.connection_string, timeout=3)
        except Exception as e:
            raise ConnectionError(
                f"Could not connect to SQL Server via ODBC: {e}"
            )

    def list_tables(self) -> list[str]:
        query = """
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = 'dbo'
            ORDER BY TABLE_NAME;
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                return [r[0] for r in cur.fetchall()]

    def describe_table(self, table_name: str) -> TableSchema:
        clean_table = table_name.lower().strip()
        tables = [t.lower() for t in self.list_tables()]
        if clean_table not in tables:
            raise ValueError(f"Table '{table_name}' does not exist in source '{self.source_id}'. Available tables: {tables}")

        col_query = """
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo' AND LOWER(TABLE_NAME) = ?
            ORDER BY ORDINAL_POSITION;
        """
        pk_query = """
            SELECT kcu.COLUMN_NAME
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
              ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
              AND tc.TABLE_SCHEMA = kcu.TABLE_SCHEMA
            WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
              AND tc.TABLE_SCHEMA = 'dbo'
              AND LOWER(tc.TABLE_NAME) = ?;
        """
        count_query = f"SELECT COUNT(*) FROM dbo.{clean_table};"

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(pk_query, (clean_table,))
                pk_cols = {r[0] for r in cur.fetchall()}

                cur.execute(col_query, (clean_table,))
                columns = [
                    ColumnInfo(
                        name=r[0],
                        data_type=r[1],
                        nullable=(r[2].upper() == "YES"),
                        is_primary_key=(r[0] in pk_cols)
                    )
                    for r in cur.fetchall()
                ]

                cur.execute(count_query)
                row_count = cur.fetchone()[0]

        return TableSchema(
            table_name=clean_table,
            columns=columns,
            row_count_estimate=row_count
        )

    def get_relationships(self) -> list[RelationshipInfo]:
        fk_query = """
            SELECT
                tp.name AS source_table,
                cp.name AS source_column,
                tr.name AS target_table,
                cr.name AS target_column
            FROM sys.foreign_keys fk
            INNER JOIN sys.tables tp ON fk.parent_object_id = tp.object_id
            INNER JOIN sys.tables tr ON fk.referenced_object_id = tr.object_id
            INNER JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
            INNER JOIN sys.columns cp ON fkc.parent_column_id = cp.column_id AND fkc.parent_object_id = cp.object_id
            INNER JOIN sys.columns cr ON fkc.referenced_column_id = cr.column_id AND fkc.referenced_object_id = cr.object_id
            ORDER BY tp.name;
        """
        relationships = []
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(fk_query)
                    for r in cur.fetchall():
                        relationships.append(RelationshipInfo(
                            source_table=r[0],
                            source_column=r[1],
                            target_table=r[2],
                            target_column=r[3],
                            relationship_type="foreign_key",
                            description=f"{r[0]}.{r[1]} references {r[2]}.{r[3]}"
                        ))
        except Exception:
            # Fallback to known schema metadata if database is unavailable
            relationships.append(
                RelationshipInfo(
                    source_table="complaints",
                    source_column="customer_id",
                    target_table="customers",
                    target_column="customer_id",
                    relationship_type="foreign_key",
                    description="complaints.customer_id references customers.customer_id"
                )
            )

        # Cross-source logical dimension
        relationships.append(
            RelationshipInfo(
                source_table="customers",
                source_column="region_id",
                target_table="sales_pg.regions",
                target_column="region_id",
                relationship_type="logical_cross_source",
                description="Logical business link between CRM customers and PostgreSQL sales regions"
            )
        )
        return relationships

    def get_sample_rows(self, table_name: str, limit: int = 3) -> list[dict[str, Any]]:
        clean_table = table_name.lower().strip()
        tables = [t.lower() for t in self.list_tables()]
        if clean_table not in tables:
            raise ValueError(f"Table '{table_name}' does not exist in source '{self.source_id}'. Available tables: {tables}")

        query = f"SELECT TOP {max(1, limit)} * FROM dbo.{clean_table};"
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                columns = [column[0] for column in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]

    def execute_read_query(
        self,
        sql: str,
        limit: int = 200,
        timeout_seconds: int = 5
    ) -> QueryResult:
        bounded_sql = apply_query_limit(sql, max_rows=limit, dialect=self.dialect)

        start_time = time.perf_counter()
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.timeout = timeout_seconds
                cur.execute(bounded_sql)
                columns = [desc[0] for desc in cur.description] if cur.description else []
                rows = [list(r) for r in cur.fetchall()]
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=(len(rows) >= limit),
            execution_time_ms=duration_ms
        )
