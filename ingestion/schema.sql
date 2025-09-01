-- ingestion/schema.sql
-- Create a UUID extension if it doesn't exist.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table to store user login information
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table to store user-specific settings
CREATE TABLE IF NOT EXISTS user_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE NOT NULL,
    amazon_email VARCHAR(255),
    amazon_password_encrypted BYTEA, -- Correct data type for encrypted data
    amazon_otp_secret_key VARCHAR(255),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_user
        FOREIGN KEY(user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);

-- Table to store high-level order information
CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(50) PRIMARY KEY,
    user_id UUID NOT NULL,
    order_placed_date DATE NOT NULL,
    grand_total NUMERIC(10, 2) NOT NULL,
    subscription_discount NUMERIC(10, 2),
    recipient_name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_orders_user
        FOREIGN KEY(user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);

-- Table to store individual items within each order
CREATE TABLE IF NOT EXISTS items (
    item_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id VARCHAR(50) NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    asin VARCHAR(20),
    full_title TEXT NOT NULL,
    link TEXT,
    thumbnail_url TEXT,
    quantity INTEGER NOT NULL,
    price_per_unit NUMERIC(10, 2) NOT NULL,
    is_subscribe_and_save BOOLEAN DEFAULT FALSE,
    -- Add a unique constraint to prevent duplicate items per order
    UNIQUE(order_id, full_title, price_per_unit)
);

CREATE INDEX IF NOT EXISTS idx_items_asin ON items(asin);