"""
HTTP entrypoint for Railway and other PaaS hosts that require a process listening on $PORT.

The desktop voice assistant (jarvis.py) is meant to run on your machine with a microphone.
This service only proves the deployment is healthy and documents how to run Jarvis locally.
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="J.A.R.V.I.S", version="1.0")


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/")
def root() -> dict[str, str]:
    return {
        "status": "online",
        "service": "J.A.R.V.I.S",
        "voice_assistant": "Run on your PC: python jarvis.py (see README)",
    }


@app.get("/ui", response_class=HTMLResponse)
def simple_ui() -> str:
    """Tiny status page you can open in a browser."""
    return """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/><title>J.A.R.V.I.S</title>
<style>body{font-family:system-ui,sans-serif;max-width:42rem;margin:2rem auto;padding:0 1rem;}
code{background:#f4f4f5;padding:.15rem .4rem;border-radius:4px;}</style></head><body>
<h1>J.A.R.V.I.S</h1>
<p>Deployment is <strong>online</strong>.</p>
<p>Voice commands and spoken replies use your microphone and speakers and run best on your own computer:</p>
<p><code>python jarvis.py</code></p>
<p>Health check: <a href="/health">/health</a></p>
</body></html>"""


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
