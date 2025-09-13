# Conditionally apply gevent monkey patching for production
import os
if os.environ.get('FLASK_ENV') == 'production':
    from gevent import monkey
    monkey.patch_all()
    from psycogreen.gevent import patch_psycopg
    patch_psycopg()

import logging
import atexit
from flask import Flask, send_from_directory, jsonify
from werkzeug.security import generate_password_hash
from backend.api.config import config_by_name
from backend.api.extensions import cors, jwt, scheduler
from backend.api.helpers.encryption import initialize_fernet
from backend.shared.db import init_pool, get_db_cursor, close_pool
from backend.api.services.ingestion_service import run_scheduled_ingestion_job_stream

def create_app(config_name=None):
    """Application factory."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')

    # Conditionally set static folder for production
    static_folder_path = None
    if config_name == 'production':
        static_folder_path = '../../frontend/build'
        
    app = Flask(__name__, static_folder=static_folder_path, static_url_path='/')
    app.config.from_object(config_by_name[config_name])

    # --- Initialize Database Pool ---
    init_pool()
    atexit.register(close_pool)

    # --- Initialize Extensions ---
    cors.init_app(app)
    jwt.init_app(app)
    initialize_fernet(app)
    
    # Initialize scheduler, but don't start it until the app is run
    scheduler.init_app(app)

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

    # --- CLI Commands ---
    @app.cli.command("db-migrate")
    def db_migrate_command():
        """Applies database migrations."""
        migrations_dir = os.environ.get('MIGRATIONS_DIR', '/app/migrations/versions')
        app.logger.info("Starting database migration process...")

        try:
            with get_db_cursor(commit=True) as cur:
                # 1. Create migrations tracking table if it doesn't exist
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version VARCHAR(255) PRIMARY KEY
                    );
                """)
                app.logger.info("Checked/created 'schema_migrations' table.")

                # 2. Get applied migrations from the DB
                cur.execute("SELECT version FROM schema_migrations")
                applied_versions = {row[0] for row in cur.fetchall()}
                app.logger.info(f"Found {len(applied_versions)} applied migrations.")

                # 3. Get available migrations from the filesystem
                available_migrations = sorted(
                    f for f in os.listdir(migrations_dir) if f.endswith('.sql')
                )
                app.logger.info(f"Found {len(available_migrations)} available migration files.")

                # 4. Determine and apply un-applied migrations
                migrations_to_apply = [
                    m for m in available_migrations if m not in applied_versions
                ]

                if not migrations_to_apply:
                    app.logger.info("Database is up to date.")
                    return

                for migration_file in migrations_to_apply:
                    app.logger.info(f"Applying migration: {migration_file}...")
                    try:
                        with open(os.path.join(migrations_dir, migration_file), 'r') as f:
                            sql_script = f.read()
                            cur.execute(sql_script)
                        
                        cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (migration_file,))
                        app.logger.info(f"Successfully applied and recorded migration: {migration_file}")
                    except Exception as e:
                        app.logger.error(f"Failed to apply migration {migration_file}: {e}")
                        # The transaction will be rolled back by the 'with' context manager
                        raise

            app.logger.info("Database migration process finished successfully.")
        except Exception as e:
            app.logger.error(f"A critical error occurred during the migration process: {e}")
            # Exit or handle failure appropriately
            raise

    @app.cli.command("seed-admin")
    def seed_admin_command():
        """Creates the initial admin user if it doesn't exist."""
        try:
            with get_db_cursor(commit=True) as cur:
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
                    app.logger.info("Admin user created successfully.")
                else:
                    app.logger.info("Admin user already exists.")
        except Exception as e:
            app.logger.error(f"An error occurred during admin user seeding: {e}")
            raise

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


    # Conditionally serve static files in production
    if config_name == 'production':
        @app.route('/', defaults={'path': ''})
        @app.route('/<path:path>')
        def serve(path):
            if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
                return send_from_directory(app.static_folder, path)
            else:
                return send_from_directory(app.static_folder, 'index.html')

    return app
