"""Tiny HTTP surface. GitHub Actions pokes /pulse; the poke also keeps Replit awake."""
import threading

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from bot import config, db, worker

app = FastAPI(title="tiktok-bot")


@app.get("/")
def root():
    return {"ok": True, "service": "tiktok-bot"}


@app.get("/status")
def status():
    db.init()
    return {"ok": True, **db.stats()}


def _run(**kw):
    try:
        result = worker.run_pass(**kw)
        print("PASS RESULT:", result)
    except Exception as e:
        print("PASS ERROR:", repr(e))


@app.post("/pulse")
def pulse(token: str = "", video: str = "", views: int = 0, follow: str = "", warmup: bool = False):
    if config.PULSE_TOKEN and token != config.PULSE_TOKEN:
        return JSONResponse({"ok": False, "error": "bad token"}, status_code=401)

    videos = [v.strip() for v in video.split(",") if v.strip()]
    follows = [f.strip() for f in follow.split(",") if f.strip()]

    threading.Thread(
        target=_run,
        kwargs={
            "videos": videos or None,
            "follows": follows or None,
            "warmup": warmup,
            "view_seconds": float(views) if views else None,
        },
        daemon=True,
    ).start()

    return {"ok": True, "started": True, "videos": videos, "follows": follows}
