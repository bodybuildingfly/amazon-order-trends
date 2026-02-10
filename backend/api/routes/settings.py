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
                          price_change_notification_webhook_url
                   FROM user_settings WHERE user_id = %s""",
                (current_user_id,)
            )
            settings_row = cur.fetchone()

        if settings_row:
            email, password_encrypted, otp, webhook_url, notification_pref, price_webhook_url = settings_row
            return jsonify({
                "is_configured": bool(email and password_encrypted),
                "amazon_email": email or '',
                "amazon_otp_secret_key": otp or '',
                "discord_webhook_url": webhook_url or '',
                "discord_notification_preference": notification_pref or 'off',
                "price_change_notification_webhook_url": price_webhook_url or '',
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
        email = data.get('amazon_email')
        password = data.get('amazon_password')
        otp = data.get('amazon_otp_secret_key')
        price_webhook_url = data.get('price_change_notification_webhook_url')

        with get_db_cursor(commit=True) as cur:
            # Logic to insert or update user settings
            if password:
                encrypted_password = fernet.encrypt(password.encode('utf-8'))
                cur.execute("""
                    INSERT INTO user_settings (user_id, amazon_email, amazon_password_encrypted, amazon_otp_secret_key, price_change_notification_webhook_url)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        amazon_email = EXCLUDED.amazon_email,
                        amazon_password_encrypted = EXCLUDED.amazon_password_encrypted,
                        amazon_otp_secret_key = EXCLUDED.amazon_otp_secret_key,
                        price_change_notification_webhook_url = EXCLUDED.price_change_notification_webhook_url;
                """, (current_user_id, email, encrypted_password, otp, price_webhook_url))
            else:
                # If no password is provided, we should only be updating an existing record.
                # Creating a new record without a password would result in an invalid state.
                cur.execute("""
                    UPDATE user_settings SET
                        amazon_email = %s,
                        amazon_otp_secret_key = %s,
                        price_change_notification_webhook_url = %s
                    WHERE user_id = %s;
                """, (email, otp, price_webhook_url, current_user_id))
                if cur.rowcount == 0:
                    # This case implies a client-side error: trying to save settings for a new user without a password.
                    return jsonify({"error": "Cannot create new settings without providing a password."}), 400

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
