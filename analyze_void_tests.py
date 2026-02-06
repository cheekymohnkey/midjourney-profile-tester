#!/usr/bin/env python3
"""Analyze VOID test results across all profiles to identify themes and gaps."""

import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from storage import get_storage

storage = get_storage()
analysis_files = storage.list_files('profile_analyses', '*_analysis.json')

print('📊 VOID Test Analysis Across Profiles')
print('=' * 80)

void_results = []

for file_path in sorted(analysis_files):
    if 'backup' in file_path:
        continue
    
    try:
        data = storage.read_json(file_path)
        profile_id = data.get('profile_id', 'unknown')
        profile_label = data.get('profile_label', 'No label')
        ratings = data.get('ratings', {})
        
        # Look for Null Prompt rating
        if 'Null Prompt' in ratings:
            void_rating = ratings['Null Prompt']
            void_results.append({
                'profile_id': profile_id,
                'label': profile_label,
                'affinity': void_rating.get('affinity', 'unknown'),
                'score': void_rating.get('score', 0),
                'commentary': void_rating.get('commentary', 'No commentary'),
                'color_palette': void_rating.get('color_palette', 'No color info')
            })
    except Exception as e:
        print(f'Error reading {file_path}: {e}')

print(f'\nFound {len(void_results)} profiles with VOID test ratings\n')

# Group by affinity
native_fit = [r for r in void_results if r['affinity'] == 'native_fit']
workable = [r for r in void_results if r['affinity'] == 'workable']
resistant = [r for r in void_results if r['affinity'] == 'resistant']

print(f'🟢 NATIVE FIT (Strong Signature): {len(native_fit)} profiles')
print(f'🟡 WORKABLE (Moderate Signature): {len(workable)} profiles')
print(f'🔴 RESISTANT (Weak Signature): {len(resistant)} profiles')
print()

# Show details for each profile
for result in sorted(void_results, key=lambda x: x['score'], reverse=True):
    print(f'\n{"="*80}')
    print(f"Profile: {result['profile_id']}")
    print(f"Label: {result['label']}")
    print(f"Affinity: {result['affinity']} | Score: {result['score']}/10")
    print(f"\nCommentary:")
    print(f"  {result['commentary']}")
    print(f"\nColor Palette:")
    print(f"  {result['color_palette']}")

print(f'\n{"="*80}')
print('SUMMARY')
print('=' * 80)
print(f'Total profiles analyzed: {len(void_results)}')
print(f'Strong signatures: {len(native_fit)}')
print(f'Moderate signatures: {len(workable)}')
print(f'Weak signatures: {len(resistant)}')
if void_results:
    print(f'Average score: {sum(r["score"] for r in void_results)/len(void_results):.1f}/10')

# Analyze themes
print('\n' + '='*80)
print('THEME ANALYSIS')
print('='*80)

# Extract common keywords from commentaries
from collections import Counter
import re

all_words = []
for result in void_results:
    # Extract meaningful words from commentary (lowercase, remove punctuation)
    words = re.findall(r'\b[a-z]{4,}\b', result['commentary'].lower())
    # Filter out common words
    stopwords = {'this', 'that', 'with', 'from', 'have', 'they', 'been', 'were', 
                 'each', 'which', 'their', 'there', 'these', 'would', 'about', 
                 'into', 'through', 'across', 'while', 'overall', 'images'}
    words = [w for w in words if w not in stopwords]
    all_words.extend(words)

word_freq = Counter(all_words)
print('\nMost common descriptive terms across all VOID tests:')
for word, count in word_freq.most_common(30):
    print(f'  {word}: {count}')

# Identify profile archetypes
print('\n' + '='*80)
print('PROFILE ARCHETYPES IDENTIFIED')
print('='*80)

archetypes = {
    'moody/dark': [],
    'bright/airy': [],
    'saturated/vibrant': [],
    'desaturated/muted': [],
    'cinematic': [],
    'photographic': [],
    'artistic/painterly': [],
    'minimalist': [],
    'atmospheric': [],
}

for result in void_results:
    commentary_lower = result['commentary'].lower()
    color_lower = result['color_palette'].lower()
    combined = commentary_lower + ' ' + color_lower
    
    if any(word in combined for word in ['moody', 'dark', 'shadow', 'low-key', 'dramatic']):
        archetypes['moody/dark'].append(result['profile_id'])
    if any(word in combined for word in ['bright', 'light', 'airy', 'high-key', 'clean']):
        archetypes['bright/airy'].append(result['profile_id'])
    if any(word in combined for word in ['saturated', 'vibrant', 'vivid', 'bold', 'rich color']):
        archetypes['saturated/vibrant'].append(result['profile_id'])
    if any(word in combined for word in ['desaturated', 'muted', 'subdued', 'soft color', 'pale']):
        archetypes['desaturated/muted'].append(result['profile_id'])
    if any(word in combined for word in ['cinematic', 'film', 'movie', 'narrative']):
        archetypes['cinematic'].append(result['profile_id'])
    if any(word in combined for word in ['photographic', 'photo', 'realistic', 'documentary']):
        archetypes['photographic'].append(result['profile_id'])
    if any(word in combined for word in ['artistic', 'painterly', 'illustrative', 'stylized']):
        archetypes['artistic/painterly'].append(result['profile_id'])
    if any(word in combined for word in ['minimal', 'simple', 'clean', 'sparse']):
        archetypes['minimalist'].append(result['profile_id'])
    if any(word in combined for word in ['atmospheric', 'fog', 'haze', 'misty', 'ethereal']):
        archetypes['atmospheric'].append(result['profile_id'])

for archetype, profiles in archetypes.items():
    if profiles:
        print(f'\n{archetype.upper()}: {len(profiles)} profiles')
        for pid in profiles:
            print(f'  - {pid}')

# Identify gaps
print('\n' + '='*80)
print('POTENTIAL GAPS IN PROFILE COVERAGE')
print('='*80)

gaps = []

# Check for missing archetypes
if not archetypes['bright/airy']:
    gaps.append('HIGH-KEY/BRIGHT profiles (clean, airy, light)')
if not archetypes['minimalist']:
    gaps.append('MINIMALIST profiles (clean, simple, sparse compositions)')
if not archetypes['saturated/vibrant']:
    gaps.append('VIBRANT/SATURATED profiles (bold, rich colors)')

# Specific style gaps
all_commentary = ' '.join(r['commentary'].lower() + ' ' + r['color_palette'].lower() for r in void_results)

if 'pastel' not in all_commentary:
    gaps.append('PASTEL COLOR profiles (soft, gentle color palettes)')
if 'neon' not in all_commentary and 'fluorescent' not in all_commentary:
    gaps.append('NEON/FLUORESCENT profiles (electric, glowing colors)')
if 'monochrome' not in all_commentary and 'black and white' not in all_commentary:
    gaps.append('MONOCHROME/B&W profiles')
if 'warm' not in all_commentary or all_commentary.count('warm') < 2:
    gaps.append('WARM COLOR profiles (orange, amber, sunset tones)')
if 'cool' not in all_commentary and 'cold' not in all_commentary:
    gaps.append('COOL/COLD profiles (blue, teal, icy tones)')
if 'abstract' not in all_commentary:
    gaps.append('ABSTRACT/NON-REPRESENTATIONAL profiles')
if 'geometric' not in all_commentary:
    gaps.append('GEOMETRIC/PATTERN-FOCUSED profiles')
if 'vintage' not in all_commentary and 'retro' not in all_commentary:
    gaps.append('VINTAGE/RETRO profiles (aged, nostalgic aesthetics)')
if 'surreal' not in all_commentary:
    gaps.append('SURREAL/DREAMLIKE profiles')

if gaps:
    print('\nConsider testing profiles that lean toward:')
    for gap in gaps:
        print(f'  • {gap}')
else:
    print('\nGood coverage across major aesthetic categories!')

print('\n' + '='*80)
