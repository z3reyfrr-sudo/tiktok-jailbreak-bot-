"""One pass = open browser, use a few accounts, act, log, close."""
import json
import threading
import traceback

from playwright.sync_api import sync_playwright

from . import browser, config, db, ratelimit

_lock = threading.Lock()


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text())


def _work_account(page, acct, videos, follows, view_seconds):
    handle = acct["handle"]
    did = 0

    for url in videos:
        if ratelimit.allowed(handle, "view"):
            try:
                watched = browser.view(page, url, view_seconds)
                ok = watched >= view_seconds * 0.8
                db.log(handle, "view", url, ok, f"watched={watched:.1f}s")
                ratelimit.note_result(handle, "view", ok)
                did += 1
            except Exception as e:
                db.log(handle, "view", url, False, repr(e))
            ratelimit.pause()

        if ratelimit.allowed(handle, "like"):
            try:
                ok, how = browser.like(page, url)
                db.log(handle, "like", url, ok, how)
                ratelimit.note_result(handle, "like", ok)
                did += 1
            except Exception as e:
                db.log(handle, "like", url, False, repr(e))
            ratelimit.pause()

    for name in follows:
        if not ratelimit.allowed(handle, "follow"):
            break
        try:
            ok, how = browser.follow(page, name)
            db.log(handle, "follow", name, ok, how)
            ratelimit.note_result(handle, "follow", ok)
            did += 1
        except Exception as e:
            db.log(handle, "follow", name, False, repr(e))
        ratelimit.pause()

    return did


def run_pass(videos=None, follows=None, max_accounts=None, warmup=False, view_seconds=None):
    """Safe to call from a request thread. Returns a summary dict."""
    if not _lock.acquire(blocking=False):
        return {"ok": True, "skipped": "a pass is already running"}

    try:
        db.init()
        cfg = load_json(config.TARGETS_PATH, {})
        videos = videos or cfg.get("videos", [])
        follows = follows or cfg.get("follow", [])
        view_seconds = view_seconds or config.WATCH_SECONDS
        limit = max_accounts or config.MAX_ACCOUNTS_PER_PASS

        accounts = [a for a in load_json(config.ACCOUNTS_PATH, []) if a.get("enabled", True)]
        accounts = [a for a in accounts if not db.is_quarantined(a["handle"])][:limit]

        summary = {"accounts": [], "skipped_quarantined": 0}
        if not accounts:
            return {"ok": True, "note": "no usable accounts", **summary}

        with sync_playwright() as pw:
            b = browser.launch(pw)
            try:
                for acct in accounts:
                    entry = {"handle": acct["handle"], "actions": 0}
                    ctx = None
                    try:
                        ctx = browser.new_context(b, acct)
                        page = ctx.new_page()
                        if warmup:
                            browser.warmup(page, minutes=0.5)
                        entry["actions"] = _work_account(page, acct, videos, follows, view_seconds)
                    except Exception as e:
                        entry["error"] = repr(e)
                        traceback.print_exc()
                    finally:
                        if ctx:
                            try:
                                ctx.close()
                            except Exception:
                                pass
                    summary["accounts"].append(entry)
            finally:
                b.close()

        summary["ok"] = True
        summary["stats"] = db.stats()
        return summary
    finally:
        _lock.release()
