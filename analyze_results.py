#!/usr/bin/env python3
"""Analyze profile test results for interesting patterns."""

import os
from collections import defaultdict
from storage import get_storage
from test_prompts_manager import load_tests

storage = get_storage()

# Load all analysis files
analyses = {}
for filename in os.listdir('profile_analyses'):
    if filename.endswith('_analysis.json'):
        profile_id = filename.replace('_analysis.json', '')
        analyses[profile_id] = storage.read_json(f'profile_analyses/{filename}') or {}

print(f'📊 Loaded {len(analyses)} profile analyses\n')

# Load test prompts for reference
test_prompts = {t['title']: t for t in load_tests()}

# Aggregate statistics
total_ratings = sum(len(a.get('ratings', {})) for a in analyses.values())
print(f'Total ratings across all profiles: {total_ratings}\n')

# Per-profile summary
print('=' * 80)
print('PROFILE SUMMARIES')
print('=' * 80)

for profile_id, data in sorted(analyses.items()):
    ratings = data.get('ratings', {})
    if not ratings:
        continue
    label = data.get('profile_label', 'No label')
    affinities = [r.get('affinity') for r in ratings.values()]
    native = affinities.count('native_fit')
    workable = affinities.count('workable')
    resistant = affinities.count('resistant')
    scores = [r.get('score', 0) for r in ratings.values()]
    avg_score = sum(scores) / len(scores) if scores else 0
    print(f'\n{profile_id} - "{label}"')
    print(f'  Ratings: {len(ratings)}')
    print(f'  Affinities: ✅ {native} native | ⚠️  {workable} workable | ❌ {resistant} resistant')
    print(f'  Avg Score: {avg_score:.1f}/10')

print('\n' + '=' * 80)
print('PROMPT/STYLE ANALYSIS')
print('=' * 80)

prompt_affinities = defaultdict(lambda: {'native': 0, 'workable': 0, 'resistant': 0, 'profiles': []})

for profile_id, data in analyses.items():
    ratings = data.get('ratings', {})
    for prompt_title, rating in ratings.items():
        affinity = rating.get('affinity', 'unknown')
        if affinity == 'native_fit':
            prompt_affinities[prompt_title]['native'] += 1
        elif affinity == 'workable':
            prompt_affinities[prompt_title]['workable'] += 1
        elif affinity == 'resistant':
            prompt_affinities[prompt_title]['resistant'] += 1
        prompt_affinities[prompt_title]['profiles'].append(profile_id)

print('\n🏆 Most Universally NATIVE prompts (high native_fit across profiles):')
sorted_prompts = sorted(prompt_affinities.items(), 
                       key=lambda x: (x[1]['native'], -x[1]['resistant']), 
                       reverse=True)
for i, (prompt, stats) in enumerate(sorted_prompts[:10], 1):
    total = stats['native'] + stats['workable'] + stats['resistant']
    if total > 0:
        native_pct = (stats['native'] / total) * 100
        print(f'{i:2}. {prompt[:60]:60} | ✅ {stats["native"]:2}/{total} ({native_pct:.0f}%) | ⚠️  {stats["workable"]:2} | ❌ {stats["resistant"]:2}')

print('\n💀 Most Universally RESISTANT prompts (high resistance across profiles):')
sorted_resistant = sorted(prompt_affinities.items(), 
                         key=lambda x: (x[1]['resistant'], -x[1]['native']), 
                         reverse=True)
for i, (prompt, stats) in enumerate(sorted_resistant[:10], 1):
    total = stats['native'] + stats['workable'] + stats['resistant']
    if total > 0:
        resistant_pct = (stats['resistant'] / total) * 100
        print(f'{i:2}. {prompt[:60]:60} | ❌ {stats["resistant"]:2}/{total} ({resistant_pct:.0f}%) | ⚠️  {stats["workable"]:2} | ✅ {stats["native"]:2}')

print('\n' + '=' * 80)
print('SCORE DISTRIBUTION')
print('=' * 80)

all_scores = []
for data in analyses.values():
    all_scores.extend([r.get('score', 0) for r in data.get('ratings', {}).values()])

if all_scores:
    print(f'\nOverall Statistics:')
    print(f'  Total Ratings: {len(all_scores)}')
    print(f'  Average Score: {sum(all_scores)/len(all_scores):.1f}/10')
    print(f'  Min Score: {min(all_scores)}')
    print(f'  Max Score: {max(all_scores)}')
    score_bins = defaultdict(int)
    for score in all_scores:
        bin_key = f'{score:.0f}'
        score_bins[bin_key] += 1
    print(f'\n  Score Distribution:')
    for score in range(1, 11):
        count = score_bins.get(str(score), 0)
        bar = '█' * (count // 5) + '▌' * (1 if count % 5 >= 3 else 0)
        print(f'    {score:2}/10: {count:3} {bar}')

print('\n' + '=' * 80)
print('STYLE CATEGORIES')
print('=' * 80)

category_stats = defaultdict(lambda: {'native': 0, 'workable': 0, 'resistant': 0, 'count': 0})

for prompt_title, prompt_data in test_prompts.items():
    category = prompt_data.get('category', 'Unknown')
    if prompt_title in prompt_affinities:
        stats = prompt_affinities[prompt_title]
        category_stats[category]['native'] += stats['native']
        category_stats[category]['workable'] += stats['workable']
        category_stats[category]['resistant'] += stats['resistant']
        category_stats[category]['count'] += 1

print('\nAffinity by Style Category:')
for category, stats in sorted(category_stats.items(), key=lambda x: x[1]['native'], reverse=True):
    total = stats['native'] + stats['workable'] + stats['resistant']
    if total > 0:
        native_pct = (stats['native'] / total) * 100
        print(f'{category:30} | ✅ {stats["native"]:3} ({native_pct:5.1f}%) | ⚠️  {stats["workable"]:3} | ❌ {stats["resistant"]:3} | ({stats["count"]} prompts)')

print('\n' + '=' * 80)
print('KEY INSIGHTS')
print('=' * 80)

print('\n🎲 Most DIVISIVE prompts (varying results across profiles):')
divisive_prompts = []
for prompt, stats in prompt_affinities.items():
    total = stats['native'] + stats['workable'] + stats['resistant']
    if total >= 3:
        variance = (stats['native'] * stats['resistant'])
        divisive_prompts.append((prompt, stats, variance))

divisive_prompts.sort(key=lambda x: x[2], reverse=True)
for i, (prompt, stats, variance) in enumerate(divisive_prompts[:10], 1):
    total = stats['native'] + stats['workable'] + stats['resistant']
    print(f'{i:2}. {prompt[:60]:60} | ✅ {stats["native"]:2} | ⚠️  {stats["workable"]:2} | ❌ {stats["resistant"]:2}')

print('\n🤝 Most CONSENSUS prompts (similar results across profiles):')
consensus_prompts = []
for prompt, stats in prompt_affinities.items():
    total = stats['native'] + stats['workable'] + stats['resistant']
    if total >= 3:
        max_count = max(stats['native'], stats['workable'], stats['resistant'])
        consensus_score = max_count / total
        consensus_prompts.append((prompt, stats, consensus_score))

consensus_prompts.sort(key=lambda x: x[2], reverse=True)
for i, (prompt, stats, consensus) in enumerate(consensus_prompts[:10], 1):
    dominant = 'Native' if stats['native'] == max(stats['native'], stats['workable'], stats['resistant']) else ('Workable' if stats['workable'] > stats['resistant'] else 'Resistant')
    print(f'{i:2}. {prompt[:60]:60} | {dominant:9} ({consensus*100:.0f}% agree) | ✅ {stats["native"]:2} | ⚠️  {stats["workable"]:2} | ❌ {stats["resistant"]:2}')

print('\n' + '=' * 80)
