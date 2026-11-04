#!/usr/bin/env bash
# Respaldo diario CIFRADO: base de datos + archivos privados + .env. Guarda 30 días.
# Tarea programada en Plesk, 2:30 a. m.:  bash /var/www/vhosts/adzone.marketing/kpi-app/servidor/respaldo.sh
# Cifrado AES-256 con la clave RESPALDO_CLAVE de backend/.env (guárdala también FUERA del servidor:
# sin ella no se puede abrir ningún respaldo). Para abrir uno:
#   openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -in base_FECHA.sql.gz.enc -out base_FECHA.sql.gz
set -euo pipefail
umask 077
APP="$(cd "$(dirname "$0")/.." && pwd)"
# Valor de backend/.env sin comillas ni fin de línea de Windows
leer() { { grep -E "^$1=" "$APP/backend/.env" || true; } | tail -1 | cut -d= -f2- | tr -d '\r' | sed -E 's/^"(.*)"$/\1/; s/^'"'"'(.*)'"'"'$/\1/'; }
DESTINO="$(leer RESPALDOS_DIR)"; DESTINO="${DESTINO:-$APP/../kpi-respaldos}"
DIAS=30
CLAVE="$(leer RESPALDO_CLAVE)"
[ -n "$CLAVE" ] || { echo "Falta RESPALDO_CLAVE en backend/.env: no se hacen respaldos sin cifrar."; exit 1; }
mkdir -p "$DESTINO" && chmod 700 "$DESTINO"
FECHA=$(date +%Y-%m-%d_%H%M)
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
# Se cifra en la carpeta temporal y luego se mueve: un respaldo a medias nunca queda en la lista.
# Junto a cada .enc queda su huella SHA-256 (para comprobar que la copia descargada está completa).
cifrar() {
  RESPALDO_CLAVE_ENV="$CLAVE" openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass env:RESPALDO_CLAVE_ENV -in "$1" -out "$1.enc"
  ( cd "$(dirname "$1")" && sha256sum "$(basename "$1").enc" > "$(basename "$1").enc.sha256" )
  mv "$1.enc.sha256" "$DESTINO/" && mv "$1.enc" "$DESTINO/"
}

if [ "$(leer DB_ENGINE)" = "mysql" ]; then
  CNF="$TMP/my.cnf"
  printf '[client]\nuser=%s\npassword=%s\nhost=%s\nport=%s\n' "$(leer DB_USER)" "$(leer DB_PASSWORD)" "$(leer DB_HOST)" "$(leer DB_PORT)" > "$CNF"
  mysqldump --defaults-extra-file="$CNF" --single-transaction --routines "$(leer DB_NAME)" | gzip > "$TMP/base_$FECHA.sql.gz"
else
  BASE="$(leer DB_NAME)"; BASE="${BASE:-$APP/backend/db.sqlite3}"
  # Copia consistente aunque la app esté escribiendo (API de respaldo de SQLite)
  python3 -c "import sqlite3,sys; a=sqlite3.connect(sys.argv[1]); b=sqlite3.connect(sys.argv[2]); a.backup(b); b.close()" "$BASE" "$TMP/base_$FECHA.sqlite3"
  gzip "$TMP/base_$FECHA.sqlite3"
fi
cifrar "$TMP"/base_$FECHA.*.gz

MEDIA=$(leer MEDIA_ROOT); MEDIA="${MEDIA:-$APP/backend/media}"
if [ -n "$MEDIA" ] && [ -d "$MEDIA" ]; then
  tar -czf "$TMP/archivos_$FECHA.tar.gz" -C "$(dirname "$MEDIA")" "$(basename "$MEDIA")"
  cifrar "$TMP/archivos_$FECHA.tar.gz"
fi
cp "$APP/backend/.env" "$TMP/env_$FECHA" && cifrar "$TMP/env_$FECHA"

find "$DESTINO" -type f \( -name '*.enc' -o -name '*.enc.sha256' \) -mtime +$DIAS -delete
# Copias SIN cifrar de versiones anteriores (incluido el .env en texto plano): se borran
find "$DESTINO" -type f \( -name 'base_*' -o -name 'archivos_*' -o -name 'env_*' \) ! -name '*.enc' ! -name '*.enc.sha256' -delete
echo "Respaldo cifrado listo en $DESTINO ($FECHA)"
