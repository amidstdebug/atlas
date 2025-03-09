#!/bin/bash

# Function to kill processes on a given port using lsof
kill_process_on_port() {
    local port=$1
    # Get process IDs listening on the specified TCP port
    pids=$(lsof -ti tcp:$port)
    if [ -n "$pids" ]; then
        echo "Killing process(es) on port $port: $pids"
        kill -9 $pids
    else
        echo "No process found on port $port"
    fi
}

echo "Bringing down any running containers (if any)..."
docker compose -f docker-compose-mac.yml down

echo "Attempting to free ports 5002 and 11434..."
kill_process_on_port 5002
kill_process_on_port 11434

echo "Waiting a few seconds for the ports to be released..."
sleep 3

# Check if port 5002 is still in use (for the new host port)
if lsof -ti tcp:5002 >/dev/null; then
    echo "Error: Port 5002 is still in use. Please free it manually and try again."
    exit 1
else
    echo "Port 5002 is free."
fi

echo "Building Docker images using docker-compose-mac.yml..."
docker compose -f docker-compose-mac.yml build

echo "Starting containers using docker-compose-mac.yml..."
docker compose -f docker-compose-mac.yml up --remove-orphans