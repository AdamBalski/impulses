FROM python:3.11-slim

WORKDIR /app

ENV PORT=8000
ENV GOOGLE_OAUTH2_CREDS={}
ENV ORIGIN=http://localhost:3001
ENV ORIGIN_API=http://localhost:8000
ENV SESSION_TTL_SEC=1800
ENV SQLITE_DB_PATH=/app/server/data-store/impulses.sqlite3

RUN apt-get update && apt-get install -y \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt

COPY . .

RUN mkdir -p /app/server/data-store

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD python3 -c "import json, os, sys, urllib.request; port = os.environ.get('PORT', '8000'); response = urllib.request.urlopen(f'http://127.0.0.1:{port}/healthz', timeout=2); payload = json.loads(response.read().decode('utf-8')); sys.exit(0 if payload.get('status') == 'UP' else 1)"

CMD ["bash", "-lc", "bash ./ops/db_migrate.sh && cd server && exec python -m src.run"]
