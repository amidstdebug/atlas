# Use the official Python image as the base image
FROM python:3.10-slim

# Set the working directory
WORKDIR /usr/src/app

# Install system dependencies
RUN apt-get -y update
RUN apt-get install -y libsndfile1

# Copy the requirements.txt file to the container
COPY requirements.txt .

# Install pip dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy server directory
COPY server /usr/src/app/server

# Create necessary directories
RUN mkdir -p /usr/src/app/misc

# Copy startup test file
COPY server/misc/startup.wav /usr/src/app/misc/

# Create a directory for downloaded models
RUN mkdir -p /usr/src/app/models

# Expose port 5001
EXPOSE 5001

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV AUDIO_SERVER_URL=http://audio_server:8000
ENV OLLAMA_SERVER_URL=http://ollama:11434
ENV JWT_SECRET=meeting_minutes_transcription_2024_secure_key
ENV JWT_ALGORITHM=HS256
ENV OLLAMA_MODEL=qwen2.5

# Command to run the FastAPI server
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "5001", "--reload"]