#!/bin/bash

# This script initializes and serves the Ollama model

echo "Starting Ollama service..."

# Start the Ollama server in background
ollama serve &

# Wait for Ollama server to start accepting connections
sleep 10

# Determine which model to ensure
MODEL_NAME=${OLLAMA_MODEL:-"gemma3:4b-it-qat"}

echo "Setting up model: $MODEL_NAME"

# Pull the model if it's not already present
if ! ollama list | grep -q "$MODEL_NAME"; then
    echo "Model not found. Pulling $MODEL_NAME..."
    ollama pull $MODEL_NAME
fi

echo "Model ready. Ollama server is running."

# Signal to Docker that we're ready
touch /tmp/ollama_ready

# Keep the container alive
tail -f /dev/null
