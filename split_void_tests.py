#!/usr/bin/env python3
"""Split VOID test into VOID_PHOTO and VOID_ART tests using the
`test_prompts_manager` so cache and storage backends are respected.
"""
from test_prompts_manager import load_tests, save_tests


# Read test prompts via manager (uses cache/storage)
tests = load_tests()

# Remove existing VOID section tests
tests = [t for t in tests if t.get('section') != 'VOID']

# Add VOID_PHOTO test (using PHOTO params without seed)
void_photo = {
    "id": "Null_Prompt_Photo",
    "title": "Null Prompt (Photo)",
    "prompt": ".",
    "section": "VOID_PHOTO",
    "params": "--ar 16:9 --quality 4 --stylize 250 --raw",
    "status": "current",
    "version": "v2",
    "created_date": "2026-02-06",
}

# Add VOID_ART test (using ART params without seed)
void_art = {
    "id": "Null_Prompt_Art",
    "title": "Null Prompt (Art)",
    "prompt": ".",
    "section": "VOID_ART",
    "params": "--ar 16:9 --quality 4 --stylize 1000",
    "status": "current",
    "version": "v2",
    "created_date": "2026-02-06",
}

# Append and save (save_tests updates cache/meta)
tests.extend([void_photo, void_art])
save_tests(tests)

print('✓ Split VOID test into two tests:')
print(f'  1. VOID_PHOTO: {void_photo["params"]}')
print(f'  2. VOID_ART: {void_art["params"]}')
print(f'✓ Total tests: {len(tests)}')
print(f'✓ Saved to test_prompts.json')
