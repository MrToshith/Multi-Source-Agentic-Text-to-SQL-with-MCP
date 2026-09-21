"""
Source router for the custom multi-source MCP server.
Dispatches tool invocations to the appropriate database source adapter.
"""

from typing import Dict, List, Optional
from src.mcp_server.adapters.base import BaseSourceAdapter
from src.mcp_server.adapters.duckdb_file import DuckDBFileAdapter
from src.mcp_server.adapters.postgres import PostgresAdapter
from src.mcp_server.adapters.sqlserver import SQLServerAdapter
from src.mcp_server.schemas import DataSourceInfo


class SourceRouter:
    """Central router directing MCP tool requests to backend database adapters."""

    def __init__(
        self,
        postgres_adapter: Optional[BaseSourceAdapter] = None,
        sqlserver_adapter: Optional[BaseSourceAdapter] = None,
        duckdb_adapter: Optional[BaseSourceAdapter] = None,
    ):
        self._adapters: Dict[str, BaseSourceAdapter] = {
            "sales_pg": postgres_adapter or PostgresAdapter(),
            "crm_mssql": sqlserver_adapter or SQLServerAdapter(),
            "analytics_duckdb": duckdb_adapter or DuckDBFileAdapter(),
        }

        self._metadata: Dict[str, DataSourceInfo] = {
            "sales_pg": DataSourceInfo(
                id="sales_pg",
                name="PostgreSQL Sales Database",
                type="postgresql",
                description="Transactional orders, line items, sales reps, and geographic sales regions"
            ),
            "crm_mssql": DataSourceInfo(
                id="crm_mssql",
                name="SQL Server CRM Database",
                type="sqlserver",
                description="CRM customer accounts, subscription tiers, and customer complaints/support tickets"
            ),
            "analytics_duckdb": DataSourceInfo(
                id="analytics_duckdb",
                name="DuckDB Analytics File Store",
                type="duckdb",
                description="Product master catalog and warehouse inventory levels stored as analytical CSV files"
            ),
        }

    def list_data_sources(self) -> List[DataSourceInfo]:
        """Returns metadata for all registered data sources."""
        return list(self._metadata.values())

    def get_adapter(self, source: str) -> BaseSourceAdapter:
        """
        Resolves the source identifier to its registered adapter.
        Raises ValueError if source is invalid.
        """
        clean_source = source.lower().strip()
        if clean_source not in self._adapters:
            available = list(self._adapters.keys())
            raise ValueError(
                f"Unknown data source '{source}'. Available data sources: {available}"
            )
        return self._adapters[clean_source]

    def register_adapter(self, source_id: str, adapter: BaseSourceAdapter, info: Optional[DataSourceInfo] = None) -> None:
        """Allows registering or replacing an adapter (e.g. for testing)."""
        self._adapters[source_id.lower().strip()] = adapter
        if info:
            self._metadata[source_id.lower().strip()] = info
