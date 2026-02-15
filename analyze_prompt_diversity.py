#!/usr/bin/env python3
"""Analyze prompt diversity across the test suite.

Loads test prompts via the cached `test_prompts_manager` API and uses the
storage backend for any JSON reads where appropriate. Produces a simple
report showing unique prompt counts, average lengths, common words, and
section distribution.
"""
from collections import Counter, defaultdict
import re
import math

from storage import get_storage
from test_prompts_manager import load_tests


def tokenize(text: str):
    return re.findall(r"\w+", text.lower())


def main():
    storage = get_storage()

    tests = load_tests()
    if not tests:
        print("No tests found in test_prompts.json")
        return

    total = len(tests)
    prompts = [t.get('prompt', '') for t in tests]
    titles = [t.get('title', '') for t in tests]

    unique_prompts = len(set(prompts))
    unique_titles = len(set(titles))

    lengths = [len(p) for p in prompts]
    avg_len = sum(lengths) / total if total else 0
    median_len = sorted(lengths)[total // 2] if total else 0

    # word frequency
    stopwords = set(["the", "and", "a", "an", "of", "in", "to", "with", "on", "is"])
    words = []
    for p in prompts:
        tokens = tokenize(p)
        words.extend([w for w in tokens if w not in stopwords])

    word_counts = Counter(words)

    # section distribution
    sections = Counter()
    for t in tests:
        sections[t.get('section', 'unspecified')] += 1

    print('=' * 80)
    print('PROMPT DIVERSITY REPORT')
    print('=' * 80)
    print(f"Total tests: {total}")
    print(f"Unique prompt texts: {unique_prompts}")
    print(f"Unique titles: {unique_titles}")
    print(f"Average prompt length (chars): {avg_len:.1f}")
    print(f"Median prompt length (chars): {median_len}")
    print('')
    print('Top 20 words (excluding small stopwords):')
    for w, c in word_counts.most_common(20):
        print(f"  {w:15} {c}")

    print('\nSection distribution:')
    for s, c in sections.most_common():
        pct = (c / total) * 100 if total else 0
        print(f"  {s:25} {c:4} ({pct:.1f}%)")

    # Optionally scan profile analyses to report coverage of prompts
    try:
        # list analysis files via local filesystem or storage.list_files
        files = []
        try:
            files = storage.list_files('profile_analyses', pattern='*_analysis.json')
        except Exception:
            # fallback: check local dir
            import os
            files = [f for f in os.listdir('profile_analyses') if f.endswith('_analysis.json')]

        covered = set()
        for filename in files:
            path = f'profile_analyses/{filename}'
            try:
                data = storage.read_json(path)
            except Exception:
                data = {}
            ratings = data.get('ratings', {})
            covered.update(ratings.keys())

        coverage_count = len(covered & set(titles))
        print('\nAnalysis coverage:')
        print(f"  Analysis files found: {len(files)}")
        print(f"  Titles covered by at least one analysis rating: {coverage_count}/{unique_titles}")
    except Exception:
        pass


if __name__ == '__main__':
    main()
