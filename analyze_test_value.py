#!/usr/bin/env python3
"""Analyze which tests provide the most differentiation value."""

from storage import get_storage
import os
from services.results_data_service import get_results_data_service
import math
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

storage = get_storage()
# Use ResultsDataService to read analysis files
rds = get_results_data_service()

# Load all analysis files
analyses = {}
files = []
try:
    files = storage.list_files('profile_analyses', pattern='*_analysis.json')
except Exception:
    import os
    files = [f for f in os.listdir('profile_analyses') if f.endswith('_analysis.json')]

for filename in files:
    fname = filename.split('/')[-1]
    profile_id = fname.replace('_analysis.json', '')
    try:
        analyses[profile_id] = rds.read_analysis(profile_id) or {}
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

logger.info('%s', '=' * 80)
logger.info('TEST DIFFERENTIATION VALUE')
logger.info('%s', '=' * 80)

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

logger.info('\nLOWEST VALUE TESTS (No differentiation - everyone agrees):')
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
    logger.info('%2d. %s | Diff: %.2f | %s', i, prompt[:50], diff, consensus)

logger.info('\n%s', '=' * 80)
logger.info('RECOMMENDATION')
logger.info('%s', '=' * 80)
low_diff_tests = [t for t in test_value if t['differentiation'] < 0.2]
high_diff_tests = [t for t in test_value if t['differentiation'] > 0.8]
logger.info('Tests with differentiation < 0.2: %d', len(low_diff_tests))
logger.info('Tests with differentiation > 0.8: %d', len(high_diff_tests))
if low_diff_tests:
    total_tests = len(test_value)
    logger.info('Potential savings: Removing %d tests would reduce the suite from %d to %d tests', len(low_diff_tests), total_tests, total_tests - len(low_diff_tests))
