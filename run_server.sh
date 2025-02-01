#!/bin/bash

# Start backend in a background process
cd web-app/backend && bash backend.sh &

# Start frontend in a background process
cd web-app/frontend && bash frontend.sh &

# Wait for both to finish (optional)
wait

echo "Both backend and frontend have started."