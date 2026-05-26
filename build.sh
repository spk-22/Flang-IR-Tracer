#!/usr/bin/env bash
set -e

# Create a virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

# Activate the virtual environment
source .venv/bin/activate

# Upgrade pip and install dependencies
export PIP_BREAK_SYSTEM_PACKAGES=1
pip install --break-system-packages -r requirements.txt
