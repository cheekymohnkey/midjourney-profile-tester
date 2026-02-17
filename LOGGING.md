# Logging Policy

This project standardizes on Python's built-in `logging` module and enforces a single stdout log provider (no log files by default).

Goals
- All console output should go through `logging` (no direct `print()` calls).
- Logs must include timestamp, level, logger name, and message.
- Only a single `StreamHandler` writing to `stdout` is used by default.
- Code should be robust: logging must not raise exceptions that affect program logic.

Core API
- Initialize logging once at process start using:

  ```py
  from services.logger_config import init_logging
  init_logging()  # safe to call multiple times
  ```

- In modules, get a module-scoped logger:

  ```py
  import logging
  logger = logging.getLogger(__name__)
  logger.info('Starting work on %s', resource)
  ```

Formatting
- The centralized formatter is: `%(asctime)s %(levelname)s %(name)s: %(message)s`.

Levels
- Use `logger.debug()` for verbose developer-only traces.
- Use `logger.info()` for normal operational messages.
- Use `logger.warning()` / `logger.error()` / `logger.critical()` for problems.
- Avoid `print()` entirely for log-like output.

Gating noisy logs
- The codebase already supports several gating flags — preserve them and use them to avoid noisy logs:
  - `services.gpt_config.LOG_TO_CONSOLE` — gated logging for AI request/response payloads
  - `S3_CONSOLE_LOGS` env var — can gate large S3 JSON payload logs
  - `MJPT_LOG_CACHE_HITS` env var — can gate cache hit logs

No file handlers by default
- `services.logger_config.init_logging()` intentionally does not add `FileHandler`s.
- If you need persistent logs, add file handlers only in deployment-specific bootstrap code (not library/module code).

Verification
- A helper script is provided to validate configuration: `scripts/verify_logging.py`.

Best Practices
- Add contextual structured data, not raw large objects. Prefer `logger.info('result=%s', short_repr(result))`.
- Keep logging side-effect free — avoid actions in format strings.
- Surround any logging of untrusted or PII-containing data with redaction/sanitization.

Migration
- If you find `print()` in the repo, replace with appropriate `logger` call and choose a level (info/debug).
- Prefer `logger.exception()` inside `except` blocks to capture tracebacks.

Example

```py
from services.logger_config import init_logging
init_logging()

import logging
logger = logging.getLogger(__name__)

def do_work():
    logger.info('Do work started')
    try:
        result = heavy_operation()
        logger.info('Result: %s', summarize(result))
    except Exception:
        logger.exception('Work failed')
```

Reference
- See `scripts/verify_logging.py` for a runtime verification script.
