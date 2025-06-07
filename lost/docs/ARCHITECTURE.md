# Auto-Transcript Architecture

This document provides an overview of the Auto-Transcript application architecture and how its components interact.

## Overall Architecture

Auto-Transcript is a web application that consists of the following major components:

1. **Frontend**: A Vue.js single-page application
2. **Backend API**: A FastAPI service for authentication and coordination
3. **Transcription Service**: A FastAPI service for audio processing
4. **Summarization Service**: An Ollama-based LLM service for summarization

These components are containerized using Docker and orchestrated with Docker Compose.

## Component Details

### Frontend

The frontend is built with Vue.js 3 and uses the following main libraries:

- **Vuex**: For state management
- **Vue Router**: For client-side routing
- **Element Plus**: For UI components
- **Axios**: For HTTP requests

The frontend is organized as follows:

- `components/`: Reusable UI components
- `views/`: Page-level components
- `services/`: API client services
- `store/`: Vuex store modules
- `router/`: Vue Router configuration
- `utils/`: Utility functions
- `assets/`: Static assets like images
- `styles/`: CSS/SCSS stylesheets

### Backend API

The backend API is built with FastAPI and is responsible for:

- User authentication and authorization
- Coordination between frontend and services
- Processing requests and responses

The backend follows a layered architecture:

- `api/`: API route handlers
- `services/`: Business logic services
- `models/`: Data models and schemas
- `config/`: Application configuration
- `utils/`: Utility functions

### Transcription Service

The transcription service processes audio recordings and converts them to text using a Whisper-based model. It runs as a separate service to handle the intensive computation required for speech-to-text.

### Summarization Service

The summarization service uses an LLM (Ollama) to generate summaries from transcriptions. It runs as a separate service to isolate the LLM processing.

## Data Flow

1. The user interacts with the Vue.js frontend
2. Frontend makes API calls to the backend
3. Backend authenticates and routes requests to appropriate services
4. Services process requests and return results
5. Backend formats responses and sends them back to the frontend
6. Frontend updates its state and displays the results to the user

## WebSocket Flow for Real-time Transcription

1. Frontend establishes a WebSocket connection with the backend
2. User starts recording audio
3. Audio chunks are sent to the backend via WebSocket
4. Backend forwards audio to the transcription service
5. Transcription service processes the audio and returns text
6. Backend sends the transcription back to the frontend via WebSocket
7. Frontend updates the UI in real-time

## Authentication Flow

1. User logs in with credentials
2. Backend validates credentials
3. Backend generates a JWT token
4. Token is sent to the frontend
5. Frontend stores the token
6. Frontend includes the token in all subsequent requests
7. Backend validates the token for each request

## Containerization

Each component is containerized using Docker:

- Frontend: Nginx serving static files in production, development server for development
- Backend API: Python-based FastAPI container
- Transcription Service: Python-based FastAPI container with GPU acceleration
- Summarization Service: Ollama container with GPU acceleration

Docker Compose orchestrates these containers, handling networking, volumes, and resource allocation.