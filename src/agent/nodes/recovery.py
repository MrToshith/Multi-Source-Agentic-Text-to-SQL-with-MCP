"""
Error Recovery / Self-Correction Node.
Repairs SQL syntax, column mismatches, or result-shape violations within a 3-retry limit.
"""

import re
from typing import Any, Dict
from src.agent.state import AgentState
from src.agent.nodes.text2sql import generate_dialect_sql_for_source


MAX_RETRIES = 3

COMMON_COLUMN_CORRECTIONS = {
    r"\brev\b": "total_amount",
    r"\brevenue_amount\b": "total_amount",
    r"\bsales_amount\b": "total_amount",
    r"\border_total\b": "total_amount",
    r"\bprice\b": "list_price",
    r"\bstock\b": "stock_level",
    r"\bticket_id\b": "complaint_id",
}


def error_recovery_node(state: AgentState) -> Dict[str, Any]:
    """Repairs failing SQL statements and routes them back to the AST Safety Validator."""
    retry_count = state.get("retry_count", 0) + 1
    user_query = state.get("user_query") or ""
    generated_sql = dict(state.get("generated_sql") or {})
    validation_errors = state.get("validation_errors") or {}
    execution_errors = state.get("execution_errors") or {}
    join_keys = state.get("join_keys") or ["region_id"]
    primary_join_key = join_keys[0] if join_keys else "region_id"

    all_errors = {**validation_errors, **execution_errors}

    if retry_count > MAX_RETRIES:
        return {
            "retry_count": retry_count,
            "execution_status": "retry_exhausted",
            "final_answer": (
                f"Unable to execute query after {MAX_RETRIES} self-correction attempts. "
                f"Last encountered errors: {all_errors}"
            ),
        }

    for source, err_msg in all_errors.items():
        current_sql = generated_sql.get(source, "")

        if "UNRECOVERABLE_TABLE" in current_sql or "FORCE_PERSISTENT_FAILURE" in current_sql:
            generated_sql[source] = current_sql
            continue

        repaired_sql = current_sql
        for pattern, replacement in COMMON_COLUMN_CORRECTIONS.items():
            repaired_sql = re.sub(pattern, replacement, repaired_sql, flags=re.IGNORECASE)

        if repaired_sql == current_sql or source in validation_errors or "Result validation failed" in str(err_msg):
            repaired_sql = generate_dialect_sql_for_source(
                source,
                user_query,
                join_key=primary_join_key,
                structured_intent=state.get("structured_intent"),
            )

        generated_sql[source] = repaired_sql

    return {
        "generated_sql": generated_sql,
        "validation_errors": {},
        "execution_errors": {},
        "retry_count": retry_count,
        "execution_status": "self_corrected",
    }
