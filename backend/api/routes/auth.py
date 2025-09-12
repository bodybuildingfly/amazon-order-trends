from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash
from flask_jwt_extended import create_access_token
from backend.shared.db import get_db_cursor

auth_bp = Blueprint('auth_bp', __name__)

@auth_bp.route("/api/auth/login", methods=['POST'])
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
