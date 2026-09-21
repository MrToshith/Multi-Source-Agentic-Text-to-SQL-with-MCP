-- ==============================================================================
-- PostgreSQL Seed Data: Sales & Transactions Domain
-- Includes Read-Only User Creation Script
-- ==============================================================================

-- 1. Insert Regions
INSERT INTO regions (region_id, region_name, headquarters) VALUES
(1, 'North America - East', 'New York'),
(2, 'North America - West', 'San Francisco'),
(3, 'Europe - Central', 'Frankfurt'),
(4, 'Asia - Pacific', 'Singapore')
ON CONFLICT (region_id) DO NOTHING;

-- 2. Insert Sales Representatives
INSERT INTO sales_reps (rep_id, rep_name, email, region_id) VALUES
(101, 'Sarah Jenkins', 'sjenkins@enterprise.com', 1),
(102, 'Michael Chen', 'mchen@enterprise.com', 2),
(103, 'Emma Schmidt', 'eschmidt@enterprise.com', 3),
(104, 'Kenji Sato', 'ksato@enterprise.com', 4),
(105, 'David Ross', 'dross@enterprise.com', 1),
(106, 'Elena Vasquez', 'evasquez@enterprise.com', 2)
ON CONFLICT (rep_id) DO NOTHING;

-- 3. Insert Orders (Quarter Q4 2025 and Q1 2026 data for realistic benchmarks)
INSERT INTO orders (order_id, customer_id, rep_id, region_id, order_date, quarter, total_amount, status) VALUES
(1001, 201, 101, 1, '2025-10-05', 'Q4-2025', 12500.00, 'COMPLETED'),
(1002, 202, 102, 2, '2025-10-12', 'Q4-2025', 45000.00, 'COMPLETED'),
(1003, 203, 102, 2, '2025-10-18', 'Q4-2025', 82000.00, 'COMPLETED'),
(1004, 204, 103, 3, '2025-10-22', 'Q4-2025', 28000.00, 'COMPLETED'),
(1005, 205, 104, 4, '2025-10-29', 'Q4-2025', 56000.00, 'COMPLETED'),
(1006, 206, 101, 1, '2025-11-03', 'Q4-2025', 18500.00, 'COMPLETED'),
(1007, 207, 102, 2, '2025-11-09', 'Q4-2025', 94000.00, 'COMPLETED'),
(1008, 208, 103, 3, '2025-11-15', 'Q4-2025', 31500.00, 'COMPLETED'),
(1009, 209, 104, 4, '2025-11-20', 'Q4-2025', 42000.00, 'COMPLETED'),
(1010, 210, 102, 2, '2025-11-27', 'Q4-2025', 112000.00, 'COMPLETED'),
(1011, 211, 101, 1, '2025-12-02', 'Q4-2025', 23000.00, 'COMPLETED'),
(1012, 212, 103, 3, '2025-12-08', 'Q4-2025', 49000.00, 'COMPLETED'),
(1013, 213, 104, 4, '2025-12-14', 'Q4-2025', 38000.00, 'COMPLETED'),
(1014, 214, 102, 2, '2025-12-19', 'Q4-2025', 135000.00, 'COMPLETED'),
(1015, 215, 101, 1, '2025-12-23', 'Q4-2025', 15000.00, 'CANCELLED'),
(1016, 201, 105, 1, '2026-01-05', 'Q1-2026', 19000.00, 'COMPLETED'),
(1017, 203, 106, 2, '2026-01-11', 'Q1-2026', 64000.00, 'COMPLETED'),
(1018, 205, 104, 4, '2026-01-18', 'Q1-2026', 48000.00, 'COMPLETED'),
(1019, 208, 103, 3, '2026-01-25', 'Q1-2026', 36000.00, 'COMPLETED'),
(1020, 210, 102, 2, '2026-02-02', 'Q1-2026', 98000.00, 'COMPLETED')
ON CONFLICT (order_id) DO NOTHING;

-- Reset sequence to avoid key collision
SELECT setval('regions_region_id_seq', (SELECT MAX(region_id) FROM regions));
SELECT setval('sales_reps_rep_id_seq', (SELECT MAX(rep_id) FROM sales_reps));
SELECT setval('orders_order_id_seq', (SELECT MAX(order_id) FROM orders));

-- 4. Provision Strictly Read-Only User & Permissions
DO
$$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'readonly_pg_user') THEN
      CREATE ROLE readonly_pg_user WITH LOGIN PASSWORD 'readonly_password';
   END IF;
END
$$;

-- Grant connect and schema usage
GRANT CONNECT ON DATABASE sales_db TO readonly_pg_user;
GRANT USAGE ON SCHEMA public TO readonly_pg_user;

-- Grant only SELECT on all existing and future tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_pg_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO readonly_pg_user;

-- Revoke all modification and DDL permissions explicitly
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM readonly_pg_user;
