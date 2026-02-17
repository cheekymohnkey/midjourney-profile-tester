#!/usr/bin/env python3
"""Verify centralized logging configuration.

This script calls `services.logger_config.init_logging()` and emits
log messages at several levels, then verifies that:
 - There are no FileHandlers attached to the root logger
 - At least one StreamHandler is attached and writes to stdout

Exit codes:
 0 = success, 2 = file handlers found, 3 = no stdout handler
"""
import sys
import logging
from pathlib import Path
import os

# Ensure the project root is on sys.path so local packages (services, etc.) can be imported
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.logger_config import init_logging


def main() -> int:
    init_logging()

    logger = logging.getLogger('verify_logging')

    logger.debug('DEBUG test message')
    logger.info('INFO test message')
    logger.warning('WARNING test message')
    logger.error('ERROR test message')
    logger.critical('CRITICAL test message')

    root = logging.getLogger()

    # Detect any file handlers (should not exist)
    file_handlers = [h for h in root.handlers if isinstance(h, logging.FileHandler)]
    if file_handlers:
        logger.error('Verification failed: FileHandler(s) present: %s', file_handlers)
        return 2

    # Ensure at least one StreamHandler writing to stdout exists
    stdout_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler) and getattr(h, 'stream', None) is sys.stdout]
    if not stdout_handlers:
        logger.error('Verification failed: No StreamHandler writing to stdout found')
        return 3

    # Warn if there are stream handlers writing elsewhere (not fatal)
    other_streams = [h for h in root.handlers if isinstance(h, logging.StreamHandler) and getattr(h, 'stream', None) is not sys.stdout]
    if other_streams:
        logger.warning('Found StreamHandler(s) not writing to stdout: %s', other_streams)

    logger.info('Verification passed: logging initialized to stdout with no file handlers')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
