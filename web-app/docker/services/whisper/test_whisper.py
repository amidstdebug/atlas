#!/usr/bin/env python3
"""
Test script for Whisper service
"""
import requests
import tempfile
import os
from pathlib import Path

def test_whisper_service():
    """Test the Whisper service with a simple audio file"""
    
    # Create a simple test audio file (silence)
    # In a real test, you would use an actual audio file
    test_content = b"test audio content"  # This would be real audio data
    
    # Test the health endpoint
    try:
        response = requests.get("http://localhost:8000/health")
        print(f"Health check: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"Health check failed: {e}")
        return False
    
    # Test the transcription endpoint
    try:
        files = {'file': ('test.webm', test_content, 'audio/webm')}
        response = requests.post("http://localhost:8000/transcribe", files=files)
        print(f"Transcription test: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {response.json()}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Transcription test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    test_whisper_service()