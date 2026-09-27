"""
Prompt templates for the Error Recovery / Self-Correction node.
"""

RECOVERY_SYSTEM_PROMPT = """You are an autonomous SQL self-correction agent.
Given a failing SQL statement, the AST validation or runtime database error message, and the valid table schemas from MCP, rewrite the SQL statement into a valid, strictly read-only SELECT query that resolves the error.
Return JSON:
{
  "corrected_sql": {
    "<source_id>": "<repaired SELECT query>"
  }
}
"""


def format_recovery_prompt(
    user_query: str,
    failing_sql: dict,
    errors: dict,
    schema_context: dict,
    retry_count: int,
) -> str:
    return (
        f"Original User Query: {user_query}\n"
        f"Retry Attempt: {retry_count + 1} of 3\n"
        f"Failing SQL Statements: {failing_sql}\n"
        f"Observed Errors: {errors}\n"
        f"Valid Schema Context: {schema_context}\n"
        "Provide the repaired read-only SQL queries in JSON."
    )
