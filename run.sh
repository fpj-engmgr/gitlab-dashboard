#!/bin/bash

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

if [ ! -f ".env" ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "Please edit .env and add your GitLab token before running the dashboard."
    exit 1
fi

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Running setup verification..."
python scripts/test_setup.py
if [ $? -ne 0 ]; then
    echo "Setup verification failed. Fix the issues above before starting."
    exit 1
fi

echo "Starting GitLab Dashboard..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
