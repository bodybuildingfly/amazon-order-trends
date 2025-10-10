-- Remove the enable_scheduled_ingestion column from the user_settings table
ALTER TABLE user_settings DROP COLUMN IF EXISTS enable_scheduled_ingestion;