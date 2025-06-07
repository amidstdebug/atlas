# Auto-Transcript Web App

Web app to perform live transcription and automated meeting minutes generation.

## Project Structure

The project follows a modern web application architecture with clear separation of concerns:

```
auto-transcript/
├── backend/              # Backend services
│   ├── api/              # API endpoints
│   ├── services/         # Business logic services
│   │   ├── transcription/  # Audio transcription services
│   │   ├── summary/        # Text summarization services
│   │   └── auth/           # Authentication services
│   ├── models/           # Data models and schemas
│   ├── config/           # Configuration files
│   ├── utils/            # Utility functions
│   └── tests/            # Backend tests
│
├── frontend/             # Vue.js frontend
│   ├── public/           # Static assets
│   └── src/              # Source code
│       ├── components/   # Reusable Vue components
│       ├── views/        # Page components
│       ├── services/     # API client services
│       ├── store/        # State management
│       ├── utils/        # Utility functions
│       ├── assets/       # Images and other assets
│       ├── styles/       # CSS/SCSS files
│       ├── router/       # Vue Router configuration
│       └── config/       # Frontend configuration
│
├── docker/               # Docker-related files
│   ├── backend/          # Backend Dockerfile and related scripts
│   ├── frontend/         # Frontend Dockerfile and related scripts
│   ├── services/         # Services Dockerfile and related scripts
│   |────── ollama/           # OLLAMA Dockerfile and related scripts
│   |────── whisper/         # WHISPER Dockerfile and related scripts
│   └── docker-compose.yml # Main Docker Compose file
│
├── start-dev.sh          # Script to start development environment
├── start-prod.sh         # Script to start production environment
├── stop.sh               # Script to stop all services
│
└── docs/                 # Documentation
```

## Overview

This application consists of three main components:

1. **Frontend**: Vue.js-based web interface for recording and displaying transcriptions
2. **Backend API**: FastAPI service for authentication and coordination
3. **Transcription Service**: FastAPI service for audio processing with Whisper
4. **Summarization Service**: LLM inference server for summarization

## Setup and Configuration

### Environment Variables

Both frontend and backend use environment files:

- Frontend: Copy `.env.example` to `.env.development` or `.env.production`
- Backend: Copy `.env.example` to `.env`

### Starting the Application

#### Development Mode

The simplest way to start the application in development mode is to use the provided script:

```bash
./start-dev.sh
```

This script will:
1. Create necessary environment files if they don't exist
2. Start the backend services using Docker Compose
3. Start the frontend development server with hot reloading

#### Production Mode

To start the application in production mode:

```bash
./start-prod.sh
```

This script will:
1. Create necessary environment files if they don't exist
2. Start all services (including the frontend) using Docker Compose
3. Build optimized production versions of all components

#### Stopping the Application

To stop all running services:

```bash
./stop.sh
```

### Manual Setup

If you prefer to start the services manually:

```bash
# Start the backend services
cd docker
docker-compose up --build

# Start the frontend in development mode
cd frontend
npm install
npm run serve
```

### Note

TODO: add ffmpeg-core.js to bundler when building i.e. webpack or vite