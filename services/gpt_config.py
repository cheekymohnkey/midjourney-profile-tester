"""Centralized GPT model configuration.

Place to control default model name and related capability flags.
"""
DEFAULT_MODEL = "gpt-5-mini"
DEFAULT_MAX_COMPLETION_TOKENS = 4000
# Whether the target model supports a `temperature` parameter. Set False for gpt-5-mini.
SUPPORTS_TEMPERATURE = False
