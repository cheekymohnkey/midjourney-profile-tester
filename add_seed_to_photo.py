#!/usr/bin/env python3
"""Add --seed 20161027 back to PHOTO tests."""
import json
from storage import get_storage
from dotenv import load_dotenv

load_dotenv()
storage = get_storage()

# Read test prompts from local file
with open('test_prompts.json', 'r') as f:
    tests = json.load(f)

# Update all PHOTO tests with seed
new_params = '--ar 16:9 --quality 4 --stylize 250 --raw --seed 20161027'
updated_count = 0

for test in tests:
    if test.get('section') == 'PHOTO':
        test['params'] = new_params
        updated_count += 1
        print(f'Updated: {test["title"]}')

# Save locally
with open('test_prompts.json', 'w') as f:
    json.dump(tests, f, indent=2)

# Upload to S3
storage.write_json('test_prompts.json', tests)

print(f'\n✓ Updated {updated_count} PHOTO tests')
print(f'✓ New params: {new_params}')
print(f'✓ Saved locally and uploaded to S3')

# Show VOID test params to confirm it's different
void_tests = [t for t in tests if t.get('section') == 'VOID']
if void_tests:
    print(f'\nVOID test params (unchanged): {void_tests[0]["params"]}')
