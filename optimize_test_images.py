#!/usr/bin/env python3
"""
Optimize test images: Resize PNGs to 1024px JPEGs and remove orphaned images.

This script:
1. Converts all PNG test images to JPEG (1024px max dimension, quality 90)
2. Deletes orphaned images (no matching test in test_prompts.json)
3. Reports space savings and cleanup results
"""

from test_prompts_manager import load_tests
from pathlib import Path
from PIL import Image
import os

def load_valid_tests():
    """Load test_prompts.json and return set of valid test titles."""
    tests = load_tests()
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
        print(f"  ❌ Error processing {img_path.name}: {e}")
        return None

def main():
    print("🔧 Optimizing Test Images")
    print("=" * 60)
    print("\n📋 Loading test prompts...")
    valid_tests = load_valid_tests()
    print(f"   Found {len(valid_tests)} valid tests")
    profile_tests_dir = Path('profile_results')
    if not profile_tests_dir.exists():
        print("❌ profile_results directory not found!")
        return
    profile_dirs = [d for d in profile_tests_dir.iterdir() if d.is_dir()]
    print(f"   Found {len(profile_dirs)} profile directories")
    total_original_size = 0
    total_new_size = 0
    converted_count = 0
    orphaned_count = 0
    error_count = 0
    for profile_dir in sorted(profile_dirs):
        print(f"\n📁 Processing {profile_dir.name}...")
        image_files = list(profile_dir.glob('*.png')) + list(profile_dir.glob('*.jpg')) + \
                     list(profile_dir.glob('*.jpeg')) + list(profile_dir.glob('*.webp'))
        if not image_files:
            print("   No images found")
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
                print(f"  🗑️  Orphaned: {img_path.name} (test no longer exists)")
                try:
                    img_path.unlink()
                    orphaned_count += 1
                except Exception:
                    print(f"  ❌ Could not delete {img_path}")
                    error_count += 1
                continue
            if img_path.suffix.lower() in ['.jpg', '.jpeg']:
                print(f"  ✓  Already JPEG: {img_path.name}")
                continue
            print(f"  🔄 Converting: {img_path.name}...", end='')
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
                print(f" ✅ {orig_size // 1024}KB → {new_size // 1024}KB ({reduction:.1f}% smaller)")
            else:
                error_count += 1
    print("\n" + "=" * 60)
    print("📊 Summary:")
    print(f"   Converted: {converted_count} images")
    print(f"   Deleted orphans: {orphaned_count} images")
    if error_count > 0:
        print(f"   Errors: {error_count} images")
    if total_original_size > 0:
        savings = total_original_size - total_new_size
        savings_pct = (savings / total_original_size) * 100
        print(f"\n💾 Space savings:")
        print(f"   Before: {total_original_size / (1024*1024):.1f} MB")
        print(f"   After:  {total_new_size / (1024*1024):.1f} MB")
        print(f"   Saved:  {savings / (1024*1024):.1f} MB ({savings_pct:.1f}%)")
    print("\n✅ Optimization complete!")

if __name__ == '__main__':
    main()
