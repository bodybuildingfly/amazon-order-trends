-- migrations/versions/0011_add_auto_sync_settings.sql

ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS is_auto_sync_enabled BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS auto_sync_time TIME;
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS auto_sync_timezone VARCHAR(50);
