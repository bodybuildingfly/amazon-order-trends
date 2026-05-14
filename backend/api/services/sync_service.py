import json
import threading
import pytz
import os
from datetime import datetime
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


def check_scheduled_syncs(app):
    """
    Runs every minute to check if any user has a scheduled sync matching the current time
    in the application's global timezone.
    """
    tz_str = os.environ.get('APP_TIMEZONE', 'UTC')
    try:
        tz = pytz.timezone(tz_str)
    except pytz.UnknownTimeZoneError:
        app.logger.warning(f"Unknown timezone '{tz_str}' specified in APP_TIMEZONE. Defaulting to UTC.")
        tz = pytz.utc

    now_local = datetime.now(tz)
    current_time_str = now_local.strftime("%H:%M")

    with app.app_context():
        try:
            with get_db_cursor() as cur:
                cur.execute(
                    """
                    SELECT user_id
                    FROM user_settings
                    WHERE is_auto_sync_enabled = TRUE
                      AND TO_CHAR(auto_sync_time, 'HH24:MI') = %s
                    """,
                    (current_time_str,)
                )
                rows = cur.fetchall()

            for (user_id,) in rows:
                run_scheduled_sync(app, user_id)

        except psycopg2.errors.UndefinedColumn:
            app.logger.warning("Could not check scheduled syncs: schema migration pending.")
        except psycopg2.errors.UndefinedTable:
            app.logger.warning("Could not check scheduled syncs: user_settings table does not exist.")
        except Exception as e:
            app.logger.error(f"Failed to check scheduled syncs: {e}")
