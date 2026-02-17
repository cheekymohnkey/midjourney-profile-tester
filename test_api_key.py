#!/usr/bin/env python3
"""Test that the OpenAI API key is working."""
import config
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)

logger.info('=== Testing OpenAI API Key ===\n')

# Check if key is loaded
if config.OPENAI_API_KEY:
    logger.info('✅ API key loaded from .env')
    logger.info('   Key starts with: %s...', config.OPENAI_API_KEY[:10])
else:
    logger.error('❌ No API key found')
    exit(1)

# Test OpenAI client initialization
try:
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    logger.info('✅ OpenAI client initialized successfully')
except Exception as e:
    logger.exception('❌ Failed to initialize OpenAI client: %s', e)
    exit(1)

# Test a simple API call
try:
    logger.info('\n🧪 Testing API with a simple completion...')
    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[{'role': 'user', 'content': 'Say "API works" and nothing else'}],
        max_tokens=10
    )
    result = response.choices[0].message.content
    logger.info('✅ API call successful!')
    logger.info('   Response: %s', result)
    logger.info('\n✨ All tests passed! Your new API key is working correctly.')
except Exception as e:
    logger.exception('❌ API call failed: %s', e)
    exit(1)
