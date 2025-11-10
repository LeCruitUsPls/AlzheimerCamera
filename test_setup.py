#!/usr/bin/env python3
"""
Test script to verify AlzheimerCamera setup
Run this after setting up your environment
"""

import os
import sys
import requests
import json
from pathlib import Path

def test_backend_health():
    """Test if backend is running"""
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ Backend is running")
            return True
        else:
            print(f"❌ Backend returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Backend is not running. Start with: cd backend && python3 app.py")
        return False
    except Exception as e:
        print(f"❌ Backend test failed: {e}")
        return False

def test_env_file():
    """Test if .env file exists and has required variables"""
    env_path = Path("backend/.env")
    if not env_path.exists():
        print("❌ backend/.env file not found. Copy from .env.example")
        return False
    
    required_vars = [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY", 
        "AWS_DEFAULT_REGION",
        "S3_BUCKET_NAME",
        "REKOGNITION_COLLECTION_ID",
        "DYNAMODB_TABLE_NAME"
    ]
    
    with open(env_path) as f:
        content = f.read()
    
    missing = []
    for var in required_vars:
        if f"{var}=" not in content or f"{var}=your_" in content:
            missing.append(var)
    
    if missing:
        print(f"❌ Missing or unconfigured variables in .env: {', '.join(missing)}")
        return False
    
    print("✅ Environment file configured")
    return True

def test_dependencies():
    """Test if required Python packages are installed"""
    required_packages = [
        "flask", "flask_cors", "boto3", "python-dotenv", 
        "PIL", "requests"
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"❌ Missing Python packages: {', '.join(missing)}")
        print("Install with: pip install flask flask-cors boto3 python-dotenv pillow requests")
        return False
    
    print("✅ Python dependencies installed")
    return True

def test_frontend_setup():
    """Test if frontend is set up"""
    package_json = Path("frontend/package.json")
    node_modules = Path("frontend/node_modules")
    
    if not package_json.exists():
        print("❌ frontend/package.json not found")
        return False
    
    if not node_modules.exists():
        print("❌ frontend/node_modules not found. Run: cd frontend && npm install")
        return False
    
    print("✅ Frontend dependencies installed")
    return True

def main():
    print("🔍 Testing AlzheimerCamera Setup\n")
    
    tests = [
        ("Environment File", test_env_file),
        ("Python Dependencies", test_dependencies),
        ("Frontend Setup", test_frontend_setup),
        ("Backend Health", test_backend_health),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"Testing {name}...")
        result = test_func()
        results.append(result)
        print()
    
    if all(results):
        print("🎉 All tests passed! Your setup is ready.")
        print("\nNext steps:")
        print("1. Start backend: cd backend && python3 app.py")
        print("2. Start frontend: cd frontend && npm start")
    else:
        print("❌ Some tests failed. Please fix the issues above.")
        sys.exit(1)

if __name__ == "__main__":
    main()