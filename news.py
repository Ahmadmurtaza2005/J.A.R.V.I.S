"""
News headlines: optional NewsAPI.org key (free tier at https://newsapi.org/register),
or no-key fallback via BBC RSS.
"""
from __future__ import annotations

import os
from typing import Any
from xml.etree import ElementTree as ET

import pyttsx3
import requests

engine = pyttsx3.init()
voices = engine.getProperty("voices")
engine.setProperty("voice", voices[0].id)

# No API key required — used when NEWSAPI_KEY is not set.
BBC_WORLD_RSS = "https://feeds.bbci.co.uk/news/world/rss.xml"


def speak(audio: str) -> None:
    engine.say(audio)
    engine.runAndWait()


def _rss_titles(feed_url: str, limit: int = 6) -> list[str]:
    r = requests.get(feed_url, timeout=15, headers={"User-Agent": "JARVIS/1.0"})
    r.raise_for_status()
    root = ET.fromstring(r.content)
    titles: list[str] = []
    for item in root.findall(".//item"):
        el = item.find("title")
        if el is not None and el.text:
            titles.append(el.text.strip())
        if len(titles) >= limit:
            break
    return titles


def _headlines_newsapi(key: str) -> tuple[list[str], str]:
    """Returns (titles, source_label)."""
    url = (
        "https://newsapi.org/v2/top-headlines"
        "?country=us&pageSize=6&apiKey=" + requests.utils.quote(key, safe="")
    )
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data: dict[str, Any] = resp.json()
    if data.get("status") != "ok":
        raise RuntimeError(data.get("message", "NewsAPI error"))
    arts = data.get("articles") or []
    titles: list[str] = []
    for a in arts:
        t = (a or {}).get("title")
        if t:
            titles.append(str(t).strip())
    return titles, "News API"


def speak_news() -> None:
    key = (os.environ.get("NEWSAPI_KEY") or os.environ.get("NEWSAPI_ORG_KEY") or "").strip()

    titles: list[str] = []
    source = ""

    if key:
        try:
            titles, source = _headlines_newsapi(key)
        except Exception:
            speak("News API failed. Switching to free BBC headlines.")
            key = ""

    if not titles:
        try:
            titles = _rss_titles(BBC_WORLD_RSS)
            source = "BBC World News RSS"
        except Exception:
            speak("Sorry Sir, I could not load the news right now.")
            return

    speak(f"Source: {source}")
    speak("Today's headlines are.")
    for i, title in enumerate(titles):
        speak(title)
        if i < len(titles) - 1:
            speak("Moving on to the next headline.")
    speak("Those were the headlines. Have a nice day, Sir.")


def getNewsUrl() -> str:
    if (os.environ.get("NEWSAPI_KEY") or os.environ.get("NEWSAPI_ORG_KEY") or "").strip():
        return "https://newsapi.org/"
    return "https://www.bbc.co.uk/news/world"


if __name__ == "__main__":
    speak_news()
