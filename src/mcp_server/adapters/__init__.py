"""
Database adapters for PostgreSQL, SQL Server, and DuckDB file storage.
"""

from src.mcp_server.adapters.base import BaseSourceAdapter
from src.mcp_server.adapters.duckdb_file import DuckDBFileAdapter
from src.mcp_server.adapters.postgres import PostgresAdapter
from src.mcp_server.adapters.sqlserver import SQLServerAdapter

__all__ = [
    "BaseSourceAdapter",
    "DuckDBFileAdapter",
    "PostgresAdapter",
    "SQLServerAdapter",
]
