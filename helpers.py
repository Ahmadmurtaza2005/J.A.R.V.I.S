import os
import pyttsx3
import pyautogui
import psutil
import pyjokes
import speech_recognition as sr
import json
import requests
import geocoder
import sys
from difflib import get_close_matches

# Set JARVIS_MIC_INDEX=N to force a device. Otherwise we auto-pick a real microphone (not Stereo Mix).
_MIC_ENV = os.environ.get("JARVIS_MIC_INDEX")
try:
    _MIC_INDEX = int(_MIC_ENV) if _MIC_ENV is not None and str(_MIC_ENV).strip() != "" else None
except ValueError:
    _MIC_INDEX = None

# Prefer name containing this substring (e.g. "Realtek", "USB", "Headset")
_MIC_PREF = (os.environ.get("JARVIS_MIC_PREF") or "").strip().lower()

_MIC_NAMES_LOGGED = False
_mic_kw_cache: dict | None = None

_MIC_EXCLUDE = (
    "stereo mix",
    "loopback",
    "wave out mix",
    "what u hear",
    "cable output",
)


def _best_mic_device_index(names: list[str]) -> int | None:
    if _MIC_PREF:
        for i, name in enumerate(names):
            if _MIC_PREF in name.lower():
                return i
        print(f"No mic matched JARVIS_MIC_PREF={_MIC_PREF!r} — picking automatically.")

    scored: list[tuple[int, int, str]] = []
    for i, name in enumerate(names):
        low = name.lower()
        if any(bad in low for bad in _MIC_EXCLUDE):
            continue
        score = 0
        if "hands-free" in low or "hands free" in low or "ag audio" in low:
            score -= 4
        if "microphone" in low or "mic input" in low or "mic array" in low:
            score += 5
        if "headset" in low or "headphones" in low:
            score += 4
        if "usb" in low or "external" in low:
            score += 2
        if "realtek" in low or "conexant" in low:
            score += 2
        scored.append((score, i, name))

    scored.sort(reverse=True)
    if scored and scored[0][0] > 0:
        return scored[0][1]

    for i, name in enumerate(names):
        low = name.lower()
        if all(bad not in low for bad in _MIC_EXCLUDE):
            return i
    return 0


def _get_mic_kwargs() -> dict:
    """Resolve once: forced index, explicit default-only, or best-guess microphone."""
    global _mic_kw_cache
    if _mic_kw_cache is not None:
        return _mic_kw_cache

    if _MIC_INDEX is not None:
        _mic_kw_cache = {"device_index": _MIC_INDEX}
        return _mic_kw_cache

    if os.environ.get("JARVIS_USE_DEFAULT_MIC", "").strip().lower() in ("1", "true", "yes"):
        _mic_kw_cache = {}
        return _mic_kw_cache

    try:
        names = sr.Microphone.list_microphone_names()
        idx = _best_mic_device_index(names)
        _mic_kw_cache = {"device_index": idx} if idx is not None else {}
    except Exception:
        _mic_kw_cache = {}
    return _mic_kw_cache
engine = pyttsx3.init()
voices = engine.getProperty('voices')
engine.setProperty('voice', voices[0].id)
g = None
try:
    g = geocoder.ip("me")
except Exception:
    print("Could not resolve location via geocoder — weather may be skipped.")
data = json.load(open('data.json'))

def speak(audio) -> None:
        engine.say(audio)
        engine.runAndWait()

def screenshot() -> None:
    img = pyautogui.screenshot()
    img.save('path of folder you want to save/screenshot.png')

def cpu() -> None:
    usage = str(psutil.cpu_percent())
    speak("CPU is at"+usage)

    battery = psutil.sensors_battery()
    if battery is not None:
        speak("battery is at")
        speak(battery.percent)

def joke() -> None:
    for i in range(5):
        speak(pyjokes.get_jokes()[i])

def takeCommand() -> str:
    """Listen once for a voice command. Tuned for sensitivity on typical laptop mics."""
    global _MIC_NAMES_LOGGED
    r = sr.Recognizer()
    r.dynamic_energy_threshold = True
    mic_kw = _get_mic_kwargs()

    if not _MIC_NAMES_LOGGED:
        _MIC_NAMES_LOGGED = True
        try:
            names = sr.Microphone.list_microphone_names()
            print("Microphones (use JARVIS_MIC_INDEX=N to pick one):", names)
            if mic_kw:
                di = mic_kw.get("device_index")
                label = names[di] if di is not None and di < len(names) else "?"
                print(f"Using device_index={di}: {label!r}")
            else:
                print("Using OS default microphone (set JARVIS_MIC_INDEX if wrong).")
        except Exception as exc:
            print("Could not list microphones:", exc)

    ratio = float(os.environ.get("JARVIS_ENERGY_RATIO", "0.38"))
    floor = int(os.environ.get("JARVIS_ENERGY_FLOOR", "38"))
    skip_ambient = os.environ.get("JARVIS_SKIP_AMBIENT", "").strip().lower() in ("1", "true", "yes")

    try:
        with sr.Microphone(**mic_kw) as source:
            print("Listening... speak now (after you hear the prompt or within a few seconds).")
            r.pause_threshold = float(os.environ.get("JARVIS_PAUSE_SEC", "0.45"))
            if skip_ambient:
                r.energy_threshold = floor
            else:
                r.adjust_for_ambient_noise(
                    source, duration=float(os.environ.get("JARVIS_AMBIENT_SEC", "0.55"))
                )
                r.energy_threshold = max(floor, int(r.energy_threshold * ratio))
            print(f"Mic sensitivity: energy_threshold={r.energy_threshold} (raise JARVIS_ENERGY_RATIO toward 1.0 if it picks noise; lower ratio = hears quieter voices)")

            phrase_limit = float(os.environ.get("JARVIS_PHRASE_SEC", "18"))
            wait_limit = float(os.environ.get("JARVIS_WAIT_SEC", "22"))
            audio = r.listen(
                source, timeout=max(14, wait_limit), phrase_time_limit=max(10, phrase_limit)
            )
    except sr.WaitTimeoutError:
        print("(No speech detected — speak a bit louder or set JARVIS_MIC_INDEX.)")
        return "none"
    except OSError as exc:
        print("Microphone error:", exc)
        return "none"
    except AttributeError as exc:
        if "PyAudio" in str(exc) or "pyaudio" in str(exc).lower():
            speak("PyAudio is not installed. Stop Jarvis and run pip install pyaudio in your virtual environment.")
        print("Microphone unavailable:", exc)
        return "none"
    except Exception as exc:
        print("Audio input error:", exc)
        if sys.stdin and sys.stdin.isatty():
            try:
                return input("Type command: ").strip() or "none"
            except EOFError:
                return "none"
        return "none"

    for lang in ("en-US", "en-IN", "en-GB"):
        try:
            print("Recognizing..")
            query = r.recognize_google(audio, language=lang)
            print(f"User said ({lang}): {query}\n")
            return query.strip()
        except sr.UnknownValueError:
            continue
        except sr.RequestError as exc:
            print("Speech recognition service error:", exc)
            return "none"
    print("Could not understand audio — try again.")
    return "none"

def weather():
    """Current weather via Open-Meteo (no API key required)."""
    if not g or not g.latlng:
        return

    lat, lon = g.latlng[0], g.latlng[1]
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
        "&wind_speed_unit=ms"
    )
    try:
        resp = requests.get(url, timeout=12)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return

    current = data.get("current") or {}
    temp = current.get("temperature_2m")
    hum = current.get("relative_humidity_2m")
    wind = current.get("wind_speed_10m")
    code = current.get("weather_code")

    speak(f"Approximate coordinates {lat} latitude, {lon} longitude.")
    if temp is not None:
        speak(f"Temperature about {round(float(temp), 1)} degrees Celsius.")
    if hum is not None:
        speak(f"Humidity about {int(hum)} percent.")
    if wind is not None:
        speak(f"Wind speed about {round(float(wind), 1)} metres per second.")
    if code is not None:
        speak(f"Weather code {int(code)} from the forecast model.")


def translate(word):
    word = word.lower()
    if word in data:
        speak(data[word])
    elif len(get_close_matches(word, data.keys())) > 0:
        x = get_close_matches(word, data.keys())[0]
        speak('Did you mean ' + x +
              ' instead,  respond with Yes or No.')
        ans = takeCommand().lower()
        if 'yes' in ans:
            speak(data[x])
        elif 'no' in ans:
            speak("Word doesn't exist. Please make sure you spelled it correctly.")
        else:
            speak("We didn't understand your entry.")

    else:
        speak("Word doesn't exist. Please double check it.")
