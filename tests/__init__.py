"""Test package — set safe defaults before importing the FastAPI app."""

import os

os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
