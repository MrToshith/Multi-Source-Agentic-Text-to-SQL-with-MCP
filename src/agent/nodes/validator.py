"""
SQL Safety Validator Node (Deterministic Service).
Parses generated SQL into an AST via sqlglot, blocks mutations, and enforces row limits before MCP execution.
"""

from typing import Any, Dict
from src.agent.state import AgentState
from src.mcp_server.guardrails import validate_read_only_sql, apply_query_limit


SOURCE_DIALECT_MAP = {
    "sales_pg": "postgres",
    "crm_mssql": "tsql",
    "analytics_duckdb": "duckdb",
}


def sql_safety_validator_node(state: AgentState) -> Dict[str, Any]:
    """
    Validates each generated SQL statement using SQLGlot AST parsing.
    Populates validation_errors if any non-SELECT or malformed query is found.
    """
    generated_sql = dict(state.get("generated_sql") or {})
    validation_errors: Dict[str, str] = {}
    validated_sql: Dict[str, str] = {}

    for source, sql in generated_sql.items():
        dialect = SOURCE_DIALECT_MAP.get(source, "postgres")
        is_valid, err_msg = validate_read_only_sql(sql, dialect=dialect)
        if not is_valid:
            validation_errors[source] = err_msg
            validated_sql[source] = sql
        else:
            validated_sql[source] = apply_query_limit(sql, max_rows=200, dialect=dialect)

    status = "validation_failed" if validation_errors else "sql_validated"
    return {
        "generated_sql": validated_sql,
        "validation_errors": validation_errors,
        "execution_status": status,
    }
