-- 011_drop_auto_sync_timezone.sql

ALTER TABLE user_settings DROP COLUMN IF EXISTS auto_sync_timezone;
