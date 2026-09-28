"""
Phase 5 End-to-End Integration Test Suite.
Validates FastAPI endpoints (/health, /query), multi-turn conversational clarification,
single-source queries, and cross-source Pandas joins across PostgreSQL, SQL Server, and DuckDB.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    return TestClient(app)


class TestFastAPIEndToEnd:
    """End-to-end integration tests for the complete vertical slice."""

    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["mcp_sources_count"] == 3
        assert set(body["mcp_sources"]) == {"sales_pg", "crm_mssql", "analytics_duckdb"}

    def test_single_source_flow(self, client):
        resp = client.post(
            "/query",
            json={
                "session_id": "sess-single-source",
                "query": "List all products with warehouse stock level below 300",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["clarification_needed"] is False
        assert "analytics_duckdb" in body["sql_queries"]
        assert len(body["data"]) > 0
        assert body["answer"] is not None
        assert "stock" in body["answer"].lower() or "product" in body["answer"].lower()

    def test_multi_source_cross_join_flow(self, client):
        resp = client.post(
            "/query",
            json={
                "session_id": "sess-multi-source",
                "query": "Which region had the highest revenue and most customer complaints last quarter?",
            },
        )
        assert resp.status_code == 200
        body = resp.json()

        assert body["status"] == "completed"
        assert body["clarification_needed"] is False
        assert "sales_pg" in body["sql_queries"]
        assert "crm_mssql" in body["sql_queries"]
        assert len(body["data"]) == 4

        # Verify in-memory join merged columns from both PostgreSQL and SQL Server
        first_row = body["data"][0]
        assert "region_id" in first_row
        assert "region_name" in first_row
        assert "total_revenue" in first_row
        assert "complaint_count" in first_row

        # Verify narrative identifies top revenue region (North America - West) and top complaint region (North America - East)
        assert "North America - West" in body["answer"]
        assert "North America - East" in body["answer"]
        assert body["visualization"] is not None

    def test_conversational_clarification_flow(self, client):
        session_id = "sess-clarification-turn"

        # Turn 1: Submit ambiguous query
        resp1 = client.post(
            "/query",
            json={"session_id": session_id, "query": "Show sales"},
        )
        assert resp1.status_code == 200
        body1 = resp1.json()
        assert body1["status"] == "clarification_needed"
        assert body1["clarification_needed"] is True
        assert body1["clarification_question"] is not None

        # Turn 2: Provide clarifying details in the same session
        resp2 = client.post(
            "/query",
            json={
                "session_id": session_id,
                "query": "Total revenue by region in Q4-2025",
            },
        )
        assert resp2.status_code == 200
        body2 = resp2.json()
        assert body2["status"] == "completed"
        assert body2["clarification_needed"] is False
        assert "sales_pg" in body2["sql_queries"]
        assert len(body2["data"]) > 0
        assert "North America - West" in body2["answer"]

    def test_frontend_static_served(self, client: TestClient) -> None:
        resp_index = client.get("/")
        assert resp_index.status_code == 200
        assert "Multi-Source Text-to-SQL Assistant" in resp_index.text

        resp_css = client.get("/styles.css")
        assert resp_css.status_code == 200

        resp_js = client.get("/app.js")
        assert resp_js.status_code == 200

