#!/bin/bash

# Start serving in the background
ollama serve &

# Wait a bit to ensure the server has time to start (you can adjust the sleep time if necessary)
sleep 10

echo "Creating the llm model..."
# Create the model
# ollama create atlas_llm -f ./ollama_serve/Modelfile_atlas
#ollama pull qwen2.5
#ollama run qwen2.5
#ollama pull deepseek-r1:7b
#ollama run deepseek-r1:7b
ollama pull hf.co/bartowski/DeepSeek-R1-Distill-Qwen-7B-GGUF:IQ4_XS

ollama run hf.co/bartowski/DeepSeek-R1-Distill-Qwen-7B-GGUF:IQ4_XS


# ollama pull llama3.1
# ollama run llama3.1

# Wait for background jobs (i.e., ollama serve) to keep the container alive
wait