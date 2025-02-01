#!/bin/bash

# Function to kill processes on a given port using lsof
kill_process_on_port() {
    local port=$1
    # Get process IDs listening on the specified TCP port
    pids=$(lsof -ti tcp:$port)
    if [ -n "$pids" ]; then
        echo "Killing process(es) on port $port: $pids"
        kill -9 $pids
    else
        echo "No process found on port $port"
    fi
}

echo "Killing processes found on port 7860..."
kill_process_on_port 7860

echo "Running frontend server..."

# Check if npm is installed; if not, install Node.js (which includes npm) using Homebrew
if ! command -v npm &> /dev/null; then
    echo "npm not found. Installing Node.js and npm..."
    if command -v brew &> /dev/null; then
        brew install node
    else
        echo "Homebrew not found. Please install Homebrew from https://brew.sh and then run this script again."
        exit 1
    fi
fi

# Install dependencies and run the server
npm install
npm run serve