#!/bin/bash
echo "Killing processes found on port 7860."
sudo fuser -k 7860/tcp
echo "Running frontend server."
npm install
npm run serve