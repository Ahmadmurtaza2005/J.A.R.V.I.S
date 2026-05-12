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
        if "microphone" in low or "mic input" in low:
            score += 4
        if "mic array" in low or "microphone array" in low:
            score -= 8
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


def _mic_kw_fallbacks(primary: dict) -> list[dict]:
    """Try primary first, then other capture devices, then OS default (fixes PyAudio / bad index)."""
    seen: list[tuple] = []
    out: list[dict] = []

    def push(kw: dict) -> None:
        sig = tuple(sorted(kw.items())) if kw else ()
        if sig not in seen:
            seen.append(sig)
            out.append(dict(kw))

    push(primary)
    # OS default early — avoids bad auto device_index picks on Windows.
    push({})
    try:
        names = sr.Microphone.list_microphone_names()
        for i, name in enumerate(names):
            low = name.lower()
            if any(bad in low for bad in _MIC_EXCLUDE):
                continue
            if (
                "microphone" in low
                or "mic input" in low
                or "mic in at front" in low
            ):
                push({"device_index": i})
    except Exception:
        pass
    return out


def _microphone_build(**kwargs) -> sr.Microphone:
    """Optional env: JARVIS_MIC_CHUNK (e.g. 2048), JARVIS_SAMPLE_RATE (e.g. 16000)."""
    merged = dict(kwargs)
    ch = os.environ.get("JARVIS_MIC_CHUNK")
    if ch is not None and str(ch).strip().isdigit():
        merged["chunk_size"] = int(ch)
    srate = os.environ.get("JARVIS_SAMPLE_RATE")
    if srate is not None and str(srate).strip().isdigit():
        merged["sample_rate"] = int(srate)
    return sr.Microphone(**merged)


def _disconnect_microphone(mic: sr.Microphone) -> None:
    """
    Close stream and PyAudio without using Microphone.__exit__.
    speech_recognition bugs: if audio.open() fails, __enter__ still returns with
    stream=None, then __exit__ does self.stream.close() and crashes.
    """
    stream = getattr(mic, "stream", None)
    if stream is not None:
        try:
            stream.close()
        except Exception:
            pass
        try:
            mic.stream = None
        except Exception:
            pass
    audio_obj = getattr(mic, "audio", None)
    if audio_obj is not None:
        try:
            audio_obj.terminate()
        except Exception:
            pass
        try:
            mic.audio = None
        except Exception:
            pass


def _pyaudio_record(
    device_index: int | None,
    seconds: float,
    chunk_size: int,
) -> sr.AudioData | None:
    """
    Bypass speech_recognition.Microphone entirely (helps when sr opens no stream).
    """
    try:
        import pyaudio
    except ImportError:
        return None

    fmt = pyaudio.paInt16
    channels = 1

    pa = pyaudio.PyAudio()
    sample_width = pa.get_sample_size(fmt)
    rates: list[int] = []
    sr_env = os.environ.get("JARVIS_SAMPLE_RATE")
    if sr_env is not None and str(sr_env).strip().isdigit():
        rates.append(int(sr_env))
    try:
        if device_index is None:
            inf = pa.get_default_input_device_info()
            rates.append(int(inf["defaultSampleRate"]))
        else:
            inf = pa.get_device_info_by_index(device_index)
            rates.append(int(inf["defaultSampleRate"]))
    except Exception:
        pass
    rates.extend([44100, 48000, 16000, 22050, 11025])

    uniq: list[int] = []
    seen: set[int] = set()
    for rate in rates:
        if rate > 0 and rate not in seen:
            seen.add(rate)
            uniq.append(rate)

    stream = None
    rate_used: int | None = None
    try:
        for rate in uniq:
            try:
                stream = pa.open(
                    format=fmt,
                    channels=channels,
                    rate=rate,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=max(256, chunk_size),
                )
                rate_used = rate
                print(f"[PyAudio fallback] opened input at {rate_used} Hz, device_index={device_index!s}")
                break
            except Exception:
                continue

        if stream is None or rate_used is None:
            print(
                "[PyAudio fallback] could not open input "
                f"device_index={device_index!s} (tried Hz: {uniq})"
            )
            pa.terminate()
            return None

        n_chunks = max(1, int(rate_used / max(256, chunk_size) * seconds))
        chunks: list[bytes] = []
        fb = max(256, chunk_size)
        for _ in range(n_chunks):
            chunks.append(stream.read(fb, exception_on_overflow=False))
        pcm = b"".join(chunks)
        stream.stop_stream()
        stream.close()
        stream = None
        pa.terminate()
        return sr.AudioData(pcm, rate_used, sample_width)
    except Exception as exc:
        print(f"[PyAudio fallback] record error device_index={device_index!s}: {exc}")
        try:
            if stream is not None:
                stream.close()
        except Exception:
            pass
        try:
            pa.terminate()
        except Exception:
            pass
        return None


def _fallback_record_any_mic() -> sr.AudioData | None:
    """Last resort after speech_recognition path fails everywhere."""
    try:
        sec = float(os.environ.get("JARVIS_PCM_SECONDS", "8"))
    except ValueError:
        sec = 8.0
    sec = max(3.0, min(sec, 30.0))
    try:
        cs = int(os.environ.get("JARVIS_MIC_CHUNK") or "1024")
    except ValueError:
        cs = 1024

    primary = dict(_get_mic_kwargs())
    print(
        "[Fallback] Direct PyAudio: speak your command in the next several seconds "
        f"(recording up to {sec:.0f}s per device)."
    )
    for kw in _mic_kw_fallbacks(primary)[:24]:
        di = kw.get("device_index")
        data = _pyaudio_record(di, sec, cs)
        if data is not None:
            return data
    return _pyaudio_record(None, sec, cs)


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
    primary_kw = dict(_get_mic_kwargs())

    if not _MIC_NAMES_LOGGED:
        _MIC_NAMES_LOGGED = True
        try:
            names = sr.Microphone.list_microphone_names()
            print("Microphones (use JARVIS_MIC_INDEX=N to pick one):", names)
            if primary_kw:
                di = primary_kw.get("device_index")
                label = names[di] if di is not None and di < len(names) else "?"
                print(f"Preferred device_index={di}: {label!r}")
            else:
                print("Preferred: OS default microphone.")
        except Exception as exc:
            print("Could not list microphones:", exc)

    ratio = float(os.environ.get("JARVIS_ENERGY_RATIO", "0.38"))
    floor = int(os.environ.get("JARVIS_ENERGY_FLOOR", "38"))
    skip_ambient = os.environ.get("JARVIS_SKIP_AMBIENT", "").strip().lower() in ("1", "true", "yes")

    phrase_limit = float(os.environ.get("JARVIS_PHRASE_SEC", "18"))
    wait_limit = float(os.environ.get("JARVIS_WAIT_SEC", "22"))

    audio = None
    mic_failures: list[str] = []
    for attempt_kw in _mic_kw_fallbacks(primary_kw):
        di = attempt_kw.get("device_index")
        label = "default"
        try:
            names = sr.Microphone.list_microphone_names()
            if di is not None and 0 <= di < len(names):
                label = names[di]
        except Exception:
            pass

        timed_out = False
        mic = _microphone_build(**attempt_kw)

        opened = False
        try:
            try:
                mic.__enter__()
            except Exception as exc:
                mic_failures.append(str(exc))
                print(f"Mic init failed [{label}]: {exc}")
                _disconnect_microphone(mic)
                continue

            if getattr(mic, "stream", None) is None:
                print(
                    "Mic init returned no audio stream "
                    f"(often wrong device or drivers) [{label}]"
                )
                _disconnect_microphone(mic)
                continue

            opened = True
            print(
                f"Listening… (device_index={di!s} — {label!r}) … speak clearly."
            )
            r.pause_threshold = float(os.environ.get("JARVIS_PAUSE_SEC", "0.45"))
            if skip_ambient:
                r.energy_threshold = floor
            else:
                r.adjust_for_ambient_noise(
                    mic,
                    duration=float(os.environ.get("JARVIS_AMBIENT_SEC", "0.55")),
                )
                r.energy_threshold = max(floor, int(r.energy_threshold * ratio))
            print(
                f"Mic sensitivity: energy_threshold={r.energy_threshold} "
                "(lower JARVIS_ENERGY_RATIO = quieter speech)"
            )
            audio = r.listen(
                mic,
                timeout=max(14, wait_limit),
                phrase_time_limit=max(10, phrase_limit),
            )
        except sr.WaitTimeoutError:
            timed_out = True
        except OSError as exc:
            mic_failures.append(str(exc))
            print(f"Mic I/O error [{label}]: {exc}")
        except AttributeError as exc:
            if "PyAudio" in str(exc) or "pyaudio" in str(exc).lower():
                speak(
                    "PyAudio is missing. Stop Jarvis and run pip install PyAudio "
                    "in your virtual environment."
                )
            mic_failures.append(str(exc))
            print(f"Microphone unavailable [{label}]: {exc}")
        except Exception as exc:
            mic_failures.append(str(exc))
            print(f"Audio error [{label}]: {exc}")
        finally:
            if opened:
                _disconnect_microphone(mic)

        if timed_out:
            print("(No speech detected — speak louder or adjust JARVIS_MIC_INDEX.)")
            return "none"

        if audio is not None:
            break

    if audio is None:
        print("No speech_recognition microphone path worked:", mic_failures)
        audio = _fallback_record_any_mic()

    if audio is None:
        print(
            "No working microphone. Check: Settings → Privacy → Microphone "
            "(allow desktop apps). Try JARVIS_MIC_INDEX in .env."
        )
        speak("Sir, I could not access any microphone.")
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
