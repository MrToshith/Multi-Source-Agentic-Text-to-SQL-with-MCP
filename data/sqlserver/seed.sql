-- ==============================================================================
-- Microsoft SQL Server Seed Data: CRM & Customer Support Domain
-- 30 Customers, 60 Complaints, and Read-Only User Setup
-- ==============================================================================

-- 1. Insert 30 Customers (mapped to regions: 1=East, 2=West, 3=Europe, 4=APAC)
-- Note: region_id is a logical relationship to PostgreSQL regions table (no cross-DB FK)
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
(215, 'Hannah Bell', 'Liberty Energy', 1, 'STANDARD', '2024-04-17', 'CHURNED'),
(216, 'Devon Brooks', 'Summit Peak Capital', 2, 'ENTERPRISE', '2023-05-10', 'ACTIVE'),
(217, 'Sofia Rossi', 'Milano Digital SpA', 3, 'GROWTH', '2024-03-01', 'ACTIVE'),
(218, 'Chen Wei', 'Horizon AI Labs', 4, 'ENTERPRISE', '2022-10-15', 'ACTIVE'),
(219, 'Arthur Pendleton', 'Beacon Harbor Media', 1, 'STANDARD', '2024-06-20', 'ACTIVE'),
(220, 'Chloe Nguyen', 'Emerald Bay Tech', 2, 'GROWTH', '2023-08-11', 'ACTIVE'),
(221, 'Lukas Becker', 'Berlin Auto Systems', 3, 'ENTERPRISE', '2022-01-25', 'ACTIVE'),
(222, 'Ananya Patel', 'Deccan Cloud Services', 4, 'GROWTH', '2023-11-19', 'ACTIVE'),
(223, 'Victor Gomez', 'Empire State Logistics', 1, 'GROWTH', '2024-02-05', 'ACTIVE'),
(224, 'Fiona Gallagher', 'Redwood BioTech', 2, 'ENTERPRISE', '2022-09-30', 'ACTIVE'),
(225, 'Matteo Bianchi', 'Alps Semiconductor', 3, 'ENTERPRISE', '2023-04-14', 'ACTIVE'),
(226, 'Nadia Petrova', 'Gotham Securities', 1, 'STANDARD', '2024-07-02', 'ACTIVE'),
(227, 'Kevin Zhang', 'Silicon Wave Networks', 2, 'GROWTH', '2023-12-01', 'ACTIVE'),
(228, 'Elena Rostova', 'Nordic Data Consult', 3, 'GROWTH', '2024-01-18', 'ACTIVE'),
(229, 'Hiroshi Takahashi', 'Tokyo Robotics Ltd', 4, 'ENTERPRISE', '2022-06-08', 'ACTIVE'),
(230, 'Gabriel Ramos', 'Mission Valley SaaS', 2, 'ENTERPRISE', '2023-07-22', 'ACTIVE');

-- 2. Insert 60 Complaints / Support Tickets (Quarter Q4 2025 and Q1 2026)
-- Note: Region 1 (East) customers (201, 206, 211, 215, 219, 223, 226) have the highest complaint volume for benchmark queries
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
(5020, 202, '2026-02-04', 'Q1-2026', 'Webhook Failure', 'HIGH', 'RESOLVED', 9.5),
(5021, 219, '2025-10-10', 'Q4-2025', 'Service Outage', 'CRITICAL', 'RESOLVED', 4.8),
(5022, 223, '2025-10-17', 'Q4-2025', 'Billing Discrepancy', 'HIGH', 'RESOLVED', 19.0),
(5023, 226, '2025-10-24', 'Q4-2025', 'Data Latency', 'HIGH', 'RESOLVED', 26.5),
(5024, 219, '2025-11-05', 'Q4-2025', 'Account Lockout', 'MEDIUM', 'RESOLVED', 11.0),
(5025, 223, '2025-11-12', 'Q4-2025', 'Service Degradation', 'HIGH', 'RESOLVED', 7.5),
(5026, 226, '2025-11-19', 'Q4-2025', 'Invoice Error', 'MEDIUM', 'RESOLVED', 38.0),
(5027, 201, '2025-12-02', 'Q4-2025', 'API Rate Limiting', 'HIGH', 'RESOLVED', 9.0),
(5028, 206, '2025-12-08', 'Q4-2025', 'Service Outage', 'CRITICAL', 'RESOLVED', 3.5),
(5029, 211, '2025-12-15', 'Q4-2025', 'Payment Gateway Timeout', 'HIGH', 'RESOLVED', 14.0),
(5030, 215, '2025-12-22', 'Q4-2025', 'Billing Overcharge', 'HIGH', 'RESOLVED', 21.0),
(5031, 219, '2025-12-28', 'Q4-2025', 'Data Sync Error', 'HIGH', 'RESOLVED', 18.5),
(5032, 223, '2026-01-05', 'Q1-2026', 'SSO Login Failure', 'HIGH', 'RESOLVED', 6.0),
(5033, 226, '2026-01-12', 'Q1-2026', 'Slow Dashboard', 'MEDIUM', 'RESOLVED', 32.0),
(5034, 210, '2025-10-22', 'Q4-2025', 'Slow Dashboard', 'MEDIUM', 'RESOLVED', 29.0),
(5035, 214, '2025-11-15', 'Q4-2025', 'Data Latency', 'HIGH', 'RESOLVED', 20.0),
(5036, 216, '2025-12-01', 'Q4-2025', 'Webhook Failure', 'HIGH', 'RESOLVED', 12.0),
(5037, 220, '2025-12-18', 'Q4-2025', 'Billing Discrepancy', 'HIGH', 'RESOLVED', 16.5),
(5038, 224, '2026-01-15', 'Q1-2026', 'Feature Request', 'LOW', 'CLOSED', 96.0),
(5039, 227, '2026-01-22', 'Q1-2026', 'Service Degradation', 'MEDIUM', 'RESOLVED', 15.0),
(5040, 230, '2026-02-10', 'Q1-2026', 'API Rate Limiting', 'HIGH', 'RESOLVED', 8.0),
(5041, 207, '2025-11-08', 'Q4-2025', 'Report Export Error', 'LOW', 'RESOLVED', 10.0),
(5042, 217, '2025-10-29', 'Q4-2025', 'Localization Bug', 'LOW', 'RESOLVED', 35.0),
(5043, 221, '2025-11-27', 'Q4-2025', 'GDPR Data Request', 'MEDIUM', 'RESOLVED', 22.0),
(5044, 225, '2025-12-20', 'Q4-2025', 'Invoice Error', 'MEDIUM', 'RESOLVED', 42.0),
(5045, 228, '2026-01-18', 'Q1-2026', 'Slow Dashboard', 'MEDIUM', 'RESOLVED', 28.0),
(5046, 212, '2025-11-10', 'Q4-2025', 'Service Outage', 'HIGH', 'RESOLVED', 5.5),
(5047, 213, '2025-10-12', 'Q4-2025', 'Payment Gateway Timeout', 'HIGH', 'RESOLVED', 16.0),
(5048, 218, '2025-11-06', 'Q4-2025', 'API Rate Limiting', 'HIGH', 'RESOLVED', 7.0),
(5049, 222, '2025-12-04', 'Q4-2025', 'Data Latency', 'HIGH', 'RESOLVED', 24.0),
(5050, 229, '2026-01-09', 'Q1-2026', 'SSO Login Failure', 'HIGH', 'RESOLVED', 4.5),
(5051, 201, '2026-01-25', 'Q1-2026', 'Invoice Error', 'MEDIUM', 'RESOLVED', 25.0),
(5052, 206, '2026-02-02', 'Q1-2026', 'Data Sync Error', 'HIGH', 'OPEN', NULL),
(5053, 211, '2026-02-14', 'Q1-2026', 'Billing Discrepancy', 'HIGH', 'OPEN', NULL),
(5054, 219, '2026-02-18', 'Q1-2026', 'Service Degradation', 'HIGH', 'ESCALATED', NULL),
(5055, 223, '2026-02-22', 'Q1-2026', 'Account Lockout', 'MEDIUM', 'RESOLVED', 8.0),
(5056, 226, '2026-02-26', 'Q1-2026', 'Service Outage', 'CRITICAL', 'RESOLVED', 2.8),
(5057, 203, '2026-02-12', 'Q1-2026', 'Slow Dashboard', 'MEDIUM', 'RESOLVED', 18.0),
(5058, 204, '2026-02-17', 'Q1-2026', 'Payment Gateway Timeout', 'HIGH', 'OPEN', NULL),
(5059, 205, '2026-02-20', 'Q1-2026', 'Report Export Error', 'LOW', 'RESOLVED', 12.0),
(5060, 208, '2026-02-25', 'Q1-2026', 'Security Vulnerability', 'CRITICAL', 'RESOLVED', 10.0);

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

-- Explicitly ensure read-only status and prevent DDL/write privileges
IF IS_ROLEMEMBER('db_datawriter', 'readonly_mssql_user') = 1
    ALTER ROLE db_datawriter DROP MEMBER readonly_mssql_user;

IF IS_ROLEMEMBER('db_ddladmin', 'readonly_mssql_user') = 1
    ALTER ROLE db_ddladmin DROP MEMBER readonly_mssql_user;

-- Explicitly deny write, alter, drop, and control permissions
DENY INSERT, UPDATE, DELETE ON SCHEMA::dbo TO readonly_mssql_user;
DENY ALTER ON SCHEMA::dbo TO readonly_mssql_user;
DENY CONTROL ON SCHEMA::dbo TO readonly_mssql_user;
