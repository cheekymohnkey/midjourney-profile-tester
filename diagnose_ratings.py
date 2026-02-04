#!/usr/bin/env python3
"""Diagnose rating count mismatch between UI and baseline_analysis.json"""

import json

# Load baseline analysis
with open('profile_analyses/baseline_analysis.json', 'r') as f:
    baseline = json.load(f)

# Load test prompts
with open('test_prompts.json', 'r') as f:
    tests = json.load(f)

# Count ratings
rating_count = len(baseline.get('ratings', {}))
test_count = len(tests)

print("=" * 60)
print("RATING COUNT DIAGNOSIS")
print("=" * 60)
print(f"\nTotal tests in test_prompts.json: {test_count}")
print(f"Total ratings in baseline_analysis.json: {rating_count}")
print(f"Remaining: {test_count - rating_count}")

print("\n" + "=" * 60)
print("RATED TESTS (from baseline_analysis.json):")
print("=" * 60)
for i, test_name in enumerate(sorted(baseline.get('ratings', {}).keys()), 1):
    print(f"  {i:2d}. {test_name}")

print("\n" + "=" * 60)
print("ALL TEST TITLES (from test_prompts.json):")
print("=" * 60)
test_titles = [test['title'] for test in tests]
for i, title in enumerate(sorted(test_titles), 1):
    print(f"  {i:2d}. {title}")

# Find unrated tests
rated_set = set(baseline.get('ratings', {}).keys())
test_set = set(test_titles)

unrated = test_set - rated_set
rated_not_in_tests = rated_set - test_set

if unrated:
    print("\n" + "=" * 60)
    print(f"❌ UNRATED TESTS ({len(unrated)}):")
    print("=" * 60)
    for name in sorted(unrated):
        print(f"  - {name}")

if rated_not_in_tests:
    print("\n" + "=" * 60)
    print(f"⚠️  RATINGS FOR TESTS NOT IN test_prompts.json ({len(rated_not_in_tests)}):")
    print("=" * 60)
    for name in sorted(rated_not_in_tests):
        print(f"  - {name}")

if not unrated and not rated_not_in_tests:
    print("\n" + "=" * 60)
    print("✅ ALL TESTS RATED - NO DISCREPANCIES FOUND")
    print("=" * 60)
