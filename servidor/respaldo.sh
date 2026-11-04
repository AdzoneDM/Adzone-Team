#!/usr/bin/env bash
# Respaldo diario CIFRADO: base de datos + archivos privados + .env. Guarda 30 días.
# Tarea programada en Plesk, 2:30 a. m.:  bash /var/www/vhosts/adzone.marketing/kpi-app/servidor/respaldo.sh
# Cifrado AES-256 con la clave RESPALDO_CLAVE de backend/.env (guárdala también FUERA del servidor:
# sin ella no se puede abrir ningún respaldo). Para abrir uno:
#   openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -in base_FECHA.sql.gz.enc -out base_FECHA.sql.gz
set -euo pipefail
umask 077
APP="$(cd "$(dirname "$0")/.." && pwd)"
leer() { { grep -E "^$1=" "$APP/backend/.env" || true; } | tail -1 | cut -d= -f2-; }
DESTINO="$(leer RESPALDOS_DIR)"; DESTINO="${DESTINO:-$APP/../kpi-respaldos}"
DIAS=30
CLAVE="$(leer RESPALDO_CLAVE)"
[ -n "$CLAVE" ] || { echo "Falta RESPALDO_CLAVE en backend/.env: no se hacen respaldos sin cifrar."; exit 1; }
export RESPALDO_CLAVE_ENV="$CLAVE"
mkdir -p "$DESTINO" && chmod 700 "$DESTINO"
FECHA=$(date +%Y-%m-%d_%H%M)
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
cifrar() { openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass env:RESPALDO_CLAVE_ENV -in "$1" -out "$DESTINO/$(basename "$1").enc"; }

if [ "$(leer DB_ENGINE)" = "mysql" ]; then
  CNF="$TMP/my.cnf"
  printf '[client]\nuser=%s\npassword=%s\nhost=%s\nport=%s\n' "$(leer DB_USER)" "$(leer DB_PASSWORD)" "$(leer DB_HOST)" "$(leer DB_PORT)" > "$CNF"
  mysqldump --defaults-extra-file="$CNF" --single-transaction --routines "$(leer DB_NAME)" | gzip > "$TMP/base_$FECHA.sql.gz"
else
  BASE="$(leer DB_NAME)"; BASE="${BASE:-$APP/backend/db.sqlite3}"
  sqlite3 "$BASE" ".backup '$TMP/base_$FECHA.sqlite3'" 2>/dev/null || cp "$BASE" "$TMP/base_$FECHA.sqlite3"
  gzip "$TMP/base_$FECHA.sqlite3"
fi
cifrar "$TMP"/base_$FECHA.*.gz

MEDIA=$(leer MEDIA_ROOT)
if [ -n "$MEDIA" ] && [ -d "$MEDIA" ]; then
  tar -czf "$TMP/archivos_$FECHA.tar.gz" -C "$(dirname "$MEDIA")" "$(basename "$MEDIA")"
  cifrar "$TMP/archivos_$FECHA.tar.gz"
fi
cp "$APP/backend/.env" "$TMP/env_$FECHA" && cifrar "$TMP/env_$FECHA"

find "$DESTINO" -type f -name '*.enc' -mtime +$DIAS -delete
echo "Respaldo cifrado listo en $DESTINO ($FECHA)"
