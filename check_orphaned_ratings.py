#!/usr/bin/env python3
import json
import os

# Check what's in the profile analyses
removed_tests = [
    'Bold Makeup Portrait', 
    'Macro Water Droplets', 
    'Fantasy Photorealism', 
    'Surreal Still Life', 
    'Interior Test', 
    'Surrealism Test'
]

print('Checking for orphaned ratings in profile analyses...\n')

total_orphaned = 0
for filename in sorted(os.listdir('profile_analyses')):
    if filename.endswith('_analysis.json'):
        profile_id = filename.replace('_analysis.json', '')
        with open(f'profile_analyses/{filename}', 'r') as f:
            data = json.load(f)
        
        ratings = data.get('ratings', {})
        orphaned = [test for test in removed_tests if test in ratings]
        
        if orphaned:
            print(f'{profile_id}: {len(orphaned)} orphaned ratings')
            for test in orphaned:
                print(f'  - {test}')
            total_orphaned += len(orphaned)

print(f'\n⚠️  Total orphaned ratings across all profiles: {total_orphaned}')
print(f'These ratings reference tests that no longer exist in test_prompts.json')
