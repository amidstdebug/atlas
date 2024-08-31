#!/bin/bash

## Set image and container names
#IMAGE_NAME="transcriber-api"
#CONTAINER_NAME="transcriber-api-container"

# Find and kill any process using port 5000 using ss
sudo fuser -k 5000/tcp

if [ -n "$PIDS" ]; then
    echo "Killing processes on port 5000: $PIDS"
    echo $PIDS | xargs sudo kill -9
else
    echo "No processes found on port 5000."
fi

## Check if the container is already running and remove it if necessary
#if [ "$(docker ps -aq -f name=$CONTAINER_NAME)" ]; then
#    echo "Stopping and removing the existing container..."
#    docker stop $CONTAINER_NAME
#    docker rm $CONTAINER_NAME
#fi

# Build the Docker image
echo "Building the Docker image..."
docker compose up --build

#echo "Docker container is running. Access the application at http://localhost:5000"
