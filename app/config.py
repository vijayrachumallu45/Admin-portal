"""Runtime configuration. Secrets are never read from a committed env file."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "var" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_PATH = DATA_DIR / "nexusops.sqlite3"

# Demo operator used only on a fresh local database. Not a production secret.
DEMO_EMAIL = "admin@nexusops.local"
DEMO_PASSWORD = "NexusAdmin#2026"
DEMO_NAME = "Avery Sterling"

SESSION_COOKIE_NAME = "nexusops_session"
SECRET_FALLBACK = "local-dev-session-material-not-a-cloud-key"


def secret_key() -> str:
    """Prefer an in-memory local secret file under var/, never a committed .env."""
    secret_path = ROOT / "var" / "session.key"
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    if secret_path.exists():
        return secret_path.read_text(encoding="utf-8").strip() or SECRET_FALLBACK
    secret_path.write_text(SECRET_FALLBACK, encoding="utf-8")
    return SECRET_FALLBACK
