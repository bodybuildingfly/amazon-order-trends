import json
import threading
import pytz
from flask import current_app
from backend.shared.db import get_db_cursor
from backend.api.extensions import scheduler
import psycopg2.errors

def run_scheduled_sync(app, user_id):
    """
    This function is triggered by the APScheduler to run a scheduled sync.
    It calls the existing run_manual_ingestion_job but logs it as a scheduled job.
    """
    from backend.api.services.ingestion_service import run_manual_ingestion_job

    with app.app_context():
        # Check if a scheduled job is already running to prevent overlap
        with get_db_cursor() as cur:
            cur.execute(
                "SELECT id FROM ingestion_jobs WHERE user_id = %s AND status = 'running' AND job_type = 'scheduled'",
                (user_id,)
            )
            if cur.fetchone():
                app.logger.info(f"Skipping scheduled sync for user {user_id}: a scheduled job is already running.")
                return

        # Create a new scheduled job record
        with get_db_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO ingestion_jobs (user_id, job_type, status, details)
                VALUES (%s, 'scheduled', 'pending', %s) RETURNING id
                """,
                (user_id, json.dumps({'log': ['Scheduled job created...']}))
            )
            job_id = cur.fetchone()[0]

        app.logger.info(f"Starting scheduled sync for user {user_id} (Job ID: {job_id}).")

        # We can reuse run_manual_ingestion_job since it takes the job_id and updates it.
        # Fetch only the last 3 days for scheduled daily syncs to catch errors from the previous execution.
        thread = threading.Thread(
            target=run_manual_ingestion_job,
            kwargs={'app': app, 'user_id': user_id, 'job_id': job_id, 'days': 3, 'debug': False, 'job_type': 'scheduled'}
        )
        thread.daemon = True
        thread.start()


def schedule_auto_sync_for_user(app, user_id):
    """
    Updates the APScheduler job for a given user based on their current settings in DB.
    """
    with app.app_context():
        with get_db_cursor() as cur:
            cur.execute(
                """
                SELECT is_auto_sync_enabled, TO_CHAR(auto_sync_time, 'HH24:MI') as auto_sync_time, auto_sync_timezone
                FROM user_settings WHERE user_id = %s
                """,
                (user_id,)
            )
            row = cur.fetchone()

        job_id = f"auto_sync_user_{user_id}"

        if row:
            is_enabled, sync_time, tz_string = row

            if is_enabled and sync_time:
                hour, minute = sync_time.split(':')

                # Set timezone if provided, otherwise default to UTC
                timezone = pytz.utc
                if tz_string:
                    try:
                        timezone = pytz.timezone(tz_string)
                    except pytz.UnknownTimeZoneError:
                        app.logger.warning(f"Unknown timezone '{tz_string}' for user {user_id}. Defaulting to UTC.")

                # Check if job exists, update it, else add it
                if scheduler.get_job(job_id):
                    scheduler.modify_job(job_id, trigger='cron', hour=hour, minute=minute, timezone=timezone)
                    app.logger.info(f"Updated scheduled sync for user {user_id} to {sync_time} ({timezone}).")
                else:
                    scheduler.add_job(
                        id=job_id,
                        func=run_scheduled_sync,
                        args=[app, user_id],
                        trigger='cron',
                        hour=hour,
                        minute=minute,
                        timezone=timezone,
                        replace_existing=True
                    )
                    app.logger.info(f"Added scheduled sync for user {user_id} at {sync_time} ({timezone}).")
            else:
                # Remove job if disabled or time is missing
                if scheduler.get_job(job_id):
                    scheduler.remove_job(job_id)
                    app.logger.info(f"Removed scheduled sync for user {user_id} (disabled or missing time).")
        else:
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
                app.logger.info(f"Removed scheduled sync for user {user_id} (settings not found).")

def schedule_all_auto_syncs(app):
    """
    On app startup, read all users with auto-sync enabled and add them to the scheduler.
    """
    with app.app_context():
        try:
            with get_db_cursor() as cur:
                cur.execute(
                    """
                    SELECT user_id, is_auto_sync_enabled, TO_CHAR(auto_sync_time, 'HH24:MI') as auto_sync_time, auto_sync_timezone
                    FROM user_settings WHERE is_auto_sync_enabled = TRUE AND auto_sync_time IS NOT NULL
                    """
                )
                rows = cur.fetchall()

            for user_id, is_enabled, sync_time, tz_string in rows:
                hour, minute = sync_time.split(':')

                timezone = pytz.utc
                if tz_string:
                    try:
                        timezone = pytz.timezone(tz_string)
                    except pytz.UnknownTimeZoneError:
                        pass

                job_id = f"auto_sync_user_{user_id}"
                if not scheduler.get_job(job_id):
                    scheduler.add_job(
                        id=job_id,
                        func=run_scheduled_sync,
                        args=[app, user_id],
                        trigger='cron',
                        hour=hour,
                        minute=minute,
                        timezone=timezone,
                        replace_existing=True
                    )
                    app.logger.info(f"Restored scheduled sync for user {user_id} at {sync_time} ({timezone}).")
        except psycopg2.errors.UndefinedColumn:
            app.logger.warning("Could not schedule auto-syncs on startup: schema migration pending.")
        except psycopg2.errors.UndefinedTable:
            app.logger.warning("Could not schedule auto-syncs on startup: user_settings table does not exist.")
        except Exception as e:
            app.logger.error(f"Failed to schedule auto-syncs on startup: {e}")
