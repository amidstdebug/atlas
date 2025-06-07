#!/bin/bash

# Start development environment
echo "Starting Auto-Transcript in development mode..."

# Navigate to project root
CD_PATH="$(dirname "$0")"
cd "$CD_PATH" || exit 1

# Check if .env files exist, if not copy from examples
if [ ! -f "./backend/.env" ]; then
  echo "Creating backend .env from example..."
  cp ./backend/.env.example ./backend/.env
fi

# Start services using docker-compose
echo "Starting backend services..."
docker-compose -f ./docker/docker-compose.yml -f ./docker/docker-compose-dev.yml up --build