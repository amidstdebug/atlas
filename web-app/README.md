# Auto-Transcript Web App

Web app to perform live transcription and automated meeting minutes generation.

## Overview

This application consists of three main components:

1. **Frontend**: Vue.js-based web interface for recording and displaying transcriptions
2. **Backend Server**: FastAPI service for authentication and coordination
3. **Audio Server**: FastAPI service for audio processing with OpenAI Whisper
4. **Ollama Server**: LLM inference server for summarization

## Setup and Configuration

### Environment Variables

Both frontend and backend use environment files:

- Frontend: Copy `.env.example` to `.env.development` or `.env.production`
- Backend: Copy `.env.example` to `.env`

### Starting the Application

```bash
# Start the backend services
cd backend
docker-compose up --build

# Start the frontend in development mode
cd frontend
npm install
npm run serve
```

### Note

TODO: add ffmpeg-core.js to bundler when building i.e. webpack or vite