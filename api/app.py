# api/app.py
from gevent import monkey
monkey.patch_all()

import os
import sys
import logging
import base64
import hashlib
import subprocess
import json
import requests
import threading
from datetime import timedelta, datetime
from functools import wraps
from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, JWTManager, jwt_required, get_jwt_identity, get_jwt
from cryptography.fernet import Fernet
from flask_apscheduler import APScheduler

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.db import get_db_cursor
from ingestion.ingestion_script import main as run_ingestion_generator

# --- App Initialization & Config ---
app = Flask(__name__, static_folder='../frontend/build', static_url_path='/')
CORS(app, supports_credentials=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Scheduler Setup ---
scheduler = APScheduler()
scheduler.init_app(app)

app.config["JWT_SECRET_KEY"] = os.environ.get('JWT_SECRET_KEY', 'default-secret-key-for-dev')
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=1)
app.config["JWT_TOKEN_LOCATION"] = ["headers", "query_string"]
app.config["JWT_QUERY_STRING_NAME"] = "token"
jwt = JWTManager(app)

# --- In-memory store for manual ingestion jobs ---
manual_import_jobs = {}
manual_import_jobs_lock = threading.Lock()

# --- Encryption Setup ---
fernet = None
def initialize_fernet():
    global fernet
    encryption_key = os.environ.get('ENCRYPTION_KEY')
    if not encryption_key:
        raise ValueError("ENCRYPTION_KEY is not set.")
    key_digest = hashlib.sha256(encryption_key.encode('utf-8')).digest()
    derived_key = base64.urlsafe_b64encode(key_digest)
    fernet = Fernet(derived_key)

# --- Decorators ---
def admin_required():
    def wrapper(fn):
        @wraps(fn)
        @jwt_required()
        def decorator(*args, **kwargs):
            claims = get_jwt()
            if claims.get("role") != "admin":
                return jsonify(error="Admins only!"), 403
            return fn(*args, **kwargs)
        return decorator
    return wrapper

# --- Database Initialization Command ---
@app.cli.command("init-db")
def init_db_command():
    """Creates tables and initial admin user if they don't exist."""
    try:
        with get_db_cursor(commit=True) as cur:
            app.logger.info("Ensuring database schema exists...")
            schema_path = os.path.join(os.path.dirname(__file__), '../ingestion/schema.sql')
            with open(schema_path, 'r') as f:
                cur.execute(f.read())
            
            admin_user = os.environ.get("ADMIN_USERNAME", "admin")
            admin_pass = os.environ.get("ADMIN_PASSWORD", "changeme")

            cur.execute("SELECT id FROM users WHERE username = %s", (admin_user,))
            if cur.fetchone() is None:
                app.logger.info(f"Creating initial admin user: '{admin_user}'")
                hashed_password = generate_password_hash(admin_pass)
                cur.execute(
                    "INSERT INTO users (username, hashed_password, role) VALUES (%s, %s, 'admin')",
                    (admin_user, hashed_password)
                )
            else:
                app.logger.info("Admin user already exists.")
            
            cur.execute("SELECT COUNT(*) FROM orders")
            order_count = cur.fetchone()[0]
            if order_count == 0:
                app.logger.info("Database is empty. Please log in, save your settings, and run the initial data import.")

        app.logger.info("Database initialization check complete.")
    except Exception as e:
        app.logger.error(f"An error occurred during DB initialization: {e}")

# --- API Endpoints ---
@app.route("/api/auth/login", methods=['POST'])
def login():
    username = request.json.get("username", None)
    password = request.json.get("password", None)
    
    with get_db_cursor() as cur:
        cur.execute("SELECT id, hashed_password, role FROM users WHERE username = %s", (username,))
        user = cur.fetchone()

    if user and check_password_hash(user[1], password):
        user_id = str(user[0])
        user_role = user[2]
        additional_claims = {"role": user_role}
        access_token = create_access_token(identity=user_id, additional_claims=additional_claims)
        return jsonify(token=access_token, role=user_role)
    
    return jsonify({"msg": "Bad username or password"}), 401


# --- User Management Endpoints ---

@app.route("/api/users", methods=['GET'])
@admin_required()
def get_users():
    """Returns a list of all users."""
    try:
        with get_db_cursor() as cur:
            cur.execute("SELECT id, username, role, created_at FROM users ORDER BY username")
            users = [dict(zip([desc[0] for desc in cur.description], row)) for row in cur.fetchall()]
        return jsonify(users)
    except Exception as e:
        app.logger.error(f"Failed to fetch users: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch users."}), 500

@app.route("/api/users", methods=['POST'])
@admin_required()
def add_user():
    """Adds a new user to the database."""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'user')

    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400
    if role not in ['admin', 'user']:
        return jsonify({"error": "Invalid role specified."}), 400

    hashed_password = generate_password_hash(password)
    try:
        with get_db_cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO users (username, hashed_password, role) VALUES (%s, %s, %s) RETURNING id, created_at",
                (username, hashed_password, role)
            )
            new_user = cur.fetchone()
            return jsonify({
                "id": new_user[0],
                "username": username,
                "role": role,
                "created_at": new_user[1]
            }), 201
    except Exception as e:
        app.logger.error(f"Failed to add user '{username}': {e}", exc_info=True)
        # Unique constraint violation error code for psycopg2
        if hasattr(e, 'pgcode') and e.pgcode == '23505':
            return jsonify({"error": f"Username '{username}' already exists."}), 409
        return jsonify({"error": "Failed to create user."}), 500

@app.route("/api/users/<uuid:user_id>/reset-password", methods=['POST'])
@admin_required()
def reset_password(user_id):
    """Resets a user's password."""
    data = request.get_json()
    password = data.get('password')

    if not password:
        return jsonify({"error": "Password is required."}), 400

    hashed_password = generate_password_hash(password)
    try:
        with get_db_cursor(commit=True) as cur:
            cur.execute("UPDATE users SET hashed_password = %s WHERE id = %s", (hashed_password, user_id))
            if cur.rowcount == 0:
                return jsonify({"error": "User not found."}), 404
        return jsonify({"message": "Password has been reset successfully."})
    except Exception as e:
        app.logger.error(f"Failed to reset password for user {user_id}: {e}", exc_info=True)
        return jsonify({"error": "Failed to reset password."}), 500

@app.route("/api/users/<uuid:user_id>", methods=['DELETE'])
@admin_required()
def delete_user(user_id):
    """Deletes a user from the database."""
    current_user_id = get_jwt_identity()
    if str(user_id) == current_user_id:
        return jsonify({"error": "You cannot delete your own account."}), 400

    try:
        with get_db_cursor(commit=True) as cur:
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            if cur.rowcount == 0:
                return jsonify({"error": "User not found."}), 404
        return jsonify({"message": "User deleted successfully."})
    except Exception as e:
        app.logger.error(f"Failed to delete user {user_id}: {e}", exc_info=True)
        return jsonify({"error": "Failed to delete user."}), 500

@app.route('/api/settings', methods=['GET'])
@jwt_required()
def get_settings():
    try:
        current_user_id = get_jwt_identity()
        with get_db_cursor() as cur:
            cur.execute(
                """SELECT amazon_email, amazon_password_encrypted, amazon_otp_secret_key, 
                          enable_scheduled_ingestion, discord_webhook_url, discord_notification_preference 
                   FROM user_settings WHERE user_id = %s""",
                (current_user_id,)
            )
            settings_row = cur.fetchone()

        if settings_row:
            email, password_encrypted, otp, enable_scheduled_ingestion, webhook_url, notification_pref = settings_row
            return jsonify({
                "is_configured": bool(email and password_encrypted),
                "amazon_email": email or '',
                "amazon_otp_secret_key": otp or '',
                "enable_scheduled_ingestion": enable_scheduled_ingestion,
                "discord_webhook_url": webhook_url or '',
                "discord_notification_preference": notification_pref or 'off',
            }), 200
        else:
            # If no settings row exists, return defaults
            return jsonify({
                "is_configured": False,
                "amazon_email": '',
                "amazon_otp_secret_key": '',
                "enable_scheduled_ingestion": False,
                "discord_webhook_url": '',
                "discord_notification_preference": 'off',
            }), 200
    except Exception as e:
        app.logger.error(f"Failed to get settings: {e}", exc_info=True)
        return jsonify({"error": "Failed to retrieve settings."}), 500

@app.route('/api/settings/user', methods=['POST'])
@jwt_required()
def save_user_settings():
    data = request.get_json()
    current_user_id = get_jwt_identity()

    try:
        initialize_fernet()
        email = data.get('amazon_email')
        password = data.get('amazon_password')
        otp = data.get('amazon_otp_secret_key')
        enable_scheduled_ingestion = data.get('enable_scheduled_ingestion', False)

        with get_db_cursor(commit=True) as cur:
            # Logic to insert or update user settings
            if password:
                encrypted_password = fernet.encrypt(password.encode('utf-8'))
                cur.execute("""
                    INSERT INTO user_settings (user_id, amazon_email, amazon_password_encrypted, amazon_otp_secret_key, enable_scheduled_ingestion)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        amazon_email = EXCLUDED.amazon_email,
                        amazon_password_encrypted = EXCLUDED.amazon_password_encrypted,
                        amazon_otp_secret_key = EXCLUDED.amazon_otp_secret_key,
                        enable_scheduled_ingestion = EXCLUDED.enable_scheduled_ingestion;
                """, (current_user_id, email, encrypted_password, otp, enable_scheduled_ingestion))
            else:
                cur.execute("""
                    UPDATE user_settings SET
                        amazon_email = %s,
                        amazon_otp_secret_key = %s,
                        enable_scheduled_ingestion = %s
                    WHERE user_id = %s;
                """, (email, otp, enable_scheduled_ingestion, current_user_id))
                if cur.rowcount == 0:
                    cur.execute("""
                        INSERT INTO user_settings (user_id, amazon_email, amazon_otp_secret_key, enable_scheduled_ingestion)
                        VALUES (%s, %s, %s, %s);
                    """, (current_user_id, email, otp, enable_scheduled_ingestion))

        return jsonify({"message": "User settings saved successfully."}), 200
    except Exception as e:
        app.logger.error(f"Failed to save user settings: {e}", exc_info=True)
        return jsonify({"error": "Failed to save user settings."}), 500

@app.route('/api/settings/admin', methods=['POST'])
@admin_required()
def save_admin_settings():
    data = request.get_json()
    # In a multi-user admin scenario, you might get a user_id from the request.
    # For now, we assume an admin is editing their own settings or a global setting.
    # As discord settings are per-user, we'll get the current user's ID.
    current_user_id = get_jwt_identity()
    
    try:
        discord_webhook_url = data.get('discord_webhook_url')
        discord_notification_preference = data.get('discord_notification_preference', 'off')

        with get_db_cursor(commit=True) as cur:
            cur.execute("""
                UPDATE user_settings SET
                    discord_webhook_url = %s,
                    discord_notification_preference = %s
                WHERE user_id = %s;
            """, (discord_webhook_url, discord_notification_preference, current_user_id))
            if cur.rowcount == 0:
                # This assumes a user_settings row has been created before saving admin settings.
                # This is a reasonable assumption if the user has to save user settings first.
                cur.execute("""
                    INSERT INTO user_settings (user_id, discord_webhook_url, discord_notification_preference)
                    VALUES (%s, %s, %s);
                """, (current_user_id, discord_webhook_url, discord_notification_preference))
        
        return jsonify({"message": "Admin settings saved successfully."}), 200
    except Exception as e:
        app.logger.error(f"Failed to save admin settings: {e}", exc_info=True)
        return jsonify({"error": "Failed to save admin settings."}), 500

def _run_manual_ingestion_job(user_id, days):
    """
    Runs the ingestion process in a background thread for a single user
    and updates the in-memory job store.
    """
    with app.app_context():
        job_status = {
            "status": "running",
            "progress": {"value": 0, "max": 100},
            "log": ["Job started..."],
            "start_time": datetime.utcnow().isoformat(),
            "end_time": None,
            "error": None
        }
        with manual_import_jobs_lock:
            manual_import_jobs[user_id] = job_status

        try:
            app.logger.info(f"Starting manual ingestion for user {user_id} for {days} days.")
            for event_type, data in run_ingestion_generator(user_id=user_id, manual_days_override=days):
                with manual_import_jobs_lock:
                    if event_type == 'status':
                        job_status['log'].append(data)
                    elif event_type == 'progress':
                        job_status['progress'] = data
                    elif event_type == 'error':
                        job_status['status'] = 'failed'
                        job_status['error'] = data
                        job_status['log'].append(f"ERROR: {data}")
                    elif event_type == 'done':
                        job_status['log'].append(data)
            
            # If the generator finishes without error, mark as completed
            with manual_import_jobs_lock:
                if job_status['status'] == 'running':
                    job_status['status'] = 'completed'

        except Exception as e:
            app.logger.error(f"Manual ingestion job failed for user {user_id}: {e}", exc_info=True)
            with manual_import_jobs_lock:
                job_status['status'] = 'failed'
                job_status['error'] = str(e)
        finally:
            with manual_import_jobs_lock:
                job_status['end_time'] = datetime.utcnow().isoformat()
            app.logger.info(f"Manual ingestion job finished for user {user_id} with status: {job_status['status']}")


@app.route("/api/ingestion/run", methods=['POST'])
@jwt_required()
def run_ingestion_route():
    current_user_id = get_jwt_identity()
    data = request.get_json()
    days = data.get('days', 60)

    with manual_import_jobs_lock:
        if manual_import_jobs.get(current_user_id, {}).get('status') == 'running':
            return jsonify({"error": "An import is already in progress for this user."}), 409

        # Clean up old job data before starting a new one
        manual_import_jobs.pop(current_user_id, None)

    # Start the ingestion in a background thread
    thread = threading.Thread(target=_run_manual_ingestion_job, args=(current_user_id, days))
    thread.daemon = True
    thread.start()

    return jsonify({"message": "Manual import process started."}), 202


@app.route("/api/ingestion/manual/status", methods=['GET'])
@jwt_required()
def get_manual_ingestion_status():
    current_user_id = get_jwt_identity()
    with manual_import_jobs_lock:
        job_status = manual_import_jobs.get(current_user_id)

    if not job_status:
        return jsonify(None)

    # If job is completed or failed, remove it after some time to conserve memory
    # For this implementation, we'll let the user clear it by starting a new job.
    # A more robust solution could use a TTL cache.
    return jsonify(job_status)


@app.route("/api/amazon-logout", methods=['POST'])
@jwt_required()
def amazon_logout():
    try:
        result = subprocess.run(["amazon-orders", "logout"], capture_output=True, text=True, check=True)
        return jsonify({"message": "Amazon session logout successful.", "output": result.stdout}), 200
    except Exception as e:
        app.logger.error(f"Amazon logout command failed: {e}", exc_info=True)
        return jsonify({"error": "Failed to execute Amazon logout command."}), 500

def send_discord_notification(webhook_url, title, description, color, log_messages):
    """Sends a formatted notification to a Discord webhook."""
    if not webhook_url:
        return

    # Truncate log messages to fit within Discord's description limits (4096 chars)
    log_content = "\n".join(log_messages)
    if len(log_content) > 3800:
        log_content = log_content[:3800] + "\n... (log truncated)"
    
    full_description = description + f"\n\n**Verbose Log:**\n```\n{log_content}\n```"
    
    embed = {
        "title": title,
        "description": full_description,
        "color": color,
        "footer": {
            "text": f"Report generated at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        }
    }

    try:
        app.logger.info(f"Sending Discord notification to {webhook_url[:30]}...")
        response = requests.post(webhook_url, json={"embeds": [embed]}, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        app.logger.info(f"Successfully sent Discord notification.")
    except requests.exceptions.RequestException as e:
        # Log the exception and the response body if available
        error_message = f"Failed to send Discord notification: {e}"
        if e.response is not None:
            error_message += f"\nResponse Status Code: {e.response.status_code}"
            error_message += f"\nResponse Body: {e.response.text}"
        app.logger.error(error_message)

def _run_scheduled_ingestion_job(job_id, triggered_by_user_id=None):
    """
    Runs the ingestion process for all enabled users and yields progress updates.
    This is a generator function.
    If triggered_by_user_id is provided, it will send a Discord notification
    to that user upon completion.
    """
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

                        # For a manually triggered run, always send a notification if a webhook is configured.
                        should_send = bool(webhook_url)
                        app.logger.info(f"Final decision to send notification: {should_send}")

                        if should_send:
                            app.logger.info(f"Preparing to send notification for job {job_id}...")
                            # Consolidate logs from all users
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


@app.route("/api/scheduler/run", methods=['GET'])
@admin_required()
def run_scheduled_ingestion_stream():
    """Manually triggers the scheduled ingestion job and streams progress."""
    current_user_id = get_jwt_identity()

    def generate_events():
        job_id = None
        with app.app_context():
            try:
                with get_db_cursor(commit=True) as cur:
                    cur.execute(
                        "INSERT INTO ingestion_jobs (job_type, status) VALUES (%s, %s) RETURNING id",
                        ('scheduled', 'pending')
                    )
                    job_id = cur.fetchone()[0]
                
                app.logger.info(f"Starting manual stream for scheduled ingestion job {job_id}.")
                
                # Pass the admin's user ID to the job runner
                for update in _run_scheduled_ingestion_job(job_id, triggered_by_user_id=current_user_id):
                    yield f"data: {json.dumps(update)}\n\n"

            except Exception as e:
                app.logger.error(f"Failed to start scheduled ingestion stream: {e}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'payload': str(e)})}\n\n"
            finally:
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                app.logger.info(f"[SSE] Stream closed for job {job_id}.")

    response = Response(generate_events(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response

@app.route('/api/ingestion/jobs/latest', methods=['GET'])
@admin_required()
def get_latest_ingestion_job():
    """Returns the most recent 'scheduled' ingestion job."""
    try:
        with get_db_cursor() as cur:
            cur.execute("""
                SELECT id, job_type, status, progress, details, created_at, updated_at
                FROM ingestion_jobs
                WHERE job_type = 'scheduled'
                ORDER BY created_at DESC
                LIMIT 1
            """)
            job = cur.fetchone()
            if job:
                job_dict = dict(zip([desc[0] for desc in cur.description], job))
                return jsonify(job_dict)
            else:
                return jsonify(None)
    except Exception as e:
        app.logger.error(f"Failed to fetch latest ingestion job: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch latest job."}), 500

@app.route("/api/items")
@jwt_required()
def get_all_items():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    offset = (page - 1) * limit
    sort_by = request.args.get('sortBy', 'order_placed_date')
    sort_order = request.args.get('sortOrder', 'desc').upper()
    filter_text = request.args.get('filterText', '')
    current_user_id = get_jwt_identity()

    valid_sort_columns = {'full_title', 'asin', 'price_per_unit', 'order_placed_date'}
    if sort_by not in valid_sort_columns or sort_order not in ['ASC', 'DESC']:
        sort_by = 'order_placed_date'
        sort_order = 'DESC'

    # Base query components
    query_from = "FROM items i JOIN orders o ON i.order_id = o.order_id"
    # Filter by the current user
    query_where = "WHERE o.user_id = %s"
    params = [current_user_id]

    # Add text filter if provided
    if filter_text:
        query_where += " AND (i.full_title ILIKE %s OR CAST(o.order_placed_date AS TEXT) ILIKE %s)"
        params.extend([f"%{filter_text}%", f"%{filter_text}%"])

    # Construct the final queries
    query = f"""
        SELECT i.full_title, i.link, i.thumbnail_url, i.asin, i.price_per_unit, o.order_placed_date
        {query_from}
        {query_where}
        ORDER BY {sort_by} {sort_order}
        LIMIT %s OFFSET %s
    """
    count_query = f"SELECT COUNT(*) {query_from} {query_where}"

    try:
        with get_db_cursor() as cur:
            # Execute count query
            cur.execute(count_query, params)
            total_items = cur.fetchone()[0]
            
            # Execute data query
            data_params = params + [limit, offset]
            cur.execute(query, data_params)
            items = [dict(zip([desc[0] for desc in cur.description], row)) for row in cur.fetchall()]

        return jsonify({
            "data": items,
            "total": total_items,
            "page": page,
            "limit": limit
        })
    except Exception as e:
        app.logger.error(f"Failed to fetch items: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch items"}), 500

@app.route('/api/repeat-items')
@jwt_required()
def get_repeat_items():
    current_user_id = get_jwt_identity()

    # --- Sorting ---
    sort_by = request.args.get('sortBy', 'full_title')
    sort_order = request.args.get('sortOrder', 'asc').upper()
    valid_sort_columns = {
        'full_title', 'price_current', 'date_current', 
        'price_prev_1', 'date_prev_1'
    }
    if sort_by not in valid_sort_columns or sort_order not in ['ASC', 'DESC']:
        sort_by = 'full_title'
        sort_order = 'ASC'

    # --- Filtering ---
    filter_text = request.args.get('filterText', '')
    price_changed_only = request.args.get('priceChangedOnly', 'false').lower() == 'true'

    params = [current_user_id]
    
    # --- Base Query ---
    base_query = """
        WITH RankedItems AS (
            SELECT
                i.asin, i.full_title, i.link, i.thumbnail_url, i.price_per_unit, o.order_placed_date,
                i.is_subscribe_and_save,
                ROW_NUMBER() OVER(PARTITION BY i.asin ORDER BY o.order_placed_date DESC) as rn
            FROM items i
            JOIN orders o ON i.order_id = o.order_id
            WHERE i.asin IS NOT NULL AND o.user_id = %s
        ),
        RepeatItems AS (
            SELECT
                current.asin,
                current.full_title,
                current.link,
                current.thumbnail_url,
                current.is_subscribe_and_save,
                current.price_per_unit AS price_current,
                current.order_placed_date AS date_current,
                p1.price_per_unit AS price_prev_1,
                p1.order_placed_date AS date_prev_1,
                p2.price_per_unit AS price_prev_2,
                p2.order_placed_date AS date_prev_2,
                p3.price_per_unit AS price_prev_3,
                p3.order_placed_date AS date_prev_3
            FROM
                RankedItems current
            LEFT JOIN RankedItems p1 ON current.asin = p1.asin AND p1.rn = 2
            LEFT JOIN RankedItems p2 ON current.asin = p2.asin AND p2.rn = 3
            LEFT JOIN RankedItems p3 ON current.asin = p3.asin AND p3.rn = 4
            WHERE
                current.rn = 1 AND p1.asin IS NOT NULL
        )
        SELECT * FROM RepeatItems
    """

    # --- Dynamic WHERE clauses ---
    where_clauses = []
    if filter_text:
        where_clauses.append("full_title ILIKE %s")
        params.append(f"%{filter_text}%")
    
    if price_changed_only:
        # Ensure prices are not null and are different
        where_clauses.append("(price_current IS NOT NULL AND price_prev_1 IS NOT NULL AND price_current != price_prev_1)")

    if where_clauses:
        base_query += " WHERE " + " AND ".join(where_clauses)

    # --- Dynamic ORDER BY clause ---
    base_query += f" ORDER BY {sort_by} {sort_order}"

    try:
        with get_db_cursor() as cur:
            cur.execute(base_query, tuple(params))
            items = [dict(zip([desc[0] for desc in cur.description], row)) for row in cur.fetchall()]
        return jsonify(items)
    except Exception as e:
        app.logger.error(f"Failed to fetch repeat items: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch repeat items."}), 500



# --- Scheduled Jobs ---
@scheduler.task('cron', id='scheduled_ingestion', hour=1, minute=0)
def scheduled_ingestion():
    """
    Runs daily to fetch orders for users who have the feature enabled.
    """
    app.logger.info("Starting scheduled ingestion cron job...")
    job_id = None
    with app.app_context():
        try:
            with get_db_cursor(commit=True) as cur:
                cur.execute(
                    "INSERT INTO ingestion_jobs (job_type, status) VALUES (%s, %s) RETURNING id",
                    ('scheduled', 'pending')
                )
                job_id = cur.fetchone()[0]
            
            # Consume the generator to execute the job
            for _ in _run_scheduled_ingestion_job(job_id):
                pass
            
            app.logger.info(f"Scheduled ingestion cron job {job_id} finished.")
        except Exception as e:
            # The error is already logged and status set inside the generator, but log here too.
            app.logger.error(f"An error occurred during the scheduled ingestion cron job wrapper: {e}", exc_info=True)


# --- Serve React App ---
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    scheduler.start()
    app.run(host='0.0.0.0', port=5001)

