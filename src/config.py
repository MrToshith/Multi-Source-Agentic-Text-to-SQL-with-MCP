"""
Configuration management for Multi-Source Agentic Text-to-SQL with MCP.
Uses Pydantic Settings to load and validate environment variables.
"""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """Configuration settings for LLM reasoning and code generation."""
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    provider: str = Field(default="ollama", alias="LLM_PROVIDER")
    base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    model_name: str = Field(default="llama3.1:8b", alias="OLLAMA_MODEL")
    temperature: float = Field(default=0.0)


class PostgresSettings(BaseSettings):
    """Configuration settings for PostgreSQL Sales database (Read-Only)."""
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    host: str = Field(default="localhost", alias="POSTGRES_HOST")
    port: int = Field(default=5432, alias="POSTGRES_PORT")
    database: str = Field(default="sales_db", alias="POSTGRES_DB")
    user: str = Field(default="readonly_pg_user", alias="POSTGRES_USER")
    password: str = Field(default="readonly_password", alias="POSTGRES_PASSWORD")

    @property
    def connection_uri(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class SQLServerSettings(BaseSettings):
    """Configuration settings for SQL Server CRM database (Read-Only)."""
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    host: str = Field(default="localhost", alias="SQLSERVER_HOST")
    port: int = Field(default=1433, alias="SQLSERVER_PORT")
    database: str = Field(default="crm_db", alias="SQLSERVER_DB")
    user: str = Field(default="readonly_mssql_user", alias="SQLSERVER_USER")
    password: str = Field(default="readonly_password", alias="SQLSERVER_PASSWORD")
    driver: str = Field(default="ODBC Driver 18 for SQL Server", alias="SQLSERVER_DRIVER")

    @property
    def odbc_connection_string(self) -> str:
        return (
            f"DRIVER={{{self.driver}}};"
            f"SERVER={self.host},{self.port};"
            f"DATABASE={self.database};"
            f"UID={self.user};"
            f"PWD={self.password};"
            f"TrustServerCertificate=yes;"
        )


class DuckDBSettings(BaseSettings):
    """Configuration settings for DuckDB file and analytical storage."""
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    database_path: str = Field(default=":memory:", alias="DUCKDB_DATABASE_PATH")
    data_files_dir: str = Field(default="data/files", alias="DATA_FILES_DIR")


class MCPServerSettings(BaseSettings):
    """Configuration settings for the custom Multi-Source MCP server."""
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    host: str = Field(default="localhost", alias="MCP_SERVER_HOST")
    port: int = Field(default=8001, alias="MCP_SERVER_PORT")
    query_timeout_seconds: int = Field(default=5, alias="MCP_QUERY_TIMEOUT_SECONDS")
    max_result_rows: int = Field(default=200, alias="MCP_MAX_RESULT_ROWS")


class APIGatewaySettings(BaseSettings):
    """Configuration settings for the FastAPI Gateway."""
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    host: str = Field(default="0.0.0.0", alias="API_HOST")
    port: int = Field(default=8000, alias="API_PORT")


class AppConfig(BaseSettings):
    """Master application settings aggregating all sub-configurations."""
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm: LLMSettings = Field(default_factory=LLMSettings)
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    sqlserver: SQLServerSettings = Field(default_factory=SQLServerSettings)
    duckdb: DuckDBSettings = Field(default_factory=DuckDBSettings)
    mcp: MCPServerSettings = Field(default_factory=MCPServerSettings)
    api: APIGatewaySettings = Field(default_factory=APIGatewaySettings)


config = AppConfig()
