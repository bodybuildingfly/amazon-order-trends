# --- Stage 1: Build the React Frontend ---
FROM node:18-alpine AS build-stage
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Create the Final Python Server Image ---
FROM python:3.12-slim
WORKDIR /app

# Install system-level dependencies needed for Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    zlib1g-dev \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Copy only the requirements files first to leverage Docker cache
COPY backend/api/requirements.txt ./api-requirements.txt
COPY backend/ingestion/requirements.txt ./ingestion-requirements.txt
RUN pip install --no-cache-dir -r api-requirements.txt && \
    pip install --no-cache-dir -r ingestion-requirements.txt

# Copy the entire backend application code
COPY backend/ .

# Copy the built static frontend from the build-stage
COPY --from=build-stage /app/frontend/build ./frontend/build

EXPOSE 5001

# Copy the entrypoint script and make it executable
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Set the entrypoint to run the script, which will in turn start Gunicorn
ENTRYPOINT ["./entrypoint.sh"]