#!/usr/bin/env python3
from storage import get_storage
import os
import logging

logger = logging.getLogger(__name__)

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

logger.info('Checking for orphaned ratings in profile analyses...\n')

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
            logger.info('%s: %d orphaned ratings', profile_id, len(orphaned))
            for test in orphaned:
                logger.info('  - %s', test)
            total_orphaned += len(orphaned)

logger.info('\nTotal orphaned ratings across all profiles: %d', total_orphaned)
logger.info('These ratings reference tests that no longer exist in test_prompts.json')
