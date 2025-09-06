import json
import threading
import subprocess
from flask import Blueprint, request, jsonify, current_app, Response
from flask_jwt_extended import jwt_required, get_jwt_identity

from shared.db import get_db_cursor
from api.helpers.decorators import admin_required
from api.services.ingestion_service import (
    run_manual_ingestion_job,
    run_scheduled_ingestion_job_stream,
    manual_import_jobs,
    manual_import_jobs_lock,
)

ingestion_bp = Blueprint('ingestion_bp', __name__)

@ingestion_bp.route("/api/ingestion/run", methods=['POST'])
@jwt_required()
def run_ingestion_route():
    current_user_id = get_jwt_identity()
    data = request.get_json()
    days = data.get('days', 60)

    with manual_import_jobs_lock:
        if manual_import_jobs.get(current_user_id, {}).get('status') == 'running':
            return jsonify({"error": "An import is already in progress for this user."}), 409

        manual_import_jobs.pop(current_user_id, None)

    app = current_app._get_current_object()
    thread = threading.Thread(target=run_manual_ingestion_job, args=(app, current_user_id, days))
    thread.daemon = True
    thread.start()

    return jsonify({"message": "Manual import process started."}), 202


@ingestion_bp.route("/api/ingestion/manual/status", methods=['GET'])
@jwt_required()
def get_manual_ingestion_status():
    current_user_id = get_jwt_identity()
    with manual_import_jobs_lock:
        job_status = manual_import_jobs.get(current_user_id)

    if not job_status:
        return jsonify(None)

    return jsonify(job_status)


@ingestion_bp.route("/api/amazon-logout", methods=['POST'])
@jwt_required()
def amazon_logout():
    try:
        result = subprocess.run(["amazon-orders", "logout"], capture_output=True, text=True, check=True)
        return jsonify({"message": "Amazon session logout successful.", "output": result.stdout}), 200
    except Exception as e:
        current_app.logger.error(f"Amazon logout command failed: {e}", exc_info=True)
        return jsonify({"error": "Failed to execute Amazon logout command."}), 500

@ingestion_bp.route("/api/scheduler/run", methods=['GET'])
@admin_required()
def run_scheduled_ingestion_stream():
    """Manually triggers the scheduled ingestion job and streams progress."""
    current_user_id = get_jwt_identity()

    def generate_events():
        job_id = None
        app = current_app._get_current_object()
        with app.app_context():
            try:
                with get_db_cursor(commit=True) as cur:
                    cur.execute(
                        "INSERT INTO ingestion_jobs (job_type, status) VALUES (%s, %s) RETURNING id",
                        ('scheduled', 'pending')
                    )
                    job_id = cur.fetchone()[0]
                
                app.logger.info(f"Starting manual stream for scheduled ingestion job {job_id}.")
                
                for update in run_scheduled_ingestion_job_stream(job_id, triggered_by_user_id=current_user_id):
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

@ingestion_bp.route('/api/ingestion/jobs/latest', methods=['GET'])
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
        current_app.logger.error(f"Failed to fetch latest ingestion job: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch latest job."}), 500
