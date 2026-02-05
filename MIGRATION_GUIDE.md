# Repository Migration Summary

## Overview

I've created a complete set of files to help you extract the MidJourney Profile Tester into its own clean repository, separate from the wallpaper management tool.

## What's Been Created

### 1. Setup Script
**File**: `setup_profile_tester_repo.sh`
- Automated script to copy profile tester files to new location
- Creates directory structure
- Copies core files and utility scripts
- Provides step-by-step instructions

**Usage**:
```bash
chmod +x setup_profile_tester_repo.sh
./setup_profile_tester_repo.sh ~/path/to/new/repo
```

### 2. New Repository Files (in `NEW_REPO_FILES/`)

#### Core Configuration
- **`config.py`** - Simplified config without wallpaper paths
- **`requirements.txt`** - Minimal dependencies (streamlit, openai, Pillow, python-dotenv, requests)
- **`.env.example`** - API key template
- **`.gitignore`** - Properly ignores images, logs, backups, etc.

#### Documentation
- **`README.md`** - Comprehensive documentation including:
  - Features overview
  - Installation instructions
  - Complete workflow guide
  - Test management
  - Cost estimates
  - Troubleshooting
- **`LICENSE`** - MIT license
- **`DIRECTORY_STRUCTURE.md`** - Complete file structure reference

## Files to Include in New Repo

### Core Application (Required)
- ✅ `midjourney_profile_tester.py` - Main app
- ✅ `test_prompts.json` - Test definitions
- ✅ `config.py` - **USE NEW VERSION** from `NEW_REPO_FILES/`
- ✅ `requirements.txt` - **USE NEW VERSION** from `NEW_REPO_FILES/`
- ✅ `.env.example` - **USE NEW VERSION** from `NEW_REPO_FILES/`
- ✅ `.gitignore` - **USE NEW VERSION** from `NEW_REPO_FILES/`

### Utility Scripts (Recommended)
- `analyze_results.py` - Statistical analysis
- `analyze_prompt_diversity.py` - Prompt coverage
- `diagnose_ratings.py` - Debug tool
- `check_orphaned_ratings.py` - Find orphaned ratings
- `cleanup_orphaned_ratings.py` - Remove orphaned ratings
- `clear_ratings.py` - Clear utility
- `fix_rating_keys.py` - Fix key format
- `optimize_test_images.py` - Image optimization
- `test_api_key.py` - API connection test
- `verify_test_removal.py` - Test cleanup verification

### Documentation (Recommended)
- ✅ `README.md` - **USE NEW VERSION** from `NEW_REPO_FILES/`
- ✅ `LICENSE` - **USE NEW VERSION** from `NEW_REPO_FILES/`
- `QUICK_START_AUTO_RATE.md` - Copy from current repo if exists
- `AUTOMATION_UPGRADE.md` - Copy from current repo if exists

### Data Directories
Create empty structure (data not tracked in git):
- `profile_analyses/` - Will store analysis JSON files
- `profile_analyses/backups/` - Automatic backups
- `profile_results/` - Will store test images
- Add `.gitkeep` files to preserve empty dirs

## Files to EXCLUDE

**DO NOT copy these** (they're wallpaper-tool specific):
- ❌ `app.py` - Wallpaper browser
- ❌ `process_images.py` - Wallpaper metadata
- ❌ `process_new_images.py` - Wallpaper processing
- ❌ `collection_suggester.py` - Collection management
- ❌ `processing_pipeline.py` - Wallpaper pipeline
- ❌ `metadata_*.json` - Wallpaper metadata
- ❌ `collections.json` - Wallpaper collections
- ❌ `add_guids.py`, `add_prompt_field.py`, etc. - Wallpaper utilities

## Quick Start Guide

### Option 1: Automated Setup

```bash
# 1. Run the setup script
./setup_profile_tester_repo.sh ~/midjourney-profile-tester

# 2. Navigate to new repo
cd ~/midjourney-profile-tester

# 3. Copy new configuration files
cp ~/wallpaper_tool/NEW_REPO_FILES/* .

# 4. Copy your API key
cp ~/wallpaper_tool/.env .

# 5. Optional: Copy existing data
cp -r ~/wallpaper_tool/profile_analyses/* profile_analyses/
cp -r ~/wallpaper_tool/profile_results/* profile_results/

# 6. Initialize git
git init
touch profile_analyses/.gitkeep
touch profile_analyses/backups/.gitkeep
touch profile_results/.gitkeep
git add .
git commit -m "Initial commit: MidJourney Profile Tester"

# 7. Setup Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 8. Test
streamlit run midjourney_profile_tester.py
```

### Option 2: Manual Setup

```bash
# 1. Create new directory
mkdir -p ~/midjourney-profile-tester
cd ~/midjourney-profile-tester

# 2. Copy files manually (see "Files to Include" above)

# 3. Follow steps 3-8 from Option 1
```

## Key Differences from Original

### Simplified Config
**Old `config.py`** (wallpaper tool):
- Multiple wallpaper directories
- Metadata file paths
- Collections management
- Watermark tracking
- Cache directories

**New `config.py`** (profile tester):
- Only profile-related paths
- OpenAI configuration
- Image processing settings
- Analysis settings
- Much simpler!

### Dependencies
**Old**: torch, transformers, many wallpaper-specific packages

**New**: streamlit, openai, Pillow, python-dotenv, requests (minimal)

### Repository Focus
**Old**: Mixed wallpaper management + profile testing

**New**: Pure profile testing and analysis tool

## Next Steps After Migration

1. **Test the new repo**:
   ```bash
   streamlit run midjourney_profile_tester.py
   ```

2. **Verify all features work**:
   - Profile creation
   - Image upload
   - Batch rating
   - Profile DNA generation
   - Analysis scripts

3. **Push to GitHub** (if desired):
   ```bash
   git remote add origin https://github.com/yourusername/midjourney-profile-tester.git
   git branch -M main
   git push -u origin main
   ```

4. **Clean up old repo**:
   - You can safely delete profile-specific files from wallpaper_tool
   - Keep wallpaper management files separate

## Benefits of Separation

✅ **Cleaner codebase** - Each repo has single responsibility

✅ **Easier to share** - Profile tester can be open-sourced without wallpaper code

✅ **Independent versioning** - Update each tool separately

✅ **Simpler dependencies** - No unnecessary packages

✅ **Better documentation** - Focused docs for each tool

✅ **Easier maintenance** - Changes don't affect other tool

## Questions?

Refer to:
- `NEW_REPO_FILES/README.md` - Complete documentation
- `NEW_REPO_FILES/DIRECTORY_STRUCTURE.md` - File organization
- `setup_profile_tester_repo.sh` - Automated migration script

## Important Notes

1. **Image Files**: The `.gitignore` excludes all images (jpg, png, etc.). Your `profile_results/` images won't be tracked in git, which is good since they're large.

2. **Analysis Files**: Profile analyses (`profile_analyses/*.json`) ARE tracked in git since they're small and contain valuable data.

3. **Environment Variables**: Remember to copy your `.env` file but NEVER commit it to git!

4. **Model Configuration**: New config defaults to `gpt-5.2` but can be overridden via `.env` file.

5. **Data Migration**: The setup script creates empty directories. You can choose to copy your existing profile data or start fresh.

---

**Ready to migrate?** Run `./setup_profile_tester_repo.sh <path>` to get started!
