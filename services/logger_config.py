import logging
import os
import sys

_DEFAULT_FMT = '%(asctime)s %(levelname)s %(name)s: %(message)s'


def init_logging(level: str | None = None) -> None:
    """Initialize root logger to write to stdout with a single StreamHandler.

    - Uses `LOG_LEVEL` env var if `level` not provided.
    - No file handlers are added.
    - Safe to call multiple times; will not add duplicate handlers.
    """
    root = logging.getLogger()

    # determine level
    lvl = level or os.environ.get('LOG_LEVEL', 'INFO')
    try:
        numeric_level = getattr(logging, lvl.upper())
    except Exception:
        numeric_level = logging.INFO

    root.setLevel(numeric_level)

    # ensure there's a single StreamHandler to stdout
    has_stdout = False
    for h in list(root.handlers):
        if isinstance(h, logging.StreamHandler) and getattr(h, 'stream', None) is sys.stdout:
            has_stdout = True
            break

    if not has_stdout:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(_DEFAULT_FMT)
        handler.setFormatter(formatter)
        root.addHandler(handler)
