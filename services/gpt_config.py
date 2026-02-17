"""Centralized GPT model configuration.

Place to control default model name and related capability flags.
"""
DEFAULT_MODEL = "gpt-5-mini"
DEFAULT_MAX_COMPLETION_TOKENS = 12000
# Whether the target model supports a `temperature` parameter. Set False for gpt-5-mini.
SUPPORTS_TEMPERATURE = False
# Enable console/stdout logging for external calls (OpenAI, S3, JSON read/write)
# Toggle this to False to disable verbose console logs.
LOG_TO_CONSOLE = True
