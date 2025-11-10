#!/usr/bin/env python3
import requests
import json

# Test mobile connection to backend
MOBILE_API_URL = "http://10.43.20.209:8000"

def test_mobile_endpoints():
    print("Testing mobile connection to backend...")
    print(f"API URL: {MOBILE_API_URL}")
    print()
    
    # Test health
    try:
        response = requests.get(f"{MOBILE_API_URL}/health", timeout=5)
        print(f"✅ Health: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"❌ Health failed: {e}")
        return
    
    # Test reminders
    try:
        response = requests.get(f"{MOBILE_API_URL}/reminders", timeout=10)
        data = response.json()
        print(f"✅ Reminders: {response.status_code}")
        print(f"   Found {len(data.get('reminders', []))} people")
        
        # Show first person if exists
        if data.get('reminders'):
            first_person = data['reminders'][0]
            print(f"   First person: {first_person.get('name')} ({first_person.get('relationship')})")
            
    except Exception as e:
        print(f"❌ Reminders failed: {e}")

if __name__ == "__main__":
    test_mobile_endpoints()