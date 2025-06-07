#!/bin/bash

# Stop all services
echo "Stopping Auto-Transcript services..."

# Navigate to project root
CD_PATH="$(dirname "$0")"
cd "$CD_PATH" || exit 1

# Stop docker services
docker-compose -f ./docker/docker-compose.yml down

echo "All services stopped."
