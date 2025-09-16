-- Add ongoing_data_retrieval_enabled to users table
-- This migration adds a boolean column to the users table to allow users
-- to opt-in to ongoing, scheduled data retrieval.

ALTER TABLE users ADD COLUMN ongoing_data_retrieval_enabled BOOLEAN NOT NULL DEFAULT FALSE;
