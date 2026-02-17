#!/usr/bin/env python3
"""Dry-run for GUID migration: list rating keys that would be mapped to GUIDs in profile_analyses_backup."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_prompts_manager as tpm
import logging

logger = logging.getLogger(__name__)


def build_safe(title):
    return title.replace(' ', '_').replace('/', '_')


tests = tpm.load_tests(status_filter=None)
if not tests:
    logger.info('No tests loaded')
    sys.exit(0)

safe_to_guid = {}
title_to_guid = {}
for t in tests:
    safe = build_safe(t.get('title',''))
    guid = t.get('guid')
    safe_to_guid[safe]=guid
    title_to_guid[t.get('title','')]=guid

backup_dir = Path('profile_analyses_backup')
if not backup_dir.exists():
    logger.info('No profile_analyses_backup directory')
    sys.exit(0)

files = sorted([p for p in backup_dir.iterdir() if p.name.endswith('_analysis.json')])
logger.info('Found %d analysis files in profile_analyses_backup', len(files))
count_changes=0
for f in files:
    try:
        data = json.loads(f.read_text())
    except Exception as e:
        logger.exception('Failed to read %s', f)
        continue
    ratings = data.get('ratings',{})
    changes=[]
    for key in list(ratings.keys()):
        guid = title_to_guid.get(key) or safe_to_guid.get(build_safe(key))
        if guid and guid!=key:
            changes.append((key,guid))
    if changes:
        count_changes += 1
        logger.info('\n%s: %d keys to change', f.name, len(changes))
        for k,g in changes:
            logger.info("  '%s' -> '%s'", k, g)
logger.info('\nFiles with changes: %d', count_changes)
