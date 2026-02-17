#!/usr/bin/env python3
"""Diagnose rating count mismatch between UI and baseline_analysis.json"""

from storage import get_storage
from services.test_data_service import get_test_data_service
import logging

logger = logging.getLogger(__name__)


storage = get_storage()

# Load test prompts via TestDataService
tds = get_test_data_service()
tests = tds.list_tests()

# Load baseline analysis via storage backend
baseline = storage.read_json('profile_analyses/baseline_analysis.json') or {}

# Load test prompts
# Load test prompts
# tests = load_tests()  (replaced above)

# Count ratings
rating_count = len(baseline.get('ratings', {}))
test_count = len(tests)

logger.info("%s", "=" * 60)
logger.info("RATING COUNT DIAGNOSIS")
logger.info("%s", "=" * 60)
logger.info("\nTotal tests in test_prompts.json: %d", test_count)
logger.info("Total ratings in baseline_analysis.json: %d", rating_count)
logger.info("Remaining: %d", test_count - rating_count)

logger.info("\n%s", "=" * 60)
logger.info("RATED TESTS (from baseline_analysis.json):")
logger.info("%s", "=" * 60)
for i, test_name in enumerate(sorted(baseline.get('ratings', {}).keys()), 1):
    logger.info("  %2d. %s", i, test_name)

logger.info("\n%s", "=" * 60)
logger.info("ALL TEST TITLES (from test_prompts.json):")
logger.info("%s", "=" * 60)
test_titles = [test['title'] for test in tests]
for i, title in enumerate(sorted(test_titles), 1):
    logger.info("  %2d. %s", i, title)

# Find unrated tests
rated_set = set(baseline.get('ratings', {}).keys())
test_set = set(test_titles)

unrated = test_set - rated_set
rated_not_in_tests = rated_set - test_set

if unrated:
    logger.info("\n%s", "=" * 60)
    logger.info("UNRATED TESTS (%d):", len(unrated))
    logger.info("%s", "=" * 60)
    for name in sorted(unrated):
        logger.info("  - %s", name)

if rated_not_in_tests:
    logger.info("\n%s", "=" * 60)
    logger.info("RATINGS FOR TESTS NOT IN test_prompts.json (%d):", len(rated_not_in_tests))
    logger.info("%s", "=" * 60)
    for name in sorted(rated_not_in_tests):
        logger.info("  - %s", name)

if not unrated and not rated_not_in_tests:
    logger.info("\n%s", "=" * 60)
    logger.info("ALL TESTS RATED - NO DISCREPANCIES FOUND")
    logger.info("%s", "=" * 60)