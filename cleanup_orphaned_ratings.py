#!/usr/bin/env python3
"""Remove orphaned test ratings from all profile analyses."""

import json
import os

# Tests that were removed from test_prompts.json
removed_tests = [
    'Bold Makeup Portrait', 
    'Macro Water Droplets', 
    'Fantasy Photorealism', 
    'Surreal Still Life', 
    'Interior Test', 
    'Surrealism Test'
]

print('Cleaning up orphaned ratings from profile analyses...\n')

total_removed = 0
for filename in sorted(os.listdir('profile_analyses')):
    if filename.endswith('_analysis.json'):
        profile_id = filename.replace('_analysis.json', '')
        filepath = f'profile_analyses/{filename}'
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
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
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f'✅ {profile_id}: Removed {removed_count} orphaned ratings')
            total_removed += removed_count

print(f'\n✅ Cleanup complete! Removed {total_removed} orphaned ratings across all profiles')
print(f'All profiles now have {len(data.get("ratings", {}))} ratings (down from 40)')
