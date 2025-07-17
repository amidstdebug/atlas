#!/usr/bin/env python3
"""
Environment Setup Script
Creates a .env file from env.template if it doesn't exist
"""

import os
import shutil
from pathlib import Path

def setup_env():
    """Create .env file from template if it doesn't exist"""
    backend_dir = Path(__file__).parent
    template_file = backend_dir / "env.template"
    env_file = backend_dir / ".env"
    
    if not template_file.exists():
        print("❌ env.template not found!")
        return False
    
    if env_file.exists():
        print("✅ .env file already exists")
        return True
    
    try:
        shutil.copy2(template_file, env_file)
        print("✅ Created .env file from template")
        print("📝 Please review and customize the .env file as needed")
        return True
    except Exception as e:
        print(f"❌ Failed to create .env file: {e}")
        return False

if __name__ == "__main__":
    setup_env() 