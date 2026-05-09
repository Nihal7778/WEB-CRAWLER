"""
Application configuration.

Centralizes env-var lookups and constants. All other modules import
from here rather than calling os.getenv directly — makes config
discoverable and easy to override in tests.

Configuration sources (in priority order):
1. Environment variables
2. .env file (loaded via python-dotenv if present)
3. Defaults defined here
"""

import os
from pathlib import Path

# Optional: load .env file if python-dotenv is installed.
# Don't make it a hard dependency — production uses real env vars.
try:
    from dotenv import load_dotenv

    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass



# service identity
SERVICE_NAME = "brightedge-crawler"
SERVICE_VERSION = "0.1.0"


# server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# Environment
# "dev" | "prod" — controls log format and a few defaults
ENV = os.getenv("ENV", "dev").lower()
IS_PROD = ENV == "prod"


# Logging
# Levels: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# In dev: human-readable. In prod: JSON for log aggregators.
LOG_FORMAT = os.getenv("LOG_FORMAT", "json" if IS_PROD else "console").lower()


# Crawler behavior
# Max characters of body text to return in API response.
# Full body kept internally for classification; this caps response size.
MAX_BODY_CHARS_RESPONSE = int(os.getenv("MAX_BODY_CHARS_RESPONSE", "10000"))

# Hard cap on request processing time. The fetcher already has its own
# timeouts; this is a safety net at the FastAPI layer.
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))