import os
import pyttsx3
import pyautogui
import psutil
import pyjokes
import speech_recognition as sr
import json
import requests
import geocoder
from difflib import get_close_matches

# Optional: set JARVIS_MIC_INDEX=0 (or device index from list) if the wrong mic is used.
_MIC_INDEX = os.environ.get("JARVIS_MIC_INDEX")
_MIC_INDEX = int(_MIC_INDEX) if _MIC_INDEX is not None and str(_MIC_INDEX).strip() != "" else None

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
    """Voice-only: microphone in, no keyboard or buttons."""
    r = sr.Recognizer()
    r.dynamic_energy_threshold = True
    r.energy_threshold = 250
    mic_kw = {}
    if _MIC_INDEX is not None:
        mic_kw["device_index"] = _MIC_INDEX
    try:
        with sr.Microphone(**mic_kw) as source:
            print("Listening...")
            r.pause_threshold = 0.8
            r.adjust_for_ambient_noise(source, duration=0.6)
            audio = r.listen(source, timeout=12, phrase_time_limit=10)
    except sr.WaitTimeoutError:
        return "none"
    except OSError:
        speak("Microphone is not available. Check your audio input device.")
        return "none"
    except Exception:
        speak("I could not access the microphone. Check permissions and drivers.")
        return "none"

    try:
        query = r.recognize_google(audio, language="en-in")
    except sr.UnknownValueError:
        speak("Sorry, I did not catch that. Please repeat.")
        return "none"
    except sr.RequestError:
        speak("Speech service is unavailable. Check your internet connection.")
        return "none"
    except Exception:
        speak("Sorry, I did not understand. Please say that again.")
        return "none"
    return query.strip()

def weather():
    if not g or not g.latlng:
        return

    api_url = "https://fcc-weather-api.glitch.me/api/current?lat=" + \
        str(g.latlng[0]) + "&lon=" + str(g.latlng[1])

    try:
        data = requests.get(api_url, timeout=8)
        data_json = data.json()
    except Exception:
        # Do not crash assistant startup if weather API is unavailable.
        return
    if data_json['cod'] == 200:
        main = data_json['main']
        wind = data_json['wind']
        weather_desc = data_json['weather'][0]
        speak(str(data_json['coord']['lat']) + 'latitude' + str(data_json['coord']['lon']) + 'longitude')
        speak('Current location is ' + data_json['name'] + data_json['sys']['country'] + 'dia')
        speak('weather type ' + weather_desc['main'])
        speak('Wind speed is ' + str(wind['speed']) + ' metre per second')
        speak('Temperature: ' + str(main['temp']) + 'degree celcius')
        speak('Humidity is ' + str(main['humidity']))


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
