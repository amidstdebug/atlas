# Migration Script

This document provides step-by-step instructions for migrating the existing project structure to the new, optimized structure.

## Prerequisites

1. Make sure you have a backup of your current code
2. Install required dependencies:
   ```bash
   sudo apt-get update && sudo apt-get install -y rsync
   ```

## Migration Steps

### 1. Create the new directory structure

```bash
# Create base directories
mkdir -p new-structure/{backend/{api,services/{transcription,summary,auth},models,config,utils,tests},frontend/{public,src/{components,views,services,store,utils,assets,styles,router,config}},docker/{backend/{transcription,ollama},frontend}}

# Create docker directory
mkdir -p new-structure/docker/{backend/{transcription,ollama},frontend}
```

### 2. Copy and restructure backend files

```bash
# Copy backend files
rsync -av --exclude="__pycache__" ./backend/server/app.py new-structure/backend/main.py
rsync -av --exclude="__pycache__" ./backend/server/funcs/ new-structure/backend/services/
rsync -av --exclude="__pycache__" ./backend/server/models/ new-structure/backend/models/prompts/
rsync -av --exclude="__pycache__" ./backend/server/tests/ new-structure/backend/tests/
rsync -av --exclude="__pycache__" ./backend/audio_server/main.py new-structure/backend/services/transcription/main.py
rsync -av --exclude="__pycache__" ./backend/audio_server/inference/ new-structure/backend/services/transcription/inference/
rsync -av --exclude="__pycache__" ./backend/.env.example new-structure/backend/.env.example
rsync -av --exclude="__pycache__" ./backend/requirements.txt new-structure/backend/requirements.txt
rsync -av --exclude="__pycache__" ./backend/ollama_server/serve_ollama.sh new-structure/docker/backend/ollama/serve_ollama.sh

# Create necessary __init__.py files
touch new-structure/backend/{__init__.py,api/__init__.py,services/__init__.py,services/transcription/__init__.py,services/summary/__init__.py,services/auth/__init__.py,models/__init__.py,config/__init__.py,utils/__init__.py}
```

### 3. Refactor backend code

```bash
# This step requires manual editing of files to adapt imports and organize code according to the new structure
# Follow these steps:

# 1. Split app.py into router files in the api directory
# 2. Move auth-related code to services/auth
# 3. Move transcription-related code to services/transcription
# 4. Move summary-related code to services/summary
# 5. Create proper models in the models directory
# 6. Update imports in all files

# Copy shell scripts
cp proposed-structure/start-dev.sh new-structure/
cp proposed-structure/start-prod.sh new-structure/
cp proposed-structure/stop.sh new-structure/

# Make scripts executable
chmod +x new-structure/*.sh

# See the sample files in the proposed-structure directory for guidance
```

### 4. Copy and restructure frontend files

```bash
# Copy frontend files
rsync -av --exclude="node_modules" ./frontend/src/components/ new-structure/frontend/src/components/
rsync -av --exclude="node_modules" ./frontend/src/assets/ new-structure/frontend/src/assets/
rsync -av --exclude="node_modules" ./frontend/src/methods/ new-structure/frontend/src/utils/
rsync -av --exclude="node_modules" ./frontend/src/styles/ new-structure/frontend/src/styles/
rsync -av --exclude="node_modules" ./frontend/src/router/ new-structure/frontend/src/router/
rsync -av --exclude="node_modules" ./frontend/src/services/ new-structure/frontend/src/services/
rsync -av --exclude="node_modules" ./frontend/public/ new-structure/frontend/public/
rsync -av --exclude="node_modules" ./frontend/package.json new-structure/frontend/package.json
rsync -av --exclude="node_modules" ./frontend/package-lock.json new-structure/frontend/package-lock.json
rsync -av --exclude="node_modules" ./frontend/.env.example new-structure/frontend/.env.example

# Create store directory for state management
mkdir -p new-structure/frontend/src/store
touch new-structure/frontend/src/store/index.js
```

### 5. Set up Docker configuration

```bash
# Copy Dockerfiles
rsync -av ./backend/Dockerfile new-structure/docker/backend/Dockerfile
rsync -av ./backend/audio_server/Dockerfile new-structure/docker/backend/transcription/Dockerfile
rsync -av ./backend/docker-compose.yml new-structure/docker/docker-compose.yml

# Update docker-compose.yml for the new structure
# This requires manual editing - see the sample file in proposed-structure/docker/docker-compose.yml
```

### 6. Testing the migration

```bash
# Test backend services
cd new-structure
docker-compose -f docker/docker-compose.yml build
docker-compose -f docker/docker-compose.yml up -d

# Test frontend
cd new-structure/frontend
npm install
npm run serve
```

### 7. Final steps

```bash
# After verifying that everything works correctly:
# 1. Back up the original structure
mv web-app web-app-backup

# 2. Replace with the new structure
mv new-structure web-app

# 3. Update documentation
# Update README.md with the new structure information
```

## Troubleshooting

If you encounter issues during migration:

1. Check import paths - most errors will be related to incorrect imports
2. Verify that all environment variables are correctly set
3. Check Docker container logs for service-specific errors
4. Ensure all required dependencies are installed