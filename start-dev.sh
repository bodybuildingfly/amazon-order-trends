#!/bin/sh

# start-dev.sh
# This script starts the backend and frontend servers for development.

echo "Starting development environment..."

# Step 1: Apply database migrations using a Flask CLI command.
# This is a robust way to ensure the schema is up-to-date before the API starts.
echo "Waiting for PostgreSQL to be ready..."
sleep 5 # A small safety delay for network DBs to respond on first startup
echo "Applying database migrations via Flask..."
export FLASK_APP=backend.api:create_app
flask db-migrate
status=$?
if [ $status -ne 0 ]; then
  echo "Database migration failed with status $status. See errors above. Exiting."
  exit $status
fi
echo "Database migration successful."

# Step 2: Seed the initial admin user.
echo "Seeding initial admin user..."
flask seed-admin
status=$?
if [ $status -ne 0 ]; then
  echo "Admin user seeding failed with status $status. See errors above. Exiting."
  exit $status
fi
echo "Admin user seeding successful."

# Step 3: Start the Flask backend API in the background
echo "Starting Flask backend server on port 5001..."
flask run --host=0.0.0.0 --port=5001 &

# Step 4: Start the React frontend development server in the foreground
echo "Starting React frontend server on port 3000..."
npm start --prefix frontend
