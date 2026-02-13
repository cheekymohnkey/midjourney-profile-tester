#!/usr/bin/env python3
"""Dry-run for GUID migration: list rating keys that would be mapped to GUIDs in profile_analyses_backup."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_prompts_manager as tpm


def build_safe(title):
    return title.replace(' ', '_').replace('/', '_')


tests = tpm.load_tests(status_filter=None)
if not tests:
    print('No tests loaded')
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
    print('No profile_analyses_backup directory')
    sys.exit(0)

files = sorted([p for p in backup_dir.iterdir() if p.name.endswith('_analysis.json')])
print(f'Found {len(files)} analysis files in profile_analyses_backup')
count_changes=0
for f in files:
    try:
        data = json.loads(f.read_text())
    except Exception as e:
        print(f'Failed to read {f}: {e}')
        continue
    ratings = data.get('ratings',{})
    changes=[]
    for key in list(ratings.keys()):
        guid = title_to_guid.get(key) or safe_to_guid.get(build_safe(key))
        if guid and guid!=key:
            changes.append((key,guid))
    if changes:
        count_changes += 1
        print(f"\n{f.name}: {len(changes)} keys to change")
        for k,g in changes:
            print(f"  '{k}' -> '{g}'")

print(f"\nFiles with changes: {count_changes}")
