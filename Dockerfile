# Adzone Team en un contenedor: Django sirve la API (/api/) y la app web compilada (todo lo demás).
#
#   docker compose up -d --build        (ver docs/DESPLIEGUE_DOCKER.md)
#
# Etapa 1 compila el frontend (React + Vite); etapa 2 deja solo Python + Gunicorn con frontend/dist.

# ── 1 · App web ───────────────────────────────────────────────────────────────
FROM node:22-alpine AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ── 2 · Servidor ──────────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=America/Santo_Domingo \
    FRONTEND_DIST=/app/frontend/dist \
    MEDIA_ROOT=/data/media \
    RESPALDOS_DIR=/data/respaldos \
    GUNICORN_WORKERS=3

# mariadb-client: mysqldump para servidor/respaldo.sh · openssl: cifrado de respaldos · tzdata: hora de RD
RUN apt-get update \
 && apt-get install -y --no-install-recommends mariadb-client openssl tzdata ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

# Supercronic: cron para contenedores (corre las tareas programadas con las variables de entorno)
ARG SUPERCRONIC_VERSION=v0.2.33
ARG SUPERCRONIC_SHA1SUM=71b0d58cc53f6bd72cf2f293e09e294b79c666d8
RUN curl -fsSLo /usr/local/bin/supercronic \
      "https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-amd64" \
 && echo "${SUPERCRONIC_SHA1SUM}  /usr/local/bin/supercronic" | sha1sum -c - \
 && chmod +x /usr/local/bin/supercronic

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend/ backend/
COPY servidor/ servidor/
COPY docker/ docker/
COPY --from=frontend /src/frontend/dist frontend/dist

# Archivos estáticos del admin y de DRF (sin clave = modo desarrollo, solo para este paso)
RUN cd backend && python manage.py collectstatic --noinput -v0

RUN useradd --create-home --uid 1000 adzone \
 && mkdir -p /data/media /data/respaldos \
 && chmod 750 /data/media && chmod 700 /data/respaldos \
 && chmod +x docker/entrypoint.sh servidor/*.sh \
 && chown -R adzone:adzone /data /app/backend
USER adzone
# Así «docker compose exec web python manage.py …» funciona directo
WORKDIR /app/backend

VOLUME ["/data/media", "/data/respaldos"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python /app/docker/salud.py

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["web"]
