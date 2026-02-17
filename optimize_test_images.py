#!/usr/bin/env python3
"""
Optimize test images: Resize PNGs to 1024px JPEGs and remove orphaned images.

This script:
1. Converts all PNG test images to JPEG (1024px max dimension, quality 90)
2. Deletes orphaned images (no matching test in test_prompts.json)
3. Reports space savings and cleanup results
"""

from services.test_data_service import get_test_data_service
from pathlib import Path
from PIL import Image
import os
import logging

logger = logging.getLogger(__name__)

def load_valid_tests():
    """Load test_prompts.json and return set of valid test titles."""
    tds = get_test_data_service()
    tests = tds.list_tests()
    return {test['title'] for test in tests}

def resize_and_convert_image(img_path, max_size=1024, quality=90):
    try:
        img = Image.open(img_path)
        original_size = os.path.getsize(img_path)
        width, height = img.size
        if max(width, height) <= max_size:
            new_size = (width, height)
        else:
            ratio = max_size / max(width, height)
            new_size = (int(width * ratio), int(height * ratio))
        if new_size != (width, height):
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        if img.mode in ('RGBA', 'P', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            if 'A' in img.mode:
                background.paste(img, mask=img.split()[-1])
            else:
                background.paste(img)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        new_path = img_path.with_suffix('.jpg')
        img.save(new_path, 'JPEG', quality=quality, optimize=True)
        new_file_size = os.path.getsize(new_path)
        return new_path, original_size, new_file_size
    except Exception as e:
        logger.exception('  ❌ Error processing %s: %s', img_path.name, e)
        return None

def main():
    logger.info('🔧 Optimizing Test Images')
    logger.info('%s', '=' * 60)
    logger.info('\n📋 Loading test prompts...')
    valid_tests = load_valid_tests()
    logger.info('   Found %d valid tests', len(valid_tests))
    profile_tests_dir = Path('profile_results')
    if not profile_tests_dir.exists():
        logger.error('❌ profile_results directory not found!')
        return
    profile_dirs = [d for d in profile_tests_dir.iterdir() if d.is_dir()]
    logger.info('   Found %d profile directories', len(profile_dirs))
    total_original_size = 0
    total_new_size = 0
    converted_count = 0
    orphaned_count = 0
    error_count = 0
    for profile_dir in sorted(profile_dirs):
        logger.info('\n📁 Processing %s...', profile_dir.name)
        image_files = list(profile_dir.glob('*.png')) + list(profile_dir.glob('*.jpg')) + \
                     list(profile_dir.glob('*.jpeg')) + list(profile_dir.glob('*.webp'))
        if not image_files:
            logger.info('   No images found')
            continue
        for img_path in image_files:
            filename_stem = img_path.stem
            if '_' in filename_stem:
                parts = filename_stem.split('_', 1)
                test_name = parts[1] if len(parts) > 1 else filename_stem
            else:
                test_name = filename_stem
            test_name_with_spaces = test_name.replace('_', ' ')
            if test_name not in valid_tests and test_name_with_spaces not in valid_tests:
                logger.info('  🗑️  Orphaned: %s (test no longer exists)', img_path.name)
                try:
                    img_path.unlink()
                    orphaned_count += 1
                except Exception:
                    logger.exception('  ❌ Could not delete %s', img_path)
                    error_count += 1
                continue
            if img_path.suffix.lower() in ['.jpg', '.jpeg']:
                logger.info('  ✓  Already JPEG: %s', img_path.name)
                continue
            logger.info('  🔄 Converting: %s...', img_path.name)
            result = resize_and_convert_image(img_path)
            if result:
                new_path, orig_size, new_size = result
                total_original_size += orig_size
                total_new_size += new_size
                converted_count += 1
                try:
                    img_path.unlink()
                except Exception:
                    pass
                reduction = (1 - new_size / orig_size) * 100 if orig_size else 0
                logger.info(' ✅ %dKB → %dKB (%.1f%% smaller)', orig_size // 1024, new_size // 1024, reduction)
            else:
                error_count += 1
    logger.info('\n%s', '=' * 60)
    logger.info('📊 Summary:')
    logger.info('   Converted: %d images', converted_count)
    logger.info('   Deleted orphans: %d images', orphaned_count)
    if error_count > 0:
        logger.info('   Errors: %d images', error_count)
    if total_original_size > 0:
        savings = total_original_size - total_new_size
        savings_pct = (savings / total_original_size) * 100
        logger.info('\n💾 Space savings:')
        logger.info('   Before: %.1f MB', total_original_size / (1024*1024))
        logger.info('   After:  %.1f MB', total_new_size / (1024*1024))
        logger.info('   Saved:  %.1f MB (%.1f%%)', savings / (1024*1024), savings_pct)
    logger.info('\n✅ Optimization complete!')

if __name__ == '__main__':
    main()
