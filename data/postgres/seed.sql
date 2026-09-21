-- ==============================================================================
-- PostgreSQL Seed Data: Sales & Transactions Domain
-- 50 Orders, Associated Items, and Read-Only User Setup
-- ==============================================================================

-- 1. Insert Regions (4 regions)
INSERT INTO regions (region_id, region_name, headquarters) VALUES
(1, 'North America - East', 'New York'),
(2, 'North America - West', 'San Francisco'),
(3, 'Europe - Central', 'Frankfurt'),
(4, 'Asia - Pacific', 'Singapore')
ON CONFLICT (region_id) DO NOTHING;

-- 2. Insert Sales Representatives (6 reps)
INSERT INTO sales_reps (rep_id, rep_name, email, region_id) VALUES
(101, 'Sarah Jenkins', 'sjenkins@enterprise.com', 1),
(102, 'Michael Chen', 'mchen@enterprise.com', 2),
(103, 'Emma Schmidt', 'eschmidt@enterprise.com', 3),
(104, 'Kenji Sato', 'ksato@enterprise.com', 4),
(105, 'David Ross', 'dross@enterprise.com', 1),
(106, 'Elena Vasquez', 'evasquez@enterprise.com', 2)
ON CONFLICT (rep_id) DO NOTHING;

-- 3. Insert 50 Orders (customer_id 201-230 logically links to SQL Server customers)
INSERT INTO orders (order_id, customer_id, rep_id, region_id, order_date, quarter, total_amount, status) VALUES
(1001, 201, 101, 1, '2025-10-05', 'Q4-2025', 12500.00, 'COMPLETED'),
(1002, 202, 102, 2, '2025-10-08', 'Q4-2025', 45000.00, 'COMPLETED'),
(1003, 203, 102, 2, '2025-10-12', 'Q4-2025', 82000.00, 'COMPLETED'),
(1004, 204, 103, 3, '2025-10-15', 'Q4-2025', 28000.00, 'COMPLETED'),
(1005, 205, 104, 4, '2025-10-19', 'Q4-2025', 56000.00, 'COMPLETED'),
(1006, 206, 101, 1, '2025-10-23', 'Q4-2025', 18500.00, 'COMPLETED'),
(1007, 207, 102, 2, '2025-10-27', 'Q4-2025', 94000.00, 'COMPLETED'),
(1008, 208, 103, 3, '2025-10-30', 'Q4-2025', 31500.00, 'COMPLETED'),
(1009, 209, 104, 4, '2025-11-02', 'Q4-2025', 42000.00, 'COMPLETED'),
(1010, 210, 106, 2, '2025-11-06', 'Q4-2025', 112000.00, 'COMPLETED'),
(1011, 211, 105, 1, '2025-11-09', 'Q4-2025', 23000.00, 'COMPLETED'),
(1012, 212, 103, 3, '2025-11-13', 'Q4-2025', 49000.00, 'COMPLETED'),
(1013, 213, 104, 4, '2025-11-16', 'Q4-2025', 38000.00, 'COMPLETED'),
(1014, 214, 102, 2, '2025-11-20', 'Q4-2025', 135000.00, 'COMPLETED'),
(1015, 215, 101, 1, '2025-11-24', 'Q4-2025', 15000.00, 'CANCELLED'),
(1016, 216, 106, 2, '2025-11-28', 'Q4-2025', 68000.00, 'COMPLETED'),
(1017, 217, 103, 3, '2025-12-02', 'Q4-2025', 22500.00, 'COMPLETED'),
(1018, 218, 104, 4, '2025-12-06', 'Q4-2025', 51000.00, 'COMPLETED'),
(1019, 219, 105, 1, '2025-12-09', 'Q4-2025', 19500.00, 'COMPLETED'),
(1020, 220, 102, 2, '2025-12-13', 'Q4-2025', 77000.00, 'COMPLETED'),
(1021, 221, 103, 3, '2025-12-16', 'Q4-2025', 34000.00, 'COMPLETED'),
(1022, 222, 104, 4, '2025-12-19', 'Q4-2025', 62000.00, 'COMPLETED'),
(1023, 223, 101, 1, '2025-12-22', 'Q4-2025', 16000.00, 'COMPLETED'),
(1024, 224, 106, 2, '2025-12-26', 'Q4-2025', 89000.00, 'COMPLETED'),
(1025, 225, 103, 3, '2025-12-29', 'Q4-2025', 27000.00, 'COMPLETED'),
(1026, 201, 101, 1, '2025-01-15', 'Q1-2025', 14000.00, 'COMPLETED'),
(1027, 202, 102, 2, '2025-02-10', 'Q1-2025', 39000.00, 'COMPLETED'),
(1028, 204, 103, 3, '2025-03-05', 'Q1-2025', 24000.00, 'COMPLETED'),
(1029, 205, 104, 4, '2025-03-22', 'Q1-2025', 47000.00, 'COMPLETED'),
(1030, 207, 106, 2, '2025-04-12', 'Q2-2025', 58000.00, 'COMPLETED'),
(1031, 208, 103, 3, '2025-05-18', 'Q2-2025', 33000.00, 'COMPLETED'),
(1032, 210, 102, 2, '2025-06-25', 'Q2-2025', 85000.00, 'COMPLETED'),
(1033, 213, 104, 4, '2025-07-14', 'Q3-2025', 41000.00, 'COMPLETED'),
(1034, 214, 106, 2, '2025-08-20', 'Q3-2025', 92000.00, 'COMPLETED'),
(1035, 217, 103, 3, '2025-09-15', 'Q3-2025', 29000.00, 'COMPLETED'),
(1036, 226, 101, 1, '2025-10-11', 'Q4-2025', 17500.00, 'COMPLETED'),
(1037, 227, 102, 2, '2025-10-25', 'Q4-2025', 63000.00, 'COMPLETED'),
(1038, 228, 103, 3, '2025-11-08', 'Q4-2025', 38000.00, 'COMPLETED'),
(1039, 229, 104, 4, '2025-11-22', 'Q4-2025', 44000.00, 'COMPLETED'),
(1040, 230, 106, 2, '2025-12-15', 'Q4-2025', 71000.00, 'COMPLETED'),
(1041, 201, 105, 1, '2026-01-08', 'Q1-2026', 19000.00, 'COMPLETED'),
(1042, 203, 106, 2, '2026-01-14', 'Q1-2026', 64000.00, 'COMPLETED'),
(1043, 205, 104, 4, '2026-01-20', 'Q1-2026', 48000.00, 'COMPLETED'),
(1044, 208, 103, 3, '2026-01-26', 'Q1-2026', 36000.00, 'COMPLETED'),
(1045, 210, 102, 2, '2026-02-03', 'Q1-2026', 98000.00, 'COMPLETED'),
(1046, 211, 101, 1, '2026-02-09', 'Q1-2026', 21000.00, 'COMPLETED'),
(1047, 214, 106, 2, '2026-02-15', 'Q1-2026', 82000.00, 'COMPLETED'),
(1048, 218, 104, 4, '2026-02-21', 'Q1-2026', 53000.00, 'COMPLETED'),
(1049, 220, 102, 2, '2026-02-27', 'Q1-2026', 75000.00, 'COMPLETED'),
(1050, 222, 104, 4, '2026-03-05', 'Q1-2026', 61000.00, 'COMPLETED')
ON CONFLICT (order_id) DO NOTHING;

-- 4. Insert Order Items (product_id 301-310 logically links to products.csv)
INSERT INTO order_items (item_id, order_id, product_id, quantity, unit_price, subtotal) VALUES
(1, 1001, 301, 5, 2500.00, 12500.00),
(2, 1002, 302, 20, 1100.00, 22000.00),
(3, 1002, 303, 10, 1800.00, 18000.00),
(4, 1002, 308, 11, 450.00, 5000.00),
(5, 1003, 301, 20, 2500.00, 50000.00),
(6, 1003, 306, 10, 2200.00, 22000.00),
(7, 1003, 310, 4, 2400.00, 10000.00),
(8, 1004, 304, 20, 1400.00, 28000.00),
(9, 1005, 301, 16, 2500.00, 40000.00),
(10, 1005, 307, 12, 1250.00, 16000.00),
(11, 1006, 305, 20, 850.00, 17000.00),
(12, 1006, 308, 3, 450.00, 1500.00),
(13, 1007, 306, 30, 2200.00, 66000.00),
(14, 1007, 309, 17, 1650.00, 28000.00),
(15, 1008, 302, 25, 1100.00, 27500.00),
(16, 1008, 308, 8, 450.00, 4000.00),
(17, 1009, 303, 20, 1800.00, 36000.00),
(18, 1009, 304, 4, 1400.00, 6000.00),
(19, 1010, 301, 32, 2500.00, 80000.00),
(20, 1010, 310, 13, 2400.00, 32000.00),
(21, 1011, 307, 16, 1250.00, 20000.00),
(22, 1011, 308, 6, 450.00, 3000.00),
(23, 1012, 306, 15, 2200.00, 33000.00),
(24, 1012, 309, 9, 1650.00, 16000.00),
(25, 1013, 302, 20, 1100.00, 22000.00),
(26, 1013, 305, 18, 850.00, 16000.00),
(27, 1014, 301, 40, 2500.00, 100000.00),
(28, 1014, 306, 15, 2200.00, 35000.00),
(29, 1015, 304, 10, 1400.00, 15000.00),
(30, 1016, 303, 30, 1800.00, 54000.00),
(31, 1016, 304, 10, 1400.00, 14000.00)
ON CONFLICT (item_id) DO NOTHING;

-- Reset sequences
SELECT setval('regions_region_id_seq', (SELECT MAX(region_id) FROM regions));
SELECT setval('sales_reps_rep_id_seq', (SELECT MAX(rep_id) FROM sales_reps));
SELECT setval('orders_order_id_seq', (SELECT MAX(order_id) FROM orders));
SELECT setval('order_items_item_id_seq', (SELECT MAX(item_id) FROM order_items));

-- 5. Provision Strictly Read-Only User & Permissions
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
REVOKE CREATE ON SCHEMA public FROM readonly_pg_user;
REVOKE CREATE ON DATABASE sales_db FROM readonly_pg_user;
-- In PostgreSQL, only the object owner or superuser can ALTER or DROP tables.
-- Revoking CREATE, TRUNCATE, and write privileges while granting only SELECT guarantees strict read-only access:
-- readonly_pg_user can SELECT, but cannot INSERT, UPDATE, DELETE, DROP, or ALTER.
