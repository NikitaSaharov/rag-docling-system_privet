import requests
import os

api_key = os.getenv('POLZA_API_KEY')
print(f"API Key loaded: {api_key[:20]}...")

try:
    resp = requests.post(
        'https://api.polza.ai/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        },
        json={
            'model': 'deepseek-chat',
            'messages': [{'role': 'user', 'content': 'Say hi in Russian'}],
            'max_tokens': 20
        },
        timeout=30
    )
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.json()}")
except Exception as e:
    print(f"Error: {e}")
