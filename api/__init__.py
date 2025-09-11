from gevent import monkey
monkey.patch_all()

import os
import logging
from flask import Flask, send_from_directory, jsonify
from werkzeug.security import generate_password_hash
from psycopg2 import errors as psycopg2_errors

from api.config import config_by_name
from api.extensions import cors, jwt, scheduler
from api.helpers.encryption import initialize_fernet
from shared.db import get_db_cursor, close_pool
from api.services.ingestion_service import run_scheduled_ingestion_job_stream

def _ensure_db_initialized(app):
    """
    Checks if the database is initialized, and if not, creates the schema
    and the initial admin user.
    """
    with app.app_context():
        try:
            # Check if the 'users' table exists. If not, this will raise an exception.
            with get_db_cursor() as cur:
                cur.execute("SELECT 1 FROM users LIMIT 1;")
            app.logger.info("Database already initialized.")
            return
        except psycopg2_errors.UndefinedTable:
            app.logger.info("Database not initialized. Initializing now...")
        except Exception as e:
            app.logger.error(f"Could not connect to database for initialization check: {e}")
            # If we can't connect, we can't initialize. The app will likely fail later, which is appropriate.
            return

        try:
            with get_db_cursor(commit=True) as cur:
                app.logger.info("Creating database schema...")
                schema_path = os.path.join(os.path.dirname(__file__), '../ingestion/schema.sql')
                with open(schema_path, 'r') as f:
                    cur.execute(f.read())
                
                admin_user = os.environ.get("ADMIN_USERNAME", "admin")
                admin_pass = os.environ.get("ADMIN_PASSWORD", "changeme")
                hashed_password = generate_password_hash(admin_pass)

                app.logger.info(f"Ensuring initial admin user '{admin_user}' exists...")
                cur.execute(
                    """
                    INSERT INTO users (username, hashed_password, role)
                    VALUES (%s, %s, 'admin')
                    ON CONFLICT (username) DO NOTHING;
                    """,
                    (admin_user, hashed_password)
                )
                app.logger.info("Database initialization complete.")
        except Exception as e:
            app.logger.error(f"An error occurred during DB initialization: {e}", exc_info=True)

def create_app(config_name=None):
    """Application factory."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
        
    app = Flask(__name__, static_folder='../frontend/build', static_url_path='/')
    app.config.from_object(config_by_name[config_name])

    # --- Initialize Extensions ---
    cors.init_app(app)
    jwt.init_app(app)
    initialize_fernet(app)
    
    # Initialize scheduler, but don't start it until the app is run
    scheduler.init_app(app)

    # --- Database Initialization ---
    # This needs to be done before registering blueprints or starting scheduler
    _ensure_db_initialized(app)

    # --- Logging ---
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # --- Register Blueprints ---
    from .routes.auth import auth_bp
    from .routes.users import users_bp
    from .routes.settings import settings_bp
    from .routes.items import items_bp
    from .routes.ingestion import ingestion_bp
    from .routes.dashboard import dashboard_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(items_bp)
    app.register_blueprint(ingestion_bp)
    app.register_blueprint(dashboard_bp)

    # --- Scheduled Jobs ---
    # We need to define the job within the factory to have access to the app context
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        if not scheduler.get_job('scheduled_ingestion'):
            @scheduler.task('cron', id='scheduled_ingestion', hour=1, minute=0)
            def scheduled_ingestion_job():
                app.logger.info("Starting scheduled ingestion cron job...")
                with app.app_context():
                    job_id = None
                    try:
                        with get_db_cursor(commit=True) as cur:
                            cur.execute(
                                "INSERT INTO ingestion_jobs (job_type, status) VALUES (%s, %s) RETURNING id",
                                ('scheduled', 'pending')
                            )
                            job_id = cur.fetchone()[0]
                        
                        # Consume the generator to execute the job
                        for _ in run_scheduled_ingestion_job_stream(job_id):
                            pass
                        
                        app.logger.info(f"Scheduled ingestion cron job {job_id} finished.")
                    except Exception as e:
                        app.logger.error(f"An error occurred during the scheduled ingestion cron job wrapper: {e}", exc_info=True)


    # --- Static Frontend Serving ---
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        else:
            return send_from_directory(app.static_folder, 'index.html')

    return app
