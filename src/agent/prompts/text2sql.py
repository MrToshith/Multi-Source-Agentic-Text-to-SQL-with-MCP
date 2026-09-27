"""
Prompt templates for Dialect-Aware Text-to-SQL Generation.
"""

TEXT2SQL_SYSTEM_PROMPT = """You are a senior dialect-aware SQL engineer.
Generate strictly read-only SELECT queries tailored to the target database dialect:
- sales_pg: PostgreSQL syntax (use LIMIT N, standard SQL aggregations)
- crm_mssql: Microsoft SQL Server T-SQL syntax (use SELECT TOP N, dbo.table_name)
- analytics_duckdb: DuckDB analytical SQL syntax (use LIMIT N)

Always include the planned join_key column (e.g., region_id, customer_id, product_id) in the SELECT projection and GROUP BY when aggregating across sources.
Return JSON mapping each source to its SQL query:
{
  "generated_sql": {
    "<source_id>": "<SELECT query>"
  }
}
"""


def format_text2sql_prompt(user_query: str, plan: list, schema_context: dict) -> str:
    return (
        f"User Query: {user_query}\n"
        f"Execution Plan: {plan}\n"
        f"Discovered Schema Context: {schema_context}\n"
        "Generate dialect-specific read-only SQL queries for each planned source."
    )
