    # --- Stage 1: Build the React Frontend ---
    FROM node:18-alpine AS build-stage
    WORKDIR /app/frontend
    COPY frontend/package.json ./
    RUN npm install
    COPY frontend/ ./
    RUN npm run build

    # --- Stage 2: Create the Final Python Server Image ---
    FROM python:3.12-slim
    WORKDIR /app

    # Install Python dependencies
    COPY api/requirements.txt ./api/
    COPY ingestion/requirements.txt ./ingestion/
    COPY shared/db.py ./shared/
    RUN pip install --no-cache-dir -r api/requirements.txt && \
        pip install --no-cache-dir -r ingestion/requirements.txt

    # Copy the backend API code
    COPY api/ ./api/
    
    # Copy the built static frontend from the build-stage
    COPY --from=build-stage /app/frontend/build ./build
    
    # Add a simple entrypoint to serve the static files with the API
    RUN echo 'from api.app import app\n\
    from flask import send_from_directory\n\
    import os\n\n\
    @app.route("/", defaults={"path": ""})\n\
    @app.route("/<path:path>")\n\
    def serve(path):\n\
        if path != "" and os.path.exists(os.path.join("build", path)):\n\
            return send_from_directory("build", path)\n\
        else:\n\
            return send_from_directory("build", "index.html")\n\
    ' >> api/app.py

    EXPOSE 5001

    # Run the application using a production server
    CMD ["gunicorn", "--bind", "0.0.0.0:5001", "api.app:app"]
    