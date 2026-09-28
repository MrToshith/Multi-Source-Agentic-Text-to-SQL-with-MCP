# Multi-Source Agentic Text-to-SQL with MCP

## 1. Project Purpose

An agentic data analyst that converts natural-language questions into safe, dialect-specific read-only SQL queries across multiple databases (`PostgreSQL`, `SQL Server`, and `DuckDB`) using **LangGraph** and the **Model Context Protocol (MCP)**.

Instead of connecting the agent directly to database drivers, all schema discovery and query execution pass through a custom MCP server with strict AST read-only validation.

---

## 2. Architecture

```text
FastAPI (/query, /health) + Chat UI
        ↓
LangGraph Agent (Intent Guard → Planner → Schema Context → Text-to-SQL → Validator → Execution → Aggregator → Explainer)
        ↓
MCP Client
        ↓
Custom MCP Server (SQLGlot Read-Only Guardrails + Row Limits)
        ↓
Source Router
   ├── PostgreSQL Adapter  → sales_db (orders, order_items, regions, sales_reps)
   ├── SQL Server Adapter  → crm_db (customers, complaints)
   └── DuckDB Adapter      → data/files/ (products.csv, inventory.csv)
```

---

## 3. Supported Data Sources

| Source ID | Engine | Domain & Tables | Shared Keys |
| :--- | :--- | :--- | :--- |
| `sales_pg` | PostgreSQL | `regions`, `orders`, `order_items`, `sales_reps` | `region_id`, `customer_id`, `product_id` |
| `crm_mssql` | SQL Server | `dbo.customers`, `dbo.complaints` | `customer_id`, `region_id`, `product_id` |
| `analytics_duckdb` | DuckDB (CSV) | `products` (`products.csv`), `inventory` (`inventory.csv`) | `product_id` |

---

## 4. Main Workflow

1. **Intent & Clarification Guard:** Checks if the user query or entity reference is ambiguous (e.g., `"Show sales"` or `"What's the price of the database agent?"`) and asks a clarifying question before writing SQL.
2. **Query Planner:** Resolves entities and attributes via MCP metadata and classifies the operation (`entity_attribute_lookup`, `multi_attribute_lookup`, `attribute_difference`, `total_aggregation`, `count_aggregation`, `grouped_aggregation`, `top_max_min`, `cross_source_entity_lookup`, `cross_source_aggregation`, `filtering`).
3. **Schema Discovery:** Calls MCP tools (`describe_table`, `get_relationships`, `get_sample_rows`) for the planned sources and tables.
4. **Dialect-Aware Text-to-SQL:** Generates native SQL for PostgreSQL (`LIMIT`), SQL Server (`SELECT TOP`), and DuckDB.
5. **SQL Safety & Result-Shape Validation:** Parses candidate SQL with `sqlglot` to block mutations, executes via MCP, and verifies that the returned rows/columns match the planned intent (self-correcting up to 3 times if needed).
6. **Cross-Source Aggregation & Explanation:** Joins multi-source results in memory with Pandas and generates a grounded natural-language answer.

---

## 5. MCP Tools

The custom MCP server exposes 6 standardized tools via the official MCP SDK:

- `list_data_sources()`
- `list_tables(source)`
- `describe_table(source, table)`
- `get_relationships(source)`
- `get_sample_rows(source, table, limit)`
- `execute_read_query(source, validated_sql)`

---

## 6. Safety Mechanism

1. **SQLGlot AST Validation:** Rejects any statement that is not a single `SELECT` query (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, and multi-statement queries are blocked).
2. **Automatic Row Limits & Timeouts:** Enforces row caps (`LIMIT` / `TOP`) and query execution timeouts.
3. **Read-Only Database Credentials:** Database adapters connect using restricted `SELECT`-only users (`readonly_pg_user`, `readonly_mssql_user`) and read-only DuckDB views.

---

## 7. Setup Instructions

```bash
# 1. Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy environment configuration
copy .env.example .env
```

---

## 8. How to Run

```bash
# Start FastAPI server and Chat UI on http://localhost:8000
.\.venv\Scripts\python.exe -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000

# Run the automated test suite
.\.venv\Scripts\pytest.exe -v tests/
```

Open **`http://localhost:8000`** in your browser to use the chat interface.

---

## 9. Example Queries

- **Single Attribute Lookup (DuckDB):**
  `"What is the cost price of Database Replica Agent?"` → `1,100`
- **Multi-Attribute Arithmetic Difference (DuckDB):**
  `"What is the difference between the list price and cost price of Database Replica Agent?"` → `list_price = 2,400`, `cost_price = 1,100`, `difference = 1,300`
- **Ungrouped Scalar Total (PostgreSQL):**
  `"What was the total completed revenue in Q4-2025?"` → `1,466,000`
- **Ungrouped Scalar Count (SQL Server):**
  `"How many complaints were recorded in Q4-2025?"` → `40`
- **Grouped Regional Breakdown (PostgreSQL):**
  `"Show completed revenue by region in Q4-2025."` → `4 regional rows`
- **Cross-Source Entity Lookup (PostgreSQL + SQL Server):**
  `"Who placed the highest-value completed order in Q4-2025, and which company do they belong to?"` → `Marcus Wright of Bayview Data Lab (135,000)`
- **Cross-Source Regional Aggregation (PostgreSQL + SQL Server):**
  `"Compare Q4-2025 revenue and complaint counts by region."` → `4 regions with total_revenue and complaint_count`
