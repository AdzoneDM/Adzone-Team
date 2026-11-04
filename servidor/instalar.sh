#!/usr/bin/env bash
# Instala o actualiza Adzone Team en el servidor. Se corre por SSH desde la carpeta kpi-app:
#   bash servidor/instalar.sh            (instalación nueva: carga también los datos)
#   bash servidor/instalar.sh --actualizar   (solo código: no toca los datos)
set -euo pipefail
cd "$(dirname "$0")/.."
APP="$(pwd)"
[ -f backend/.env ] || { echo "Falta backend/.env (copia ahí el archivo env-servidor)."; exit 1; }
grep -q "PON_AQUI" backend/.env && { echo "Completa DB_PASSWORD en backend/.env."; exit 1; }
chmod 600 backend/.env
grep -qE '^RESPALDO_CLAVE=.+' backend/.env || echo "AVISO: falta RESPALDO_CLAVE en backend/.env: los respaldos nocturnos no se harán hasta que la pongas."


[ -d venv ] || python3 -m venv venv
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r backend/requirements.txt

MEDIA=$(grep -E '^MEDIA_ROOT=' backend/.env | cut -d= -f2-)
[ -n "$MEDIA" ] && mkdir -p "$MEDIA" && chmod 750 "$MEDIA"

cd backend
"$APP/venv/bin/python" manage.py check --deploy --fail-level ERROR
"$APP/venv/bin/python" manage.py migrate --noinput
"$APP/venv/bin/python" manage.py collectstatic --noinput -v0

if [ "${1:-}" != "--actualizar" ]; then
  if [ -f "$APP/../datos.json" ]; then
    "$APP/venv/bin/python" manage.py loaddata "$APP/../datos.json"
    echo "Datos cargados. Borra el archivo: rm $APP/../datos.json"
  else
    echo "No encontré ../datos.json: la base queda vacía (solo lo que crean las migraciones)."
  fi
fi

mkdir -p "$APP/backend/tmp" && touch "$APP/backend/tmp/restart.txt"   # Passenger se reinicia con este archivo
echo "Listo. Reinicia la app en Plesk (Python → Reiniciar) si no se reinició sola."
