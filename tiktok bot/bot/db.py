"""SQLite state: account quarantine + full action log."""
import contextlib
import datetime
import sqlite3
import time

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS actions (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  ts      REAL    NOT NULL,
  handle  TEXT    NOT NULL,
  kind    TEXT    NOT NULL,
  target  TEXT,
  ok      INTEGER NOT NULL,
  detail  TEXT
);
CREATE INDEX IF NOT EXISTS idx_actions_hk ON actions(handle, kind, ts);

CREATE TABLE IF NOT EXISTS quarantine (
  handle   TEXT PRIMARY KEY,
  until    REAL NOT NULL,
  reason   TEXT
);
"""


@contextlib.contextmanager
def conn():
    c = sqlite3.connect(config.DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init():
    with conn() as c:
        c.executescript(SCHEMA)


def log(handle, kind, target, ok, detail=""):
    with conn() as c:
        c.execute(
            "INSERT INTO actions(ts,handle,kind,target,ok,detail) VALUES(?,?,?,?,?,?)",
            (time.time(), handle, kind, str(target)[:300], 1 if ok else 0, str(detail)[:500]),
        )


def _day_start():
    return datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


def count_today(handle, kind):
    with conn() as c:
        r = c.execute(
            "SELECT COUNT(*) n FROM actions WHERE handle=? AND kind=? AND ok=1 AND ts>=?",
            (handle, kind, _day_start()),
        ).fetchone()
        return r["n"]


def consecutive_failures(handle, kind):
    """How many of the most recent attempts failed (stops at first success)."""
    with conn() as c:
        rows = c.execute(
            "SELECT ok FROM actions WHERE handle=? AND kind=? ORDER BY ts DESC LIMIT 10",
            (handle, kind),
        ).fetchall()
    n = 0
    for r in rows:
        if r["ok"]:
            break
        n += 1
    return n


def quarantine(handle, reason, seconds):
    with conn() as c:
        c.execute(
            "INSERT INTO quarantine(handle,until,reason) VALUES(?,?,?) "
            "ON CONFLICT(handle) DO UPDATE SET until=excluded.until, reason=excluded.reason",
            (handle, time.time() + seconds, reason),
        )


def is_quarantined(handle):
    with conn() as c:
        r = c.execute("SELECT until FROM quarantine WHERE handle=?", (handle,)).fetchone()
    return bool(r and r["until"] > time.time())


def stats():
    with conn() as c:
        rows = c.execute(
            "SELECT kind, COUNT(*) total, COALESCE(SUM(ok),0) ok FROM actions GROUP BY kind"
        ).fetchall()
        q = c.execute("SELECT COUNT(*) n FROM quarantine WHERE until > ?", (time.time(),)).fetchone()
    return {"actions": [dict(r) for r in rows], "quarantined": q["n"]}
