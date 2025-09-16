-- This migration adds the 'notification_seen' column to the 'ingestion_jobs' table.
-- This is used to track whether a notification has been shown to the user for a completed job.

ALTER TABLE ingestion_jobs
ADD COLUMN notification_seen BOOLEAN DEFAULT FALSE;