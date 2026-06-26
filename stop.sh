#!/bin/bash
# Stop the GitLab Dashboard server

# Load PORT from .env if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | grep PORT | xargs)
fi

# Get port from environment or default to 8000
PORT=${PORT:-8000}

echo "Stopping GitLab Dashboard server on port $PORT..."

# Kill processes on the configured port
if lsof -ti :$PORT > /dev/null 2>&1; then
    lsof -ti :$PORT | xargs kill -9
    echo "Server stopped (port $PORT)"
else
    echo "No server running on port $PORT"
fi
