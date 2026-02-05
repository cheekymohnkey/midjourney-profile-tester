#!/usr/bin/env python3
"""Test that the OpenAI API key is working."""
import config
from openai import OpenAI

print('=== Testing OpenAI API Key ===\n')

# Check if key is loaded
if config.OPENAI_API_KEY:
    print(f'✅ API key loaded from .env')
    print(f'   Key starts with: {config.OPENAI_API_KEY[:10]}...')
else:
    print('❌ No API key found')
    exit(1)

# Test OpenAI client initialization
try:
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    print('✅ OpenAI client initialized successfully')
except Exception as e:
    print(f'❌ Failed to initialize OpenAI client: {e}')
    exit(1)

# Test a simple API call
try:
    print('\n🧪 Testing API with a simple completion...')
    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[{'role': 'user', 'content': 'Say "API works" and nothing else'}],
        max_tokens=10
    )
    result = response.choices[0].message.content
    print(f'✅ API call successful!')
    print(f'   Response: {result}')
    print('\n✨ All tests passed! Your new API key is working correctly.')
except Exception as e:
    print(f'❌ API call failed: {e}')
    exit(1)
