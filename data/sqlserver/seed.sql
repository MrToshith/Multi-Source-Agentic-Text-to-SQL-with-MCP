-- ==============================================================================
-- Microsoft SQL Server Seed Data: CRM & Customer Support Domain
-- Includes Read-Only User Creation Script
-- ==============================================================================

-- 1. Insert Customers (mapped to regions: 1=East, 2=West, 3=Europe, 4=APAC)
INSERT INTO dbo.customers (customer_id, customer_name, company_name, region_id, tier, signup_date, account_status) VALUES
(201, 'Alex Mercer', 'Apex Financial', 1, 'ENTERPRISE', '2023-03-15', 'ACTIVE'),
(202, 'Jordan Lee', 'Pacific Cloud Inc', 2, 'ENTERPRISE', '2022-07-20', 'ACTIVE'),
(203, 'Morgan Taylor', 'Silicon Dynamics', 2, 'ENTERPRISE', '2023-01-10', 'ACTIVE'),
(204, 'Julian Weber', 'Bavaria Logistics', 3, 'GROWTH', '2024-02-18', 'ACTIVE'),
(205, 'Mei Lin', 'Singapore FinTech', 4, 'ENTERPRISE', '2022-11-05', 'ACTIVE'),
(206, 'Rachel Adams', 'Metro Commerce', 1, 'STANDARD', '2024-05-12', 'ACTIVE'),
(207, 'Derek Vance', 'Cascade Analytics', 2, 'GROWTH', '2023-09-01', 'ACTIVE'),
(208, 'Klaus Mueller', 'Rhine Tech GmbH', 3, 'ENTERPRISE', '2021-12-03', 'ACTIVE'),
(209, 'Priya Sharma', 'Indus Retail Corp', 4, 'GROWTH', '2023-06-25', 'ACTIVE'),
(210, 'Samuel King', 'Golden Gate Software', 2, 'ENTERPRISE', '2022-04-14', 'ACTIVE'),
(211, 'Laura Scott', 'Atlantic Health', 1, 'GROWTH', '2024-01-09', 'ACTIVE'),
(212, 'Claire Dupont', 'Seine Solutions', 3, 'STANDARD', '2023-10-30', 'ACTIVE'),
(213, 'Taro Tanaka', 'Nippon Systems', 4, 'ENTERPRISE', '2022-08-19', 'ACTIVE'),
(214, 'Marcus Wright', 'Bayview Data Lab', 2, 'ENTERPRISE', '2023-02-28', 'ACTIVE'),
(215, 'Hannah Bell', 'Liberty Energy', 1, 'STANDARD', '2024-04-17', 'CHURNED');

-- 2. Insert Complaints / Support Tickets (Quarter Q4 2025 and Q1 2026)
-- Note: Region 1 (East) has the highest complaint volume for benchmark queries
INSERT INTO dbo.complaints (complaint_id, customer_id, complaint_date, quarter, category, severity, status, resolution_time_hours) VALUES
(5001, 201, '2025-10-06', 'Q4-2025', 'Billing Discrepancy', 'HIGH', 'RESOLVED', 14.5),
(5002, 206, '2025-10-14', 'Q4-2025', 'Service Outage', 'CRITICAL', 'RESOLVED', 3.2),
(5003, 211, '2025-10-21', 'Q4-2025', 'Data Latency', 'HIGH', 'RESOLVED', 28.0),
(5004, 215, '2025-10-28', 'Q4-2025', 'Invoice Error', 'MEDIUM', 'CLOSED', 48.0),
(5005, 201, '2025-11-04', 'Q4-2025', 'API Rate Limiting', 'HIGH', 'RESOLVED', 8.5),
(5006, 206, '2025-11-11', 'Q4-2025', 'Service Outage', 'CRITICAL', 'RESOLVED', 4.1),
(5007, 211, '2025-11-18', 'Q4-2025', 'Account Lockout', 'MEDIUM', 'RESOLVED', 12.0),
(5008, 201, '2025-11-25', 'Q4-2025', 'Data Discrepancy', 'HIGH', 'RESOLVED', 16.0),
(5009, 215, '2025-12-03', 'Q4-2025', 'Contract Dispute', 'CRITICAL', 'CLOSED', 72.0),
(5010, 206, '2025-12-10', 'Q4-2025', 'Service Degradation', 'HIGH', 'RESOLVED', 6.0),
(5011, 211, '2025-12-16', 'Q4-2025', 'Billing Overcharge', 'HIGH', 'RESOLVED', 22.5),
(5012, 202, '2025-10-15', 'Q4-2025', 'Feature Request', 'LOW', 'CLOSED', 120.0),
(5013, 203, '2025-11-20', 'Q4-2025', 'Slow Dashboard', 'MEDIUM', 'RESOLVED', 36.0),
(5014, 204, '2025-10-18', 'Q4-2025', 'Localization Bug', 'LOW', 'RESOLVED', 44.0),
(5015, 205, '2025-11-12', 'Q4-2025', 'Payment Gateway Timeout', 'HIGH', 'RESOLVED', 18.0),
(5016, 208, '2025-12-05', 'Q4-2025', 'GDPR Data Request', 'MEDIUM', 'RESOLVED', 24.0),
(5017, 209, '2025-12-14', 'Q4-2025', 'Report Export Error', 'LOW', 'RESOLVED', 15.0),
(5018, 201, '2026-01-08', 'Q1-2026', 'SSO Login Failure', 'HIGH', 'RESOLVED', 5.0),
(5019, 206, '2026-01-19', 'Q1-2026', 'Notification Delay', 'MEDIUM', 'RESOLVED', 31.0),
(5020, 202, '2026-02-04', 'Q1-2026', 'Webhook Failure', 'HIGH', 'RESOLVED', 9.5);

-- 3. Provision Strictly Read-Only User & Permissions
USE crm_db;
IF NOT EXISTS (SELECT * FROM sys.server_principals WHERE name = 'readonly_mssql_user')
BEGIN
    CREATE LOGIN readonly_mssql_user WITH PASSWORD = 'readonly_password', CHECK_POLICY = OFF;
END

IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = 'readonly_mssql_user')
BEGIN
    CREATE USER readonly_mssql_user FOR LOGIN readonly_mssql_user;
END

-- Grant database-level read role
ALTER ROLE db_datareader ADD MEMBER readonly_mssql_user;

-- Explicitly deny write and DDL roles
ALTER ROLE db_datawriter DROP MEMBER readonly_mssql_user;
DENY INSERT, UPDATE, DELETE ON SCHEMA::dbo TO readonly_mssql_user;
DENY ALTER ON SCHEMA::dbo TO readonly_mssql_user;
