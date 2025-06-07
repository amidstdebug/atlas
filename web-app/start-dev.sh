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

if [ ! -f "./frontend/.env.development" ]; then
  echo "Creating frontend .env.development from example..."
  cp ./frontend/.env.example ./frontend/.env.development
fi

# Start services using docker-compose
echo "Starting backend services..."
docker-compose -f ./docker/docker-compose.yml -f ./docker/docker-compose-dev.yml up -d --build

# Start frontend development server
echo "Starting frontend development server..."
cd frontend || exit 1
npm install
npm run dev
