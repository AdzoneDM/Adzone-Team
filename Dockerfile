# Adzone Team en un contenedor: Django sirve la API (/api/) y la app web compilada (todo lo demás).
#
# Etapa 1 compila el frontend (React + Vite); etapa 2 deja solo Python + Gunicorn con frontend/dist.
# Versiones fijas: Node 24.22.3 y Python 3.12.16 (actualizaciones de seguridad de noviembre de 2026).

# ── 1 · App web ───────────────────────────────────────────────────────────────
FROM node:24.22.3-alpine3.24 AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
# --ignore-scripts: ningún paquete corre código al instalarse (esbuild, tailwind y rollup traen su binario aparte)
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ── 2 · Supercronic (cron para contenedores), descargado y verificado aparte ─────
FROM python:3.12.16-slim-trixie AS supercronic
ARG SUPERCRONIC_VERSION=v0.2.51
ARG TARGETARCH=amd64
RUN case "$TARGETARCH" in \
      amd64) SUMA=cc232108374e8e2b537045f2d5eaa1229f619db314c3ba6a14d38b35dc0aa123 ;; \
      arm64) SUMA=4ae22576a78223d8ccdf5f3b3660a5cbb5288416bf0ca96afc4a36d195932b94 ;; \
      *) echo "Arquitectura no soportada: $TARGETARCH" >&2; exit 1 ;; \
    esac \
 && python -c "import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], '/supercronic')" \
      "https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-${TARGETARCH}" \
 && echo "${SUMA}  /supercronic" | sha256sum -c - \
 && chmod 755 /supercronic

# ── 3 · Servidor ──────────────────────────────────────────────────────────────
FROM python:3.12.16-slim-trixie

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
# upgrade: parches de seguridad de Debian publicados después de la imagen base
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && apt-get install -y --no-install-recommends mariadb-client openssl tzdata ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Supercronic corre las tareas programadas (servicio «tareas») con las variables de entorno
COPY --from=supercronic /supercronic /usr/local/bin/supercronic

WORKDIR /app
# Versiones exactas con huella: si un paquete de PyPI cambia, la instalación falla en vez de aceptarlo
COPY backend/requirements.lock backend/requirements.lock
RUN pip install --require-hashes -r backend/requirements.lock

COPY backend/ backend/
COPY servidor/ servidor/
COPY docker/ docker/
COPY --from=frontend /src/frontend/dist frontend/dist

# Archivos estáticos del admin y de DRF (sin clave = modo desarrollo, solo para este paso)
RUN cd backend && python manage.py collectstatic --noinput -v0

# El código queda de root (solo lectura para la app); el usuario adzone solo escribe en /data
RUN useradd --create-home --uid 1000 adzone \
 && mkdir -p /data/media /data/respaldos \
 && chown adzone:adzone /data/media /data/respaldos \
 && chmod 750 /data/media && chmod 700 /data/respaldos \
 && chmod 755 docker/entrypoint.sh servidor/*.sh
USER adzone
# Así «docker compose exec web python manage.py …» funciona directo
WORKDIR /app/backend

VOLUME ["/data/media", "/data/respaldos"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD ["python", "/app/docker/salud.py"]

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["web"]
