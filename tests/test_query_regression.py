"""
Regression test suite for intent classification, entity & attribute extraction,
fuzzy matching, post-execution result validation, and database-grounded answers.
"""

import pytest
from src.agent.state import create_initial_state
from src.agent.graph import agent_graph


class TestQueryPipelineRegressions:
    """Verifies end-to-end fixes for exact entity lookups, filtering, ranking, grouping, and cross-source queries."""

    def test_1_cost_price_of_database_replica_agent(self) -> None:
        """TEST 1: 'What is the cost price of Database Replica Agent?'"""
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
        assert "inventory filter" not in answer.lower()

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
        """SECTION 13: Natural language & lowercase variations all resolve to the same product cost_price."""
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
        """TEST 2: 'What is the stock level of Security Audit Module?'"""
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
        """TEST 3: 'Show products with stock below 300.'"""
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
        """TEST 4: 'Which product has the highest list price?'"""
        state = create_initial_state("Which product has the highest list price?")
        final = agent_graph.invoke(state)

        intent = final.get("structured_intent") or {}
        assert intent.get("intent") == "aggregation"
        sql = final["generated_sql"]["analytics_duckdb"]
        assert "ORDER BY list_price DESC" in sql
        assert "LIMIT 1" in sql

        rows = final.get("aggregated_data") or []
        assert len(rows) == 1
        assert rows[0]["product_name"] == "Enterprise Cloud Suite"
        assert float(rows[0]["list_price"]) == 2500.0
        assert "Enterprise Cloud Suite" in (final.get("final_answer") or "")

    def test_5_total_revenue_by_region(self) -> None:
        """TEST 5: 'Show total revenue by region.'"""
        state = create_initial_state("Show total revenue by region.")
        final = agent_graph.invoke(state)

        assert "sales_pg" in final["generated_sql"]
        sql = final["generated_sql"]["sales_pg"]
        assert "GROUP BY r.region_id, r.region_name" in sql
        rows = final.get("aggregated_data") or []
        assert len(rows) == 4

    def test_6_cross_source_highest_revenue_and_complaints_last_quarter(self) -> None:
        """TEST 6: 'Which region had the highest revenue and most customer complaints last quarter?'"""
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
        """SECTION 6: 'What's the price of the database agent?' asks 'Which product do you mean?'"""
        state = create_initial_state("What's the price of the database agent?")
        final = agent_graph.invoke(state)

        assert final.get("clarification_needed") is True
        question = final.get("clarification_question") or ""
        assert "Which product do you mean?" in question

    def test_8_result_validation_rejects_broad_inventory_query_and_self_corrects(self) -> None:
        """SECTION 7: Post-execution Result Validation catches 10-row inventory results and regenerates exact SQL."""
        state = create_initial_state("What is the cost price of Database Replica Agent?")
        # Pre-inject the old buggy broad 10-row inventory SQL to prove Result Validation rejects it and self-corrects
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
