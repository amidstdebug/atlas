#!/bin/bash

# Start serving in the background
ollama serve &

# Wait a bit to ensure the server has time to start (you can adjust the sleep time if necessary)
sleep 10

echo "Creating the llm model..."
# Create the model
# ollama create atlas_llm -f ./ollama_serve/Modelfile_atlas
# ollama run qwen2.5
ollama pull llama3.1
ollama run llama3.1

# Wait for background jobs (i.e., ollama serve) to keep the container alive
wait