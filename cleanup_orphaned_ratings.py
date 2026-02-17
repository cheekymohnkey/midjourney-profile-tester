#!/usr/bin/env python3
"""Remove orphaned test ratings from all profile analyses."""

import os
from storage import get_storage
import logging

logger = logging.getLogger(__name__)

storage = get_storage()

# Tests that were removed from test_prompts.json
removed_tests = [
    'Bold Makeup Portrait', 
    'Macro Water Droplets', 
    'Fantasy Photorealism', 
    'Surreal Still Life', 
    'Interior Test', 
    'Surrealism Test'
]

logger.info('Cleaning up orphaned ratings from profile analyses...\n')

total_removed = 0
for filename in sorted(os.listdir('profile_analyses')):
    if filename.endswith('_analysis.json'):
        profile_id = filename.replace('_analysis.json', '')
        filepath = f'profile_analyses/{filename}'

        data = storage.read_json(filepath) or {}

        # Remove orphaned ratings
        ratings = data.get('ratings', {})
        removed_count = 0
        for test in removed_tests:
            if test in ratings:
                del ratings[test]
                removed_count += 1

        if removed_count > 0:
            # Recalculate affinity summary
            affinity_summary = {
                "native_fit": [],
                "workable": [],
                "resistant": []
            }

            for test_name, rating in ratings.items():
                affinity = rating.get('affinity')
                if affinity in affinity_summary:
                    affinity_summary[affinity].append(test_name)

            data['affinity_summary'] = affinity_summary

            # Save back
            storage.write_json(filepath, data)

            logger.info('✅ %s: Removed %d orphaned ratings', profile_id, removed_count)
            total_removed += removed_count

logger.info('\n✅ Cleanup complete! Removed %d orphaned ratings across all profiles', total_removed)
logger.info('All profiles now have %d ratings (down from 40)', len(data.get('ratings', {})))
