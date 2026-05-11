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
    r = sr.Recognizer()
    r.dynamic_energy_threshold = True
    r.energy_threshold = 250
    try:
        with sr.Microphone() as source:
            print('Listening...')
            r.pause_threshold = 1
            r.adjust_for_ambient_noise(source, duration=0.8)
            audio = r.listen(source, timeout=8, phrase_time_limit=7)
    except sr.WaitTimeoutError:
        print('No speech detected, retrying...')
        return 'none'
    except Exception:
        # Useful fallback on systems without PyAudio/mic setup.
        if sys.stdin and sys.stdin.isatty():
            return input("Type command: ")
        return 'none'

    try:
        print('Recognizing..')
        query = r.recognize_google(audio, language='en-in')
        print(f'User said: {query}\n')

    except Exception as e:
        # print(e)

        print('Say that again please...')
        return 'None'
    return query

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
