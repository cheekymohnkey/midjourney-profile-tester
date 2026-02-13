#!/usr/bin/env python3
"""Migration script: assign GUIDs to tests and rename existing image/analysis files to use GUID-based filenames.

Usage: python scripts/migrate_to_guids.py
"""
import sys
from pathlib import Path
import uuid
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from storage import get_storage
import test_prompts_manager as tpm


def ensure_guids(tests):
    changed = False
    for test in tests:
        if 'guid' not in test or not test['guid']:
            test['guid'] = uuid.uuid4().hex
            changed = True
    return changed


def build_safe(title):
    return title.replace(' ', '_').replace('/', '_')


def main():
    storage = get_storage()
    print("Loading tests...")
    tests = tpm.load_tests(status_filter=None)
    if not tests:
        print("No tests found in test_prompts.json")
        return

    changed = ensure_guids(tests)
    if changed:
        tpm.save_tests(tests)
        print("Assigned GUIDs to tests and saved test_prompts.json")
    else:
        print("All tests already have GUIDs")

    # Build mapping from safe_name -> guid and title -> guid
    safe_to_guid = {}
    title_to_guid = {}
    for t in tests:
        safe = build_safe(t.get('title',''))
        guid = t.get('guid')
        safe_to_guid[safe] = guid
        title_to_guid[t.get('title','')] = guid

    # Rename image files under profile_results
    print("Renaming image files in profile_results/ ...")
    all_files = storage.list_files('profile_results', '*')
    moved = 0
    for fp in all_files:
        parts = fp.split('/')
        if len(parts) < 3:
            continue
        prof = parts[1]
        filename = parts[2]
        filename_no_ext = filename.rsplit('.',1)[0]
        for safe, guid in safe_to_guid.items():
            prefix = f"{prof}_{safe}"
            if filename_no_ext.startswith(prefix):
                new_filename = filename.replace(f"{prof}_{safe}", f"{prof}_{guid}", 1)
                old_path = fp
                new_path = f"profile_results/{prof}/{new_filename}"
                try:
                    data = storage.read_bytes(old_path)
                    storage.write_bytes(new_path, data)
                    storage.delete(old_path)
                    moved += 1
                except Exception as e:
                    print(f"Failed to move {old_path} -> {new_path}: {e}")
                break

    print(f"Renamed {moved} image files.")

    # Update profile analyses to reference GUIDs instead of titles
    print("Updating profile_analyses files to use GUID keys for ratings...")
    analysis_files = storage.list_files('profile_analyses', '*_analysis.json')
    updated = 0
    for af in analysis_files:
        try:
            data = storage.read_json(af)
            if not data:
                continue
            ratings = data.get('ratings', {})
            new_ratings = {}
            changed_local = False
            for key, val in ratings.items():
                # key is test title or maybe old safe name; try title->guid mapping, else safe->guid
                guid = title_to_guid.get(key)
                if not guid:
                    guid = safe_to_guid.get(build_safe(key))
                if guid:
                    new_ratings[guid] = val
                    changed_local = True
                else:
                    # keep original key if no mapping
                    new_ratings[key] = val

            if changed_local:
                data['ratings'] = new_ratings
                storage.write_json(af, data)
                updated += 1
        except Exception as e:
            print(f"Failed to update {af}: {e}")

    print(f"Updated {updated} analysis files.")

    print("Migration complete.")


if __name__ == '__main__':
    main()
