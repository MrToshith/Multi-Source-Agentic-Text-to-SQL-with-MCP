"""
PostgreSQL database adapter for the sales_db domain.
Connects with readonly_pg_user and inspects information_schema metadata.
"""

import time
from typing import Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

from src.config import config
from src.mcp_server.adapters.base import BaseSourceAdapter
from src.mcp_server.schemas import TableSchema, ColumnInfo, RelationshipInfo, QueryResult
from src.mcp_server.guardrails import apply_query_limit


class PostgresAdapter(BaseSourceAdapter):
    """Adapter for querying PostgreSQL sales and transactions domain."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.host = host or config.postgres.host
        self.port = port or config.postgres.port
        self.database = database or config.postgres.database
        self.user = user or config.postgres.user
        self.password = password or config.postgres.password

    @property
    def source_id(self) -> str:
        return "sales_pg"

    @property
    def dialect(self) -> str:
        return "postgres"

    def _get_connection(self):
        try:
            return psycopg2.connect(
                host=self.host,
                port=self.port,
                dbname=self.database,
                user=self.user,
                password=self.password,
                connect_timeout=3,
            )
        except Exception as e:
            raise ConnectionError(
                f"Could not connect to PostgreSQL ({self.host}:{self.port}/{self.database}): {e}"
            )

    def list_tables(self) -> list[str]:
        query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                return [r[0] for r in cur.fetchall()]

    def describe_table(self, table_name: str) -> TableSchema:
        clean_table = table_name.lower().strip()
        tables = self.list_tables()
        if clean_table not in tables:
            raise ValueError(f"Table '{table_name}' does not exist in source '{self.source_id}'. Available tables: {tables}")

        col_query = """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position;
        """
        pk_query = """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = 'public'
              AND tc.table_name = %s;
        """
        count_query = "SELECT COUNT(*) FROM " + clean_table + ";"

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
                kcu1.table_name AS source_table,
                kcu1.column_name AS source_column,
                kcu2.table_name AS target_table,
                kcu2.column_name AS target_column
            FROM information_schema.referential_constraints rc
            JOIN information_schema.key_column_usage kcu1
                ON rc.constraint_name = kcu1.constraint_name
                AND rc.constraint_schema = kcu1.constraint_schema
            JOIN information_schema.key_column_usage kcu2
                ON rc.unique_constraint_name = kcu2.constraint_name
                AND rc.unique_constraint_schema = kcu2.constraint_schema
            WHERE rc.constraint_schema = 'public'
            ORDER BY kcu1.table_name;
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
            relationships.extend([
                RelationshipInfo(
                    source_table="sales_reps",
                    source_column="region_id",
                    target_table="regions",
                    target_column="region_id",
                    relationship_type="foreign_key",
                    description="sales_reps.region_id references regions.region_id"
                ),
                RelationshipInfo(
                    source_table="orders",
                    source_column="region_id",
                    target_table="regions",
                    target_column="region_id",
                    relationship_type="foreign_key",
                    description="orders.region_id references regions.region_id"
                ),
                RelationshipInfo(
                    source_table="orders",
                    source_column="rep_id",
                    target_table="sales_reps",
                    target_column="rep_id",
                    relationship_type="foreign_key",
                    description="orders.rep_id references sales_reps.rep_id"
                ),
                RelationshipInfo(
                    source_table="order_items",
                    source_column="order_id",
                    target_table="orders",
                    target_column="order_id",
                    relationship_type="foreign_key",
                    description="order_items.order_id references orders.order_id"
                ),
            ])

        # Cross-source logical dimensions
        relationships.extend([
            RelationshipInfo(
                source_table="orders",
                source_column="customer_id",
                target_table="crm_mssql.customers",
                target_column="customer_id",
                relationship_type="logical_cross_source",
                description="Logical business link between sales orders and CRM customer profiles"
            ),
            RelationshipInfo(
                source_table="order_items",
                source_column="product_id",
                target_table="analytics_duckdb.products",
                target_column="product_id",
                relationship_type="logical_cross_source",
                description="Logical business link between order items and the product master catalog"
            )
        ])
        return relationships

    def get_sample_rows(self, table_name: str, limit: int = 3) -> list[dict[str, Any]]:
        clean_table = table_name.lower().strip()
        tables = self.list_tables()
        if clean_table not in tables:
            raise ValueError(f"Table '{table_name}' does not exist in source '{self.source_id}'. Available tables: {tables}")

        query = f"SELECT * FROM {clean_table} LIMIT %s;"
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (max(1, limit),))
                return [dict(row) for row in cur.fetchall()]

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
                # Set PostgreSQL statement execution timeout in milliseconds
                cur.execute(f"SET statement_timeout = {int(timeout_seconds * 1000)};")
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
