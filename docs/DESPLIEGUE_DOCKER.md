# Publicar Adzone Team con Docker

Alternativa a Plesk + Passenger (`docs/DESPLIEGUE.md`) para un VPS o cualquier servidor con Docker.

## Qué hay

| Archivo | Para qué |
|---|---|
| `Dockerfile` | Imagen única: compila el frontend (Node 22) y lo sirve con Django + Gunicorn (Python 3.12) |
| `docker-compose.yml` | 3 servicios: `web` (la app), `tareas` (tareas programadas) y `db` (MariaDB 11.4) |
| `docker/entrypoint.sh` | `web`: espera la base, `check --deploy`, `migrate` y Gunicorn · `tareas`: cron (supercronic) |
| `docker/crontab` | Las tareas de `servidor/tareas-programadas.txt`, en hora de RD, más el respaldo cifrado de las 2:30 |
| `docker/env.ejemplo` | Plantilla de la configuración (`.env.docker`) |
| `.dockerignore` | Deja fuera de la imagen `.env`, bases `.sqlite3`, `media/`, `datos_privados/` y `.xlsx` |

Volúmenes: `db` (MariaDB), `media` (evidencias y archivos privados, `/data/media`) y `respaldos` (`/data/respaldos`).

## 1 · Primera instalación

```bash
git clone <repo> adzone-team && cd adzone-team
cp docker/env.ejemplo .env.docker && chmod 600 .env.docker
nano .env.docker            # DJANGO_SECRET_KEY, contraseñas de la base (DB_* = MARIADB_*), RESPALDO_CLAVE, dominio
docker compose up -d --build
docker compose ps           # web «healthy», tareas y db arriba
```

Claves: `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`. **Guarda `RESPALDO_CLAVE` y una copia de `.env.docker` fuera del servidor**: en Docker el respaldo no incluye la configuración.

Datos iniciales (una sola vez):

```bash
docker compose exec web python manage.py departamentos_oficiales --aplicar
docker compose exec web python manage.py cargar_puestos datos_iniciales/organigrama_adzone.json
docker compose exec web python manage.py organigrama_2026 --aplicar
docker compose exec web python manage.py puestos_oficiales --aplicar
docker compose exec web python manage.py createsuperuser
```

Equipo real o datos de una instalación anterior (los archivos privados **no** van en la imagen; se copian al contenedor):

```bash
docker compose cp datos.json web:/tmp/datos.json
docker compose exec web python manage.py loaddata /tmp/datos.json
docker compose exec web rm /tmp/datos.json
```

Avisos al celular: `docker compose exec web python manage.py generar_vapid`, pega las 3 líneas `VAPID_…` en `.env.docker` y `docker compose up -d`.

## 2 · Proxy con HTTPS (obligatorio)

La app escucha solo en `127.0.0.1:8000` (cámbialo con `PUERTO=` en el entorno). Delante va nginx, Caddy, Traefik o el proxy de Plesk con Let's Encrypt. Sin HTTPS el celular no instala la app y Django redirige todo a `https://`.

Ejemplo nginx:

```nginx
server {
    server_name kpi.adzone.marketing;
    client_max_body_size 64m;                 # evidencias: hasta 6 archivos de 10 MB
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;   # imprescindible
        proxy_read_timeout 120s;
    }
    # listen 443 ssl; + certificados (certbot --nginx)
}
```

`NUM_PROXIES=1` en `.env.docker` corresponde a un solo proxy delante (ajústalo si hay Cloudflare + nginx = 2).

## 3 · Actualizar

```bash
git pull
docker compose up -d --build     # las migraciones se aplican solas al arrancar «web»
```

## 4 · Operación

```bash
docker compose logs -f web                    # registros de la app
docker compose logs -f tareas                 # tareas programadas
docker compose exec web python manage.py …    # cualquier comando de Django
docker compose exec tareas bash /app/servidor/respaldo.sh   # respaldo a mano
docker compose cp web:/data/respaldos ./respaldos-copia     # sacar los respaldos del servidor
```

Los respaldos cifrados quedan 30 días en el volumen `respaldos` y la Dirección los descarga en **Administración → Respaldos**. Conviene copiar también ese volumen a otro lugar (otro servidor o almacenamiento externo).

Abrir un respaldo: `openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -in base_FECHA.sql.gz.enc -out base_FECHA.sql.gz`, luego `gunzip` y `docker compose exec -T db mariadb -u root -p adzone_team < base_FECHA.sql`.

## Comprobar

- `https://kpi.adzone.marketing` muestra la pantalla «Entrar».
- `https://kpi.adzone.marketing/media/` no muestra nada.
- `docker compose ps`: `web` en **healthy**.
