# Railway / Docker: lightweight web process on $PORT (required for deploy to pass).
# For the full voice + OpenCV assistant, run `python jarvis.py` on Windows/Linux desktop.
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements-railway.txt .
RUN pip install --upgrade pip && pip install -r requirements-railway.txt

COPY server.py .

EXPOSE 8080

CMD ["python", "server.py"]
