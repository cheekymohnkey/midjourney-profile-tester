#!/usr/bin/env python3
"""
Configuration for MidJourney Profile Tester.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from storage import init_storage, get_storage

# Load environment variables from .env file
load_dotenv(override=True)

# Initialize storage backend (S3 or local based on environment)
storage = init_storage()

# Project root directory
PROJECT_ROOT = Path(__file__).parent

# Data directories (paths used with storage backend)
PROFILE_ANALYSES_DIR = 'profile_analyses'
PROFILE_RESULTS_DIR = 'profile_results'
BACKUP_DIR = 'profile_analyses/backups'

# Test prompts file
TEST_PROMPTS_FILE = 'test_prompts.json'

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
    storage.ensure_directory(PROFILE_ANALYSES_DIR)
    storage.ensure_directory(PROFILE_RESULTS_DIR)
    storage.ensure_directory(BACKUP_DIR)

def ensure_files():
    """Initialize required files if they don't exist."""
    # Initialize test prompts file if missing
    if not storage.exists(TEST_PROMPTS_FILE):
        storage.write_json(TEST_PROMPTS_FILE, [])
        print(f'Initialized empty test prompts file: {TEST_PROMPTS_FILE}')

# Auto-initialize on import
ensure_directories()
ensure_files()
