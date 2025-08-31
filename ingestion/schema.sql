-- ingestion/schema.sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Stores user accounts for authentication
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Key-value store for all application settings
CREATE TABLE IF NOT EXISTS settings (
    key VARCHAR(255) PRIMARY KEY,
    value TEXT,
    is_encrypted BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table to store high-level order information
CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(50) PRIMARY KEY,
    order_placed_date DATE NOT NULL,
    grand_total NUMERIC(10, 2) NOT NULL,
    subscription_discount NUMERIC(10, 2),
    recipient_name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table to store individual items within each order
CREATE TABLE IF NOT EXISTS items (
    item_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id VARCHAR(50) NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    asin VARCHAR(20),
    full_title TEXT NOT NULL,
    short_title VARCHAR(255),
    link TEXT,
    quantity INTEGER NOT NULL,
    price_per_unit NUMERIC(10, 2) NOT NULL,
    is_subscribe_and_save BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_items_asin ON items(asin);
