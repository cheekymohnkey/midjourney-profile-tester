#!/usr/bin/env python3
from storage import get_storage
import os
from services.results_data_service import get_results_data_service
import logging

logger = logging.getLogger(__name__)


storage = get_storage()
# Use ResultsDataService to read analyses
rds = get_results_data_service()

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
files = []
try:
    files = storage.list_files('profile_analyses', pattern='*_analysis.json')
except Exception:
    import os
    files = [f for f in os.listdir('profile_analyses') if f.endswith('_analysis.json')]

for filename in sorted(files):
    fname = filename.split('/')[-1]
    profile_id = fname.replace('_analysis.json', '')
    try:
        data = rds.read_analysis(profile_id) or {}
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
