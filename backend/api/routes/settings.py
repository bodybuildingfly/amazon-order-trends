import requests
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from backend.shared.db import get_db_cursor
from backend.api.helpers.encryption import get_fernet
from backend.api.helpers.decorators import admin_required

settings_bp = Blueprint('settings_bp', __name__)

@settings_bp.route('/api/settings', methods=['GET'])
@jwt_required()
def get_settings():
    try:
        current_user_id = get_jwt_identity()
        with get_db_cursor() as cur:
            cur.execute(
                """SELECT amazon_email, amazon_password_encrypted, amazon_otp_secret_key, 
                          discord_webhook_url, discord_notification_preference,
                          price_change_notification_webhook_url,
                          default_notification_threshold_type, default_notification_threshold_value
                   FROM user_settings WHERE user_id = %s""",
                (current_user_id,)
            )
            settings_row = cur.fetchone()

        if settings_row:
            email, password_encrypted, otp, webhook_url, notification_pref, price_webhook_url, def_thresh_type, def_thresh_val = settings_row
            return jsonify({
                "is_configured": bool(email and password_encrypted),
                "amazon_email": email or '',
                "amazon_otp_secret_key": otp or '',
                "discord_webhook_url": webhook_url or '',
                "discord_notification_preference": notification_pref or 'off',
                "price_change_notification_webhook_url": price_webhook_url or '',
                "default_notification_threshold_type": def_thresh_type or 'percent',
                "default_notification_threshold_value": def_thresh_val
            }), 200
        else:
            # If no settings row exists, return defaults
            return jsonify({
                "is_configured": False,
                "amazon_email": '',
                "amazon_otp_secret_key": '',
                "discord_webhook_url": '',
                "discord_notification_preference": 'off',
                "price_change_notification_webhook_url": '',
                "default_notification_threshold_type": 'percent',
                "default_notification_threshold_value": None
            }), 200
    except Exception as e:
        current_app.logger.error(f"Failed to get settings: {e}", exc_info=True)
        return jsonify({"error": "Failed to retrieve settings."}), 500

@settings_bp.route('/api/settings/user', methods=['POST'])
@jwt_required()
def save_user_settings():
    data = request.get_json()
    current_user_id = get_jwt_identity()

    try:
        fernet = get_fernet()

        # Map request keys to database columns
        # Tuples of (json_key, db_column)
        fields_map = [
            ('amazon_email', 'amazon_email'),
            ('amazon_otp_secret_key', 'amazon_otp_secret_key'),
            ('price_change_notification_webhook_url', 'price_change_notification_webhook_url'),
            ('default_notification_threshold_type', 'default_notification_threshold_type'),
            ('default_notification_threshold_value', 'default_notification_threshold_value')
        ]

        columns = ['user_id']
        values = [current_user_id]

        # Handle password specially
        if 'amazon_password' in data:
            password = data['amazon_password']
            if password:
                encrypted_password = fernet.encrypt(password.encode('utf-8'))
                columns.append('amazon_password_encrypted')
                values.append(encrypted_password)
            # If password is provided as empty/null, we might ignore it or clear it?
            # Existing logic implies we update it if provided.

        for json_key, db_col in fields_map:
            if json_key in data:
                columns.append(db_col)
                values.append(data[json_key])

        if len(columns) == 1:
            # No fields to update
            return jsonify({"message": "No changes detected."}), 200

        # Construct Dynamic SQL
        placeholders = ', '.join(['%s'] * len(columns))
        col_names = ', '.join(columns)

        # Exclude user_id from SET clause
        update_assignments = [f"{col} = EXCLUDED.{col}" for col in columns if col != 'user_id']
        update_clause = ', '.join(update_assignments)

        query = f"""
            INSERT INTO user_settings ({col_names})
            VALUES ({placeholders})
            ON CONFLICT (user_id) DO UPDATE SET
            {update_clause};
        """

        with get_db_cursor(commit=True) as cur:
            cur.execute(query, tuple(values))

        return jsonify({"message": "User settings saved successfully."}), 200
    except Exception as e:
        current_app.logger.error(f"Failed to save user settings: {e}", exc_info=True)
        return jsonify({"error": "Failed to save user settings."}), 500

@settings_bp.route('/api/settings/admin', methods=['POST'])
@admin_required()
def save_admin_settings():
    data = request.get_json()
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
                # If admin tries to save global settings but doesn't have a user_settings row yet
                # We could insert one, but existing logic returned 404.
                # Given we now have a dynamic insert in user settings, we could suggest using that,
                # but admin settings are separate in UI.
                # Let's keep existing behavior or use INSERT ON CONFLICT here too?
                # The prompt is only about user settings defaults. Let's leave admin settings as is.
                return jsonify({
                    "error": "User settings not found. Please configure your main user settings before saving admin-specific settings."
                }), 404
        
        return jsonify({"message": "Admin settings saved successfully."}), 200
    except Exception as e:
        current_app.logger.error(f"Failed to save admin settings: {e}", exc_info=True)
        return jsonify({"error": "Failed to save admin settings."}), 500

@settings_bp.route('/api/settings/test-webhook', methods=['POST'])
@jwt_required()
def test_webhook():
    data = request.get_json()
    webhook_url = data.get('webhook_url')

    if not webhook_url:
        return jsonify({"error": "Webhook URL is required"}), 400

    from backend.api.services.notification_service import send_price_drop_notification

    success = send_price_drop_notification(
        webhook_url,
        item_name="Test Product - Premium Widget",
        current_price=19.99,
        previous_price=24.99,
        url="https://www.amazon.com/"
    )

    if success:
        return jsonify({"message": "Test notification sent successfully!"}), 200
    else:
        return jsonify({"error": "Failed to send test notification. Check server logs for details."}), 400
