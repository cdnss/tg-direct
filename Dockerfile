FROM python:3.9-slim-buster

WORKDIR /app

COPY requirements.txt .

RUN apt-get update && apt-get install -y ffmpeg && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install watchdog

# Use volume mount for source code to avoid rebuilding
CMD ["watchmedo", "auto-restart", "--directory=/app", "--pattern=*.py", "--", "python", "-m", "main"]
EXPOSE 8080