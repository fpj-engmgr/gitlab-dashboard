#!/bin/bash
# Start the GitLab Dashboard server
# Port is configurable via PORT env var, defaults to 8000 (set in .env)

# Load PORT from .env if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | grep PORT | xargs)
fi

# Get port from environment or default to 8000
PORT=${PORT:-8000}

# Kill any existing process on the port
echo "Checking for existing processes on port $PORT..."
if lsof -ti :$PORT > /dev/null 2>&1; then
    echo "Killing existing processes on port $PORT..."
    lsof -ti :$PORT | xargs kill -9
    sleep 2
fi

# Start the server
echo "Starting GitLab Dashboard server on http://localhost:$PORT"
cd "$(dirname "$0")"
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port $PORT
