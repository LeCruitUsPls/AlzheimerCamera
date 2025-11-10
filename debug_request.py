#!/usr/bin/env python3
import requests
import json
import base64

# Test add_person endpoint
def test_add_person():
    # Create a simple test image (1x1 pixel PNG)
    test_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAI9jU77yQAAAABJRU5ErkJggg=="
    
    data = {
        "image": test_image_b64,
        "name": "Test Person",
        "relationship": "friend",
        "age": 30,
        "notes": "Test notes"
    }
    
    print("Sending request to add_person...")
    print(f"Data: {json.dumps(data, indent=2)}")
    
    try:
        response = requests.post(
            "http://localhost:8000/add_person",
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_add_person()