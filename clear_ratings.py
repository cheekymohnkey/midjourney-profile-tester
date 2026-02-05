#!/usr/bin/env python3
"""Clear ratings from all profiles to allow re-rating with improved prompt."""

import json
from pathlib import Path

# List all analysis files
analysis_dir = Path('profile_analyses')
files = sorted(analysis_dir.glob('*_analysis.json'))

print("Available profiles:")
for i, file in enumerate(files, 1):
    with open(file) as f:
        data = json.load(f)
    rating_count = len(data.get('ratings', {}))
    profile_id = data.get('profile_id', 'unknown')
    print(f"{i}. {profile_id} ({file.name}) - {rating_count} ratings")

print("\nClearing ALL profiles...")

for file in files:
    with open(file, 'r') as f:
        data = json.load(f)
    
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
        
        with open(file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✅ Cleared {rating_count} ratings from {data.get('profile_id')}")
    else:
        print(f"⏭️  {data.get('profile_id')} already has 0 ratings")

print("\n✅ All profiles cleared and ready for re-rating with improved prompt!")
