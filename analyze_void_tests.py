#!/usr/bin/env python3
"""Analyze VOID test results across all profiles to identify themes and gaps."""

import json
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

from storage import get_storage

storage = get_storage()
analysis_files = storage.list_files('profile_analyses', '*_analysis.json')

logger.info('📊 VOID Test Analysis Across Profiles')
logger.info('%s', '=' * 80)

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
        logger.exception('Error reading %s', file_path)

logger.info('\nFound %d profiles with VOID test ratings\n', len(void_results))

# Group by affinity
native_fit = [r for r in void_results if r['affinity'] == 'native_fit']
workable = [r for r in void_results if r['affinity'] == 'workable']
resistant = [r for r in void_results if r['affinity'] == 'resistant']

logger.info('🟢 NATIVE FIT (Strong Signature): %d profiles', len(native_fit))
logger.info('🟡 WORKABLE (Moderate Signature): %d profiles', len(workable))
logger.info('🔴 RESISTANT (Weak Signature): %d profiles', len(resistant))
logger.info('')

# Show details for each profile
for result in sorted(void_results, key=lambda x: x['score'], reverse=True):
    logger.info('\n%s', '=' * 80)
    logger.info('Profile: %s', result['profile_id'])
    logger.info('Label: %s', result['label'])
    logger.info('Affinity: %s | Score: %s/10', result['affinity'], result['score'])
    logger.info('\nCommentary:')
    logger.info('  %s', result['commentary'])
    logger.info('\nColor Palette:')
    logger.info('  %s', result['color_palette'])

logger.info('\n%s', '=' * 80)
logger.info('SUMMARY')
logger.info('%s', '=' * 80)
logger.info('Total profiles analyzed: %d', len(void_results))
logger.info('Strong signatures: %d', len(native_fit))
logger.info('Moderate signatures: %d', len(workable))
logger.info('Weak signatures: %d', len(resistant))
if void_results:
    logger.info('Average score: %.1f/10', sum(r['score'] for r in void_results) / len(void_results))

# Analyze themes
logger.info('\n%s', '=' * 80)
logger.info('THEME ANALYSIS')
logger.info('%s', '=' * 80)

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
logger.info('\nMost common descriptive terms across all VOID tests:')
for word, count in word_freq.most_common(30):
    logger.info('  %s: %d', word, count)

# Identify profile archetypes
logger.info('\n%s', '=' * 80)
logger.info('PROFILE ARCHETYPES IDENTIFIED')
logger.info('%s', '=' * 80)

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
        logger.info('\n%s: %d profiles', archetype.upper(), len(profiles))
        for pid in profiles:
            logger.info('  - %s', pid)

# Identify gaps
logger.info('\n%s', '=' * 80)
logger.info('POTENTIAL GAPS IN PROFILE COVERAGE')
logger.info('%s', '=' * 80)

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
    logger.info('\nConsider testing profiles that lean toward:')
    for gap in gaps:
        logger.info('  • %s', gap)
else:
    logger.info('\nGood coverage across major aesthetic categories!')

logger.info('\n%s', '=' * 80)
