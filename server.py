"""
HTTP entrypoint for Railway: serves a Jarvis-style HUD in the browser and JSON for APIs.

Full voice + OpenCV assistant: run `python jarvis.py` on your PC (see dashboard copy).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="Jarvis", version="1.0")


def _dashboard_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Jarvis · System Interface</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700&family=Share+Tech+Mono&display=swap" rel="stylesheet"/>
  <style>
    :root {
      --bg0: #030810;
      --bg1: #0a1628;
      --cyan: #00d4ff;
      --cyan-dim: rgba(0, 212, 255, 0.35);
      --amber: #ffb020;
      --text: #c8e8f0;
      --muted: #5a7a8a;
      --grid: rgba(0, 212, 255, 0.06);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      min-height: 100vh;
      font-family: "Share Tech Mono", ui-monospace, monospace;
      color: var(--text);
      background: radial-gradient(ellipse 120% 80% at 50% -20%, #0d2840 0%, var(--bg0) 45%),
                  linear-gradient(180deg, var(--bg1) 0%, var(--bg0) 100%);
      background-attachment: fixed;
      overflow-x: hidden;
    }
    .grid-bg {
      position: fixed; inset: 0; pointer-events: none;
      background-image: linear-gradient(var(--grid) 1px, transparent 1px),
                        linear-gradient(90deg, var(--grid) 1px, transparent 1px);
      background-size: 48px 48px;
      mask-image: radial-gradient(ellipse 70% 60% at 50% 40%, black 20%, transparent 70%);
    }
    .wrap { max-width: 920px; margin: 0 auto; padding: 2rem 1.25rem 4rem; position: relative; z-index: 1; }
    header {
      text-align: center;
      margin-bottom: 2.5rem;
      padding-bottom: 1.5rem;
      border-bottom: 1px solid var(--cyan-dim);
    }
    .arc {
      width: 180px; height: 90px; margin: 0 auto 1rem;
      border: 2px solid var(--cyan);
      border-bottom: none;
      border-radius: 180px 180px 0 0;
      opacity: 0.85;
      box-shadow: 0 0 24px var(--cyan-dim), inset 0 0 20px rgba(0, 212, 255, 0.08);
    }
    h1 {
      font-family: Orbitron, sans-serif;
      font-weight: 700;
      font-size: clamp(1.75rem, 5vw, 2.35rem);
      letter-spacing: 0.35em;
      color: var(--cyan);
      text-shadow: 0 0 40px var(--cyan-dim);
    }
    .subtitle {
      font-size: 0.72rem;
      letter-spacing: 0.28em;
      color: var(--muted);
      margin-top: 0.5rem;
    }
    .status-row {
      display: flex; flex-wrap: wrap; gap: 0.75rem; justify-content: center; margin-top: 1.25rem;
    }
    .pill {
      display: inline-flex; align-items: center; gap: 0.5rem;
      padding: 0.35rem 0.9rem;
      border: 1px solid var(--cyan-dim);
      border-radius: 2px;
      font-size: 0.75rem;
      letter-spacing: 0.12em;
    }
    .pill .dot {
      width: 8px; height: 8px; border-radius: 50%;
      background: #00ff88;
      box-shadow: 0 0 10px #00ff88;
      animation: pulse 2s ease-in-out infinite;
    }
    @keyframes pulse { 50% { opacity: 0.5; } }
    .hud {
      display: grid; gap: 1.25rem;
      grid-template-columns: 1fr;
    }
    @media (min-width: 720px) {
      .hud { grid-template-columns: 1fr 1fr; }
    }
    .panel {
      border: 1px solid var(--cyan-dim);
      background: linear-gradient(145deg, rgba(0, 40, 60, 0.35) 0%, rgba(0, 12, 24, 0.6) 100%);
      padding: 1.25rem 1.35rem;
      border-radius: 2px;
      position: relative;
    }
    .panel::before {
      content: ""; position: absolute; top: 0; left: 0; right: 0; height: 2px;
      background: linear-gradient(90deg, transparent, var(--cyan), transparent);
      opacity: 0.5;
    }
    .panel h2 {
      font-family: Orbitron, sans-serif;
      font-size: 0.68rem;
      letter-spacing: 0.2em;
      color: var(--amber);
      margin-bottom: 1rem;
    }
    .panel p, .panel li { font-size: 0.85rem; line-height: 1.65; color: var(--text); }
    .panel ul { margin: 0.75rem 0 0 1.1rem; }
    .panel code {
      display: inline-block; margin-top: 0.75rem;
      padding: 0.5rem 0.75rem;
      background: rgba(0, 0, 0, 0.45);
      border-left: 2px solid var(--cyan);
      font-size: 0.8rem;
      color: var(--cyan);
    }
    .links { margin-top: 2rem; text-align: center; font-size: 0.75rem; color: var(--muted); }
    .links a { color: var(--cyan); text-decoration: none; margin: 0 0.75rem; letter-spacing: 0.1em; }
    .links a:hover { text-decoration: underline; text-underline-offset: 4px; }
  </style>
</head>
<body>
  <div class="grid-bg" aria-hidden="true"></div>
  <div class="wrap">
    <header>
      <div class="arc" aria-hidden="true"></div>
      <h1>JARVIS</h1>
      <p class="subtitle">JUST A RATHER VERY INTELLIGENT SYSTEM</p>
      <div class="status-row">
        <span class="pill"><span class="dot"></span> CLOUD CORE ONLINE</span>
        <span class="pill">VOICE UNIT · LOCAL HOST</span>
      </div>
    </header>
    <div class="hud">
      <section class="panel">
        <h2>// WHAT YOU ARE SEEING</h2>
        <p>This URL is your <strong>deployed control shell</strong> on Railway: a lightweight web
        process that keeps the service <em>alive</em> and shows system status. It is not the
        full desktop assistant.</p>
        <p style="margin-top:0.75rem">The <strong>real</strong> Jarvis assistant (microphone, speech, Wikipedia,
        browser control, optional camera) runs as <code>python jarvis.py</code> on your own computer.</p>
      </section>
      <section class="panel">
        <h2>// ACTIVATE LOCAL VOICE</h2>
        <ul>
          <li>Clone this repo and create a Python 3.11 venv</li>
          <li><code style="display:block;margin:0.5rem 0 0 0">pip install -r requirements.txt</code></li>
          <li><code style="display:block;margin:0.5rem 0 0 0">python jarvis.py</code></li>
        </ul>
        <p style="margin-top:1rem;font-size:0.78rem;color:var(--muted)">
          <strong>News API key:</strong> Only you have this key. Get a free one at
          <a href="https://newsapi.org/register" style="color:var(--cyan)">newsapi.org/register</a>.
          In <strong>Railway → Variables → + New Variable</strong> set name <code>NEWSAPI_KEY</code>
          and paste the value. On your PC, copy <code>env.example</code> to <code>.env</code> with the same variable for <code>python jarvis.py</code>.
          If unset, news uses BBC RSS (no key). Weather uses Open-Meteo (no key).
        </p>
      </section>
    </div>
    <div class="links">
      <a href="/api/status">API STATUS</a>
      <a href="/health">HEALTH</a>
    </div>
  </div>
</body>
</html>"""


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/status")
def api_status() -> JSONResponse:
    news_configured = bool(
        (os.environ.get("NEWSAPI_KEY") or os.environ.get("NEWSAPI_ORG_KEY") or "").strip()
    )
    return JSONResponse(
        {
            "status": "online",
            "service": "Jarvis",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "voice_assistant": "Run on your PC: python jarvis.py",
            "newsapi_configured": news_configured,
        }
    )


@app.get("/", response_class=HTMLResponse)
def root() -> str:
    return _dashboard_html()


@app.get("/ui", response_class=HTMLResponse)
def legacy_ui() -> str:
    """Same HUD as / (kept for older links)."""
    return _dashboard_html()


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
