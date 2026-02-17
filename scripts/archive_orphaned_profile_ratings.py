"""Script to archive orphaned ratings from profile analysis files.

Usage:
  python scripts/archive_orphaned_profile_ratings.py [--dry-run] [--profile PROFILE_ID]

This script collects the set of active test GUIDs from the TestDataService and
for each profile analysis file will move any ratings whose keys are not in the
active set into a profile-specific archive JSON file. By default it runs as a
dry-run and prints a summary; pass `--apply` to persist changes.
"""
import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path when script is executed directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
    
# Load .env so S3 credentials and USE_S3 are available when script runs directly
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=ROOT / '.env', override=False)
except Exception:
    pass

from services.test_data_service import get_test_data_service
from services.profiles_data_service import get_profiles_data_service
from services.results_data_service import get_results_data_service
from storage import get_storage

logger = logging.getLogger(__name__)


def collect_active_test_guids():
    tds = get_test_data_service()
    tests = tds.list_tests()
    guids = set()
    for t in tests:
        g = t.get('guid') or t.get('id')
        if g:
            guids.add(g)
    return guids


def collect_profile_ids():
    # Prefer profiles manager if available
    psvc = get_profiles_data_service()
    profiles = psvc.list_profiles()
    if profiles:
        return [p.get('id') for p in profiles if p.get('id')]

    # Fallback: scan profile_analyses directory for files named '<profile>_analysis.json'
    storage = get_storage()
    try:
        files = storage.list_files('profile_analyses', '*')
    except Exception:
        logger.exception('Failed to list profile_analyses')
        return []
    ids = []
    for fp in files:
        if not fp.endswith('_analysis.json') or fp.endswith('_analysis_archive.json'):
            continue
        name = fp.split('/')[-1]
        pid = name.replace('_analysis.json', '')
        ids.append(pid)
    return ids


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', default=True, dest='dry_run', help='Do not persist changes')
    parser.add_argument('--apply', action='store_false', dest='dry_run', help='Persist changes')
    parser.add_argument('--profile', help='Run only for a single profile id')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    active_guids = collect_active_test_guids()
    logger.info('Active test guids: %d', len(active_guids))

    profiles = [args.profile] if args.profile else collect_profile_ids()
    logger.info('Profiles to check: %d', len(profiles))

    rsvc = get_results_data_service()

    total_moved = 0
    report = {}
    for pid in profiles:
        res = rsvc.archive_orphaned_ratings(pid, active_test_guids=active_guids, dry_run=args.dry_run)
        moved = res.get('moved', 0)
        if moved:
            report[pid] = res.get('moved_keys', [])
            total_moved += moved
            logger.info('Profile %s: would move %d ratings', pid, moved) if args.dry_run else logger.info('Profile %s: moved %d ratings', pid, moved)

    logger.info('Total moved across profiles: %d', total_moved)
    if args.dry_run:
        logger.info('Dry-run mode: no files were modified. Re-run with --apply to persist changes.')


if __name__ == '__main__':
    main()
