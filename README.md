# Multi-Source Agentic Text-to-SQL with MCP

## 1. Project Purpose

An agentic data analyst that converts natural-language questions into safe, dialect-specific read-only SQL queries across multiple databases (`PostgreSQL`, `SQL Server`, and `DuckDB`) using **LangGraph** and the **Model Context Protocol (MCP)**.

Instead of connecting the agent directly to database drivers, all schema discovery and query execution pass through a custom MCP server with strict AST read-only validation.

---

## 2. Architecture

### System Architecture Diagram

```mermaid
flowchart TD
    subgraph UI ["1. Client & Presentation Layer"]
        User(["User / Business Analyst"])
        ChatUI["Minimal ChatGPT-Style Chat UI<br/>(Single input, tables, auto-collapsible SQL)"]
    end

    subgraph API ["2. API & Orchestration Layer"]
        FastAPI["FastAPI Application<br/>(POST /query, GET /health, Session Manager)"]
    end

    subgraph Agent ["3. LangGraph Agentic Pipeline"]
        direction TB
        Guard{"Intent & Clarification Guard<br/>(Entity Disambiguation & Ambiguity Check)"}
        Context["Schema Context Builder<br/>(Targeted Schema Discovery via MCP)"]
        Text2SQL["Dialect-Aware Text-to-SQL<br/>(PostgreSQL, T-SQL, DuckDB)"]
        Execution["MCP Execution Coordinator<br/>(Dynamic Cross-Source Key Chaining)"]
        Recovery["Self-Correction Recovery<br/>(Automated Column/Syntax Repair &le; 3 retries)"]
        Aggregator["Cross-Source Aggregator<br/>(In-Memory Pandas Join on Shared Keys)"]
        Explainer["Result Explainer<br/>(Human Narrative + Clean Table + Optional Chart)"]
    end

    subgraph MCP ["4. Model Context Protocol (MCP) Integration"]
        MCPClient["MCP Client<br/>(Standard Tool Caller)"]
        MCPServer["Custom MCP Server<br/>(SQLGlot Read-Only AST Guardrails + Limits)"]
    end

    subgraph Storage ["5. Storage & Database Adapters Layer"]
        Router{"Source Router"}
        PGAdapter["PostgreSQL Adapter<br/>(Read-Only Pool)"]
        MSSQLAdapter["SQL Server Adapter<br/>(Read-Only pyodbc Pool)"]
        DuckDBAdapter["DuckDB Adapter<br/>(Read-Only Parquet/CSV Engine)"]

        PGDB[("PostgreSQL: sales_db<br/>• regions<br/>• sales_reps<br/>• orders<br/>• order_items")]
        MSSQLDB[("SQL Server: crm_db<br/>• dbo.customers<br/>• dbo.complaints")]
        DuckDB[("DuckDB: data/files/<br/>• products.csv<br/>• inventory.csv")]
    end

    %% Client / API Flow
    User <-->|"Natural Language Prompt / Follow-up"| ChatUI
    ChatUI <-->|"JSON Request / Response (/query)"| FastAPI
    FastAPI <-->|"StateGraph.invoke(AgentState)"| Guard

    %% Agent State Flow
    Guard -->|"Ambiguous Query (Needs Clarification)"| Explainer
    Guard -->|"Intent Verified"| Context
    Context --> Text2SQL
    Text2SQL --> Execution
    Execution -->|"Runtime Error / Typo"| Recovery
    Recovery -->|"Repaired SQL"| Execution
    Execution -->|"Execution Success"| Aggregator
    Aggregator --> Explainer
    Explainer -->|"Final Grounded Response"| FastAPI

    %% MCP Tool Invocations
    Context -.->|"describe_table / get_sample_rows"| MCPClient
    Execution -.->|"execute_read_query"| MCPClient
    MCPClient <-->|"MCP Tool Protocol (JSON-RPC)"| MCPServer
    MCPServer --> Router

    %% Database Routing
    Router -->|"sales_pg"| PGAdapter --> PGDB
    Router -->|"crm_mssql"| MSSQLAdapter --> MSSQLDB
    Router -->|"analytics_duckdb"| DuckDBAdapter --> DuckDB
```

### Layer-by-Layer Architecture Breakdown

| Layer | Component | Technology / Implementation | Core Responsibility |
| :--- | :--- | :--- | :--- |
| **1. Presentation** | Modern Chat UI | HTML5, CSS3, Vanilla JS | Minimal ChatGPT-style interface with a single auto-centering bottom composer, response streaming, collapsible SQL preview, and clean tabular rendering. |
| **2. API Gateway** | REST API & Sessions | FastAPI, Uvicorn, Pydantic | Exposes `/query` and `/health`, manages conversation session memory (`thread_id`), and bridges HTTP clients to the agent graph. |
| **3. Agent Core** | LangGraph StateGraph | LangGraph, Python 3.11 | Coordinates the linear agentic workflow: disambiguation guard, dynamic schema context building, dialect-specific SQL generation, execution, error self-correction, cross-source in-memory joins, and grounded answer synthesis. |
| **4. MCP Layer** | Custom MCP Server & Client | Model Context Protocol SDK, SQLGlot | Abstracts database drivers behind 6 standardized tools. Enforces AST read-only AST safety validation (`validate_read_only_sql`), row limits (`apply_query_limit`), and query execution timeouts. |
| **5. Storage Layer** | Heterogeneous Databases | PostgreSQL 16, MS SQL Server, DuckDB | Stores business data across distributed domains: operational sales in PostgreSQL, customer support in SQL Server, and catalog/inventory in analytical CSV files. |


---

## 3. Supported Data Sources

> [!NOTE]
> For complete table schemas, data types, sample data rows, cross-source key diagrams, and sample natural language queries with expected answers, see [DATA_README.md](DATA_README.md).

| Source ID | Engine | Domain & Tables | Shared Keys |
| :--- | :--- | :--- | :--- |
| `sales_pg` | PostgreSQL | `regions`, `orders`, `order_items`, `sales_reps` | `region_id`, `customer_id`, `product_id` |
| `crm_mssql` | SQL Server | `dbo.customers`, `dbo.complaints` | `customer_id`, `region_id`, `product_id` |
| `analytics_duckdb` | DuckDB (CSV) | `products` (`products.csv`), `inventory` (`inventory.csv`) | `product_id` |

---

## 4. Main Workflow

1. **Intent & Clarification Guard:** Checks if the user query or entity reference is ambiguous (e.g., `"Show sales"` or `"What's the price of the database agent?"`) and asks a clarifying question before proceeding. For clear queries, extracts the structured intent (`operation`, `filters`, `attributes`, and target sources).
2. **Schema Discovery (Context Builder):** Performs targeted schema discovery through MCP tools (`describe_table`, `get_relationships`, `get_sample_rows`) for the identified data sources and tables.
3. **Dialect-Aware Text-to-SQL:** Generates native SQL for PostgreSQL (`LIMIT`), SQL Server (`SELECT TOP`), and DuckDB directly matching the verified intent.
4. **Execution & Self-Correction:** Executes queries via the MCP Client, chains dynamic entity keys across sources, and automatically repairs SQL if runtime errors occur.
5. **Cross-Source Aggregation & Explanation:** Merges multi-source records in memory and generates a clear, grounded natural-language response.


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
