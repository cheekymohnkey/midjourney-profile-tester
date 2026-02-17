#!/usr/bin/env python3
from test_prompts_manager import load_tests
import logging

logger = logging.getLogger(__name__)

tests = load_tests()
logger.info('✅ Test suite updated')
logger.info('New test count: %d (was 40)', len(tests))

logger.info('\nVerifying removed tests are gone:')
removed = [
    'Bold Makeup Portrait',
    'Macro Water Droplets',
    'Fantasy Photorealism',
    'Surreal Still Life',
    'Interior Test',
    'Surrealism Test',
]
titles = [t['title'] for t in tests]

for r in removed:
    status = '❌ STILL PRESENT' if r in titles else '✅ Removed'
    logger.info('  %s: %s', r, status)

logger.info('\nVerifying Wildlife Test is kept:')
wt_status = '✅ Kept' if 'Wildlife Test' in titles else '❌ REMOVED'
logger.info('  Wildlife Test: %s', wt_status)

logger.info('\n💰 Savings: %d tests × 9 profiles = %d fewer ratings needed for new profiles', len(removed), len(removed) * 9)
logger.info("   That's 18%% reduction in time and API costs!")
