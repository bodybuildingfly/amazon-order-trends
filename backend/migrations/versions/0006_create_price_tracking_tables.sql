CREATE TABLE IF NOT EXISTS tracked_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    asin VARCHAR(20),
    url TEXT NOT NULL,
    name TEXT,
    current_price NUMERIC(10, 2),
    currency VARCHAR(10) DEFAULT 'USD',
    last_checked TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_tracked_items_user
        FOREIGN KEY(user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS price_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tracked_item_id UUID NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_price_history_item
        FOREIGN KEY(tracked_item_id)
        REFERENCES tracked_items(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tracked_items_user_id ON tracked_items(user_id);
CREATE INDEX IF NOT EXISTS idx_price_history_item_id ON price_history(tracked_item_id);
