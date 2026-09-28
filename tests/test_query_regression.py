"""
Regression test suite for intent classification, entity & attribute extraction,
multi-attribute & arithmetic difference queries, ungrouped scalar aggregations vs grouped aggregations,
cross-source entity lookups, fuzzy matching, and post-execution result-shape validation.
"""

import pytest
from src.agent.state import create_initial_state
from src.agent.graph import agent_graph


class TestQueryPipelineRegressions:
    """Verifies end-to-end fixes across all required intent types and regression scenarios."""

    def test_1_cost_price_of_database_replica_agent(self) -> None:
        """Single attribute entity lookup: 'What is the cost price of Database Replica Agent?'"""
        state = create_initial_state("What is the cost price of Database Replica Agent?")
        final = agent_graph.invoke(state)

        intent = final.get("structured_intent") or {}
        assert intent.get("intent") == "entity_attribute_lookup"
        assert intent.get("source") == "analytics_duckdb"
        assert intent.get("table") == "products"
        assert intent.get("entity") == "Database Replica Agent"
        assert intent.get("attribute") == "cost_price"

        sql = final["generated_sql"]["analytics_duckdb"]
        assert "SELECT product_name, cost_price" in sql
        assert "FROM products" in sql
        assert "Database Replica Agent" in sql
        assert "inventory" not in sql.lower()

        rows = final.get("aggregated_data") or []
        assert len(rows) == 1
        assert float(rows[0]["cost_price"]) == 1100.0

        answer = final.get("final_answer") or ""
        assert "Database Replica Agent" in answer
        assert "1100" in answer or "1,100" in answer
        assert "stock" not in answer.lower()

    @pytest.mark.parametrize(
        "query_variation",
        [
            "What is the cost price of Database Replica Agent?",
            "How much does Database Replica Agent cost?",
            "What is Database Replica Agent's cost price?",
            "Tell me the cost price for Database Replica Agent.",
            "Database Replica Agent cost?",
            "database replica agent price",
        ],
    )
    def test_1b_natural_language_variations(self, query_variation: str) -> None:
        """Natural language & lowercase variations all resolve to the same product cost_price."""
        state = create_initial_state(query_variation)
        final = agent_graph.invoke(state)

        assert final.get("clarification_needed") is False
        intent = final.get("structured_intent") or {}
        assert intent.get("entity") == "Database Replica Agent"
        assert intent.get("attribute") == "cost_price"

        rows = final.get("aggregated_data") or []
        assert len(rows) == 1
        assert float(rows[0]["cost_price"]) == 1100.0
        assert "1100" in (final.get("final_answer") or "")

    def test_2_stock_level_of_security_audit_module(self) -> None:
        """Inventory attribute entity lookup: 'What is the stock level of Security Audit Module?'"""
        state = create_initial_state("What is the stock level of Security Audit Module?")
        final = agent_graph.invoke(state)

        intent = final.get("structured_intent") or {}
        assert intent.get("intent") == "entity_attribute_lookup"
        assert intent.get("source") == "analytics_duckdb"
        assert intent.get("table") == "inventory"
        assert intent.get("entity") == "Security Audit Module"
        assert intent.get("attribute") == "stock_level"

        rows = final.get("aggregated_data") or []
        assert len(rows) == 1
        assert int(rows[0]["stock_level"]) == 140
        assert "140" in (final.get("final_answer") or "")

    def test_3_products_with_stock_below_300(self) -> None:
        """Filtering query: 'Show products with stock below 300.'"""
        state = create_initial_state("Show products with stock below 300.")
        final = agent_graph.invoke(state)

        intent = final.get("structured_intent") or {}
        assert intent.get("intent") == "filtering"
        sql = final["generated_sql"]["analytics_duckdb"]
        assert "stock_level < 300" in sql

        rows = final.get("aggregated_data") or []
        assert len(rows) > 1
        assert all(int(r["stock_level"]) < 300 for r in rows)

    def test_4_product_with_highest_list_price(self) -> None:
        """Top-1 product ranking: 'Which product has the highest list price?'"""
        state = create_initial_state("Which product has the highest list price?")
        final = agent_graph.invoke(state)

        intent = final.get("structured_intent") or {}
        assert intent.get("intent") == "top_max_min"
        sql = final["generated_sql"]["analytics_duckdb"]
        assert "ORDER BY list_price DESC" in sql
        assert "LIMIT 1" in sql

        rows = final.get("aggregated_data") or []
        assert len(rows) == 1
        assert rows[0]["product_name"] == "Enterprise Cloud Suite"
        assert float(rows[0]["list_price"]) == 2500.0
        assert "Enterprise Cloud Suite" in (final.get("final_answer") or "")

    def test_5_total_revenue_by_region(self) -> None:
        """Grouped regional query: 'Show total revenue by region.'"""
        state = create_initial_state("Show total revenue by region.")
        final = agent_graph.invoke(state)

        assert "sales_pg" in final["generated_sql"]
        sql = final["generated_sql"]["sales_pg"]
        assert "GROUP BY r.region_id, r.region_name" in sql
        rows = final.get("aggregated_data") or []
        assert len(rows) == 4

    def test_6_cross_source_highest_revenue_and_complaints_last_quarter(self) -> None:
        """Cross-source regional aggregation: 'Which region had the highest revenue and most customer complaints last quarter?'"""
        state = create_initial_state(
            "Which region had the highest revenue and most customer complaints last quarter?"
        )
        final = agent_graph.invoke(state)

        assert "sales_pg" in final["generated_sql"]
        assert "crm_mssql" in final["generated_sql"]
        assert "region_id" in (final.get("join_keys") or [])

        rows = final.get("aggregated_data") or []
        assert len(rows) >= 1
        assert "total_revenue" in rows[0]
        assert "complaint_count" in rows[0]

    def test_7_ambiguous_partial_product_asks_for_clarification(self) -> None:
        """Ambiguous partial entity asks 'Which product do you mean?'"""
        state = create_initial_state("What's the price of the database agent?")
        final = agent_graph.invoke(state)

        assert final.get("clarification_needed") is True
        question = final.get("clarification_question") or ""
        assert "Which product do you mean?" in question

    def test_8_result_validation_rejects_broad_inventory_query_and_self_corrects(self) -> None:
        """Post-execution Result Validation catches 10-row inventory results and regenerates exact SQL."""
        state = create_initial_state("What is the cost price of Database Replica Agent?")
        state["generated_sql"] = {
            "analytics_duckdb": (
                "SELECT p.product_id, p.product_name, p.cost_price, i.stock_level "
                "FROM products p JOIN inventory i ON p.product_id = i.product_id LIMIT 50"
            )
        }
        final = agent_graph.invoke(state)

        assert final.get("retry_count", 0) >= 1
        rows = final.get("aggregated_data") or []
        assert len(rows) == 1
        assert float(rows[0]["cost_price"]) == 1100.0
        assert "1100" in (final.get("final_answer") or "")

    # =========================================================================
    # NEW REGRESSION TESTS FOR OBSERVED FAILURES 1 - 8
    # =========================================================================

    def test_observed_failure_1_difference_list_price_and_cost_price(self) -> None:
        """
        1. 'What is the difference between the list price and cost price of Database Replica Agent?'
        Expected: list_price = 2400, cost_price = 1100, difference = 1300
        """
        state = create_initial_state(
            "What is the difference between the list price and cost price of Database Replica Agent?"
        )
        final = agent_graph.invoke(state)

        intent = final.get("structured_intent") or {}
        assert intent.get("intent") == "attribute_difference"
        assert "list_price" in (intent.get("attributes") or [])
        assert "cost_price" in (intent.get("attributes") or [])

        rows = final.get("aggregated_data") or []
        assert len(rows) == 1
        assert float(rows[0]["list_price"]) == 2400.0
        assert float(rows[0]["cost_price"]) == 1100.0
        assert float(rows[0]["price_difference"]) == 1300.0

        answer = final.get("final_answer") or ""
        assert "2,400" in answer or "2400" in answer
        assert "1,100" in answer or "1100" in answer
        assert "1,300" in answer or "1300" in answer

    def test_observed_failure_2_total_completed_revenue_q4_2025(self) -> None:
        """
        2. 'What was the total completed revenue in Q4-2025?'
        Expected: 1466000 (Scalar SUM without GROUP BY region)
        """
        state = create_initial_state("What was the total completed revenue in Q4-2025?")
        final = agent_graph.invoke(state)

        intent = final.get("structured_intent") or {}
        assert intent.get("intent") == "total_aggregation"
        assert intent.get("group_by") is None

        sql = final["generated_sql"]["sales_pg"]
        assert "GROUP BY" not in sql.upper()
        assert "Q4-2025" in sql
        assert "COMPLETED" in sql

        rows = final.get("aggregated_data") or []
        assert len(rows) == 1
        assert float(rows[0]["total_revenue"]) == 1466000.0

        answer = final.get("final_answer") or ""
        assert "1,466,000" in answer or "1466000" in answer
        assert "North America" not in answer

    def test_observed_failure_3_total_completed_revenue_q1_2026(self) -> None:
        """
        3. 'What was the total completed revenue in Q1-2026?'
        Expected: 557000 (Scalar SUM without GROUP BY region)
        """
        state = create_initial_state("What was the total completed revenue in Q1-2026?")
        final = agent_graph.invoke(state)

        intent = final.get("structured_intent") or {}
        assert intent.get("intent") == "total_aggregation"
        assert intent.get("group_by") is None

        sql = final["generated_sql"]["sales_pg"]
        assert "GROUP BY" not in sql.upper()
        assert "Q1-2026" in sql
        assert "COMPLETED" in sql

        rows = final.get("aggregated_data") or []
        assert len(rows) == 1
        assert float(rows[0]["total_revenue"]) == 557000.0

        answer = final.get("final_answer") or ""
        assert "557,000" in answer or "557000" in answer
        assert "North America" not in answer

    def test_observed_failure_4_complaint_count_q4_2025(self) -> None:
        """
        4. 'How many complaints were recorded in Q4-2025?'
        Expected: 40 (Scalar COUNT without GROUP BY region)
        """
        state = create_initial_state("How many complaints were recorded in Q4-2025?")
        final = agent_graph.invoke(state)

        intent = final.get("structured_intent") or {}
        assert intent.get("intent") == "count_aggregation"
        assert intent.get("group_by") is None

        sql = final["generated_sql"]["crm_mssql"]
        assert "GROUP BY" not in sql.upper()
        assert "Q4-2025" in sql

        rows = final.get("aggregated_data") or []
        assert len(rows) == 1
        assert int(rows[0]["complaint_count"]) == 40

        answer = final.get("final_answer") or ""
        assert "40" in answer
        assert "Region" not in answer

    def test_observed_failure_5_who_placed_highest_value_order_q4_2025(self) -> None:
        """
        5. 'Who placed the highest-value completed order in Q4-2025, and which company do they belong to?'
        Expected: Marcus Wright, Bayview Data Lab, 135000, customer_id = 214
        """
        state = create_initial_state(
            "Who placed the highest-value completed order in Q4-2025, and which company do they belong to?"
        )
        final = agent_graph.invoke(state)

        intent = final.get("structured_intent") or {}
        assert intent.get("intent") == "cross_source_entity_lookup"
        assert "sales_pg" in final["generated_sql"]
        assert "crm_mssql" in final["generated_sql"]

        rows = final.get("aggregated_data") or []
        assert len(rows) == 1
        row = rows[0]
        assert int(row["customer_id"]) == 214
        assert float(row["total_amount"]) == 135000.0
        assert row["customer_name"] == "Marcus Wright"
        assert row["company_name"] == "Bayview Data Lab"

        answer = final.get("final_answer") or ""
        assert "Marcus Wright" in answer
        assert "Bayview Data Lab" in answer
        assert "135,000" in answer or "135000" in answer

    def test_observed_6_completed_revenue_by_region_q4_2025(self) -> None:
        """
        6. 'Show completed revenue by region in Q4-2025.'
        Expected: 4 regional rows
        """
        state = create_initial_state("Show completed revenue by region in Q4-2025.")
        final = agent_graph.invoke(state)

        intent = final.get("structured_intent") or {}
        assert intent.get("intent") == "grouped_aggregation"
        assert intent.get("group_by") == ["region"]

        rows = final.get("aggregated_data") or []
        assert len(rows) == 4
        assert all("region_name" in r and "total_revenue" in r for r in rows)

    def test_observed_7_which_region_highest_completed_revenue_q4_2025(self) -> None:
        """
        7. 'Which region generated the highest completed revenue in Q4-2025?'
        Expected: North America - West, 836000
        """
        state = create_initial_state(
            "Which region generated the highest completed revenue in Q4-2025?"
        )
        final = agent_graph.invoke(state)

        intent = final.get("structured_intent") or {}
        assert intent.get("intent") == "top_max_min"

        rows = final.get("aggregated_data") or []
        assert len(rows) == 1
        assert rows[0]["region_name"] == "North America - West"
        assert float(rows[0]["total_revenue"]) == 836000.0

        answer = final.get("final_answer") or ""
        assert "North America - West" in answer
        assert "836,000" in answer or "836000" in answer

    def test_observed_8_compare_q4_2025_revenue_and_complaints_by_region(self) -> None:
        """
        8. 'Compare Q4-2025 revenue and complaint counts by region.'
        Expected: 4 regions with both total_revenue and complaint_count columns
        """
        state = create_initial_state(
            "Compare Q4-2025 revenue and complaint counts by region."
        )
        final = agent_graph.invoke(state)

        intent = final.get("structured_intent") or {}
        assert intent.get("intent") == "cross_source_aggregation"
        assert "sales_pg" in final["generated_sql"]
        assert "crm_mssql" in final["generated_sql"]

        rows = final.get("aggregated_data") or []
        assert len(rows) == 4
        assert all("total_revenue" in r and "complaint_count" in r for r in rows)

    def test_result_shape_validation_rejects_grouped_rows_for_scalar_total(self) -> None:
        """
        Verifies that if a 4-row grouped regional query is injected for 'What was the total completed revenue in Q4-2025?',
        Result-Shape Validation rejects the 4-row result and self-corrects to the 1-row scalar 1,466,000 result.
        """
        state = create_initial_state("What was the total completed revenue in Q4-2025?")
        state["generated_sql"] = {
            "sales_pg": (
                "SELECT r.region_id, r.region_name, SUM(o.total_amount) AS total_revenue "
                "FROM regions r JOIN orders o ON r.region_id = o.region_id "
                "WHERE o.status = 'COMPLETED' AND o.quarter = 'Q4-2025' "
                "GROUP BY r.region_id, r.region_name"
            )
        }
        final = agent_graph.invoke(state)

        assert final.get("retry_count", 0) >= 1
        rows = final.get("aggregated_data") or []
        assert len(rows) == 1
        assert float(rows[0]["total_revenue"]) == 1466000.0
