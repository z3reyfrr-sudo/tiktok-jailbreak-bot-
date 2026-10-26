import random
import time

from . import config, db


def allowed(handle, kind):
    if db.is_quarantined(handle):
        return False
    if db.count_today(handle, kind) >= config.CAPS[kind]:
        return False
    return True


def pause():
    time.sleep(random.uniform(config.DELAY_MIN, config.DELAY_MAX))


def note_result(handle, kind, ok):
    if not ok and db.consecutive_failures(handle, kind) >= config.QUARANTINE_AFTER:
        db.quarantine(handle, f"{kind} failing repeatedly", config.QUARANTINE_SECONDS)
