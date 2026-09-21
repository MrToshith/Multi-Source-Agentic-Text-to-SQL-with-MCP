"""
Abstract base class defining the standard interface for all database source adapters.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from src.mcp_server.schemas import TableSchema, RelationshipInfo, QueryResult


class BaseSourceAdapter(ABC):
    """Abstract interface that each database-specific adapter must implement."""

    @property
    @abstractmethod
    def source_id(self) -> str:
        """Unique source identifier (e.g., 'sales_pg', 'crm_mssql', 'analytics_duckdb')."""
        pass

    @property
    @abstractmethod
    def dialect(self) -> str:
        """SQL dialect name for sqlglot parsing (e.g., 'postgres', 'tsql', 'duckdb')."""
        pass

    @abstractmethod
    def list_tables(self) -> list[str]:
        """Returns the list of accessible table names within this data source."""
        pass

    @abstractmethod
    def describe_table(self, table_name: str) -> TableSchema:
        """Returns the schema description for a specific table."""
        pass

    @abstractmethod
    def get_relationships(self) -> list[RelationshipInfo]:
        """Returns foreign key constraints and logical linkages for this source."""
        pass

    @abstractmethod
    def get_sample_rows(self, table_name: str, limit: int = 3) -> list[dict[str, Any]]:
        """Returns top sample rows for a table to provide schema value context."""
        pass

    @abstractmethod
    def execute_read_query(
        self,
        sql: str,
        limit: int = 200,
        timeout_seconds: int = 5
    ) -> QueryResult:
        """Executes a validated read-only query and returns structured results."""
        pass
