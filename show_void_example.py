#!/usr/bin/env python3
"""Show example VOID test response."""
import json
from dotenv import load_dotenv
load_dotenv()

from storage import get_storage

storage = get_storage()
data = storage.read_json('profile_analyses/9hoxpdm_analysis.json')
void_rating = data['ratings'].get('Null Prompt', {})

print('Example VOID Test AI Response JSON:')
print('=' * 80)
print()
print(json.dumps({'ratings': {'Null Prompt': void_rating}}, indent=2))
