#!/usr/bin/env bash
# Arranque del contenedor.
#   web     → espera la base, aplica migraciones y levanta Gunicorn (por defecto)
#   tareas  → tareas programadas (docker/crontab) con supercronic
#   otro    → se ejecuta tal cual, p. ej.:  docker compose run --rm web python backend/manage.py createsuperuser
set -euo pipefail
cd /app/backend

esperar_base() {
  [ "${DB_ENGINE:-sqlite}" = "sqlite" ] && return 0
  echo "Esperando la base de datos en ${DB_HOST:-localhost}:${DB_PORT:-3306}…"
  for _ in $(seq 1 60); do
    python - <<'PY' && return 0
import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.db import connection
try:
    connection.ensure_connection()
except Exception:
    sys.exit(1)
PY
    sleep 2
  done
  echo "La base de datos no respondió en 2 minutos." >&2
  exit 1
}

case "${1:-web}" in
  web)
    esperar_base
    python manage.py check --deploy --fail-level ERROR
    python manage.py migrate --noinput
    exec gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers "${GUNICORN_WORKERS:-3}" \
      --timeout "${GUNICORN_TIMEOUT:-120}" \
      --forwarded-allow-ips '*' \
      --access-logfile - --error-logfile -
    ;;
  tareas)
    esperar_base
    exec /usr/local/bin/supercronic -passthrough-logs /app/docker/crontab
    ;;
  *)
    exec "$@"
    ;;
esac
