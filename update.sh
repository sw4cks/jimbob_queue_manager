#!/bin/bash

# Script to automatically fetch and pull new changes from the git repository
# This script is designed to run on Linux Debian systems

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the project directory
cd "$SCRIPT_DIR" || exit 1

# Fetch the latest changes from the remote repository
echo "Fetching latest changes from repository..."
git fetch origin

# Pull the changes from the current branch
echo "Pulling changes from the remote branch..."
git pull origin "$(git rev-parse --abbrev-ref HEAD)"

# Check if pull was successful
if [ $? -eq 0 ]; then
    echo "Successfully updated the project!"
else
    echo "Error: Failed to pull changes from the repository"
    exit 1
fi

echo "Update complete."
