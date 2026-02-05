#!/usr/bin/env python3
import os
import time
from dotenv import load_dotenv

# Force reload environment
load_dotenv(override=True)

print(f"Environment check:")
print(f"  USE_S3 env var: '{os.getenv('USE_S3')}'")
print(f"  S3_BUCKET_NAME: '{os.getenv('S3_BUCKET_NAME')}'")

# Test storage initialization with timing
print(f"\n--- Testing Local Storage ---")
os.environ['USE_S3'] = 'false'
start = time.time()
from storage import init_storage
storage = init_storage(use_s3=False)
print(f"Init time: {time.time() - start:.3f}s")

# Test reading test_prompts.json
start = time.time()
tests = storage.read_json('test_prompts.json')
elapsed = time.time() - start
print(f"Read {len(tests)} tests in {elapsed:.3f}s")

# Test S3 (if credentials are valid)
print(f"\n--- Testing S3 Storage ---")
try:
    # Reset storage singleton
    import storage as storage_module
    storage_module._storage = None
    
    start = time.time()
    storage_s3 = init_storage(use_s3=True)
    print(f"Init time: {time.time() - start:.3f}s")
    
    start = time.time()
    tests_s3 = storage_s3.read_json('test_prompts.json')
    elapsed = time.time() - start
    print(f"Read {len(tests_s3)} tests in {elapsed:.3f}s")
except Exception as e:
    print(f"S3 test failed: {e}")
