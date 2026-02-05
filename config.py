#!/usr/bin/env python3
"""
Configuration for MidJourney Profile Tester.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)

# Project root directory
PROJECT_ROOT = Path(__file__).parent

# Data directories
PROFILE_ANALYSES_DIR = PROJECT_ROOT / 'profile_analyses'
PROFILE_RESULTS_DIR = PROJECT_ROOT / 'profile_results'
BACKUP_DIR = PROFILE_ANALYSES_DIR / 'backups'

# Test prompts file
TEST_PROMPTS_FILE = PROJECT_ROOT / 'test_prompts.json'

# OpenAI Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-5.2')

# Image Processing Settings
MAX_IMAGE_SIZE = 1024  # Max dimension for test images
JPEG_QUALITY = 90      # JPEG compression quality
THUMBNAIL_SIZE = 512   # Size for OpenAI vision API

# Analysis Settings
ANALYSIS_VERSION = '2.3-signature'
MIN_RATINGS_FOR_DNA = 10  # Minimum ratings before generating profile DNA

# Ensure required directories exist
def ensure_directories():
    """Create necessary directories if they don't exist."""
    PROFILE_ANALYSES_DIR.mkdir(exist_ok=True, parents=True)
    PROFILE_RESULTS_DIR.mkdir(exist_ok=True, parents=True)
    BACKUP_DIR.mkdir(exist_ok=True, parents=True)

def ensure_files():
    """Initialize required files if they don't exist."""
    # Initialize test prompts file if missing
    if not TEST_PROMPTS_FILE.exists():
        TEST_PROMPTS_FILE.write_text('[]')
        print(f'Initialized empty test prompts file: {TEST_PROMPTS_FILE}')

# Auto-initialize on import
ensure_directories()
ensure_files()
