import json
import threading
import subprocess
import re
from datetime import datetime, timedelta, time
from flask import Blueprint, request, jsonify, current_app, Response
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.shared.db import get_db_cursor
from backend.api.helpers.decorators import admin_required
from backend.api.services.ingestion_service import (
    run_manual_ingestion_job,
)

ingestion_bp = Blueprint('ingestion_bp', __name__)

@ingestion_bp.route("/api/ingestion/run", methods=['POST'])
@jwt_required()
def run_ingestion_route():
    current_user_id = get_jwt_identity()
    data = request.get_json()
    days = data.get('days', 60)
    debug = data.get('debug', False)

    # Check if a job is already running for this user
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT id FROM ingestion_jobs WHERE user_id = %s AND status = 'running' AND job_type = 'manual'",
            (current_user_id,)
        )
        if cur.fetchone():
            return jsonify({"error": "An import is already in progress for this user."}), 409

    # Create a new job record in the database
    with get_db_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO ingestion_jobs (user_id, job_type, status, details)
            VALUES (%s, 'manual', 'pending', %s) RETURNING id
            """,
            (current_user_id, json.dumps({'log': ['Job created...']}))
        )
        job_id = cur.fetchone()[0]

    app = current_app._get_current_object()
    thread = threading.Thread(target=run_manual_ingestion_job, args=(app, current_user_id, job_id, days, debug))
    thread.daemon = True
    thread.start()

    return jsonify({"message": "Manual import process started.", "job_id": job_id}), 202


@ingestion_bp.route("/api/ingestion/manual/status", methods=['GET'])
@jwt_required()
def get_manual_ingestion_status():
    current_user_id = get_jwt_identity()
    job_id_param = request.args.get('job_id')

    with get_db_cursor(commit=True) as cur:
        # If job_id is provided, fetch that specific job.
        if job_id_param:
            cur.execute(
                "SELECT id, status, progress, details, notification_seen FROM ingestion_jobs WHERE id = %s AND user_id = %s",
                (job_id_param, current_user_id)
            )
            job_record = cur.fetchone()
        # If no job_id, fetch the latest running or most recently completed manual job for the user.
        else:
            cur.execute(
                """
                SELECT id, status, progress, details, notification_seen FROM ingestion_jobs
                WHERE user_id = %s AND job_type = 'manual'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (current_user_id,)
            )
            job_record = cur.fetchone()

        if not job_record:
            return jsonify(None)

        job_id, status, progress, details, notification_seen = job_record

        show_notification = (status == 'completed' and not notification_seen)

        # The frontend expects a flat object with 'log' and 'error' keys.
        # We construct this object from the 'details' JSON field.
        response_data = {
            "id": job_id,
            "status": status,
            "progress": progress or {"value": 0, "max": 100},
            "log": details.get('log', []),
            "error": details.get('error'),
            "show_notification": show_notification,
            "notification_seen": notification_seen
        }

        return jsonify(response_data)


@ingestion_bp.route("/api/amazon-logout", methods=['POST'])
@jwt_required()
def amazon_logout():
    try:
        result = subprocess.run(["amazon-orders", "logout"], capture_output=True, text=True, check=True)
        return jsonify({"message": "Amazon session logout successful.", "output": result.stdout}), 200
    except Exception as e:
        current_app.logger.error(f"Amazon logout command failed: {e}", exc_info=True)
        return jsonify({"error": "Failed to execute Amazon logout command."}), 500


@ingestion_bp.route('/api/ingestion/jobs/seen', methods=['POST'])
@jwt_required()
def mark_notification_seen():
    data = request.get_json()
    job_id = data.get('job_id')
    current_user_id = get_jwt_identity()
    try:
        with get_db_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE ingestion_jobs SET notification_seen = TRUE WHERE id = %s AND user_id = %s",
                (job_id, current_user_id)
            )
        return jsonify({"message": "Notification marked as seen."})
    except Exception as e:
        current_app.logger.error(f"Failed to mark notification as seen: {e}", exc_info=True)
        return jsonify({"error": "Failed to mark notification as seen."}), 500