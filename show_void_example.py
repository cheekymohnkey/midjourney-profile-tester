#!/usr/bin/env python3
"""Show example VOID test response."""
import json
from dotenv import load_dotenv
load_dotenv()

from storage import get_storage
import logging

logger = logging.getLogger(__name__)

storage = get_storage()
data = storage.read_json('profile_analyses/9hoxpdm_analysis.json')
void_rating = data['ratings'].get('Null Prompt', {})

logger.info('Example VOID Test AI Response JSON:')
logger.info('%s', '=' * 80)
logger.info('')
logger.info('%s', json.dumps({'ratings': {'Null Prompt': void_rating}}, indent=2))
