#!/usr/bin/env python3
"""Show example VOID test response."""
import json
from dotenv import load_dotenv
load_dotenv()

from services.results_data_service import get_results_data_service
import logging

logger = logging.getLogger(__name__)

rs = get_results_data_service()
data = rs.read_analysis('9hoxpdm') or {}
void_rating = data.get('ratings', {}).get('Null Prompt', {})

logger.info('Example VOID Test AI Response JSON:')
logger.info('%s', '=' * 80)
logger.info('')
logger.info('%s', json.dumps({'ratings': {'Null Prompt': void_rating}}, indent=2))
