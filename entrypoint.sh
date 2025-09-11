#!/bin/sh

# Exit immediately if a command exits with a non-zero status.
set -e

# Run database initializations.
# This runs the 'init-db' command defined in 'api/__init__.py'.
echo "Running database initializations..."
flask init-db

# Start the Gunicorn server.
# 'exec' replaces the shell process with the Gunicorn process.
# This is important for proper signal handling (e.g., stopping the container).
echo "Starting Gunicorn server..."
exec gunicorn --bind 0.0.0.0:5001 --workers 4 --worker-class gevent --timeout 120 "api.app:app"
