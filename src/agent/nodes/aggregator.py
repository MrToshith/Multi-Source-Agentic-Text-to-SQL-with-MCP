"""
Cross-Source Result Aggregator Node (Deterministic Service / Pandas).
Merges heterogeneous tabular datasets across PostgreSQL, SQL Server, and DuckDB in memory.
"""

from typing import Any, Dict, List
import pandas as pd

from src.agent.state import AgentState


def cross_source_aggregator_node(state: AgentState) -> Dict[str, Any]:
    """
    Converts per-source query execution results into Pandas DataFrames and
    joins them on shared logical business keys (e.g., region_id, customer_id, product_id).
    """
    execution_results = state.get("execution_results") or {}
    join_keys = state.get("join_keys") or ["region_id"]

    dataframes: List[pd.DataFrame] = []

    # Preserve deterministic order: sales_pg first (for region_name), then crm_mssql, then analytics_duckdb
    ordered_sources = [
        s for s in ("sales_pg", "crm_mssql", "analytics_duckdb") if s in execution_results
    ] + [s for s in execution_results if s not in ("sales_pg", "crm_mssql", "analytics_duckdb")]

    for source in ordered_sources:
        res = execution_results[source]
        columns = res.get("columns") or []
        rows = res.get("rows") or []
        if columns:
            df = pd.DataFrame(rows, columns=columns)
            dataframes.append(df)

    if not dataframes:
        return {
            "aggregated_data": [],
            "execution_status": "aggregated",
        }

    structured_intent = state.get("structured_intent") or {}
    join_how = "inner" if structured_intent.get("intent") == "cross_source_entity_lookup" else "outer"

    merged_df = dataframes[0]
    for next_df in dataframes[1:]:
        common_keys = [k for k in join_keys if k in merged_df.columns and k in next_df.columns]
        if not common_keys:
            common_keys = [col for col in merged_df.columns if col in next_df.columns]

        if common_keys:
            merged_df = pd.merge(
                merged_df,
                next_df,
                on=common_keys[0],
                how=join_how,
                suffixes=("", "_joined"),
            )
        else:
            merged_df = pd.concat([merged_df, next_df], axis=1)

    # Clean up NaN values for JSON serialization
    for col in merged_df.columns:
        if pd.api.types.is_numeric_dtype(merged_df[col]):
            merged_df[col] = merged_df[col].fillna(0)
        else:
            merged_df[col] = merged_df[col].fillna("")

    aggregated_records = merged_df.to_dict(orient="records")
    return {
        "aggregated_data": aggregated_records,
        "execution_status": "aggregated",
    }
