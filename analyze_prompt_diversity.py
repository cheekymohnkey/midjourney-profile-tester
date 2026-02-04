#!/usr/bin/env python3
"""
Analyze prompt diversity to determine optimal test split between photography and art.
Repeatable analysis as new images are added.
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
import config
import random
import sys

def load_metadata(metadata_file=None):
    """Load metadata from specified file or configured file."""
    file_path = metadata_file or config.METADATA_FILE
    with open(file_path, 'r') as f:
        return json.load(f)

def clean_prompt(prompt_text):
    """Remove MidJourney parameters and metadata from prompt."""
    if not prompt_text:
        return ""
    
    # Remove everything after -- parameters
    cleaned = re.split(r'\s*--', prompt_text)[0]
    
    # Remove Job ID references
    cleaned = re.sub(r'\s*Job ID:.*$', '', cleaned, flags=re.IGNORECASE)
    
    # Remove URLs
    cleaned = re.sub(r'https?://\S+', '', cleaned)
    
    return cleaned.strip()

def extract_keywords(prompt_text):
    """Extract meaningful keywords from prompt, removing common words."""
    if not prompt_text:
        return []
    
    # Clean MidJourney metadata first
    prompt_text = clean_prompt(prompt_text)
    
    # Common words to ignore
    stopwords = {
        'a', 'an', 'the', 'of', 'in', 'on', 'at', 'to', 'for', 'with', 'by',
        'from', 'as', 'is', 'was', 'are', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those'
    }
    
    # Extract words (alphanumeric sequences)
    words = re.findall(r'\b[a-z]{3,}\b', prompt_text.lower())
    
    # Filter stopwords
    return [w for w in words if w not in stopwords]

def calculate_diversity_score(prompts):
    """Calculate diversity metrics for a set of prompts."""
    if not prompts:
        return {
            'total_prompts': 0,
            'unique_prompts': 0,
            'uniqueness_ratio': 0.0,
            'avg_length': 0,
            'unique_keywords': 0,
            'keyword_diversity': 0,
            'top_keywords': []
        }
    
    # Basic stats
    total = len(prompts)
    unique = len(set(prompts))
    avg_length = sum(len(clean_prompt(p).split()) for p in prompts) / total
    
    # Keyword analysis
    all_keywords = []
    for prompt in prompts:
        all_keywords.extend(extract_keywords(prompt))
    
    keyword_counts = Counter(all_keywords)
    unique_keywords = len(keyword_counts)
    total_keywords = sum(keyword_counts.values())
    
    # Keyword diversity: ratio of unique to total keywords (higher = more diverse)
    keyword_diversity = unique_keywords / total_keywords if total_keywords > 0 else 0
    
    # Top keywords
    top_keywords = keyword_counts.most_common(20)
    
    return {
        'total_prompts': total,
        'unique_prompts': unique,
        'uniqueness_ratio': unique / total,
        'avg_length': avg_length,
        'unique_keywords': unique_keywords,
        'keyword_diversity': keyword_diversity,
        'top_keywords': top_keywords
    }

def categorize_by_medium(metadata):
    """Categorize prompts by medium (Photography vs Art) and track submediums."""
    photo_prompts = []
    art_prompts = []
    art_by_submedium = defaultdict(list)
    no_prompt = 0
    
    for filename, data in metadata.items():
        prompt = data.get('prompt')
        if not prompt or prompt == 'null':
            no_prompt += 1
            continue
        
        medium = (data.get('medium') or '').lower()
        submedium = data.get('submedium') or 'Unknown'
        
        # Categorize as photography vs art
        if 'photography' in medium or 'photo' in medium:
            photo_prompts.append(prompt)
        else:
            art_prompts.append(prompt)
            art_by_submedium[submedium].append(prompt)
    
    return photo_prompts, art_prompts, art_by_submedium, no_prompt

def suggest_test_split(photo_metrics, art_metrics, total_tests=20):
    """Suggest optimal test split based on diversity metrics."""
    photo_diversity = photo_metrics['keyword_diversity']
    art_diversity = art_metrics['keyword_diversity']
    
    photo_count = photo_metrics['total_prompts']
    art_count = art_metrics['total_prompts']
    
    # Calculate weighted score (diversity × log(count))
    import math
    photo_score = photo_diversity * math.log(photo_count + 1)
    art_score = art_diversity * math.log(art_count + 1)
    
    # Allocate tests proportionally, with minimum of 5 for each
    total_score = photo_score + art_score
    if total_score > 0:
        photo_tests = max(5, min(15, round((photo_score / total_score) * total_tests)))
        art_tests = total_tests - photo_tests
    else:
        photo_tests = 10
        art_tests = 10
    
    return photo_tests, art_tests

def identify_common_patterns(prompts, n=10):
    """Identify common patterns/themes in prompts."""
    # Clean prompts first
    cleaned_prompts = [clean_prompt(p) for p in prompts]
    
    # Look for recurring phrases (2-3 word sequences)
    bigrams = Counter()
    trigrams = Counter()
    
    for prompt in cleaned_prompts:
        words = prompt.lower().split()
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            bigrams[bigram] += 1
        for i in range(len(words) - 2):
            trigram = f"{words[i]} {words[i+1]} {words[i+2]}"
            trigrams[trigram] += 1
    
    return {
        'top_bigrams': bigrams.most_common(n),
        'top_trigrams': trigrams.most_common(n)
    }

def main():
    # Parse command-line arguments
    metadata_file = sys.argv[1] if len(sys.argv) > 1 else None
    
    print("=" * 80)
    print("PROMPT DIVERSITY ANALYSIS (Cleaned Prompts)")
    print("=" * 80)
    if metadata_file:
        print(f"📁 Analyzing: {metadata_file}")
    else:
        print(f"📁 Analyzing: {config.METADATA_FILE}")
    print()
    
    # Load metadata
    metadata = load_metadata(metadata_file)
    print(f"📊 Total images in metadata: {len(metadata)}")
    print()
    
    # Categorize by medium
    photo_prompts, art_prompts, art_by_submedium, no_prompt = categorize_by_medium(metadata)
    
    print(f"📷 Photography prompts: {len(photo_prompts)}")
    print(f"🎨 Art prompts: {len(art_prompts)}")
    print(f"❌ No prompt: {no_prompt}")
    print()
    
    # Show art breakdown by submedium
    print("Art by submedium:")
    for submedium, prompts in sorted(art_by_submedium.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"  {submedium}: {len(prompts)}")
    print()
    
    # Calculate diversity metrics
    print("=" * 80)
    print("PHOTOGRAPHY DIVERSITY")
    print("=" * 80)
    photo_metrics = calculate_diversity_score(photo_prompts)
    print(f"Total prompts: {photo_metrics['total_prompts']}")
    print(f"Unique prompts: {photo_metrics['unique_prompts']} ({photo_metrics['uniqueness_ratio']:.1%})")
    print(f"Avg prompt length: {photo_metrics['avg_length']:.1f} words")
    print(f"Unique keywords: {photo_metrics['unique_keywords']}")
    print(f"Keyword diversity score: {photo_metrics['keyword_diversity']:.3f}")
    print()
    print("Top keywords:")
    for keyword, count in photo_metrics['top_keywords'][:10]:
        print(f"  {keyword}: {count}")
    print()
    
    # Common patterns in photography
    photo_patterns = identify_common_patterns(photo_prompts)
    print("Common photography patterns:")
    for phrase, count in photo_patterns['top_trigrams'][:5]:
        print(f"  '{phrase}': {count} times")
    print()
    
    print("=" * 80)
    print("ART DIVERSITY")
    print("=" * 80)
    art_metrics = calculate_diversity_score(art_prompts)
    print(f"Total prompts: {art_metrics['total_prompts']}")
    print(f"Unique prompts: {art_metrics['unique_prompts']} ({art_metrics['uniqueness_ratio']:.1%})")
    print(f"Avg prompt length: {art_metrics['avg_length']:.1f} words")
    print(f"Unique keywords: {art_metrics['unique_keywords']}")
    print(f"Keyword diversity score: {art_metrics['keyword_diversity']:.3f}")
    print()
    print("Top keywords:")
    for keyword, count in art_metrics['top_keywords'][:10]:
        print(f"  {keyword}: {count}")
    print()
    
    # Common patterns in art
    art_patterns = identify_common_patterns(art_prompts)
    print("Common art patterns:")
    for phrase, count in art_patterns['top_trigrams'][:5]:
        print(f"  '{phrase}': {count} times")
    print()
    
    # Suggest test split
    print("=" * 80)
    print("RECOMMENDED TEST SPLIT")
    print("=" * 80)
    photo_tests, art_tests = suggest_test_split(photo_metrics, art_metrics)
    print(f"📷 Photography tests: {photo_tests}")
    print(f"🎨 Art tests: {art_tests}")
    print()
    print("Rationale:")
    print(f"  Photography diversity: {photo_metrics['keyword_diversity']:.3f}")
    print(f"  Art diversity: {art_metrics['keyword_diversity']:.3f}")
    print()
    if art_metrics['keyword_diversity'] > photo_metrics['keyword_diversity']:
        print("  → Art shows higher diversity, allocating more tests")
    elif photo_metrics['keyword_diversity'] > art_metrics['keyword_diversity']:
        print("  → Photography shows higher diversity, allocating more tests")
    else:
        print("  → Similar diversity, using balanced split")
    print()
    
    # Check if rebalancing recommendation applies
    photo_div = photo_metrics['keyword_diversity']
    art_div = art_metrics['keyword_diversity']
    
    if photo_div > 0 and art_div > 0:
        diversity_ratio = art_div / photo_div if photo_div > art_div else photo_div / art_div
        
        if art_div >= 0.300 and diversity_ratio > 0.70:
            print("⚠️  REBALANCING OPPORTUNITY DETECTED")
            print("=" * 80)
            print(f"Art diversity has reached {art_div:.3f} (threshold: 0.300)")
            print(f"Diversity ratio: {diversity_ratio:.1%} (photo vs art)")
            print()
            print("Consider creating a balanced 10/10 test suite:")
            print("  • Current recommendation is data-driven for your existing collection")
            print("  • With increased art diversity, a 10/10 split would be more representative")
            print("  • Re-test profiles with balanced suite to compare results")
            print()
    print()
    
    # Sample prompts for inspiration (cleaned)
    print("=" * 80)
    print("SAMPLE PROMPTS FOR TEST DESIGN (cleaned)")
    print("=" * 80)
    print()
    print("Photography samples:")
    if photo_prompts:
        for i, prompt in enumerate(random.sample(photo_prompts, min(5, len(photo_prompts))), 1):
            cleaned = clean_prompt(prompt)
            print(f"  {i}. {cleaned[:120]}{'...' if len(cleaned) > 120 else ''}")
    print()
    print("Art samples:")
    if art_prompts:
        for i, prompt in enumerate(random.sample(art_prompts, min(5, len(art_prompts))), 1):
            cleaned = clean_prompt(prompt)
            print(f"  {i}. {cleaned[:120]}{'...' if len(cleaned) > 120 else ''}")
    print()
    
    # Submedium diversity analysis
    print("=" * 80)
    print("ART SUBMEDIUM DIVERSITY")
    print("=" * 80)
    for submedium, prompts in sorted(art_by_submedium.items(), key=lambda x: len(x[1]), reverse=True):
        if len(prompts) >= 5:  # Only show submediums with meaningful sample size
            metrics = calculate_diversity_score(prompts)
            print(f"\n{submedium} ({len(prompts)} prompts):")
            print(f"  Uniqueness: {metrics['uniqueness_ratio']:.1%}")
            print(f"  Keyword diversity: {metrics['keyword_diversity']:.3f}")
            print(f"  Avg length: {metrics['avg_length']:.1f} words")
    print()

if __name__ == '__main__':
    main()
