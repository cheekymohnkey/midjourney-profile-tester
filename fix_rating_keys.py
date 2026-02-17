#!/usr/bin/env python3
"""Fix rating keys in baseline_analysis.json by mapping Test N to actual test names"""

import re
import os
from pathlib import Path
from test_prompts_manager import load_tests
from storage import get_storage
import logging

logger = logging.getLogger(__name__)

storage = get_storage()

# Load test prompts
tests = load_tests()

# Create dict of test titles
test_titles = {test['title']: test for test in tests}

# Load baseline analysis via storage
baseline_path = 'profile_analyses/baseline_analysis.json'
baseline = storage.read_json(baseline_path) or {}

logger.info('Current ratings keys:')
for key in sorted(baseline.get('ratings', {}).keys()):
    logger.info('  - %s', key)

# Check the profile_results/baseline folder for images
images_dir = Path('profile_results/baseline')
if images_dir.exists():
    # Get list of image files sorted by modification time (order of upload)
    image_files = []
    for f in os.listdir(images_dir):
        if f.endswith(('.jpg', '.png', '.jpeg')) and f.startswith('baseline_'):
            filepath = images_dir / f
            mtime = filepath.stat().st_mtime
            image_files.append((f, mtime))

    # Sort by modification time (upload order)
    image_files.sort(key=lambda x: x[1])

    logger.info('\nFound %d images in %s/ (sorted by upload time)', len(image_files), images_dir)

    # Create mapping: Test N -> actual test name from filenames
    test_mapping = {}
    for idx, (filename, mtime) in enumerate(image_files, 1):
        name_part = filename.replace('baseline_', '').rsplit('.', 1)[0]
        test_name = name_part.replace('_', ' ')
            if test_name in test_titles:
                test_key = f"Test {idx}"
                if test_key in baseline.get('ratings', {}):
                    test_mapping[test_key] = test_name
                    logger.info('  Test %d: %s -> %s', idx, filename, test_name)

    # Apply mapping to fix ratings
    fixed_ratings = {}
    changes_made = []
    for key, value in baseline.get('ratings', {}).items():
        if key in test_mapping:
            new_key = test_mapping[key]
            fixed_ratings[new_key] = value
            changes_made.append(f"  {key} -> {new_key}")
        else:
            fixed_ratings[key] = value

    if changes_made:
        logger.info('\nChanges to be made (%d):', len(changes_made))
        for change in changes_made:
            logger.info('%s', change)

        # Update baseline
        baseline['ratings'] = fixed_ratings

        # Save via storage
        storage.write_json(baseline_path, baseline)

        logger.info('\n✅ Fixed %d rating keys in %s', len(changes_made), baseline_path)
    else:
        logger.info('\n⚠️  No changes needed or couldn\'t map Test N to actual names')
else:
    logger.error('\n❌ Directory %s/ not found. Cannot determine Test N mapping.', images_dir)
    logger.info('\nManual mapping needed. The \'Test 1\' through \'Test 15\' ratings need to be')
    logger.info('mapped to actual test names based on the order they were uploaded.')
