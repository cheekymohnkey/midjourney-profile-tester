#!/usr/bin/env python3
"""Analyze which tests provide the most differentiation value."""

from storage import get_storage
import os
import math
from collections import defaultdict

storage = get_storage()

# Load all analysis files
analyses = {}
for filename in os.listdir('profile_analyses'):
    if filename.endswith('_analysis.json'):
        profile_id = filename.replace('_analysis.json', '')
        try:
            analyses[profile_id] = storage.read_json(f'profile_analyses/{filename}')
        except Exception:
            analyses[profile_id] = {}

# Analyze test variance
prompt_stats = defaultdict(lambda: {'native': 0, 'workable': 0, 'resistant': 0, 'total': 0})

for profile_id, data in analyses.items():
    ratings = data.get('ratings', {})
    for prompt_title, rating in ratings.items():
        affinity = rating.get('affinity', 'unknown')
        prompt_stats[prompt_title]['total'] += 1
        if affinity == 'native_fit':
            prompt_stats[prompt_title]['native'] += 1
        elif affinity == 'workable':
            prompt_stats[prompt_title]['workable'] += 1
        elif affinity == 'resistant':
            prompt_stats[prompt_title]['resistant'] += 1

print('=' * 80)
print('TEST DIFFERENTIATION VALUE')
print('=' * 80)

# Calculate differentiation score
test_value = []
for prompt, stats in prompt_stats.items():
    if stats['total'] == 0:
        continue
    total = stats['total']
    native_ratio = stats['native'] / total
    workable_ratio = stats['workable'] / total
    resistant_ratio = stats['resistant'] / total
    entropy = 0
    for ratio in [native_ratio, workable_ratio, resistant_ratio]:
        if ratio > 0:
            entropy -= ratio * math.log2(ratio)
    differentiation = entropy / 1.585
    test_value.append({
        'prompt': prompt,
        'differentiation': differentiation,
        'stats': stats
    })

test_value.sort(key=lambda x: x['differentiation'])

print('\nLOWEST VALUE TESTS (No differentiation - everyone agrees):')
for i, item in enumerate(test_value[:15], 1):
    prompt = item['prompt']
    stats = item['stats']
    diff = item['differentiation']
    max_count = max(stats['native'], stats['workable'], stats['resistant'])
    if stats['native'] == max_count:
        consensus = f"Native ({stats['native']}/{stats['total']})"
    elif stats['workable'] == max_count:
        consensus = f"Workable ({stats['workable']}/{stats['total']})"
    else:
        consensus = f"Resistant ({stats['resistant']}/{stats['total']})"
    print(f"{i:2}. {prompt[:50]:50} | Diff: {diff:.2f} | {consensus}")

print('\n' + '=' * 80)
print('RECOMMENDATION')
print('=' * 80)
low_diff_tests = [t for t in test_value if t['differentiation'] < 0.2]
high_diff_tests = [t for t in test_value if t['differentiation'] > 0.8]
print(f"Tests with differentiation < 0.2: {len(low_diff_tests)}")
print(f"Tests with differentiation > 0.8: {len(high_diff_tests)}")
if low_diff_tests:
    total_tests = len(test_value)
    print(f"Potential savings: Removing {len(low_diff_tests)} tests would reduce the suite from {total_tests} to {total_tests - len(low_diff_tests)} tests")
