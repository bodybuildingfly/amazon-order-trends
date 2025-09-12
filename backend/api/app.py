import os
from backend.api import create_app
from backend.api.extensions import scheduler

# Create the Flask app using the factory
app = create_app()

if __name__ == '__main__':
    # Start the scheduler only when running the app directly
    if not scheduler.running:
        scheduler.start()
    
    # Use Gunicorn for production, but this is fine for local dev
    host = os.environ.get('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_RUN_PORT', 5001))
    app.run(host=host, port=port)
