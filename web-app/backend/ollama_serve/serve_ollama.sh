#!/bin/bash

# Start serving in the background
ollama serve &

# Wait a bit to ensure the server has time to start (you can adjust the sleep time if necessary)
sleep 10

echo "Pulling model llama3.1..."
# Pull the 3.1 model
ollama pull llama3.1

echo "Creating the atc model..."
# Create the model
ollama create atc -f /root/ollama_serve/Modelfile_atc

# Wait for background jobs (i.e., ollama serve) to keep the container alive
wait
