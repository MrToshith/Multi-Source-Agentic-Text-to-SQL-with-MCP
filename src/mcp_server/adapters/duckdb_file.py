"""
DuckDB local analytical file adapter for CSV / Parquet data sources.
Exposes 'products' and 'inventory' tables stored in data/files/.
"""

import os
import time
from typing import Any
import duckdb

from src.config import config
from src.mcp_server.adapters.base import BaseSourceAdapter
from src.mcp_server.schemas import TableSchema, ColumnInfo, RelationshipInfo, QueryResult
from src.mcp_server.guardrails import apply_query_limit


class DuckDBFileAdapter(BaseSourceAdapter):
    """Adapter for querying local analytical file stores via DuckDB."""

    def __init__(self, data_files_dir: str = None):
        self._data_files_dir = data_files_dir or config.duckdb.data_files_dir
        self._con = duckdb.connect(database=":memory:")
        self._initialize_views()

    @property
    def source_id(self) -> str:
        return "analytics_duckdb"

    @property
    def dialect(self) -> str:
        return "duckdb"

    def _initialize_views(self) -> None:
        """Mounts CSV files in data_files_dir as DuckDB views."""
        products_csv = os.path.join(self._data_files_dir, "products.csv").replace("\\", "/")
        inventory_csv = os.path.join(self._data_files_dir, "inventory.csv").replace("\\", "/")

        if os.path.exists(products_csv):
            self._con.execute(f"CREATE OR REPLACE VIEW products AS SELECT * FROM read_csv_auto('{products_csv}')")

        if os.path.exists(inventory_csv):
            self._con.execute(f"CREATE OR REPLACE VIEW inventory AS SELECT * FROM read_csv_auto('{inventory_csv}')")

    def list_tables(self) -> list[str]:
        tables = []
        res = self._con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall()
        for r in res:
            tables.append(r[0])
        return sorted(tables)

    def describe_table(self, table_name: str) -> TableSchema:
        clean_name = table_name.lower().strip()
        tables = self.list_tables()
        if clean_name not in tables:
            raise ValueError(f"Table '{table_name}' does not exist in source '{self.source_id}'. Available tables: {tables}")

        desc_res = self._con.execute(f"DESCRIBE {clean_name}").fetchall()
        # DESCRIBE returns: (column_name, column_type, null, key, default, extra)
        columns = []
        for row in desc_res:
            col_name = str(row[0])
            col_type = str(row[1])
            nullable = str(row[2]).upper() == "YES" if len(row) > 2 else True
            is_pk = (col_name == "product_id")
            columns.append(ColumnInfo(
                name=col_name,
                data_type=col_type,
                nullable=nullable,
                is_primary_key=is_pk
            ))

        count_res = self._con.execute(f"SELECT COUNT(*) FROM {clean_name}").fetchone()
        row_count = count_res[0] if count_res else None

        return TableSchema(
            table_name=clean_name,
            columns=columns,
            row_count_estimate=row_count
        )

    def get_relationships(self) -> list[RelationshipInfo]:
        return [
            RelationshipInfo(
                source_table="inventory",
                source_column="product_id",
                target_table="products",
                target_column="product_id",
                relationship_type="foreign_key",
                description="Inventory records map to the master products catalog via product_id"
            )
        ]

    def get_sample_rows(self, table_name: str, limit: int = 3) -> list[dict[str, Any]]:
        clean_name = table_name.lower().strip()
        tables = self.list_tables()
        if clean_name not in tables:
            raise ValueError(f"Table '{table_name}' does not exist in source '{self.source_id}'. Available tables: {tables}")

        df = self._con.execute(f"SELECT * FROM {clean_name} LIMIT {max(1, limit)}").df()
        return df.to_dict(orient="records")

    def execute_read_query(
        self,
        sql: str,
        limit: int = 200,
        timeout_seconds: int = 5
    ) -> QueryResult:
        # Ensure query is bounded by limit
        bounded_sql = apply_query_limit(sql, max_rows=limit, dialect=self.dialect)

        start_time = time.perf_counter()
        cursor = self._con.cursor()
        res = cursor.execute(bounded_sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = [list(r) for r in res.fetchall()]
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=(len(rows) >= limit),
            execution_time_ms=duration_ms
        )
