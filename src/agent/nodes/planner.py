"""
Query Planner & Source Selector Node.
Converts the structured_intent into exact single-source or cross-source SubQueryTasks and join_keys.
Never forces regional grouping unless structured_intent explicitly specifies group_by=['region'].
"""

from typing import Any, Dict, List
from src.agent.state import AgentState, SubQueryTask
from src.agent.intent_resolver import resolve_query_intent
from src.mcp_client import default_mcp_client


def query_planner_node(state: AgentState, mcp_client=None) -> Dict[str, Any]:
    """
    Analyzes the user query and produces both a structured_intent and a multi-source execution plan.
    """
    client = mcp_client or default_mcp_client
    user_query = (state.get("user_query") or "").strip()

    structured_intent = state.get("structured_intent") or resolve_query_intent(user_query, client)
    intent_type = structured_intent.get("intent")
    primary_source = structured_intent.get("source")
    group_by = structured_intent.get("group_by")

    # 1. Cross-Source Entity Lookup (e.g., Highest-value order in PostgreSQL -> Customer & Company in SQL Server)
    if intent_type == "cross_source_entity_lookup":
        plan: List[SubQueryTask] = [
            SubQueryTask(
                sub_task_id="sub_sales_pg_top_order",
                source="sales_pg",
                description=f"Find top order and customer_id for: {user_query}",
                target_tables=["orders"],
                join_key="customer_id",
            ),
            SubQueryTask(
                sub_task_id="sub_crm_mssql_customer",
                source="crm_mssql",
                description=f"Lookup customer name and company by customer_id for: {user_query}",
                target_tables=["customers"],
                join_key="customer_id",
            ),
        ]
        return {
            "structured_intent": structured_intent,
            "plan": plan,
            "join_keys": ["customer_id"],
            "execution_status": "planned",
        }

    # 2. Cross-Source Aggregation (e.g., Revenue in PostgreSQL + Complaints in SQL Server by region)
    if intent_type == "cross_source_aggregation" or primary_source == "multi":
        join_key = structured_intent.get("join_key") or "region_id"
        plan = [
            SubQueryTask(
                sub_task_id="sub_sales_pg",
                source="sales_pg",
                description=f"Aggregate regional sales metrics for: {user_query}",
                target_tables=["regions", "orders"],
                join_key=join_key,
            ),
            SubQueryTask(
                sub_task_id="sub_crm_mssql",
                source="crm_mssql",
                description=f"Aggregate regional complaint metrics for: {user_query}",
                target_tables=["customers", "complaints"],
                join_key=join_key,
            ),
        ]
        return {
            "structured_intent": structured_intent,
            "plan": plan,
            "join_keys": [join_key],
            "execution_status": "planned",
        }

    # 3. Single-Source DuckDB Queries (Entity Lookup, Multi-Attribute, Difference, Filtering, Ranking, Total Aggregation)
    if primary_source == "analytics_duckdb":
        primary_table = structured_intent.get("table") or "products"
        target_tables = ["products"] if primary_table == "products" else ["inventory", "products"]
        plan = [
            SubQueryTask(
                sub_task_id="sub_analytics_duckdb",
                source="analytics_duckdb",
                description=f"Execute {intent_type} on {primary_table} for: {user_query}",
                target_tables=target_tables,
                join_key="product_id",
            )
        ]
        return {
            "structured_intent": structured_intent,
            "plan": plan,
            "join_keys": ["product_id"],
            "execution_status": "planned",
        }

    # 4. Single-Source SQL Server (CRM / Complaints)
    if primary_source == "crm_mssql":
        target_tables = ["customers", "complaints"] if group_by else ["complaints"]
        plan = [
            SubQueryTask(
                sub_task_id="sub_crm_mssql",
                source="crm_mssql",
                description=f"Execute {intent_type} on CRM complaints for: {user_query}",
                target_tables=target_tables,
                join_key="region_id" if group_by else None,
            )
        ]
        return {
            "structured_intent": structured_intent,
            "plan": plan,
            "join_keys": ["region_id"] if group_by else [],
            "execution_status": "planned",
        }

    # 5. Single-Source PostgreSQL (Sales / Orders)
    target_tables = ["regions", "orders"] if group_by else ["orders"]
    plan = [
        SubQueryTask(
            sub_task_id="sub_sales_pg",
            source="sales_pg",
            description=f"Execute {intent_type} on sales orders for: {user_query}",
            target_tables=target_tables,
            join_key="region_id" if group_by else None,
        )
    ]
    return {
        "structured_intent": structured_intent,
        "plan": plan,
        "join_keys": ["region_id"] if group_by else [],
        "execution_status": "planned",
    }
