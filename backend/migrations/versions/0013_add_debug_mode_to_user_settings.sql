-- Add is_debug_mode_enabled to user_settings table
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS is_debug_mode_enabled BOOLEAN DEFAULT FALSE NOT NULL;
