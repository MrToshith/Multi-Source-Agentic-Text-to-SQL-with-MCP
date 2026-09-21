"""
Pydantic schemas and dataclasses for MCP server tool inputs, outputs, and metadata.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class DataSourceInfo(BaseModel):
    """Metadata describing a registered data source."""
    id: str = Field(..., description="Unique source identifier (e.g., 'sales_pg', 'crm_mssql', 'analytics_duckdb')")
    name: str = Field(..., description="Human-readable display name")
    type: str = Field(..., description="Underlying technology: 'postgresql', 'sqlserver', or 'duckdb'")
    description: str = Field(..., description="Business domain and purpose of this data source")


class ColumnInfo(BaseModel):
    """Metadata describing an individual table column."""
    name: str = Field(..., description="Column name")
    data_type: str = Field(..., description="SQL data type (e.g., INT, VARCHAR(100), NUMERIC(12,2))")
    nullable: bool = Field(default=True, description="Whether NULL values are permitted")
    is_primary_key: bool = Field(default=False, description="Whether this column is part of the primary key")


class TableSchema(BaseModel):
    """Full schema definition for a table."""
    table_name: str = Field(..., description="Name of the table")
    columns: list[ColumnInfo] = Field(..., description="List of columns and their definitions")
    row_count_estimate: Optional[int] = Field(default=None, description="Estimated or exact row count")


class RelationshipInfo(BaseModel):
    """Metadata describing relational links between tables."""
    source_table: str = Field(..., description="Origin table containing foreign key or cross-link")
    source_column: str = Field(..., description="Origin column")
    target_table: str = Field(..., description="Referenced target table")
    target_column: str = Field(..., description="Referenced target column")
    relationship_type: str = Field(default="foreign_key", description="Relationship classification: 'foreign_key' or 'logical_cross_source'")
    description: Optional[str] = Field(default=None, description="Additional context regarding the relationship")


class QueryResult(BaseModel):
    """Tabular query execution result returned to the agent."""
    columns: list[str] = Field(..., description="Column headers in result order")
    rows: list[list[Any]] = Field(..., description="List of rows, where each row is an ordered list of cell values")
    row_count: int = Field(..., description="Total rows included in this result batch")
    truncated: bool = Field(default=False, description="True if the result was capped by the max row limit")
    execution_time_ms: Optional[float] = Field(default=None, description="Server-side execution time in milliseconds")
