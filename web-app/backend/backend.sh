#!/bin/bash
#
## Set image and container names
#IMAGE_NAME="transcriber-api"
#CONTAINER_NAME="transcriber-api-container"
#
# Find and kill any process using port 5000 using ss
sudo fuser -k 5000/tcp
sudo fuser -k 5000/tcp
#
sudo fuser -k 11434/tcp
sudo fuser -k 11434/tcp
#
sudo systemctl stop ollama.service
#
if [ -n "$PIDS" ]; then
    echo "Killing processes on port 5000: $PIDS"
    echo $PIDS | xargs sudo kill -9 5000
else
    echo "No processes found on port 5000."
fi
#
if [ -n "$PIDS" ]; then
    echo "Killing processes on port 11434: $PIDS"
    echo $PIDS | xargs sudo kill -9 11434
else
    echo "No processes found on port 11434."
fi
#
## Check if the container is already running and remove it if necessary
#if [ "$(docker ps -aq -f name=$CONTAINER_NAME)" ]; then
#    echo "Stopping and removing the existing container..."
#    docker stop $CONTAINER_NAME
#    docker rm $CONTAINER_NAME
#fi
#
# Build the Docker image
echo "Running backend server."
docker compose up --build --remove-orphans