#!/usr/bin/env python3
from test_prompts_manager import load_tests

tests = load_tests()
print(f'✅ Test suite updated')
print(f'New test count: {len(tests)} (was 40)')

print('\nVerifying removed tests are gone:')
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
    print(f'  {r}: {status}')

print('\nVerifying Wildlife Test is kept:')
wt_status = '✅ Kept' if 'Wildlife Test' in titles else '❌ REMOVED'
print(f'  Wildlife Test: {wt_status}')

print('\n💰 Savings: {len(removed)} tests × 9 profiles = {len(removed) * 9} fewer ratings needed for new profiles')
print("   That's 18% reduction in time and API costs!")
