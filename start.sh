#!/bin/bash

# Script to start the jimbob_queue_manager bot with virtual environment

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the project directory
cd "$SCRIPT_DIR" || exit 1

# Activate virtual environment
source venv/bin/activate

# Run the bot
python ./main.py
