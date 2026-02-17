#!/usr/bin/env python3
"""Add --seed 20161027 back to PHOTO tests."""
from services.test_data_service import get_test_data_service
from storage import get_storage
#!/usr/bin/env python3
"""Add --seed 20161027 back to PHOTO tests."""
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

load_dotenv()
storage = get_storage()

# Read test prompts via TestDataService
tds = get_test_data_service()
tests = tds.list_tests()

# Update all PHOTO tests with seed
new_params = '--ar 16:9 --quality 4 --stylize 250 --raw --seed 20161027'
updated_count = 0

for test in tests:
    if test.get('section') == 'PHOTO':
        test['params'] = new_params
        updated_count += 1
        logger.info('Updated: %s', test['title'])

# Save locally (updates cache)
tds.save_tests(tests)

# Upload to S3
storage.write_json('test_prompts.json', tests)

logger.info('\n✓ Updated %d PHOTO tests', updated_count)
logger.info('✓ New params: %s', new_params)
logger.info('✓ Saved locally and uploaded to S3')

# Show VOID test params to confirm it's different
void_tests = [t for t in tests if t.get('section') == 'VOID']
if void_tests:
    logger.info('\nVOID test params (unchanged): %s', void_tests[0]['params'])
if void_tests:
