-- ==============================================================================
-- Microsoft SQL Server Database Schema: CRM & Customer Support Domain
-- Database: crm_db
-- ==============================================================================

IF OBJECT_ID('dbo.complaints', 'U') IS NOT NULL DROP TABLE dbo.complaints;
IF OBJECT_ID('dbo.customers', 'U') IS NOT NULL DROP TABLE dbo.customers;

-- Customers table
CREATE TABLE dbo.customers (
    customer_id INT PRIMARY KEY,
    customer_name NVARCHAR(100) NOT NULL,
    company_name NVARCHAR(100) NOT NULL,
    region_id INT NOT NULL,  -- Relational link to PostgreSQL regions
    tier NVARCHAR(20) NOT NULL CHECK (tier IN ('ENTERPRISE', 'GROWTH', 'STANDARD')),
    signup_date DATE NOT NULL,
    account_status NVARCHAR(20) NOT NULL CHECK (account_status IN ('ACTIVE', 'CHURNED', 'SUSPENDED'))
);

-- Complaints / Support Tickets table
CREATE TABLE dbo.complaints (
    complaint_id INT PRIMARY KEY,
    customer_id INT NOT NULL REFERENCES dbo.customers(customer_id),
    complaint_date DATE NOT NULL,
    quarter NVARCHAR(10) NOT NULL,
    category NVARCHAR(50) NOT NULL,
    severity NVARCHAR(20) NOT NULL CHECK (severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    status NVARCHAR(20) NOT NULL CHECK (status IN ('OPEN', 'RESOLVED', 'ESCALATED', 'CLOSED')),
    resolution_time_hours NUMERIC(6, 2) NULL
);

-- Indexes for efficient querying
CREATE INDEX idx_customers_region_id ON dbo.customers(region_id);
CREATE INDEX idx_complaints_customer_id ON dbo.complaints(customer_id);
CREATE INDEX idx_complaints_quarter ON dbo.complaints(quarter);
CREATE INDEX idx_complaints_severity ON dbo.complaints(severity);
