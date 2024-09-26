#!/bin/zsh

# Define your sudo password
SUDO_PASSWORD="apeXvinylbuff325!"

# Name your tmux session
SESSION_NAME="auto_transcript_dev"

# Start a new tmux session with the specified name
tmux new-session -d -s $SESSION_NAME

# Rename the window (optional)
tmux rename-window -t $SESSION_NAME:0 'Dev'

# Split the window horizontally
tmux split-window -h

# Change to the appropriate directory and run the frontend script in the left pane (pane 0) with sudo
tmux send-keys -t $SESSION_NAME:0.0 "cd ./web-app/frontend && echo $SUDO_PASSWORD | sudo -S bash frontend.sh" C-m

# Change to the appropriate directory and run the backend script in the right pane (pane 1) with sudo
tmux send-keys -t $SESSION_NAME:0.1 "cd ./web-app/backend && echo $SUDO_PASSWORD | sudo -S bash backend.sh" C-m

# Select the left pane as the active pane
tmux select-pane -t $SESSION_NAME:0.0

# Attach to the session
tmux attach-session -t $SESSION_NAME