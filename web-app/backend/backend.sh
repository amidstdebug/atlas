#!/bin/bash

# Kill processes on ports 5000 and 11434, ignoring errors if none are found
sudo fuser -k 5000/tcp || true
sudo fuser -k 11434/tcp || true

# Attempt to stop ollama.service only if systemd is actually supported
if command -v systemctl &> /dev/null
then
    echo "Stopping ollama.service using systemctl..."
    sudo systemctl stop ollama.service
else
    echo "systemctl not found or not supported in WSL. Skipping stopping ollama.service..."
fi

echo "Running backend server..."

# Build and run with Docker Compose
docker compose up --build --remove-orphans
