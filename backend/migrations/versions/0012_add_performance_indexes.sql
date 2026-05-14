-- Add indexes to improve query performance for common joins and user filters

CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_items_order_id ON items(order_id);
