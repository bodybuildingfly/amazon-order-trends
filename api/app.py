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

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.db import get_db_cursor
from ingestion.ingestion_script import main as run_ingestion_generator

# --- App Initialization & Config ---
app = Flask(__name__, static_folder='../frontend/build', static_url_path='/')
CORS(app, supports_credentials=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

@app.route('/api/settings', methods=['GET'])
@admin_required()
def get_settings():
    try:
        current_user_id = get_jwt_identity()
        with get_db_cursor() as cur:
            cur.execute(
                "SELECT amazon_email, amazon_password_encrypted, amazon_otp_secret_key FROM user_settings WHERE user_id = %s",
                (current_user_id,)
            )
            settings_row = cur.fetchone()
        
        if settings_row:
            email, password_encrypted, otp = settings_row
            return jsonify({
                "is_configured": bool(email and password_encrypted),
                "amazon_email": email or '',
                "amazon_otp_secret_key": otp or ''
            }), 200
        else:
            return jsonify({
                "is_configured": False,
                "amazon_email": '',
                "amazon_otp_secret_key": ''
            }), 200
    except Exception as e:
        app.logger.error(f"Failed to get settings: {e}", exc_info=True)
        return jsonify({"error": "Failed to retrieve settings."}), 500

@app.route('/api/settings', methods=['POST'])
@admin_required()
def save_settings():
    data = request.get_json()
    current_user_id = get_jwt_identity()
    
    try:
        initialize_fernet()
        email = data.get('amazon_email')
        password = data.get('amazon_password')
        otp = data.get('amazon_otp_secret_key')

        with get_db_cursor(commit=True) as cur:
            if password:
                encrypted_password = fernet.encrypt(password.encode('utf-8'))
                cur.execute("""
                    INSERT INTO user_settings (user_id, amazon_email, amazon_password_encrypted, amazon_otp_secret_key)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        amazon_email = EXCLUDED.amazon_email,
                        amazon_password_encrypted = EXCLUDED.amazon_password_encrypted,
                        amazon_otp_secret_key = EXCLUDED.amazon_otp_secret_key;
                """, (current_user_id, email, encrypted_password, otp))
            else:
                cur.execute("""
                    UPDATE user_settings SET amazon_email = %s, amazon_otp_secret_key = %s WHERE user_id = %s;
                """, (email, otp, current_user_id))
                # If no rows were updated, it means the user doesn't exist yet. Insert a new row.
                if cur.rowcount == 0:
                    cur.execute("""
                        INSERT INTO user_settings (user_id, amazon_email, amazon_otp_secret_key)
                        VALUES (%s, %s, %s);
                    """, (current_user_id, email, otp))
        
        return jsonify({"message": "Settings saved successfully."}), 200
    except Exception as e:
        app.logger.error(f"Failed to save settings: {e}", exc_info=True)
        return jsonify({"error": "Failed to save settings."}), 500

@app.route("/api/ingestion/run", methods=['GET'])
@admin_required()
def run_ingestion_route():
    days = request.args.get('days', 60, type=int)
    
    def generate_events():
        app.logger.info(f"[SSE] Stream opened for ingestion run ({days} days).")
        try:
            for event_type, data in run_ingestion_generator(manual_days_override=days):
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

@app.route("/api/items")
@jwt_required()
def get_all_items():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    offset = (page - 1) * limit
    sort_by = request.args.get('sortBy', 'order_placed_date')
    sort_order = request.args.get('sortOrder', 'desc').upper()
    filter_text = request.args.get('filterText', '')

    valid_sort_columns = {'full_title', 'asin', 'price_per_unit', 'order_placed_date'}
    if sort_by not in valid_sort_columns or sort_order not in ['ASC', 'DESC']:
        sort_by = 'order_placed_date'
        sort_order = 'DESC'
    
    query = """
        SELECT i.full_title, i.link, i.asin, i.price_per_unit, o.order_placed_date
        FROM items i JOIN orders o ON i.order_id = o.order_id
    """
    count_query = "SELECT COUNT(*) FROM items i JOIN orders o ON i.order_id = o.order_id"
    params = []
    
    if filter_text:
        query += " WHERE i.full_title ILIKE %s OR CAST(o.order_placed_date AS TEXT) ILIKE %s"
        count_query += " WHERE i.full_title ILIKE %s OR CAST(o.order_placed_date AS TEXT) ILIKE %s"
        params.extend([f"%{filter_text}%", f"%{filter_text}%"])

    query += f" ORDER BY {sort_by} {sort_order} LIMIT %s OFFSET %s"
    
    try:
        with get_db_cursor() as cur:
            count_params = params.copy()
            cur.execute(count_query, count_params)
            total_items = cur.fetchone()[0]
            
            params.extend([limit, offset])
            cur.execute(query, params)
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

@app.route('/api/sns-items')
@jwt_required()
def get_sns_items():
    try:
        with get_db_cursor() as cur:
            cur.execute("""
                WITH RankedItems AS (
                    SELECT
                        i.asin, i.full_title, i.link, i.price_per_unit, o.order_placed_date,
                        ROW_NUMBER() OVER(PARTITION BY i.asin ORDER BY o.order_placed_date DESC) as rn
                    FROM items i
                    JOIN orders o ON i.order_id = o.order_id
                    WHERE i.is_subscribe_and_save = TRUE AND i.asin IS NOT NULL
                )
                SELECT
                    current.asin, current.full_title, current.link,
                    current.price_per_unit AS current_price,
                    current.order_placed_date AS current_date,
                    previous.price_per_unit AS previous_price,
                    previous.order_placed_date AS previous_date
                FROM RankedItems current
                LEFT JOIN RankedItems previous ON current.asin = previous.asin AND previous.rn = 2
                WHERE current.rn = 1
                ORDER BY current.full_title;
            """)
            items = [dict(zip([desc[0] for desc in cur.description], row)) for row in cur.fetchall()]
        return jsonify(items)
    except Exception as e:
        app.logger.error(f"Failed to fetch S&S items: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch Subscribe & Save items."}), 500

# --- Serve React App ---
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)

