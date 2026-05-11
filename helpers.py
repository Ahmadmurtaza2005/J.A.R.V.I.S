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

# Set JARVIS_MIC_INDEX=0 (etc.) if Jarvis listens on the wrong device (see first "Listening" printout).
_MIC_ENV = os.environ.get("JARVIS_MIC_INDEX")
try:
    _MIC_INDEX = int(_MIC_ENV) if _MIC_ENV is not None and str(_MIC_ENV).strip() != "" else None
except ValueError:
    _MIC_INDEX = None

_MIC_NAMES_LOGGED = False
engine = pyttsx3.init()
voices = engine.getProperty('voices')
engine.setProperty('voice', voices[0].id)
g = geocoder.ip('me')
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
    mic_kw: dict = {}
    if _MIC_INDEX is not None:
        mic_kw["device_index"] = _MIC_INDEX

    if not _MIC_NAMES_LOGGED:
        _MIC_NAMES_LOGGED = True
        try:
            names = sr.Microphone.list_microphone_names()
            print("Microphones (use JARVIS_MIC_INDEX=N to pick one):", names)
            if _MIC_INDEX is not None:
                print(f"Using device_index={_MIC_INDEX}: {names[_MIC_INDEX]!r}")
        except Exception as exc:
            print("Could not list microphones:", exc)

    try:
        with sr.Microphone(**mic_kw) as source:
            print("Listening...")
            r.pause_threshold = 0.5
            r.adjust_for_ambient_noise(source, duration=1.0)
            # Softer voices / farther mics: bias threshold down after calibration
            r.energy_threshold = max(45, int(r.energy_threshold * 0.55))
            audio = r.listen(source, timeout=18, phrase_time_limit=14)
    except sr.WaitTimeoutError:
        print("(No speech detected — speak a bit louder or set JARVIS_MIC_INDEX.)")
        return "none"
    except OSError as exc:
        print("Microphone error:", exc)
        return "none"
    except Exception as exc:
        print("Audio input error:", exc)
        if sys.stdin and sys.stdin.isatty():
            return input("Type command: ").strip() or "none"
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
