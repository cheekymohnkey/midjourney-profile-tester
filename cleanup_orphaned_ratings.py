#!/usr/bin/env python3
"""Remove orphaned test ratings from all profile analyses."""

import os
from storage import get_storage
import logging

logger = logging.getLogger(__name__)

storage = get_storage()
# Use ResultsDataService for analysis read/write
from services.results_data_service import get_results_data_service
rds = get_results_data_service()

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
files = []
try:
    files = storage.list_files('profile_analyses', pattern='*_analysis.json')
except Exception:
    import os
    files = [f for f in os.listdir('profile_analyses') if f.endswith('_analysis.json')]

for filename in sorted(files):
    fname = filename.split('/')[-1]
    profile_id = fname.replace('_analysis.json', '')
    data = rds.read_analysis(profile_id) or {}

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

            # Save back via ResultsDataService
            rds.write_analysis(profile_id, data)

            logger.info('✅ %s: Removed %d orphaned ratings', profile_id, removed_count)
            total_removed += removed_count

logger.info('\n✅ Cleanup complete! Removed %d orphaned ratings across all profiles', total_removed)
logger.info('All profiles now have %d ratings (down from 40)', len(data.get('ratings', {})))
