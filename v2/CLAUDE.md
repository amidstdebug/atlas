# ATLAS V2 Development Guide

## Commands
- Backend setup: `conda create --name nemo python==3.10.12 && conda activate nemo`
- Backend install: `pip install -r backend/requirements.txt`
- Run backend: `cd backend && python app.py`
- Frontend install: `cd frontend && npm install`
- Frontend dev: `cd frontend && npm run dev`
- Frontend build: `cd frontend && npm run build`

## Code Style
- Use Python 3.10+ type hints throughout backend code
- Prefer dataclasses for structured data
- Use consistent error handling with try/except blocks
- Function/method names use snake_case
- Class names use PascalCase
- Backend uses PyTorch for tensor operations
- Frontend uses Vue 3 with Composition API
- Frontend components use PascalCase filenames and component names
- Keep processing functions pure when possible
- Document complex audio processing logic with clear comments

## Architecture
- Backend: FastAPI + WebSockets + PyTorch for real-time audio processing
- Frontend: Nuxt 3 + Vue 3 for reactive UI components
- Data flow: Audio capture → VAD → Diarization → Speaker clustering