#!/usr/bin/env python3
from storage import get_storage
import os

storage = get_storage()

# Check what's in the profile analyses
removed_tests = [
    'Bold Makeup Portrait',
    'Macro Water Droplets',
    'Fantasy Photorealism',
    'Surreal Still Life',
    'Interior Test',
    'Surrealism Test',
]

print('Checking for orphaned ratings in profile analyses...\n')

total_orphaned = 0
for filename in sorted(os.listdir('profile_analyses')):
    if filename.endswith('_analysis.json'):
        profile_id = filename.replace('_analysis.json', '')
        filepath = f'profile_analyses/{filename}'
        try:
            data = storage.read_json(filepath)
        except Exception:
            data = {}

        ratings = data.get('ratings', {})
        orphaned = [test for test in removed_tests if test in ratings]

        if orphaned:
            print(f'{profile_id}: {len(orphaned)} orphaned ratings')
            for test in orphaned:
                print(f'  - {test}')
            total_orphaned += len(orphaned)

print(f'\nTotal orphaned ratings across all profiles: {total_orphaned}')
print('These ratings reference tests that no longer exist in test_prompts.json')
