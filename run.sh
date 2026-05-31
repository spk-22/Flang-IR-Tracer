#!/usr/bin/env bash
set -e

# Activate the virtual environment
source .venv/bin/activate

# Start the FastAPI server using uvicorn
python3 -m uvicorn flang_tracer.server:app --host 0.0.0.0 --port 8000
