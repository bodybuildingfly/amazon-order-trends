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
from datetime import timedelta
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

@app.route('/api/settings', methods=['POST'])
@jwt_required()
def save_settings():
    data = request.get_json()
    current_user_id = get_jwt_identity()

    try:
        initialize_fernet()
        email = data.get('amazon_email')
        password = data.get('amazon_password')
        otp = data.get('amazon_otp_secret_key')
        enable_scheduled_ingestion = data.get('enable_scheduled_ingestion', False)
        discord_webhook_url = data.get('discord_webhook_url')
        discord_notification_preference = data.get('discord_notification_preference', 'off')

        with get_db_cursor(commit=True) as cur:
            # This logic handles both insert and update operations for user settings.
            if password:
                # If a new password is provided, it must be encrypted.
                encrypted_password = fernet.encrypt(password.encode('utf-8'))
                cur.execute("""
                    INSERT INTO user_settings (user_id, amazon_email, amazon_password_encrypted, amazon_otp_secret_key, enable_scheduled_ingestion, discord_webhook_url, discord_notification_preference)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        amazon_email = EXCLUDED.amazon_email,
                        amazon_password_encrypted = EXCLUDED.amazon_password_encrypted,
                        amazon_otp_secret_key = EXCLUDED.amazon_otp_secret_key,
                        enable_scheduled_ingestion = EXCLUDED.enable_scheduled_ingestion,
                        discord_webhook_url = EXCLUDED.discord_webhook_url,
                        discord_notification_preference = EXCLUDED.discord_notification_preference;
                """, (current_user_id, email, encrypted_password, otp, enable_scheduled_ingestion, discord_webhook_url, discord_notification_preference))
            else:
                # If no password is provided, update other fields without changing the password.
                cur.execute("""
                    UPDATE user_settings SET
                        amazon_email = %s,
                        amazon_otp_secret_key = %s,
                        enable_scheduled_ingestion = %s,
                        discord_webhook_url = %s,
                        discord_notification_preference = %s
                    WHERE user_id = %s;
                """, (email, otp, enable_scheduled_ingestion, discord_webhook_url, discord_notification_preference, current_user_id))
                
                # If no row was updated, it means the user is saving settings for the first time
                # without setting a password, which is not a complete setup.
                if cur.rowcount == 0:
                    cur.execute("""
                        INSERT INTO user_settings (user_id, amazon_email, amazon_otp_secret_key, enable_scheduled_ingestion, discord_webhook_url, discord_notification_preference)
                        VALUES (%s, %s, %s, %s, %s, %s);
                    """, (current_user_id, email, otp, enable_scheduled_ingestion, discord_webhook_url, discord_notification_preference))

        return jsonify({"message": "Settings saved successfully."}), 200
    except Exception as e:
        app.logger.error(f"Failed to save settings: {e}", exc_info=True)
        return jsonify({"error": "Failed to save settings."}), 500

@app.route("/api/ingestion/run", methods=['GET'])
@jwt_required()
def run_ingestion_route():
    days = request.args.get('days', 60, type=int)
    current_user_id = get_jwt_identity()

    def generate_events():
        app.logger.info(f"[SSE] Stream opened for ingestion run for user {current_user_id} ({days} days).")
        try:
            for event_type, data in run_ingestion_generator(user_id=current_user_id, manual_days_override=days):
                event_data = json.dumps({"type": event_type, "payload": data})
                yield f"data: {event_data}\n\n"
        except Exception as e:
            app.logger.error(f"[SSE] An error occurred during the ingestion stream: {e}", exc_info=True)
            error_data = json.dumps({"type": "error", "payload": str(e)})
            yield f"data: {error_data}\n\n"
        finally:
            app.logger.info("[SSE] Stream closed for ingestion run.")
            
    response = Response(generate_events(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response

@app.route("/api/amazon-logout", methods=['POST'])
@admin_required()
def amazon_logout():
    try:
        result = subprocess.run(["amazon-orders", "logout"], capture_output=True, text=True, check=True)
        return jsonify({"message": "Amazon session logout successful.", "output": result.stdout}), 200
    except Exception as e:
        app.logger.error(f"Amazon logout command failed: {e}", exc_info=True)
        return jsonify({"error": "Failed to execute Amazon logout command."}), 500

@app.route("/api/scheduler/run", methods=['POST'])
@admin_required()
def run_scheduler_manually():
    """Manually triggers the scheduled ingestion job."""
    try:
        scheduler.run_job('scheduled_ingestion')
        app.logger.info("Manually triggered the scheduled ingestion job.")
        return jsonify({"message": "Scheduled ingestion job has been triggered successfully."}), 200
    except Exception as e:
        app.logger.error(f"Failed to manually trigger scheduled job: {e}", exc_info=True)
        return jsonify({"error": "Failed to trigger the scheduled job."}), 500

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
    Runs daily to fetch the last 3 days of orders for users who have the feature enabled.
    """
    app.logger.info("Starting scheduled ingestion job...")
    with app.app_context():
        try:
            with get_db_cursor() as cur:
                cur.execute(
                    "SELECT user_id FROM user_settings WHERE enable_scheduled_ingestion = TRUE"
                )
                user_ids = [row[0] for row in cur.fetchall()]
            
            app.logger.info(f"Found {len(user_ids)} users for scheduled ingestion.")

            for user_id in user_ids:
                try:
                    app.logger.info(f"Running ingestion for user {user_id}...")
                    # The generator needs to be consumed for the code to execute
                    for event, data in run_ingestion_generator(user_id=user_id, manual_days_override=3):
                        if event == 'error':
                            app.logger.error(f"Error during ingestion for user {user_id}: {data}")
                except Exception as e:
                    app.logger.error(f"Failed to run ingestion for user {user_id}: {e}", exc_info=True)

        except Exception as e:
            app.logger.error(f"An error occurred during the scheduled ingestion job: {e}", exc_info=True)
    app.logger.info("Scheduled ingestion job finished.")


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

