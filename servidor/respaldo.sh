#!/usr/bin/env bash
# Respaldo diario: base de datos + archivos privados. Guarda 14 días.
# Tarea programada en Plesk, 2:30 a. m.:  bash /var/www/vhosts/adzone.marketing/kpi-app/servidor/respaldo.sh
set -euo pipefail
APP="$(cd "$(dirname "$0")/.." && pwd)"
DESTINO="${RESPALDOS:-$APP/../kpi-respaldos}"
DIAS=14
mkdir -p "$DESTINO" && chmod 700 "$DESTINO"
leer() { grep -E "^$1=" "$APP/backend/.env" | tail -1 | cut -d= -f2-; }
FECHA=$(date +%Y-%m-%d_%H%M)

if [ "$(leer DB_ENGINE)" = "mysql" ]; then
  CNF=$(mktemp); chmod 600 "$CNF"
  printf '[client]\nuser=%s\npassword=%s\nhost=%s\nport=%s\n' "$(leer DB_USER)" "$(leer DB_PASSWORD)" "$(leer DB_HOST)" "$(leer DB_PORT)" > "$CNF"
  mysqldump --defaults-extra-file="$CNF" --single-transaction --routines "$(leer DB_NAME)" | gzip > "$DESTINO/base_$FECHA.sql.gz"
  rm -f "$CNF"
else
  cp "$APP/backend/db.sqlite3" "$DESTINO/base_$FECHA.sqlite3" && gzip "$DESTINO/base_$FECHA.sqlite3"
fi

MEDIA=$(leer MEDIA_ROOT)
[ -n "$MEDIA" ] && [ -d "$MEDIA" ] && tar -czf "$DESTINO/archivos_$FECHA.tar.gz" -C "$(dirname "$MEDIA")" "$(basename "$MEDIA")"
cp "$APP/backend/.env" "$DESTINO/env_$FECHA" && chmod 600 "$DESTINO"/env_* "$DESTINO"/*.gz

find "$DESTINO" -type f -mtime +$DIAS -delete
echo "Respaldo listo en $DESTINO ($FECHA)"
