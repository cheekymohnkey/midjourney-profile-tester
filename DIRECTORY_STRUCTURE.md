# Directory Structure for Profile Tester Repository

```
midjourney-profile-tester/
├── .env                           # Your API keys (DO NOT COMMIT)
├── .env.example                   # Template for .env
├── .gitignore                     # Git ignore rules
├── LICENSE                        # MIT License
├── README.md                      # Main documentation
├── config.py                      # Configuration settings
├── requirements.txt               # Python dependencies
│
├── midjourney_profile_tester.py  # Main Streamlit application
├── test_prompts.json              # Test prompt definitions
│
├── profile_analyses/              # Profile analysis data
│   ├── .gitkeep                   # Keep empty directory
│   ├── baseline_analysis.json     # Example profile
│   └── backups/                   # Automatic backups
│       └── .gitkeep
│
├── profile_results/               # Test images (not tracked in git)
│   ├── .gitkeep                   # Keep empty directory
│   └── baseline/                  # Images for baseline profile
│       └── .gitkeep
│
├── scripts/                       # Utility scripts
│   ├── analyze_results.py         # Statistical analysis
│   ├── analyze_prompt_diversity.py # Prompt coverage analysis
│   ├── diagnose_ratings.py        # Debug ratings
│   ├── check_orphaned_ratings.py  # Find orphaned ratings
│   ├── cleanup_orphaned_ratings.py # Remove orphaned ratings
│   ├── clear_ratings.py           # Clear ratings utility
│   ├── fix_rating_keys.py         # Fix rating key format
│   ├── optimize_test_images.py    # Optimize image sizes
│   ├── test_api_key.py            # Test OpenAI connection
│   └── verify_test_removal.py     # Verify test cleanup
│
└── docs/                          # Additional documentation
    ├── QUICK_START_AUTO_RATE.md   # Auto-rating guide
    └── AUTOMATION_UPGRADE.md      # Automation features
```

## Files to Copy

### Core Application
- `midjourney_profile_tester.py` - Main app (required)
- `test_prompts.json` - Test definitions (required)
- `config.py` - Use NEW version from NEW_REPO_FILES/
- `requirements.txt` - Use NEW version from NEW_REPO_FILES/
- `.env.example` - Use NEW version from NEW_REPO_FILES/
- `.gitignore` - Use NEW version from NEW_REPO_FILES/

### Utility Scripts
All scripts in the scripts/ directory are optional but recommended

### Documentation
- `README.md` - Use NEW version from NEW_REPO_FILES/
- `LICENSE` - Use NEW version from NEW_REPO_FILES/
- `QUICK_START_AUTO_RATE.md` - Copy from original if exists
- `AUTOMATION_UPGRADE.md` - Copy from original if exists

### Data (Optional)
- `profile_analyses/*.json` - Your existing analysis data
- `profile_results/*/` - Your existing test images
- Note: Images are large, consider excluding from git

## Setup Script Usage

```bash
# 1. Create the repository structure
./setup_profile_tester_repo.sh ~/midjourney-profile-tester

# 2. Navigate to new repo
cd ~/midjourney-profile-tester

# 3. Copy the new config files
cp /path/to/wallpaper_tool/NEW_REPO_FILES/* .

# 4. Copy your .env file
cp /path/to/wallpaper_tool/.env .

# 5. Optional: Copy existing data
# cp -r /path/to/wallpaper_tool/profile_analyses/* profile_analyses/
# cp -r /path/to/wallpaper_tool/profile_results/* profile_results/

# 6. Initialize git
git init
git add .
git commit -m "Initial commit: MidJourney Profile Tester"

# 7. Setup Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 8. Test the application
streamlit run midjourney_profile_tester.py
```

## .gitkeep Files

Create `.gitkeep` files to preserve empty directory structure:

```bash
touch profile_analyses/.gitkeep
touch profile_analyses/backups/.gitkeep
touch profile_results/.gitkeep
```

## What NOT to Include

From the wallpaper_tool repo, **DO NOT** copy:
- `app.py` - Wallpaper browser
- `process_images.py` - Wallpaper metadata
- `process_new_images.py` - Wallpaper processing
- `collection_suggester.py` - Collection management
- `metadata_*.json` - Wallpaper metadata
- `collections.json` - Wallpaper collections
- Any files related to wallpaper management
- `processing_pipeline.py` - Wallpaper pipeline
