import json
import threading
from datetime import datetime
from flask import Flask, current_app

from backend.shared.db import get_db_cursor
from backend.ingestion.ingestion_script import main as run_ingestion_generator
from backend.api.services.notification_service import send_discord_notification

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
            
            app.logger.info(f"Manual ingestion job {job_id} finished for user {user_id}. Checking for notifications...")
            try:
                with get_db_cursor() as cur:
                    # For manual jobs, we now use the admin's settings globally.
                    # First, get the admin user's ID by their role.
                    cur.execute("SELECT id FROM users WHERE role = 'admin' ORDER BY created_at ASC LIMIT 1")
                    admin_user_result = cur.fetchone()
                    
                    if not admin_user_result:
                        app.logger.error("Could not find an admin user to use for global notifications.")
                        settings = None
                    else:
                        admin_user_id = admin_user_result[0]
                        app.logger.info(f"Found admin user with ID {admin_user_id} for global notification settings.")
                        cur.execute(
                            "SELECT discord_webhook_url, discord_notification_preference FROM user_settings WHERE user_id = %s",
                            (admin_user_id,)
                        )
                        settings = cur.fetchone()
                
                if settings:
                    webhook_url, pref = settings
                    job_has_error = bool(details.get('error'))
                    app.logger.info(f"[Notification Check] User: {user_id}, Job: {job_id}, Webhook Present: {bool(webhook_url)}, Preference: '{pref}', Job Has Error: {job_has_error}")

                    should_send = False
                    if webhook_url:
                        if pref == 'always':
                            should_send = True
                        elif pref == 'errors_only' and job_has_error:
                            should_send = True
                    
                    app.logger.info(f"[Notification Check] Final decision for job {job_id}: should_send = {should_send}")

                    if should_send:
                        app.logger.info(f"Preparing to send notification for manual job {job_id}...")
                        if job_has_error:
                            title = f"Manual Ingestion Job Failed (ID: {job_id})"
                            description = "Your manually triggered ingestion job has failed."
                            color = 15158332  # Red
                        else:
                            title = f"Manual Ingestion Job Completed (ID: {job_id})"
                            description = "Your manually triggered ingestion job has finished successfully."
                            color = 3066993  # Green
                        
                        send_discord_notification(webhook_url, title, description, color, details.get('log', []))
                else:
                    app.logger.info(f"No notification settings found for user {user_id}.")
            except Exception as e:
                app.logger.error(f"Failed to send notification for manual job {job_id}: {e}", exc_info=True)
