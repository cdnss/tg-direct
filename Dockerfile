FROM python:3.9-slim-buster

WORKDIR /app

COPY requirements.txt .

RUN apt-get update && apt-get install --no-install-recommends -y sudo ffmpeg curl unzip && \
    pip install --no-cache-dir -r requirements.txt && \
    curl -fsSL https://deno.land/x/install/install.sh | sh && \
    mv /root/.deno/bin/deno /usr/local/bin/

# Use volume mount for source code to avoid rebuilding
CMD ["python", "-m", "main"]
EXPOSE 8080
