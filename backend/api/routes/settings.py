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
                cur.execute("""
                    INSERT INTO user_settings (user_id, discord_webhook_url, discord_notification_preference)
                    VALUES (%s, %s, %s);
                """, (current_user_id, discord_webhook_url, discord_notification_preference))
        
        return jsonify({"message": "Admin settings saved successfully."}), 200
    except Exception as e:
        current_app.logger.error(f"Failed to save admin settings: {e}", exc_info=True)
        return jsonify({"error": "Failed to save admin settings."}), 500
