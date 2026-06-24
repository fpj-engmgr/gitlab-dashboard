#!/bin/bash
# Start the GitLab Dashboard server
# This script will kill any existing server on port 8000 before starting

# Kill any existing process on port 8000
echo "Checking for existing processes on port 8000..."
if lsof -ti :8000 > /dev/null 2>&1; then
    echo "Killing existing processes on port 8000..."
    lsof -ti :8000 | xargs kill -9
    sleep 2
fi

# Start the server
echo "Starting GitLab Dashboard server on http://localhost:8000"
cd "$(dirname "$0")"
source venv/bin/activate
uvicorn app.main:app --reload
