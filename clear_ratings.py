#!/usr/bin/env python3
"""Clear ratings from all profiles to allow re-rating with improved prompt."""

from pathlib import Path
from storage import get_storage
import logging

logger = logging.getLogger(__name__)

storage = get_storage()
# Use ResultsDataService for read/write
from services.results_data_service import get_results_data_service
rds = get_results_data_service()

# List all analysis files (use storage.list_files to support S3/local)
files = []
try:
    files = storage.list_files('profile_analyses', pattern='*_analysis.json')
except Exception:
    # Fallback to local filesystem listing
    files = [str(p) for p in sorted(Path('profile_analyses').glob('*_analysis.json'))]

logger.info("Available profiles:")
for i, file in enumerate(files, 1):
    try:
        profile_id = file.name.replace('_analysis.json', '')
        data = rds.read_analysis(profile_id) or {}
    except Exception:
        data = {}
    rating_count = len(data.get('ratings', {}))
    profile_id = data.get('profile_id', 'unknown')
    logger.info("%d. %s (%s) - %d ratings", i, profile_id, file.name, rating_count)

logger.info("\nClearing ALL profiles...")

for fp in files:
    # Normalize to filename
    fname = str(fp).split('/')[-1]
    try:
        profile_id = fname.replace('_analysis.json', '')
        data = rds.read_analysis(profile_id) or {}
    except Exception:
        data = {}

    rating_count = len(data.get('ratings', {}))
    if rating_count > 0:
        data['ratings'] = {}
        data['profile_label'] = ''
        data['profile_dna'] = []
        if 'affinity_summary' in data:
            data['affinity_summary'] = {
                "native_fit": [],
                "workable": [],
                "resistant": []
            }
        # Save via ResultsDataService so S3/local backends are handled
        rds.write_analysis(profile_id, data)
        logger.info("✅ Cleared %d ratings from %s", rating_count, data.get('profile_id'))
    else:
        logger.info("⏭️  %s already has 0 ratings", data.get('profile_id'))

logger.info("\n✅ All profiles cleared and ready for re-rating with improved prompt!")
