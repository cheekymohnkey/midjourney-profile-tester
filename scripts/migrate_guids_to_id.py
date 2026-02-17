#!/usr/bin/env python3
"""Migrate test_prompts.json: copy `guid` into `id` and remove `guid`.

Usage:
  ./scripts/migrate_guids_to_id.py [--apply]

By default this runs as a dry-run and prints a migration plan. Use --apply to
perform the migration and write back to storage (creates a timestamped backup).
"""
import argparse
import re
import time
import logging
from pathlib import Path

from storage import get_storage

logger = logging.getLogger(__name__)

GUID_RE = re.compile(r"^[0-9a-f]{32}$")


def looks_like_guid(s: str) -> bool:
    if not s:
        return False
    return bool(GUID_RE.match(s))


def main(apply: bool = False):
    storage = get_storage()
    path = "test_prompts.json"
    data = storage.read_json(path) or []
    if not isinstance(data, list):
        logger.error("Unexpected format for %s: expected top-level list, got %s", path, type(data))
        return 1

    changes = []
    for i, test in enumerate(data):
        guid = test.get("guid")
        idv = test.get("id")
        if not guid:
            continue
        # Decide whether to copy guid -> id. If id is already a GUID-like value,
        # skip unless forcing.
        if idv and looks_like_guid(idv):
            # already GUID-like, skip
            continue
        # We'll set id to guid and remove guid
        changes.append((i, test.get("title"), idv, guid))

    if not changes:
        logger.info("No changes required: no guid->id migrations detected.")
        return 0
    logger.info("Detected %d tests to migrate (guid -> id). Sample: %s", len(changes), changes[:5])
    if not apply:
        logger.info("Dry-run: no changes written. Re-run with --apply to perform migration.")
        return 0

    # Create backup
    ts = time.strftime("%Y%m%dT%H%M%SZ")
    backup_path = f"test_prompts.json.bak.{ts}"
    storage.write_json(backup_path, data)
    logger.info("Backup written to %s", backup_path)

    # Apply changes
    for idx, title, old_id, guid in changes:
        data[idx]["id"] = guid
        # remove guid key
        if "guid" in data[idx]:
            del data[idx]["guid"]

    # Validate counts
    storage.write_json(path, data)
    logger.info("Wrote migrated %s with %d updates.", path, len(changes))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run)")
    args = parser.parse_args()
    raise SystemExit(main(apply=args.apply))
