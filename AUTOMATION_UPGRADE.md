# 🤖 MidJourney Profile Tester - Automation Upgrade

## Overview
Your profile testing system has been completely rebuilt for full automation. The system now manages test prompts locally and can perform batch AI analysis similar to your Custom GPT.

## 🎯 Key Changes

### 1. Local Test Management (No More Google Sheets!)
- **Before**: Test prompts loaded from Google Sheets CSV
- **After**: Test prompts stored in `test_prompts.json` with version control

**Benefits:**
- ✅ No external dependencies
- ✅ Version control (v1, v2, v3)
- ✅ Archive old tests while preserving them
- ✅ Import/Export for backups
- ✅ Full CRUD operations via UI

### 2. New "🛠️ Tests" Tab
Complete test management interface with 5 sub-tabs:

#### 📋 View Tests
- Filter by status (current/archived/all)
- Filter by section (PHOTO/ART)
- Filter by version (v1/v2/v3)
- View all test details

#### ➕ Add Test
- Create new test prompts
- Auto-generates unique IDs
- Set section, parameters, version

#### ✏️ Edit Test
- Modify existing tests
- Change status (current/archived)
- Update version, parameters
- **📋 Duplicate Test**: Clone test with auto-incremented version

#### 📦 Archive
- Archive tests to hide from active use
- Restore archived tests
- Preserve historical test data

#### 📥 Import/Export
- Export tests as JSON or CSV
- Import tests from files
- Backup and share test suites

### 3. 🤖 Auto-Rate All Feature
**This is the big one!** Complete batch AI analysis with one click.

**Location**: Rate tab → "🤖 Auto-Rate All" button

**What it does:**
1. Sends all uploaded images to GPT-4o-mini
2. Analyzes the entire profile at once
3. Generates comprehensive profile analysis:
   - **Profile Label**: 2-4 word aesthetic description
   - **Profile DNA**: 5-10 distinctive traits
   - **Per-Test Ratings**: For each test:
     - Affinity (native_fit/workable/resistant)
     - Score (1-10)
     - Confidence (0.0-1.0)
     - Commentary (2-3 sentences)

**How to use:**
1. Upload all test images in Images tab
2. Go to Rate tab
3. Click "🤖 Auto-Rate All"
4. Optionally provide a profile label suggestion
5. Click "🚀 Start AI Analysis"
6. Wait ~30-60 seconds for complete analysis
7. Results auto-save to recommendation engine

## 📁 New Files

### `test_prompts.json`
Your local test prompt database. Structure:
```json
{
  "id": "PHOTO_Night_Urban_Traffic",
  "title": "Night Urban Traffic",
  "prompt": "A busy city street at night...",
  "section": "PHOTO",
  "params": "--ar 16:9 --stylize 1000 --v 6.1",
  "status": "current",
  "version": "v2",
  "created_date": "2026-02-01"
}
```

### `test_prompts_manager.py`
Python module for test management. Functions:
- `load_tests(status_filter=None)` - Load tests with optional filtering
- `save_tests(tests)` - Save tests to JSON
- `add_test(...)` - Create new test
- `update_test(test_id, ...)` - Modify existing test
- `delete_test(test_id)` - Remove test
- `archive_test(test_id)` - Change status to archived
- `duplicate_test(test_id, new_version)` - Clone test
- `get_test_by_title(title)` - Find test by title

### Backup Files
- `midjourney_profile_tester_pre_json.py` - Your original version before changes

## 🚀 Usage Workflows

### Workflow 1: Traditional Manual Rating
1. Enter profile ID
2. Copy prompts from Prompts tab
3. Generate in MidJourney
4. Upload images in Images tab
5. Manually rate each image in Rate tab
6. Add Profile DNA traits
7. Use in Recommend tab

### Workflow 2: Automated AI Rating (NEW!)
1. Enter profile ID
2. Copy prompts from Prompts tab
3. Generate in MidJourney
4. Upload images in Images tab
5. **Click "🤖 Auto-Rate All" in Rate tab**
6. **AI analyzes everything at once**
7. Review/adjust AI ratings if needed
8. Use in Recommend tab

### Workflow 3: Managing Test Suites
1. Go to Tests tab
2. View current test suite (v2)
3. Archive old v1 tests
4. Add new experimental v3 tests
5. Export v2 as backup
6. Duplicate v2 tests → v3 for modifications
7. Compare results across versions

## 💡 Best Practices

### Test Versioning
- **v1**: Historical/deprecated tests
- **v2**: Current stable test suite (20 tests)
- **v3**: Experimental new tests

### Archiving Strategy
- Archive tests when:
  - No longer representative
  - Replaced by better prompts
  - Too similar to other tests
- **Don't delete** - archive preserves history

### AI Rating Tips
- Upload all images before running Auto-Rate All
- Provide a profile label suggestion if you have one
- Review AI ratings - they're good but not perfect
- AI is better at identifying patterns than you realize
- Use AI for first pass, manual adjust outliers

### Backup Recommendations
- Export test suite monthly: Tests tab → Import/Export → Download JSON
- Git commit `test_prompts.json` after major changes
- Keep `profile_analyses/` folder backed up

## 🔧 Technical Details

### API Usage
- **Model**: GPT-4o-mini (cost-effective with vision)
- **Detail level**: "low" for images (saves tokens)
- **Batch size**: All uploaded images in one request
- **Cost**: ~$0.10-0.30 per batch analysis (20 images)

### Data Flow
```
test_prompts.json
    ↓
test_prompts_manager.py
    ↓
Streamlit UI (all tabs)
    ↓
OpenAI API (batch analysis)
    ↓
profile_analyses/{profile_id}_analysis.json
    ↓
Recommendation engine
```

### Migration Notes
- All 20 tests migrated from CSV
- All marked as status='current', version='v2'
- CSV loading code completely removed
- Backward compatible - old analysis files still work

## 📊 What's Next?

### Completed ✅
1. CSV → JSON migration
2. Test management UI
3. Batch AI rating
4. Version control system

### Future Enhancements (Optional)
- Test effectiveness scoring
- A/B testing between versions
- AI-suggested test prompts
- Bulk profile comparison
- Export recommendations to MidJourney prompts

## 🐛 Troubleshooting

### "Port 8555 is already in use"
```bash
# Kill old Streamlit process
pkill -f streamlit
# Or use different port
streamlit run midjourney_profile_tester.py --server.port=8556
```

### "OPENAI_API_KEY environment variable not set"
```bash
# Set in terminal
export OPENAI_API_KEY="sk-..."
# Or add to ~/.zshrc for persistence
echo 'export OPENAI_API_KEY="sk-..."' >> ~/.zshrc
```

### Tests not showing in UI
- Check `test_prompts.json` exists
- Verify status filter not hiding tests
- Check version filter matches test versions

### Auto-Rate All fails
- Ensure OpenAI API key is set
- Check all images uploaded successfully
- Verify internet connection
- Check OpenAI API status

## 📝 Summary

You now have a fully automated profile testing system that:
- Manages test prompts locally with version control
- Performs complete AI analysis with one click
- Generates profile labels, DNA traits, and detailed ratings
- Supports multiple test suite versions
- No longer depends on Google Sheets

The "🤖 Auto-Rate All" feature is what you requested - it works like your Custom GPT, analyzing all images at once and generating comprehensive profile analysis automatically.

**Ready to test it!** 🚀
