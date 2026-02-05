#!/usr/bin/env python3
"""Fix rating keys in baseline_analysis.json by mapping Test N to actual test names"""

import json
import re
from pathlib import Path
import os

# Load test prompts
with open('test_prompts.json', 'r') as f:
    tests = json.load(f)

# Create dict of test titles
test_titles = {test['title']: test for test in tests}

# Load baseline analysis
baseline_path = 'profile_analyses/baseline_analysis.json'
with open(baseline_path, 'r') as f:
    baseline = json.load(f)

print("Current ratings keys:")
for key in sorted(baseline['ratings'].keys()):
    print(f"  - {key}")

# Check the profile_results/baseline folder for images
images_dir = 'profile_results/baseline'
if os.path.exists(images_dir):
    # Get list of image files sorted by modification time (order of upload)
    image_files = []
    for f in os.listdir(images_dir):
        if f.endswith(('.jpg', '.png', '.jpeg')) and f.startswith('baseline_'):
            filepath = os.path.join(images_dir, f)
            mtime = os.path.getmtime(filepath)
            image_files.append((f, mtime))
    
    # Sort by modification time (upload order)
    image_files.sort(key=lambda x: x[1])
    
    print(f"\nFound {len(image_files)} images in {images_dir}/ (sorted by upload time)")
    
    # Create mapping: Test N -> actual test name from filenames
    # Filenames are like "baseline_Test_Name.png"
    test_mapping = {}
    for idx, (filename, mtime) in enumerate(image_files, 1):
        # Extract test name from filename: baseline_Test_Name.png
        # Remove "baseline_" prefix and file extension
        name_part = filename.replace('baseline_', '').rsplit('.', 1)[0]
        # Convert underscores to spaces
        test_name = name_part.replace('_', ' ')
        
        # Check if this matches any test title
        if test_name in test_titles:
            # Check if there's a corresponding "Test N" rating
            test_key = f"Test {idx}"
            if test_key in baseline['ratings']:
                test_mapping[test_key] = test_name
                print(f"  Test {idx}: {filename} -> {test_name}")
    
    # Apply mapping to fix ratings
    fixed_ratings = {}
    changes_made = []
    for key, value in baseline['ratings'].items():
        if key in test_mapping:
            new_key = test_mapping[key]
            fixed_ratings[new_key] = value
            changes_made.append(f"  {key} -> {new_key}")
        else:
            fixed_ratings[key] = value
    
    if changes_made:
        print(f"\nChanges to be made ({len(changes_made)}):")
        for change in changes_made:
            print(change)
        
        # Update baseline
        baseline['ratings'] = fixed_ratings
        
        # Save
        with open(baseline_path, 'w') as f:
            json.dump(baseline, f, indent=2)
        
        print(f"\n✅ Fixed {len(changes_made)} rating keys in {baseline_path}")
    else:
        print("\n⚠️  No changes needed or couldn't map Test N to actual names")
else:
    print(f"\n❌ Directory {images_dir}/ not found. Cannot determine Test N mapping.")
    print("\nManual mapping needed. The 'Test 1' through 'Test 15' ratings need to be")
    print("mapped to actual test names based on the order they were uploaded.")
