
"""
Single Test: Categories Request
Tests the most important function - getting categories through Gemini
"""

import requests
import json

def test_categories():
    url = "http://localhost:8000/chat/text"
    payload = {
        "message": "What complaint categories are available?"
    }
    
    print("🧪 Testing Categories Request via Gemini Chat")
    print("="*50)
    print(f"URL: {url}")
    print(f"Message: {payload['message']}")
    print("\n🔄 Making request...")
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        
        print(f"✅ Status Code: {response.status_code}")
        print(f"📄 Response:")
        print(json.dumps(response.json(), indent=2))
        
        # Check if it worked
        data = response.json()
        if data.get("success") and "categories" in data.get("response", "").lower():
            print("\n🎉 SUCCESS: Gemini successfully called the categories API!")
        elif "technical problem" in data.get("response", "").lower():
            print("\n⚠️  ISSUE: API call failed - check if your original API is running")
        else:
            print("\n🤔 UNCLEAR: Check the response above")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Is the Gemini agent running?")
        print("💡 Start it with: python main_with_gemini.py")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_categories()