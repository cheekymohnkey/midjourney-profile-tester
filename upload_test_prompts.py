#!/usr/bin/env python3
"""Upload test_prompts.json to S3."""
import json
from dotenv import load_dotenv
from storage import init_storage

# Load .env file
load_dotenv()

# Initialize S3 storage
storage = init_storage()

# Read local file
with open('test_prompts.json', 'r') as f:
    data = json.load(f)

# Upload to S3
storage.write_json('test_prompts.json', data)
print(f'✓ Successfully uploaded test_prompts.json to S3 with {len(data)} tests')

# Verify by reading back
stored_data = storage.read_json('test_prompts.json')
print(f'✓ Verified: S3 file contains {len(stored_data)} tests')
