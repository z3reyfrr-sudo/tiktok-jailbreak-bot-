"""Central config. Everything is overridable by env var so Replit secrets work."""
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _env(name, default=None):
    return os.environ.get(name, default)


DB_PATH = _env("BOT_DB", str(ROOT / "state.db"))
ACCOUNTS_PATH = pathlib.Path(_env("BOT_ACCOUNTS", str(ROOT / "accounts.json")))
TARGETS_PATH = pathlib.Path(_env("BOT_TARGETS", str(ROOT / "targets.json")))

PULSE_TOKEN = _env("PULSE_TOKEN", "change-me")

HEADLESS = _env("BOT_HEADLESS", "1") == "1"
MAX_ACCOUNTS_PER_PASS = int(_env("BOT_MAX_ACCOUNTS_PER_PASS", "4"))
WATCH_SECONDS = float(_env("BOT_WATCH_SECONDS", "6"))

# human-ish pause between actions
DELAY_MIN = float(_env("BOT_DELAY_MIN", "1.5"))
DELAY_MAX = float(_env("BOT_DELAY_MAX", "5.0"))

# per-account daily caps (keep conservative while accounts are young)
CAPS = {
    "view": int(_env("CAP_VIEW", "60")),
    "like": int(_env("CAP_LIKE", "120")),
    "follow": int(_env("CAP_FOLLOW", "50")),
}

# skip an account for this many seconds after N consecutive failures
QUARANTINE_AFTER = int(_env("BOT_QUARANTINE_AFTER", "3"))
QUARANTINE_SECONDS = int(_env("BOT_QUARANTINE_SECONDS", str(6 * 3600)))
