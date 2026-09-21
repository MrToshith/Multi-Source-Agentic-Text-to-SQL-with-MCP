"""
Server-side safety guardrails for the MCP server.
Enforces read-only AST verification via sqlglot, prevents multi-statement injections,
and bounds result rows.
"""

from typing import Optional, Tuple
import sqlglot
from sqlglot import exp


class SQLSecurityError(Exception):
    """Raised when a query fails read-only or safety validation."""
    pass


class QueryTimeoutError(Exception):
    """Raised when query execution exceeds the configured timeout threshold."""
    pass


# Forbidden AST node types that indicate data or schema modification
FORBIDDEN_EXPRESSIONS = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Create,
    exp.Command,
    exp.Commit,
    exp.Rollback,
    exp.Set,
    exp.Merge,
    exp.Grant,
    exp.Revoke,
)


def validate_read_only_sql(sql: str, dialect: Optional[str] = None) -> Tuple[bool, str]:
    """
    Validates that a SQL string represents a safe, read-only SELECT or CTE query.

    Rules enforced:
    1. Query cannot be empty.
    2. Must contain exactly ONE statement (blocks chained injection like `SELECT 1; DROP TABLE`).
    3. Must be an instance of exp.Select or exp.Union, or contain an exp.Select without any forbidden nodes.
    4. Must not contain any mutation AST nodes (INSERT, UPDATE, DELETE, DROP, ALTER, etc.).

    Returns:
        (True, "") if valid, or (False, error_message) if invalid.
    """
    if not sql or not sql.strip():
        return False, "Query cannot be empty."

    clean_sql = sql.strip().rstrip(";")

    try:
        parsed = sqlglot.parse(clean_sql, read=dialect)
    except Exception as e:
        return False, f"SQL syntax parsing error: {e}"

    if not parsed or any(p is None for p in parsed):
        return False, "Failed to parse valid SQL syntax."

    if len(parsed) > 1:
        return False, "Multiple statements are not permitted. Only single read-only queries are allowed."

    expr = parsed[0]

    # Check for forbidden mutation AST nodes anywhere in the expression tree
    for node_type in FORBIDDEN_EXPRESSIONS:
        found = expr.find(node_type)
        if found is not None:
            return False, f"Forbidden statement type detected: '{node_type.__name__}'. Only read-only queries are allowed."

    # Verify that the query contains a SELECT operation
    is_select = isinstance(expr, (exp.Select, exp.Union)) or expr.find(exp.Select) is not None
    if not is_select:
        return False, f"Query root is '{type(expr).__name__}'. Only SELECT or CTE queries are permitted."

    return True, ""


def apply_query_limit(sql: str, max_rows: int = 200, dialect: str = "postgres") -> str:
    """
    Ensures that the query has an upper bound on returned rows.
    If no LIMIT / TOP is specified, adds LIMIT max_rows.
    If an existing limit exceeds max_rows, clamps it to max_rows.
    """
    clean_sql = sql.strip().rstrip(";")
    try:
        expr = sqlglot.parse_one(clean_sql, read=dialect)
        select = expr if isinstance(expr, exp.Select) else expr.find(exp.Select)
        if select:
            limit_arg = select.args.get("limit")
            if limit_arg is not None:
                try:
                    curr_limit = int(limit_arg.expression.this)
                    if curr_limit > max_rows:
                        select.set("limit", exp.Limit(expression=exp.Literal.number(max_rows)))
                except Exception:
                    select.set("limit", exp.Limit(expression=exp.Literal.number(max_rows)))
            else:
                select.set("limit", exp.Limit(expression=exp.Literal.number(max_rows)))
            return expr.sql(dialect=dialect)
        return clean_sql
    except Exception:
        # Fallback to appending LIMIT if AST rewrite fails
        if "limit" not in clean_sql.lower() and "top" not in clean_sql.lower():
            return f"{clean_sql} LIMIT {max_rows}"
        return clean_sql
