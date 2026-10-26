"""All TikTok interaction. API-first via in-page fetch, DOM click as fallback."""
import json
import pathlib
import re
import shutil
import time

from . import config, db

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

VIDEO_ID_RE = re.compile(r"/video/(\d+)")
LIKE_API = "/api/commit/item/digg/?aid=1988"
FOLLOW_API = "/api/commit/follow/user/?aid=1988"

LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
    "--disable-gpu",
    "--mute-audio",
    "--autoplay-policy=no-user-gesture-required",
]


# ── session loading ────────────────────────────────────────────────
def load_state(acct):
    """Session can be a file path (session) or inline base64/JSON (session_json)."""
    if acct.get("session_json"):
        raw = acct["session_json"]
        return json.loads(raw)
    path = acct.get("session")
    if not path:
        return None
    p = pathlib.Path(path)
    if not p.is_absolute():
        p = config.ROOT / p
    if not p.exists():
        raise FileNotFoundError(f"session not found: {p}")
    return json.loads(p.read_text())


# ── browser plumbing ───────────────────────────────────────────────
def _chromium_path():
    for name in ("chromium", "chromium-browser", "google-chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


def launch(pw):
    kwargs = {"headless": config.HEADLESS, "args": LAUNCH_ARGS}
    exe = _chromium_path()
    if exe:
        kwargs["executable_path"] = exe
    return pw.chromium.launch(**kwargs)


def new_context(browser, acct):
    kwargs = {
        "user_agent": UA,
        "viewport": {"width": 1366, "height": 768},
        "locale": "en-US",
        "timezone_id": "America/New_York",
    }
    state = load_state(acct)
    if state:
        kwargs["storage_state"] = state
    if acct.get("proxy"):
        kwargs["proxy"] = {"server": acct["proxy"]}
    ctx = browser.new_context(**kwargs)
    ctx.add_init_script(
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
    )
    ctx.set_default_timeout(45000)
    return ctx


def _dismiss(page):
    """Kill cookie banners / login modals that block the player."""
    for sel in (
        'button:has-text("Accept all")',
        'button:has-text("Allow all")',
        '[data-e2e="browse-close"]',
        'div[role="dialog"] button[aria-label="Close"]',
    ):
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click(timeout=2000)
                page.wait_for_timeout(300)
        except Exception:
            pass


def _api_post(page, path, data):
    """POST through the page so cookies, origin and referer are all correct."""
    try:
        return page.evaluate(
            """async ([path, data]) => {
                const r = await fetch(path, {
                    method: 'POST',
                    credentials: 'include',
                    headers: {'content-type': 'application/x-www-form-urlencoded'},
                    body: new URLSearchParams(data),
                });
                const t = await r.text();
                let j = null; try { j = JSON.parse(t); } catch (e) {}
                return {status: r.status, json: j, text: t.slice(0, 400)};
            }""",
            [path, data],
        )
    except Exception as e:
        return {"status": 0, "json": None, "text": str(e)}


# ── actions ────────────────────────────────────────────────────────
def _run_video(page, seconds):
    """Play the video and measure how much playback time actually elapsed."""
    started = page.evaluate(
        """() => {
            const v = document.querySelector('video');
            if (!v) return -1;
            v.muted = true;
            const p = v.play(); if (p && p.catch) p.catch(() => {});
            return v.currentTime;
        }"""
    )
    if started is None or started < 0:
        return 0.0
    deadline = time.time() + seconds + 15
    last = started
    while time.time() < deadline:
        page.wait_for_timeout(500)
        cur = page.evaluate(
            "() => { const v = document.querySelector('video'); return v ? v.currentTime : -1; }"
        )
        if cur is None or cur < 0:
            break
        last = cur
        if last - started >= seconds:
            break
    return max(0.0, last - started)


def view(page, url, seconds=None):
    """Returns watched seconds. A real view needs playback, not a page hit."""
    seconds = seconds or config.WATCH_SECONDS
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_selector("video", timeout=20000)
    except Exception:
        return 0.0
    _dismiss(page)
    watched = _run_video(page, seconds)
    if watched < seconds * 0.6:
        # probably paused behind an overlay — click the player, then retry
        size = page.viewport_size or {"width": 1366, "height": 768}
        page.mouse.click(size["width"] // 2, size["height"] // 2)
        page.wait_for_timeout(800)
        watched = max(watched, _run_video(page, seconds))
    return watched


def video_id_from_url(url):
    m = VIDEO_ID_RE.search(url)
    return m.group(1) if m else None


def like(page, url):
    vid = video_id_from_url(url)
    if vid:
        res = _api_post(page, LIKE_API, {"itemId": vid, "type": "1"})
        if res["status"] == 200 and isinstance(res["json"], dict) and res["json"].get("status_code") == 0:
            return True, "api"
    for sel in ('[data-e2e="like-icon"]', '[data-e2e="browse-like-icon"]'):
        try:
            el = page.query_selector(sel)
            if el:
                el.click(timeout=4000)
                return True, "dom"
        except Exception:
            continue
    return False, f"status={res.get('status')}"


def resolve_user(page, username):
    username = username.lstrip("@")
    page.goto(f"https://www.tiktok.com/@{username}", wait_until="domcontentloaded", timeout=60000)
    _dismiss(page)
    return page.evaluate(
        """() => {
            const s = document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__');
            if (!s) return null;
            try {
                const j = JSON.parse(s.textContent);
                const u = j['__DEFAULT_SCOPE__']['webapp.user-detail'].userInfo.user;
                return {id: u.id, secUid: u.secUid};
            } catch (e) { return null; }
        }"""
    )


def follow(page, username):
    user = resolve_user(page, username)
    if user:
        res = _api_post(
            page,
            FOLLOW_API,
            {"user_id": user["id"], "secUid": user["secUid"], "type": "1"},
        )
        if res["status"] == 200 and isinstance(res["json"], dict) and res["json"].get("status_code") == 0:
            return True, "api"
    try:
        el = page.query_selector('[data-e2e="follow-button"]')
        if el and el.inner_text().strip().lower() != "following":
            el.click(timeout=4000)
            return True, "dom"
    except Exception:
        pass
    return False, "no follow button"


def warmup(page, minutes=1.0):
    """Scroll the For You feed like a human. Run this on fresh accounts."""
    page.goto("https://www.tiktok.com/foryou", wait_until="domcontentloaded", timeout=60000)
    _dismiss(page)
    deadline = time.time() + minutes * 60
    while time.time() < deadline:
        page.mouse.wheel(0, 900)
        page.wait_for_timeout(int(4000 + 4000 * __import__("random").random()))
