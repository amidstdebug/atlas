#!/usr/bin/env python3
"""
Health check script for Whisper service
"""

import requests
import sys
import time

def check_health():
    """Check if the Whisper service is healthy"""
    try:
        # Try to connect to the health endpoint
        response = requests.get("http://localhost:8000/health", timeout=5)
        
        if response.status_code == 200:
            print("✅ Whisper service is healthy")
            return True
        else:
            print(f"❌ Whisper service returned status {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to Whisper service")
        return False
    except requests.exceptions.Timeout:
        print("❌ Whisper service health check timed out")
        return False
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

if __name__ == "__main__":
    # Try multiple times with short delays
    for attempt in range(3):
        if check_health():
            sys.exit(0)
        if attempt < 2:  # Don't sleep after the last attempt
            time.sleep(1)
    
    sys.exit(1) 