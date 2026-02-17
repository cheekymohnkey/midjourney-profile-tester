#!/usr/bin/env python3
import os
import time
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# Force reload environment
load_dotenv(override=True)

logger.info('Environment check:')
logger.info("  USE_S3 env var: '%s'", os.getenv('USE_S3'))
logger.info("  S3_BUCKET_NAME: '%s'", os.getenv('S3_BUCKET_NAME'))

# Test storage initialization with timing
logger.info('\n--- Testing Local Storage ---')
os.environ['USE_S3'] = 'false'
start = time.time()
from storage import init_storage
storage = init_storage(use_s3=False)
logger.info('Init time: %.3fs', time.time() - start)

# Test reading test_prompts.json
start = time.time()
tests = storage.read_json('test_prompts.json')
elapsed = time.time() - start
logger.info('Read %d tests in %.3fs', len(tests), elapsed)

# Test S3 (if credentials are valid)
logger.info('\n--- Testing S3 Storage ---')
try:
    # Reset storage singleton
    import storage as storage_module
    storage_module._storage = None
    
    start = time.time()
    storage_s3 = init_storage(use_s3=True)
    logger.info('Init time: %.3fs', time.time() - start)
    
    start = time.time()
    tests_s3 = storage_s3.read_json('test_prompts.json')
    elapsed = time.time() - start
    logger.info('Read %d tests in %.3fs', len(tests_s3), elapsed)
except Exception as e:
    logger.exception('S3 test failed: %s', e)
