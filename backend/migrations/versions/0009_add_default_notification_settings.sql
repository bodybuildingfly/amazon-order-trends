-- migrations/versions/0009_add_default_notification_settings.sql

ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS default_notification_threshold_type VARCHAR(20) DEFAULT 'percent';
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS default_notification_threshold_value NUMERIC(10, 2);
