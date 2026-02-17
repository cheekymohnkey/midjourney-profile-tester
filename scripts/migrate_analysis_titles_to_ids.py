#!/usr/bin/env python3
"""Migrate profile analysis rating keys from test titles to canonical `id`/`guid` keys.

Creates a backup of each analysis file before writing. Safe to run multiple times.
"""
import datetime
import json
from pathlib import Path
from storage import get_storage
from services.test_data_service import get_test_data_service
from midjourney_profile_tester import canonical_test_key
import logging

logger = logging.getLogger(__name__)


def migrate_one(path: str):
    storage = get_storage()
    data = storage.read_json(path) or {}
    ratings = data.get('ratings', {}) or {}

    tds = get_test_data_service()
    tests = tds.list_tests()
    title_map = {t.get('title'): t for t in tests if t.get('title')}

    changes = []
    new_ratings = dict(ratings)  # copy

    for key in list(ratings.keys()):
        # If key is already an id/guid (i.e. not a known title), skip
        if key in title_map:
            test_obj = title_map.get(key)
            write_key = canonical_test_key(test_obj, key)
            if write_key != key:
                # Avoid overwriting an existing canonical entry
                if write_key in new_ratings:
                    # Skip migration if destination exists
                    changes.append((path, key, write_key, 'destination_exists'))
                    del new_ratings[key]
                else:
                    new_ratings[write_key] = new_ratings.pop(key)
                    changes.append((path, key, write_key, 'migrated'))

    if changes:
        # Backup original
        ts = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        backup_path = f"{path}.bak.{ts}"
        storage.write_json(backup_path, data)
        data['ratings'] = new_ratings
        storage.write_json(path, data)
        logger.info("Updated %s: %d changes, backup -> %s", path, len(changes), backup_path)
        for c in changes:
            logger.info(" %s", c)
    else:
        logger.info("No changes for %s", path)


def main():
    storage = get_storage()
    files = storage.list_files('profile_analyses', '*_analysis.json')
    if not files:
        logger.info('No analysis files found')
        return
    for f in files:
        migrate_one(f)


if __name__ == '__main__':
    main()
