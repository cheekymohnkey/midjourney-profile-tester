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
from services.test_data_service import get_test_data_service
import logging

logger = logging.getLogger(__name__)


def tokenize(text: str):
    return re.findall(r"\w+", text.lower())


def main():
    storage = get_storage()

    tds = get_test_data_service()
    tests = tds.list_tests()
    if not tests:
        logger.info('No tests found in test_prompts.json')
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

    logger.info('%s', '=' * 80)
    logger.info('PROMPT DIVERSITY REPORT')
    logger.info('%s', '=' * 80)
    logger.info('Total tests: %d', total)
    logger.info('Unique prompt texts: %d', unique_prompts)
    logger.info('Unique titles: %d', unique_titles)
    logger.info('Average prompt length (chars): %.1f', avg_len)
    logger.info('Median prompt length (chars): %d', median_len)
    logger.info('')
    logger.info('Top 20 words (excluding small stopwords):')
    for w, c in word_counts.most_common(20):
        logger.info('  %s %d', w, c)

    logger.info('\nSection distribution:')
    for s, c in sections.most_common():
        pct = (c / total) * 100 if total else 0
        logger.info('  %s %4d (%.1f%%)', s, c, pct)

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
        logger.info('\nAnalysis coverage:')
        logger.info('  Analysis files found: %d', len(files))
        logger.info('  Titles covered by at least one analysis rating: %d/%d', coverage_count, unique_titles)
    except Exception:
        pass


if __name__ == '__main__':
    main()
