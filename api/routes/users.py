from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash
from flask_jwt_extended import get_jwt_identity
from shared.db import get_db_cursor
from api.helpers.decorators import admin_required

users_bp = Blueprint('users_bp', __name__)

@users_bp.route("/api/users", methods=['GET'])
@admin_required()
def get_users():
    """Returns a list of all users."""
    try:
        with get_db_cursor() as cur:
            cur.execute("SELECT id, username, role, created_at FROM users ORDER BY username")
            users = [dict(zip([desc[0] for desc in cur.description], row)) for row in cur.fetchall()]
        return jsonify(users)
    except Exception as e:
        current_app.logger.error(f"Failed to fetch users: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch users."}), 500

@users_bp.route("/api/users", methods=['POST'])
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
        current_app.logger.error(f"Failed to add user '{username}': {e}", exc_info=True)
        # Unique constraint violation error code for psycopg2
        if hasattr(e, 'pgcode') and e.pgcode == '23505':
            return jsonify({"error": f"Username '{username}' already exists."}), 409
        return jsonify({"error": "Failed to create user."}), 500

@users_bp.route("/api/users/<uuid:user_id>/reset-password", methods=['POST'])
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
        current_app.logger.error(f"Failed to reset password for user {user_id}: {e}", exc_info=True)
        return jsonify({"error": "Failed to reset password."}), 500

@users_bp.route("/api/users/<uuid:user_id>", methods=['DELETE'])
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
        current_app.logger.error(f"Failed to delete user {user_id}: {e}", exc_info=True)
        return jsonify({"error": "Failed to delete user."}), 500
