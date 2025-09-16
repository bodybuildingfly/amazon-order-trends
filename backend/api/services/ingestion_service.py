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
            # 4. Send notification
            notification_user_id = triggered_by_user_id
            is_automated_run = not bool(triggered_by_user_id)

            if is_automated_run:
                # Automated run, send summary to admin (user_id='1')
                notification_user_id = '1'
                app.logger.info(f"Job {job_id} was an automated run. Attempting to send summary to admin (user_id='1').")
            else:
                app.logger.info(f"Job {job_id} was manually triggered by user {notification_user_id}. Checking preferences.")

            if notification_user_id:
                try:
                    with get_db_cursor() as cur:
                        cur.execute(
                            "SELECT discord_webhook_url, discord_notification_preference FROM user_settings WHERE user_id = %s",
                            (notification_user_id,)
                        )
                        settings = cur.fetchone()
                    
                    app.logger.info(f"Found notification settings for user {notification_user_id}: {settings}")

                    if settings:
                        webhook_url, pref = settings
                        
                        # For automated runs, we always send if a webhook is present, ignoring the 'errors_only' preference for the admin.
                        # For manual runs, we respect the user's preference.
                        overall_status_is_error = job_failed or any(u.get('status') == 'failed' for u in details.get('users', {}).values())
                        
                        should_send = False
                        if webhook_url:
                            if is_automated_run:
                                should_send = True
                                app.logger.info("Sending notification for automated run to admin.")
                            else: # Manually triggered run
                                if pref == 'always':
                                    should_send = True
                                    app.logger.info("Notification preference is 'always'.")
                                elif pref == 'errors_only' and overall_status_is_error:
                                    should_send = True
                                    app.logger.info("Notification preference is 'errors_only' and the job has errors.")
                        
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

                            # Modify title for automated runs
                            base_title = "Scheduled Ingestion Run Finished"
                            if is_automated_run:
                                base_title = "Automated Daily Ingestion Finished"

                            if overall_status_is_error:
                                title = f"{base_title} with Errors"
                                description = "The scheduled data ingestion process ran, but one or more users failed."
                                color = 15158332  # Red
                            else:
                                title = f"{base_title} Successfully"
                                description = "The scheduled data ingestion process completed for all users."
                                color = 3066993  # Green
                            
                            send_discord_notification(webhook_url, title, description, color, all_logs)
                    else:
                        app.logger.info(f"No notification settings found for user {notification_user_id}, no notification will be sent.")
                except Exception as e:
                    app.logger.error(f"Failed to send Discord notification for job {job_id}: {e}", exc_info=True)
