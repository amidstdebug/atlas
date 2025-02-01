#!/bin/bash

echo "Killing processes found on port 7860..."
sudo fuser -k 7860/tcp || true

echo "Running frontend server..."

# Check if npm is installed; if not, install Node.js and npm
if ! command -v npm &> /dev/null
then
    echo "npm not found. Installing Node.js and npm..."
    sudo apt-get update
    sudo apt-get install -y nodejs npm
fi

# Install deps and run the server
npm install
npm run serve
