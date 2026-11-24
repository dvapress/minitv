# OPTIONAL image. The supported deployment on aiexplorer.asia does not use Docker.
# harleyw cannot access the Docker daemon and must not be granted that access for this demo.
FROM node:22-bookworm-slim AS web
WORKDIR /src/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 --shell /usr/sbin/nologin leap
WORKDIR /opt/leapdrama
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY import-selection.json ./import-selection.json
COPY scripts ./scripts
COPY --from=web /src/web/build ./web/build
ENV LEAPDRAMA_DATA_DIR=/data \
    LEAPDRAMA_STATIC_DIR=/opt/leapdrama/web/build \
    LEAPDRAMA_SELECTION=/opt/leapdrama/import-selection.json \
    LEAPDRAMA_BIND=0.0.0.0 \
    LEAPDRAMA_PORT=18080 \
    PYTHONPATH=/opt/leapdrama/backend \
    PYTHONUNBUFFERED=1
EXPOSE 18080
RUN mkdir -p /data && chown -R leap:leap /opt/leapdrama /data
USER leap
CMD ["python", "-m", "uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "18080", "--workers", "1"]
