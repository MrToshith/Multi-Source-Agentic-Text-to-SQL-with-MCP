# Data Catalog & Sample Queries Reference

This document provides a complete guide to all data sources, table schemas, logical cross-source relationships, sample data rows, and standard sample questions with their expected answers and generated SQL queries.

---

## 1. Data Sources Overview

The architecture connects three heterogeneous, distributed data sources through the Model Context Protocol (MCP):

| Source ID | Engine / Storage | Schema / Path | Domain | Primary Tables / Files |
| :--- | :--- | :--- | :--- | :--- |
| **`sales_pg`** | PostgreSQL 16 | `public` | Sales & Order Transactions | `regions`, `sales_reps`, `orders`, `order_items` |
| **`crm_mssql`** | Microsoft SQL Server | `dbo` | Customer CRM & Support | `dbo.customers`, `dbo.complaints` |
| **`analytics_duckdb`** | DuckDB (Embedded) | `data/files/*.csv` | Product Catalog & Inventory | `products` (`products.csv`), `inventory` (`inventory.csv`) |

---

## 2. Cross-Source Logical Keys

Because these databases reside in separate database engines, relational integrity across sources is maintained via shared logical foreign keys joined in memory:

```
[ PostgreSQL: sales_pg ]           [ SQL Server: crm_mssql ]         [ DuckDB: analytics_duckdb ]
  orders.region_id       <------->   customers.region_id
  regions.region_id      <------->   customers.region_id
  orders.customer_id     <------->   customers.customer_id
                                     complaints.customer_id
  order_items.product_id <----------------------------------------->   products.product_id
                                                                       inventory.product_id
```

| Logical Join Key | Source 1 (Origin) | Source 2 (Target) | Description |
| :--- | :--- | :--- | :--- |
| **`region_id`** | `sales_pg.regions` / `sales_pg.orders` | `crm_mssql.customers` | Connects sales geographical performance to customer regional distributions and complaint rates. |
| **`customer_id`** | `sales_pg.orders` | `crm_mssql.customers` / `crm_mssql.complaints` | Connects order purchases directly to customer account details, tier, and service tickets. |
| **`product_id`** | `sales_pg.order_items` | `analytics_duckdb.products` / `analytics_duckdb.inventory` | Connects transaction items to product specifications, pricing, margins, and warehouse inventory. |

---

## 3. Data Tables & Sample Data

### Source 1: PostgreSQL (`sales_pg`)

#### Table: `regions`
Geographic sales territories.

| Column | Data Type | Key | Description |
| :--- | :--- | :--- | :--- |
| `region_id` | `INTEGER` | **PK** | Unique region identifier (1 to 4) |
| `region_name` | `VARCHAR(100)` | | Territory name |
| `headquarters` | `VARCHAR(100)` | | Regional operational office |

**Sample Rows:**
| region_id | region_name | headquarters |
| :--- | :--- | :--- |
| `1` | North America - East | New York |
| `2` | North America - West | San Francisco |
| `3` | Europe - Central | Frankfurt |
| `4` | Asia - Pacific | Singapore |

---

#### Table: `sales_reps`
Account managers assigned to regional territories.

| Column | Data Type | Key | Description |
| :--- | :--- | :--- | :--- |
| `rep_id` | `INTEGER` | **PK** | Sales representative ID |
| `rep_name` | `VARCHAR(100)` | | Full representative name |
| `email` | `VARCHAR(150)` | | Enterprise email address |
| `region_id` | `INTEGER` | **FK** | Links to `regions.region_id` |

**Sample Rows:**
| rep_id | rep_name | email | region_id |
| :--- | :--- | :--- | :--- |
| `101` | Sarah Jenkins | sjenkins@enterprise.com | `1` |
| `102` | Michael Chang | mchang@enterprise.com | `2` |
| `103` | Elena Rostova | erostova@enterprise.com | `3` |
| `104` | David Tanaka | dtanaka@enterprise.com | `4` |

---

#### Table: `orders`
High-level order header transactions across fiscal quarters.

| Column | Data Type | Key | Description |
| :--- | :--- | :--- | :--- |
| `order_id` | `INTEGER` | **PK** | Unique order transaction ID |
| `customer_id` | `INTEGER` | **Logical FK** | Links to `crm_mssql.customers.customer_id` |
| `rep_id` | `INTEGER` | **FK** | Links to `sales_reps.rep_id` |
| `region_id` | `INTEGER` | **FK** | Links to `regions.region_id` |
| `order_date` | `DATE` | | Date the order was placed |
| `quarter` | `VARCHAR(10)` | | Fiscal quarter (`Q3-2025`, `Q4-2025`, `Q1-2026`) |
| `total_amount` | `NUMERIC(12,2)` | | Order total revenue in USD |
| `status` | `VARCHAR(20)` | | Order state (`COMPLETED`, `CANCELLED`, `REFUNDED`) |

**Sample Rows:**
| order_id | customer_id | rep_id | region_id | order_date | quarter | total_amount | status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `1001` | `201` | `101` | `1` | `2025-10-05` | Q4-2025 | $12,500.00 | COMPLETED |
| `1002` | `202` | `101` | `1` | `2025-10-12` | Q4-2025 | $45,000.00 | COMPLETED |
| `1014` | `214` | `102` | `2` | `2025-11-20` | Q4-2025 | $135,000.00 | COMPLETED |
| `1040` | `220` | `103` | `3` | `2026-01-14` | Q1-2026 | $85,000.00 | COMPLETED |

---

#### Table: `order_items`
Detailed line-item records for each order.

| Column | Data Type | Key | Description |
| :--- | :--- | :--- | :--- |
| `item_id` | `INTEGER` | **PK** | Line item ID |
| `order_id` | `INTEGER` | **FK** | Links to `orders.order_id` |
| `product_id` | `INTEGER` | **Logical FK** | Links to `analytics_duckdb.products.product_id` |
| `quantity` | `INTEGER` | | Number of units purchased |
| `unit_price` | `NUMERIC(10,2)` | | Price charged per unit |
| `subtotal` | `NUMERIC(12,2)` | | Line total (`quantity * unit_price`) |

**Sample Rows:**
| item_id | order_id | product_id | quantity | unit_price | subtotal |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `1` | `1001` | `301` | 5 | $2,500.00 | $12,500.00 |
| `2` | `1002` | `306` | 20 | $2,250.00 | $45,000.00 |
| `15` | `1014` | `310` | 50 | $2,400.00 | $120,000.00 |

---

### Source 2: SQL Server (`crm_mssql`)

#### Table: `dbo.customers`
Client profiles and enterprise account classifications.

| Column | Data Type | Key | Description |
| :--- | :--- | :--- | :--- |
| `customer_id` | `INTEGER` | **PK** | Unique customer identifier (201 to 230) |
| `customer_name` | `VARCHAR(100)` | | Primary contact full name |
| `company_name` | `VARCHAR(150)` | | Company / organization name |
| `region_id` | `INTEGER` | **Logical FK** | Links to `sales_pg.regions.region_id` |
| `tier` | `VARCHAR(30)` | | Account tier (`ENTERPRISE`, `MID-MARKET`, `SMB`) |
| `signup_date` | `DATE` | | Onboarding date |
| `account_status` | `VARCHAR(20)` | | Account health (`ACTIVE`, `CHURNED`) |

**Sample Rows:**
| customer_id | customer_name | company_name | region_id | tier | signup_date | account_status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `201` | Alex Mercer | Apex Financial | `1` | ENTERPRISE | `2023-03-15` | ACTIVE |
| `202` | Brenda Vance | Vance Analytics | `1` | MID-MARKET | `2023-05-20` | ACTIVE |
| `214` | Marcus Wright | Bayview Data Lab | `2` | ENTERPRISE | `2024-01-10` | ACTIVE |
| `220` | Hans Gruber | Alpine Logistics | `3` | ENTERPRISE | `2024-04-12` | ACTIVE |

---

#### Table: `dbo.complaints`
Customer support incidents, severity classifications, and SLA resolutions.

| Column | Data Type | Key | Description |
| :--- | :--- | :--- | :--- |
| `complaint_id` | `INTEGER` | **PK** | Support ticket ID (5001+) |
| `customer_id` | `INTEGER` | **FK** | Links to `dbo.customers.customer_id` |
| `complaint_date` | `DATE` | | Incident report date |
| `quarter` | `VARCHAR(10)` | | Fiscal quarter (`Q3-2025`, `Q4-2025`, `Q1-2026`) |
| `category` | `VARCHAR(50)` | | Issue domain (`Billing Discrepancy`, `Service Outage`, etc.) |
| `severity` | `VARCHAR(20)` | | Priority (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) |
| `status` | `VARCHAR(20)` | | Resolution status (`RESOLVED`, `PENDING`, `ESCALATED`) |
| `resolution_time_hours` | `FLOAT` | | Hours taken to resolve ticket |

**Sample Rows:**
| complaint_id | customer_id | complaint_date | quarter | category | severity | status | resolution_time_hours |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `5001` | `201` | `2025-10-06` | Q4-2025 | Billing Discrepancy | HIGH | RESOLVED | 14.5 |
| `5002` | `202` | `2025-10-18` | Q4-2025 | Performance Lag | MEDIUM | RESOLVED | 8.0 |
| `5018` | `214` | `2025-11-25` | Q4-2025 | SLA Breach | CRITICAL | RESOLVED | 4.2 |

---

### Source 3: DuckDB / Analytical Files (`analytics_duckdb`)

#### File / Table: `products.csv` (`products`)
Product master catalog, pricing, and active status.

| Column | Data Type | Key | Description |
| :--- | :--- | :--- | :--- |
| `product_id` | `BIGINT` | **PK** | Unique product ID (301 to 310) |
| `product_name` | `VARCHAR` | | Commercial product name |
| `category` | `VARCHAR` | | Product segment (Software, Security, Storage, etc.) |
| `cost_price` | `DOUBLE` | | Internal manufacturing / licensing cost ($) |
| `list_price` | `DOUBLE` | | Retail / customer catalog price ($) |
| `is_active` | `BOOLEAN` | | Active for sale flag |

**Complete Catalog Rows:**
| product_id | product_name | category | cost_price | list_price | is_active |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `301` | Enterprise Cloud Suite | Software | $1,200.00 | $2,500.00 | `True` |
| `302` | AI Analytics Addon | Software | $450.00 | $1,100.00 | `True` |
| `303` | Data Sync Bridge | Infrastructure | $800.00 | $1,800.00 | `True` |
| `304` | Security Audit Module | Security | $600.00 | $1,400.00 | `True` |
| `305` | CRM Connector Pro | Integration | $350.00 | $850.00 | `True` |
| `306` | High-Throughput Queue | Infrastructure | $950.00 | $2,200.00 | `True` |
| `307` | Compliance Tracker | Governance | $500.00 | $1,250.00 | `True` |
| `308` | Custom Domain Gateway | Networking | $200.00 | $450.00 | `True` |
| `309` | Real-time Log Aggregator | Monitoring | $750.00 | $1,650.00 | `True` |
| `310` | Database Replica Agent | Storage | $1,100.00 | $2,400.00 | `True` |

---

#### File / Table: `inventory.csv` (`inventory`)
Warehouse storage distribution, stock counts, and safety replenishment thresholds.

| Column | Data Type | Key | Description |
| :--- | :--- | :--- | :--- |
| `product_id` | `BIGINT` | **FK** | Links to `products.product_id` |
| `warehouse_id` | `VARCHAR` | | Facility identifier (`WH-01` to `WH-04`) |
| `warehouse_location` | `VARCHAR` | | Facility location (New Jersey, California, etc.) |
| `stock_level` | `BIGINT` | | Current on-hand quantity |
| `reorder_point` | `BIGINT` | | Threshold quantity triggering reorder |
| `safety_stock` | `BIGINT` | | Buffer minimum inventory level |

**Complete Inventory Rows:**
| product_id | warehouse_id | warehouse_location | stock_level | reorder_point | safety_stock |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `301` | WH-01 | New Jersey | 450 | 100 | 50 |
| `302` | WH-01 | New Jersey | 210 | 80 | 40 |
| `303` | WH-02 | California | 890 | 200 | 100 |
| `304` | WH-02 | California | 140 | 50 | 25 |
| `305` | WH-03 | Frankfurt | 320 | 100 | 50 |
| `306` | WH-03 | Frankfurt | 550 | 150 | 75 |
| `307` | WH-04 | Singapore | 780 | 250 | 100 |
| `308` | WH-04 | Singapore | 190 | 60 | 30 |
| `309` | WH-01 | New Jersey | 620 | 150 | 75 |
| `310` | WH-02 | California | 340 | 100 | 50 |

---

## 4. Sample Questions & Expected Answers

The table below outlines representative questions across all query categories, detailing the target data sources, generated SQL statements, and expected results:

### 1. Exact Entity Attribute Lookup
- **User Question:** `"What is the cost price of Database Replica Agent?"`
- **Target Source:** `analytics_duckdb`
- **Generated SQL:**
  ```sql
  SELECT cost_price
  FROM products
  WHERE product_name = 'Database Replica Agent'
  LIMIT 1;
  ```
- **Expected Answer:**
  > Database Replica Agent has a cost price of **$1,100.00**.

---

### 2. Multi-Attribute & Arithmetic Difference
- **User Question:** `"What is the difference between the list price and cost price of Database Replica Agent?"`
- **Target Source:** `analytics_duckdb`
- **Generated SQL:**
  ```sql
  SELECT product_name, list_price, cost_price, (list_price - cost_price) AS price_difference
  FROM products
  WHERE product_name = 'Database Replica Agent'
  LIMIT 1;
  ```
- **Expected Answer:**
  > Database Replica Agent has a list price of **$2,400.00** and a cost price of **$1,100.00**, resulting in a difference of **$1,300.00**.

---

### 3. Inventory Warehouse Stock Check
- **User Question:** `"What is the stock level of Security Audit Module?"`
- **Target Source:** `analytics_duckdb`
- **Generated SQL:**
  ```sql
  SELECT p.product_name, i.warehouse_location, i.stock_level
  FROM products p
  JOIN inventory i ON p.product_id = i.product_id
  WHERE p.product_name = 'Security Audit Module'
  LIMIT 1;
  ```
- **Expected Answer:**
  > Security Audit Module has a stock level of **140 units** located at the **California (WH-02)** warehouse.

---

### 4. Threshold Inventory Filtering
- **User Question:** `"List all products with warehouse stock level below 300."`
- **Target Source:** `analytics_duckdb`
- **Generated SQL:**
  ```sql
  SELECT p.product_name, i.warehouse_id, i.warehouse_location, i.stock_level
  FROM products p
  JOIN inventory i ON p.product_id = i.product_id
  WHERE i.stock_level < 300
  ORDER BY i.stock_level ASC
  LIMIT 50;
  ```
- **Expected Answer:**
  > Found 3 products with stock level below 300:
  > - **Security Audit Module**: 140 units (California, WH-02)
  > - **Custom Domain Gateway**: 190 units (Singapore, WH-04)
  > - **AI Analytics Addon**: 210 units (New Jersey, WH-01)

---

### 5. Total Ungrouped Completed Revenue (Q4-2025)
- **User Question:** `"What was the total completed revenue in Q4-2025?"`
- **Target Source:** `sales_pg`
- **Generated SQL:**
  ```sql
  SELECT COALESCE(SUM(total_amount), 0) AS total_revenue
  FROM orders
  WHERE status = 'COMPLETED'
    AND quarter = 'Q4-2025';
  ```
- **Expected Answer:**
  > Total completed revenue across all regions in Q4-2025 was **$1,466,000.00**.

---

### 6. Total Ungrouped Completed Revenue (Q1-2026)
- **User Question:** `"What was the total completed revenue in Q1-2026?"`
- **Target Source:** `sales_pg`
- **Generated SQL:**
  ```sql
  SELECT COALESCE(SUM(total_amount), 0) AS total_revenue
  FROM orders
  WHERE status = 'COMPLETED'
    AND quarter = 'Q1-2026';
  ```
- **Expected Answer:**
  > Total completed revenue in Q1-2026 was **$557,000.00**.

---

### 7. Total Complaint Count (Scalar Aggregation)
- **User Question:** `"How many complaints were recorded in Q4-2025?"`
- **Target Source:** `crm_mssql`
- **Generated SQL:**
  ```sql
  SELECT COUNT(complaint_id) AS complaint_count
  FROM dbo.complaints
  WHERE quarter = 'Q4-2025';
  ```
- **Expected Answer:**
  > A total of **40 customer complaints** were recorded in Q4-2025.

---

### 8. Regional Revenue Ranking (Top Performer)
- **User Question:** `"Which region had the highest completed revenue in Q4-2025?"`
- **Target Source:** `sales_pg`
- **Generated SQL:**
  ```sql
  SELECT r.region_id, r.region_name, COUNT(o.order_id) AS order_count, SUM(o.total_amount) AS total_revenue
  FROM regions r
  JOIN orders o ON r.region_id = o.region_id
  WHERE o.status = 'COMPLETED'
    AND o.quarter = 'Q4-2025'
  GROUP BY r.region_id, r.region_name
  ORDER BY total_revenue DESC
  LIMIT 1;
  ```
- **Expected Answer:**
  > **North America - West** had the highest completed revenue in Q4-2025 at **$836,000.00** across 16 orders.

---

### 9. Cross-Source Entity Chaining (PostgreSQL Order → SQL Server Customer)
- **User Question:** `"Who placed the highest value completed order in Q4-2025?"`
- **Target Sources:** `sales_pg` → `crm_mssql`
- **Step 1 (`sales_pg`):**
  ```sql
  SELECT order_id, customer_id, total_amount, quarter, status
  FROM orders
  WHERE status = 'COMPLETED'
    AND quarter = 'Q4-2025'
  ORDER BY total_amount DESC
  LIMIT 1;
  ```
  *(Identifies Order #1014, Customer ID 214, Total Amount $135,000.00)*
- **Step 2 (`crm_mssql`):**
  ```sql
  SELECT TOP 1 customer_id, customer_name, company_name, tier, region_id
  FROM dbo.customers
  WHERE customer_id = 214;
  ```
- **Expected Answer:**
  > The highest-value completed order in Q4-2025 was **Order #1014** for **$135,000.00**, placed by **Marcus Wright** from **Bayview Data Lab** (Customer ID 214, Enterprise tier).

---

### 10. Cross-Source Regional Comparison (Revenue vs. Complaints)
- **User Question:** `"Compare Q4-2025 revenue and complaint counts by region."`
- **Target Sources:** `sales_pg` (`orders`) and `crm_mssql` (`complaints`)
- **Join Key:** `region_id`
- **SQL 1 (`sales_pg`):**
  ```sql
  SELECT r.region_id, r.region_name, COUNT(o.order_id) AS order_count, SUM(o.total_amount) AS total_revenue
  FROM regions r
  JOIN orders o ON r.region_id = o.region_id
  WHERE o.status = 'COMPLETED'
    AND o.quarter = 'Q4-2025'
  GROUP BY r.region_id, r.region_name
  ORDER BY total_revenue DESC
  LIMIT 50;
  ```
- **SQL 2 (`crm_mssql`):**
  ```sql
  SELECT TOP 50 c.region_id, COUNT(comp.complaint_id) AS complaint_count
  FROM dbo.customers c
  JOIN dbo.complaints comp ON c.customer_id = comp.customer_id
  WHERE comp.quarter = 'Q4-2025'
  GROUP BY c.region_id
  ORDER BY complaint_count DESC;
  ```
- **In-Memory Join Result:**
  | Region | Orders | Total Revenue | Complaints |
  | :--- | :--- | :--- | :--- |
  | North America - West | 16 | $836,000.00 | 18 |
  | North America - East | 12 | $310,000.00 | 11 |
  | Europe - Central | 8 | $210,000.00 | 7 |
  | Asia - Pacific | 4 | $110,000.00 | 4 |
- **Expected Answer:**
  > In Q4-2025, North America - West generated the highest completed revenue at $836,000.00 but also recorded the highest customer complaints (18), followed by North America - East ($310,000.00, 11 complaints), Europe - Central ($210,000.00, 7 complaints), and Asia - Pacific ($110,000.00, 4 complaints).
