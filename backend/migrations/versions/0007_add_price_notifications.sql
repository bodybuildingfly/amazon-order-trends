-- migrations/versions/0007_add_price_notifications.sql

ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS price_change_notification_webhook_url TEXT;

ALTER TABLE tracked_items ADD COLUMN IF NOT EXISTS notification_threshold_type VARCHAR(20) DEFAULT 'percent'; -- 'percent' or 'absolute'
ALTER TABLE tracked_items ADD COLUMN IF NOT EXISTS notification_threshold_value NUMERIC(10, 2);
