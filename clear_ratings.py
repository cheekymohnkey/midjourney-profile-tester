#!/usr/bin/env python3
"""Clear ratings from all profiles to allow re-rating with improved prompt."""

from pathlib import Path
from storage import get_storage

storage = get_storage()

# List all analysis files (works for local or S3 - use storage.list_files when available)
analysis_dir = Path('profile_analyses')
files = sorted(analysis_dir.glob('*_analysis.json'))

print("Available profiles:")
for i, file in enumerate(files, 1):
    try:
        data = storage.read_json(str(file))
    except Exception:
        data = {}
    rating_count = len(data.get('ratings', {}))
    profile_id = data.get('profile_id', 'unknown')
    print(f"{i}. {profile_id} ({file.name}) - {rating_count} ratings")

print("\nClearing ALL profiles...")

for file in files:
    filepath = str(file)
    try:
        data = storage.read_json(filepath)
    except Exception:
        data = {}

    rating_count = len(data.get('ratings', {}))
    if rating_count > 0:
        data['ratings'] = {}
        data['profile_label'] = ''
        data['profile_dna'] = []
        if 'affinity_summary' in data:
            data['affinity_summary'] = {
                "native_fit": [],
                "workable": [],
                "resistant": []
            }
        # Save via storage so S3/local backends are handled
        storage.write_json(filepath, data)
        print(f"✅ Cleared {rating_count} ratings from {data.get('profile_id')}")
    else:
        print(f"⏭️  {data.get('profile_id')} already has 0 ratings")

print("\n✅ All profiles cleared and ready for re-rating with improved prompt!")
