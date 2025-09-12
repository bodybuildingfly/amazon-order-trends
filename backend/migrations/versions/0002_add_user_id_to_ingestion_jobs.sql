-- migrations/versions/0002_add_user_id_to_ingestion_jobs.sql

-- This migration adds the 'user_id' column to the 'ingestion_jobs' table.
-- This is necessary to associate manual ingestion jobs with the user who started them.

ALTER TABLE ingestion_jobs
ADD COLUMN user_id UUID,
ADD CONSTRAINT fk_ingestion_jobs_user
    FOREIGN KEY(user_id)
    REFERENCES users(id)
    ON DELETE SET NULL;
