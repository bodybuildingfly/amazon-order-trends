#!/bin/sh

# Exit immediately if a command exits with a non-zero status.
set -e

# Apply database migrations.
# This runs the 'db-migrate' command defined in 'api/__init__.py'.
echo "Applying database migrations..."
export FLASK_APP=backend.api.app
flask db-migrate

# Start the Gunicorn server.
# 'exec' replaces the shell process with the Gunicorn process.
# This is important for proper signal handling (e.g., stopping the container).
echo "Starting Gunicorn server..."
exec gunicorn --bind 0.0.0.0:5001 --workers 4 --worker-class gevent --timeout 120 "backend.api.app:app"
