-- ==============================================================================
-- PostgreSQL Database Schema: Sales & Transactions Domain
-- Database: sales_db
-- ==============================================================================

DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS sales_reps CASCADE;
DROP TABLE IF EXISTS regions CASCADE;

-- 1. Regions table (Internal PK)
CREATE TABLE regions (
    region_id SERIAL PRIMARY KEY,
    region_name VARCHAR(50) NOT NULL UNIQUE,
    headquarters VARCHAR(100) NOT NULL
);

-- 2. Sales Representatives table (Internal FK -> regions)
CREATE TABLE sales_reps (
    rep_id SERIAL PRIMARY KEY,
    rep_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    region_id INT NOT NULL REFERENCES regions(region_id)
);

-- 3. Orders table (Internal FKs -> sales_reps, regions; Logical link -> CRM customers)
CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    customer_id INT NOT NULL,  -- Logical relationship to SQL Server dbo.customers(customer_id) (no DB foreign key)
    rep_id INT NOT NULL REFERENCES sales_reps(rep_id),
    region_id INT NOT NULL REFERENCES regions(region_id),
    order_date DATE NOT NULL,
    quarter VARCHAR(10) NOT NULL,
    total_amount NUMERIC(12, 2) NOT NULL,
    status VARCHAR(30) NOT NULL CHECK (status IN ('COMPLETED', 'PENDING', 'CANCELLED', 'REFUNDED'))
);

-- 4. Order Items table (Internal FK -> orders; Logical link -> Products file)
CREATE TABLE order_items (
    item_id SERIAL PRIMARY KEY,
    order_id INT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    product_id INT NOT NULL,  -- Logical relationship to products.csv(product_id) (no DB foreign key)
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(10, 2) NOT NULL,
    subtotal NUMERIC(12, 2) NOT NULL
);

-- Indexes for efficient querying
CREATE INDEX idx_orders_region_id ON orders(region_id);
CREATE INDEX idx_orders_quarter ON orders(quarter);
CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_order_items_product_id ON order_items(product_id);
