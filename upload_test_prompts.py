#!/usr/bin/env python3
"""Upload test_prompts.json to S3 using the cached source from
`test_prompts_manager` so we don't repeatedly hit the filesystem.
"""
from test_prompts_manager import load_tests
from dotenv import load_dotenv
from storage import init_storage

# Load .env file
load_dotenv()

# Initialize S3 storage (or local depending on env)
storage = init_storage()

# Read from cached source
data = load_tests()

# Upload to S3
storage.write_json('test_prompts.json', data)
print(f'✓ Successfully uploaded test_prompts.json to S3 with {len(data)} tests')

# Verify by reading back
stored_data = storage.read_json('test_prompts.json')
print(f'✓ Verified: S3 file contains {len(stored_data)} tests')
