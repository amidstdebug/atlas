#!/bin/bash

# Define your sudo password (if needed)
SUDO_PASSWORD="abc"

# Name your tmux session
SESSION_NAME="auto_transcript_dev"

# Create and detach a new tmux session
tmux new-session -d -s "$SESSION_NAME" -n Dev

# Give tmux a moment to initialize
sleep 1

# Split the window horizontally: left pane (frontend), right pane (backend)
tmux split-window -h -t "$SESSION_NAME"

# Start the frontend in pane 0
tmux send-keys -t "$SESSION_NAME:0.0" \
  "cd ./web-app/frontend && bash frontend.sh" C-m

# Start the backend in pane 1
tmux send-keys -t "$SESSION_NAME:0.1" \
  "cd ./web-app/backend && bash backend.sh" C-m

# Select the left pane by default
tmux select-pane -t "$SESSION_NAME:0.0"

# Finally, attach to the tmux session
tmux attach-session -t "$SESSION_NAME"
