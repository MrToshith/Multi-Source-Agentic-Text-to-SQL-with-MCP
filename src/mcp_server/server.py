"""
Custom Multi-Source Model Context Protocol (MCP) Server.
Initialized using the official Python MCP SDK (mcp 2.2.0).
Exposes a compact, strictly read-only 6-tool interface with dynamic source routing.
"""

from typing import Any, Dict, List, Optional
from mcp.server.mcpserver import MCPServer

from src.config import config
from src.mcp_server.guardrails import validate_read_only_sql, SQLSecurityError
from src.mcp_server.router import SourceRouter


def create_mcp_server(router: Optional[SourceRouter] = None) -> MCPServer:
    """
    Factory creating and configuring the custom multi-source MCP server.
    Registers all 6 read-only tools and attaches them to the provided router.
    """
    source_router = router or SourceRouter()
    server = MCPServer("multi-source-sql-server")

    # --------------------------------------------------------------------------
    # Tool 1: list_data_sources
    # --------------------------------------------------------------------------
    @server.tool()
    def list_data_sources() -> List[Dict[str, Any]]:
        """
        List all available enterprise data sources with their identifiers, types, and descriptions.
        """
        sources = source_router.list_data_sources()
        return [s.model_dump() for s in sources]

    # --------------------------------------------------------------------------
    # Tool 2: list_tables
    # --------------------------------------------------------------------------
    @server.tool()
    def list_tables(source: str) -> List[str]:
        """
        List all accessible tables available within the specified data source.
        Args:
            source: The target data source ('sales_pg', 'crm_mssql', 'analytics_duckdb').
        """
        adapter = source_router.get_adapter(source)
        return adapter.list_tables()

    # --------------------------------------------------------------------------
    # Tool 3: describe_table
    # --------------------------------------------------------------------------
    @server.tool()
    def describe_table(source: str, table: str) -> Dict[str, Any]:
        """
        Retrieve column definitions, data types, nullability, and primary keys for a specific table.
        Args:
            source: The target data source ('sales_pg', 'crm_mssql', 'analytics_duckdb').
            table: The table name to inspect.
        """
        adapter = source_router.get_adapter(source)
        schema = adapter.describe_table(table)
        return schema.model_dump()

    # --------------------------------------------------------------------------
    # Tool 4: get_relationships
    # --------------------------------------------------------------------------
    @server.tool()
    def get_relationships(source: str) -> List[Dict[str, Any]]:
        """
        Retrieve relational constraints, foreign keys, and logical cross-source connections for a data source.
        Args:
            source: The target data source ('sales_pg', 'crm_mssql', 'analytics_duckdb').
        """
        adapter = source_router.get_adapter(source)
        relationships = adapter.get_relationships()
        return [r.model_dump() for r in relationships]

    # --------------------------------------------------------------------------
    # Tool 5: get_sample_rows
    # --------------------------------------------------------------------------
    @server.tool()
    def get_sample_rows(source: str, table: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Fetch representative sample rows from a table to provide value formatting context.
        Args:
            source: The target data source ('sales_pg', 'crm_mssql', 'analytics_duckdb').
            table: The table name to sample.
            limit: Maximum number of rows to return (default: 3).
        """
        adapter = source_router.get_adapter(source)
        return adapter.get_sample_rows(table, limit=limit)

    # --------------------------------------------------------------------------
    # Tool 6: execute_read_query
    # --------------------------------------------------------------------------
    @server.tool()
    def execute_read_query(source: str, validated_sql: str) -> Dict[str, Any]:
        """
        Safely execute a read-only SQL query against the specified data source and return tabular results.
        Enforces server-side AST guardrails, query timeout, and max row bounds.
        Args:
            source: The target data source ('sales_pg', 'crm_mssql', 'analytics_duckdb').
            validated_sql: The SELECT SQL query to execute.
        """
        adapter = source_router.get_adapter(source)

        # Server-side safety guardrail check
        is_valid, error_msg = validate_read_only_sql(validated_sql, dialect=adapter.dialect)
        if not is_valid:
            raise SQLSecurityError(f"Server Guardrail Rejected Query: {error_msg}")

        result = adapter.execute_read_query(
            sql=validated_sql,
            limit=config.mcp.max_result_rows,
            timeout_seconds=config.mcp.query_timeout_seconds,
        )
        return result.model_dump()

    return server


# Default server instance for application runtime
mcp_server = create_mcp_server()


def main():
    """CLI entrypoint to run the MCP server using standard IO transport."""
    import anyio
    mcp_server.run()


if __name__ == "__main__":
    main()
