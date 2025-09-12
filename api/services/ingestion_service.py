import json
import threading
from datetime import datetime
from flask import Flask, current_app

from shared.db import get_db_cursor
from ingestion.ingestion_script import main as run_ingestion_generator
from api.services.notification_service import send_discord_notification

def run_manual_ingestion_job(app: Flask, user_id: str, job_id: int, days: int):
    """
    Runs the ingestion process in a background thread for a single user
    and updates the job status in the database.
    """
    with app.app_context():
        # Initialize job details in the database
        log = ["Job started..."]
        progress = {"value": 0, "max": 100}
        details = {"log": log, "error": None}
        
        try:
            with get_db_cursor(commit=True) as cur:
                cur.execute(
                    "UPDATE ingestion_jobs SET status = 'running', progress = %s, details = %s WHERE id = %s",
                    (json.dumps(progress), json.dumps(details), job_id)
                )

            app.logger.info(f"Starting manual ingestion for user {user_id} (Job ID: {job_id}) for {days} days.")
            
            # The core ingestion logic
            for event_type, data in run_ingestion_generator(user_id=user_id, manual_days_override=days):
                if event_type == 'status':
                    log.append(data)
                    details['log'] = log
                    with get_db_cursor(commit=True) as cur:
                        cur.execute("UPDATE ingestion_jobs SET details = %s WHERE id = %s", (json.dumps(details), job_id))
                
                elif event_type == 'progress':
                    progress = data
                    with get_db_cursor(commit=True) as cur:
                        cur.execute("UPDATE ingestion_jobs SET progress = %s WHERE id = %s", (json.dumps(progress), job_id))

                elif event_type == 'error':
                    log.append(f"ERROR: {data}")
                    details['log'] = log
                    details['error'] = data
                    with get_db_cursor(commit=True) as cur:
                        cur.execute(
                            "UPDATE ingestion_jobs SET status = 'failed', details = %s WHERE id = %s",
                            (json.dumps(details), job_id)
                        )

                elif event_type == 'done':
                    log.append(data)
                    details['log'] = log
                    with get_db_cursor(commit=True) as cur:
                        cur.execute("UPDATE ingestion_jobs SET details = %s WHERE id = %s", (json.dumps(details), job_id))

            # Finalize job status
            with get_db_cursor(commit=True) as cur:
                # Check current status to avoid overwriting a 'failed' status
                cur.execute("SELECT status FROM ingestion_jobs WHERE id = %s", (job_id,))
                current_status = cur.fetchone()[0]
                if current_status == 'running':
                    cur.execute("UPDATE ingestion_jobs SET status = 'completed' WHERE id = %s", (job_id,))

        except Exception as e:
            app.logger.error(f"Manual ingestion job {job_id} failed for user {user_id}: {e}", exc_info=True)
            details['error'] = str(e)
            with get_db_cursor(commit=True) as cur:
                cur.execute(
                    "UPDATE ingestion_jobs SET status = 'failed', details = %s WHERE id = %s",
                    (json.dumps(details), job_id)
                )
        finally:
            with get_db_cursor(commit=True) as cur:
                cur.execute("UPDATE ingestion_jobs SET updated_at = %s WHERE id = %s", (datetime.utcnow(), job_id))
            app.logger.info(f"Manual ingestion job {job_id} finished for user {user_id}.")


def run_scheduled_ingestion_job_stream(job_id, triggered_by_user_id=None):
    """
    Runs the ingestion process for all enabled users and yields progress updates.
    This is a generator function.
    If triggered_by_user_id is provided, it will send a Discord notification
    to that user upon completion.
    """
    app = current_app._get_current_object()
    with app.app_context():
        details = {}
        job_failed = False
        try:
            # 1. Get users and initialize job details
            with get_db_cursor(commit=True) as cur:
                cur.execute(
                    """
                    SELECT u.id, u.username FROM users u
                    JOIN user_settings s ON u.id = s.user_id
                    WHERE s.enable_scheduled_ingestion = TRUE
                    """
                )
                users_to_process = cur.fetchall()

            user_map = {str(user_id): username for user_id, username in users_to_process}
            user_ids = list(user_map.keys())
            
            progress = {"current": 0, "total": len(user_ids)}
            details = {'users': {uid: {'status': 'pending', 'username': user_map[uid], 'log': []} for uid in user_ids}}

            with get_db_cursor(commit=True) as cur:
                cur.execute(
                    "UPDATE ingestion_jobs SET status = 'running', progress = %s, details = %s WHERE id = %s",
                    (json.dumps(progress), json.dumps(details), job_id)
                )
            yield {'type': 'job_update', 'payload': {'id': str(job_id), 'status': 'running', 'progress': progress, 'details': details}}

            # 2. Loop through users and run ingestion
            for i, user_id in enumerate(user_ids):
                details['users'][user_id]['status'] = 'running'
                progress['current'] = i
                
                with get_db_cursor(commit=True) as cur:
                    cur.execute("UPDATE ingestion_jobs SET progress = %s, details = %s WHERE id = %s", (json.dumps(progress), json.dumps(details), job_id))
                yield {'type': 'job_update', 'payload': {'progress': progress, 'details': details}}

                try:
                    for event_type, data in run_ingestion_generator(user_id=user_id, manual_days_override=3):
                        # Add to log for webhook, but filter out progress updates
                        if event_type != 'progress':
                            log_entry = f"{event_type}: {data}"
                            details['users'][user_id]['log'].append(log_entry)
                    details['users'][user_id]['status'] = 'completed'
                except Exception as e:
                    app.logger.error(f"Ingestion failed for user {user_id} in job {job_id}: {e}", exc_info=True)
                    details['users'][user_id]['status'] = 'failed'
                    details['users'][user_id]['error'] = str(e)
                
                with get_db_cursor(commit=True) as cur:
                    cur.execute("UPDATE ingestion_jobs SET details = %s WHERE id = %s", (json.dumps(details), job_id))
                yield {'type': 'job_update', 'payload': {'details': details}}
            
            # 3. Finalize job
            progress['current'] = len(user_ids)
            with get_db_cursor(commit=True) as cur:
                cur.execute(
                    "UPDATE ingestion_jobs SET status = 'completed', progress = %s, details = %s WHERE id = %s",
                    (json.dumps(progress), json.dumps(details), job_id)
                )
            yield {'type': 'job_update', 'payload': {'status': 'completed', 'progress': progress, 'details': details}}

        except Exception as e:
            job_failed = True
            app.logger.error(f"Scheduled ingestion job {job_id} failed: {e}", exc_info=True)
            # Update details with the overarching error
            if 'error' not in details: details['error'] = 'Job failed during initialization.'
            with get_db_cursor(commit=True) as cur:
                cur.execute("UPDATE ingestion_jobs SET status = 'failed', details = %s WHERE id = %s", (json.dumps(details), job_id))
            yield {'type': 'error', 'payload': str(e)}
        finally:
            # 4. Send notification if manually triggered
            app.logger.info(f"Notification check for job {job_id}. Triggered by user: {triggered_by_user_id}")
            if triggered_by_user_id:
                try:
                    with get_db_cursor() as cur:
                        cur.execute(
                            "SELECT discord_webhook_url, discord_notification_preference FROM user_settings WHERE user_id = %s",
                            (triggered_by_user_id,)
                        )
                        settings = cur.fetchone()
                    
                    app.logger.info(f"Found settings for user {triggered_by_user_id}: {settings}")

                    if settings:
                        webhook_url, pref = settings
                        app.logger.info(f"Webhook URL: '{webhook_url}', Preference: '{pref}'")
                        
                        overall_status_is_error = job_failed or any(u.get('status') == 'failed' for u in details.get('users', {}).values())
                        app.logger.info(f"Overall job status is_error: {overall_status_is_error}")

                        should_send = bool(webhook_url)
                        app.logger.info(f"Final decision to send notification: {should_send}")

                        if should_send:
                            app.logger.info(f"Preparing to send notification for job {job_id}...")
                            all_logs = []
                            if details.get('error'):
                                all_logs.append(f"CRITICAL JOB ERROR: {details['error']}\n")

                            for uid, u_details in details.get('users', {}).items():
                                username = u_details.get('username', 'Unknown User')
                                status = u_details.get('status', 'unknown').upper()
                                all_logs.append(f"--- User: {username} | Status: {status} ---")
                                all_logs.extend(u_details.get('log', ['No log entries.']))
                                if u_details.get('status') == 'failed':
                                    all_logs.append(f"ERROR: {u_details.get('error', 'Unknown error')}")
                                all_logs.append("")

                            if overall_status_is_error:
                                title = "Scheduled Ingestion Run Finished with Errors"
                                description = "The scheduled data ingestion process ran, but one or more users failed."
                                color = 15158332  # Red
                            else:
                                title = "Scheduled Ingestion Run Successful"
                                description = "The scheduled data ingestion process completed for all users."
                                color = 3066993  # Green
                            
                            send_discord_notification(webhook_url, title, description, color, all_logs)
                    else:
                        app.logger.info(f"No settings found for triggering user {triggered_by_user_id}, no notification will be sent.")
                except Exception as e:
                    app.logger.error(f"Failed to send Discord notification for job {job_id}: {e}", exc_info=True)
            else:
                app.logger.info(f"Job was not manually triggered, skipping notification.")
