# MidJourney Profile Tester

An AI-powered tool for discovering and testing MidJourney generation profiles through systematic prompt evaluation.

## Overview

The MidJourney Profile Tester helps you:
- **Discover your aesthetic preferences** through automated AI analysis
- **Test MidJourney profiles** against a diverse set of prompts
- **Generate profile DNA** - detailed aesthetic signatures based on test results
- **Compare profiles** to understand how different settings affect output
- **Optimize prompts** for specific aesthetic goals

## Features

- 📊 **Batch Rating**: Analyze multiple test images with GPT-5.2 vision
- 🧬 **Profile DNA Generation**: AI creates detailed aesthetic signatures
- 🎯 **Affinity Scoring**: Native Fit / Workable / Resistant classification
- 📈 **Analytics**: Statistical analysis across all profiles
- 🔄 **Test Management**: Add, archive, and manage test prompts
- 💾 **Backup System**: Automatic backups before clearing ratings
- 🎨 **34 Diverse Tests**: Photography, art, and design challenges

## Quick Start

### Prerequisites

- Python 3.8+
- OpenAI API key (with GPT-5.2 access)
- MidJourney account for generating test images

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/midjourney-profile-tester.git
cd midjourney-profile-tester

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure API key
cp .env.example .env
# Edit .env and add your OpenAI API key
```

### Usage

```bash
# Start the Streamlit app
streamlit run midjourney_profile_tester.py

# Open http://localhost:8501 in your browser
```

## Workflow

### 1. Create a Profile

1. Go to **Profile Management** tab
2. Enter profile ID (e.g., `baseline`, `stylize-1000`)
3. Optionally add MidJourney parameters
4. Click **Create Profile**

### 2. Generate Test Images

1. Go to **Test Images** tab
2. Copy prompts from the list
3. Generate in MidJourney with your profile settings
4. Download images and upload to the app

### 3. Rate Images

**Manual Rating:**
- Rate individual images (0-10 scale)
- Select affinity: Native Fit / Workable / Resistant
- Add commentary
- Set confidence level

**Batch Rating (Recommended):**
- Select multiple images
- Click **Batch Rate with AI**
- GPT-5.2 analyzes all images in one call
- Review and adjust AI-generated ratings

### 4. Generate Profile DNA

1. Rate at least 10-15 tests
2. Go to **Profile DNA** tab
3. Click **Generate Profile DNA**
4. AI analyzes all ratings and creates aesthetic signature

### 5. Analyze Results

Use included scripts for deeper analysis:

```bash
# Statistical overview of all profiles
python3 analyze_results.py

# Check prompt diversity
python3 analyze_prompt_diversity.py

# Diagnose rating issues
python3 diagnose_ratings.py
```

## Test Prompts

The default test suite includes 34 prompts across two categories:

**PHOTO (19 tests):**
- Minimalist Product, Street Night, Editorial Fashion
- Urban Night, Industrial, Wildlife
- Food Photography, Foggy City Aerial, and more

**ART (15 tests):**
- Watercolor, Digital Character, Retro Poster Design
- Art Nouveau, Abstract Geometry, Concept Art
- Fine Art Landscape, Illustration, and more

### Managing Tests

**Test Management Tab:**
- View all tests with parameters
- Add new tests
- Archive outdated tests
- See cross-profile analyses

**Test Criteria:**
- Each test should be unambiguous
- Avoid overlapping concepts
- Balance easy/challenging prompts
- Mix photography and art styles

## Analysis Version

Current: **2.3-signature** (Enhanced aesthetic signature capture)

Includes:
- Affinity classification (Native Fit / Workable / Resistant)
- 0-10 scoring with confidence levels
- Detailed AI commentary
- Strength/weakness analysis
- Aesthetic pattern recognition

## Configuration

### Environment Variables

Create `.env` file:

```env
OPENAI_API_KEY=your_api_key_here
```

### Model Configuration

In `config.py`:

```python
OPENAI_MODEL = 'gpt-5.2'  # Current default
```

**Model options:**
- `gpt-5.2` - Best quality, reasoning capabilities ($1.75/$14 per 1M tokens)
- `gpt-5` - Good balance ($1.25 per 1M tokens)
- `gpt-5-mini` - Cheapest ($0.25 per 1M tokens)

## File Structure

```
midjourney-profile-tester/
├── midjourney_profile_tester.py  # Main Streamlit app
├── test_prompts.json              # Test definitions
├── config.py                      # Configuration
├── requirements.txt               # Dependencies
├── .env.example                   # Environment template
├── README.md                      # This file
│
├── profile_analyses/              # Analysis JSON files
│   ├── baseline_analysis.json
│   ├── stylize_1000_analysis.json
│   └── backups/                   # Automatic backups
│
├── profile_results/               # Test images (not in git)
│   ├── baseline/
│   │   ├── Minimalist_Product.jpg
│   │   └── ...
│   └── stylize_1000/
│       └── ...
│
└── scripts/                       # Utility scripts
    ├── analyze_results.py
    ├── analyze_prompt_diversity.py
    └── diagnose_ratings.py
```

## Data Storage

**Profile Analyses:**
- Location: `profile_analyses/{profile_id}_analysis.json`
- Contains: Ratings, profile DNA, metadata
- Backed up automatically before clearing

**Test Images:**
- Location: `profile_results/{profile_id}/{test_name}.jpg`
- Format: JPEG, 1024px max dimension, quality 90
- Size: ~200KB per image
- Not tracked in git (see `.gitignore`)

## Cost Estimates

**Per profile analysis (34 images):**
- Batch rating: ~$0.30
- Profile DNA generation: ~$0.05
- **Total per profile: ~$0.35**

**Typical usage:**
- Testing 5-10 profiles: $2-4
- Re-running with new tests: $0.30 per profile

## Tips & Best Practices

1. **Start with Baseline**: Test default MidJourney settings first
2. **Batch Rating**: Much faster than manual, consistent quality
3. **Review AI Ratings**: Always check and adjust if needed
4. **Profile DNA**: Wait until you have 15+ ratings for best results
5. **Test Diversity**: Mix easy and challenging prompts
6. **Backup Often**: Use the backup button before major changes
7. **Compare Profiles**: Look at Test Management cross-profile analyses

## Troubleshooting

**Images not uploading:**
- Check file format (JPG/PNG)
- Ensure filename matches test title exactly
- Try optimizing images: `python3 optimize_test_images.py`

**API errors:**
- Verify `.env` has correct API key
- Check OpenAI account has credits
- Ensure GPT-5.2 access enabled

**Ratings not saving:**
- Check `profile_analyses/` directory permissions
- Verify JSON file not corrupted
- Use backup and restore if needed

**Performance issues:**
- Reduce image size (1024px max recommended)
- Clear browser cache
- Restart Streamlit app

## Contributing

Contributions welcome! Areas for improvement:
- Additional test prompts
- Analysis visualizations
- Export/reporting features
- Multi-user support

## License

MIT License - See LICENSE file for details

## Acknowledgments

- Built with [Streamlit](https://streamlit.io/)
- AI analysis powered by [OpenAI GPT-5.2](https://platform.openai.com/docs/models/gpt-5.2)
- Designed for [MidJourney](https://www.midjourney.com/) users

## Support

For issues or questions:
- Open an issue on GitHub
- Check existing documentation
- Review example analyses in `profile_analyses/`

---

**Note**: This tool is for personal use and experimentation. Not affiliated with MidJourney or OpenAI.
