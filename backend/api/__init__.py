# Conditionally apply gevent monkey patching for production
import os
if os.environ.get('FLASK_ENV') == 'production':
    from gevent import monkey
    monkey.patch_all()
    from psycogreen.gevent import patch_psycopg
    patch_psycopg()

import logging
import atexit
try:
    import fcntl
except ImportError:
    fcntl = None
from flask import Flask, send_from_directory, jsonify
from werkzeug.security import generate_password_hash
from backend.api.config import config_by_name
from backend.api.extensions import cors, jwt, scheduler
from backend.api.helpers.encryption import initialize_fernet
from backend.shared.db import init_pool, get_db_cursor, close_pool

def create_app(config_name=None):
    """Application factory."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')

    # Conditionally set static folder for production
    static_folder_path = None
    if config_name == 'production':
        # Use an absolute path to be safe. The app's root is two levels up from this file's directory.
        static_folder_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'build'))
        
    app = Flask(__name__, static_folder=None)
    if static_folder_path:
        app.static_folder = static_folder_path

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

    # Add scheduled job for price tracking
    from backend.api.services.price_service import update_all_prices
    if not scheduler.get_job('update_prices'):
         scheduler.add_job(id='update_prices', func=update_all_prices, trigger='interval', hours=1, replace_existing=True)

    # --- Logging ---
    # Configure Flask's built-in logger to stream to stdout
    app.logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)
    app.logger.propagate = False

    # Conditionally start the scheduler if environment variable is set
    if os.environ.get('SCHEDULER_AUTOSTART') == 'True':
        if fcntl:
            try:
                # Open a lock file to ensure only one worker starts the scheduler
                lock_file = open("/tmp/scheduler.lock", "w")
                # Try to acquire an exclusive non-blocking lock.
                # If another process holds the lock, this will raise an IOError (BlockingIOError).
                fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)

                # Keep reference to the file object to prevent it from being closed/garbage-collected
                app.scheduler_lock_file = lock_file

                if not scheduler.running:
                    scheduler.start()
                    app.logger.info("Scheduler started by this worker.")
            except IOError:
                app.logger.info("Scheduler already running in another worker (lock held).")
            except Exception as e:
                app.logger.error(f"Failed to start scheduler: {e}")
        else:
            # Fallback for systems without fcntl (e.g., Windows development)
            if not scheduler.running:
                scheduler.start()
                app.logger.info("Scheduler started (fcntl not available).")

    # --- Register Blueprints ---
    from .routes.auth import auth_bp
    from .routes.users import users_bp
    from .routes.settings import settings_bp
    from .routes.items import items_bp
    from .routes.ingestion import ingestion_bp
    from .routes.dashboard import dashboard_bp
    from .routes.price_tracking import price_tracking_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(items_bp)
    app.register_blueprint(ingestion_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(price_tracking_bp)

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



    # Conditionally serve static files in production
    if config_name == 'production':
        @app.route('/', defaults={'path': ''})
        @app.route('/<path:path>')
        def serve(path):
            # Do not serve API routes from the frontend catch-all
            if path.startswith('api/'):
                return jsonify({"error": "Not Found"}), 404
            
            if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
                return send_from_directory(app.static_folder, path)
            else:
                return send_from_directory(app.static_folder, 'index.html')

    return app
