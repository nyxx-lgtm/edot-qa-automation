"""Single place that reads environment variables. Nothing secret is ever hardcoded."""
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

# One short tag per test session. It is appended to every record we create so a
# reviewer (and our cleanup) can tell our data apart on the shared environment.
RUN_ID = os.getenv("RUN_ID") or uuid.uuid4().hex[:6].upper()

ESUITE_BASE_URL = os.getenv("ESUITE_BASE_URL", "https://esuite.edot.id")
ESUITE_EMAIL = os.getenv("ESUITE_EMAIL", "")
ESUITE_PASSWORD = os.getenv("ESUITE_PASSWORD", "")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AI_DATA_MODEL = os.getenv("AI_DATA_MODEL", "claude-haiku-4-5")
AI_TRIAGE_MODEL = os.getenv("AI_TRIAGE_MODEL", "claude-sonnet-5-5")

EWORK_COMPANY_ID = os.getenv("EWORK_COMPANY_ID", "")
EWORK_USERNAME = os.getenv("EWORK_USERNAME", "")
EWORK_PASSWORD = os.getenv("EWORK_PASSWORD", "")
MAESTRO_BIN = os.getenv("MAESTRO_BIN", "maestro")

VIEWPORT = {"width": 1440, "height": 900}

# Deliberate breakage for the triage demo only (see README): "missing_locator" or "wrong_element".
QA_BREAK = os.getenv("QA_BREAK", "")

AUTH_DIR = ROOT_DIR / "auth"
# A saved session younger than this is reused instead of logging in again (local reruns).
# CI always starts without one, so it always logs in exactly once per session.
AUTH_MAX_AGE_MIN = int(os.getenv("AUTH_MAX_AGE_MIN", "30"))
STORAGE_STATE = AUTH_DIR / "esuite_state.json"
HANDOFF_FILE = ROOT_DIR / "handoff" / "company.json"
HANDOFF_USER_FILE = ROOT_DIR / "handoff" / "mobile_user.json"
MOBILE_OUTPUT_DIR = ROOT_DIR / "mobile" / "output"
