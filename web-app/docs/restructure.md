# Project Restructuring Plan

This document outlines the implementation plan for restructuring the Auto-Transcript web application to improve maintainability, scalability, and code organization.

## Current Issues

1. Mixed concerns in the backend app.py file
2. No clear service layer separation
3. Docker configuration is scattered
4. Frontend lacks clear organization of components
5. Node modules at root level

## Restructuring Plan

### Phase 1: Backend Restructuring

1. **Create Service Layers**
   - Move transcription logic to `backend/services/transcription/`
   - Move summarization logic to `backend/services/summary/`
   - Move authentication logic to `backend/services/auth/`

2. **API Reorganization**
   - Split app.py into separate route files in `backend/api/`
   - Create router objects for each API domain (auth, transcription, summary)

3. **Model Refactoring**
   - Move Pydantic models to `backend/models/`
   - Organize by domain (auth models, transcription models, etc.)

4. **Configuration Management**
   - Move environment variable handling to `backend/config/`
   - Create configuration classes for different environments

### Phase 2: Frontend Restructuring

1. **Component Organization**
   - Move Vue components to appropriate directories:
     - Reusable components to `frontend/src/components/`
     - Page components to `frontend/src/views/`

2. **Service Layer**
   - Create API clients in `frontend/src/services/`
   - Organize by domain (auth service, transcription service, etc.)

3. **Asset Management**
   - Organize assets in `frontend/src/assets/`
   - Move styles to `frontend/src/styles/`

4. **State Management**
   - Implement proper state management in `frontend/src/store/`
   - Separate state by domain

### Phase 3: Docker Configuration

1. **Docker File Organization**
   - Move Docker-related files to `docker/` directory
   - Create separate dockerfiles for each service
   - Update docker-compose.yml to reference new locations

2. **Environment Configuration**
   - Create example environment files
   - Document required environment variables

### Phase 4: Documentation

1. **Update README.md**
   - Document new structure
   - Update setup instructions

2. **Create API Documentation**
   - Document API endpoints
   - Include request/response examples

## Implementation Steps

1. Create the new directory structure
2. Copy files to their new locations, adapting imports as needed
3. Update docker configuration
4. Test each component independently
5. Update documentation
6. Perform end-to-end testing

## Dependencies

1. Backend still requires audio_server and a vLLM service for transcription and summarization
2. Frontend requires the backend API to be running
3. Environment variables need to be properly configured

## Execution Timeline

1. Phase 1: Backend Restructuring - 2 days
2. Phase 2: Frontend Restructuring - 2 days
3. Phase 3: Docker Configuration - 1 day
4. Phase 4: Documentation - 1 day
5. Testing and Refinement - 2 days

Total estimated time: 8 days