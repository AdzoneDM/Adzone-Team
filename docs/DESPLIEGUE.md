# Publicar Adzone Team en el servidor (kpi.adzone.marketing)

La app es **una sola**: Django sirve la API (`/api/`) y también la app web ya compilada (todo lo demás). No hacen falta dos dominios ni configurar CORS.

> **Antes de nada:** el subdominio kpi.adzone.marketing tiene hoy una puerta trasera (`wp-blog-header.php`, `wp-cron.php` y dos `.htaccess` del 28/08/2026). Hay que **vaciar la carpeta del subdominio por completo** antes de subir esto, y cambiar las contraseñas de FTP y Plesk.

## 1 · En tu computadora: compilar la app web

```bash
cd frontend
npm install
npm run build        # crea frontend/dist
```

`frontend/dist` no se guarda en GitHub: se compila en tu computadora (o en el servidor, si tiene Node) antes de subir.

## 2 · En Plesk

Plesk necesita la extensión **Python** (Phusion Passenger). Si no aparece en «Sitios web y dominios → kpi.adzone.marketing», hay que pedirla al proveedor del servidor o usar un VPS pequeño con Gunicorn.

1. **Base de datos:** Bases de datos → Agregar → `adzone_team` (MariaDB), con su usuario.
2. **Archivos:** sube `backend/` y `frontend/dist/` **fuera** de `httpdocs`, por ejemplo `/var/www/vhosts/adzone.marketing/kpi-app/`. Deben quedar con la misma estructura: `kpi-app/backend` y `kpi-app/frontend/dist`.
3. **Entorno de Python** (en una terminal SSH, desde la carpeta `kpi-app`):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r backend/requirements.txt
   ```
4. **Configuración:** copia `backend/.env.example` como `backend/.env` y completa:
   - la clave secreta;
   - `DJANGO_ALLOWED_HOSTS=kpi.adzone.marketing`;
   - `CSRF_ORIGINS=https://kpi.adzone.marketing`;
   - `DB_ENGINE=mysql` y los datos de la base;
   - `MEDIA_ROOT` en una carpeta privada.
5. **Preparar la base** (dentro de la carpeta `backend`):
   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   python manage.py departamentos_oficiales --aplicar
   python manage.py cargar_puestos datos_iniciales/organigrama_adzone.json
   python manage.py createsuperuser    # tu usuario de administrador
   ```
   Para crear las cuentas del equipo de una vez, sube aparte (nunca a GitHub) `datos_privados/equipo.json` siguiendo `datos_iniciales/equipo.ejemplo.json` y corre `python manage.py cargar_equipo datos_privados/equipo.json --aplicar`. Muestra la contraseña inicial de cada persona una sola vez.

   Para traer los puestos y datos que ya existen en `db.sqlite3`: `python manage.py dumpdata --exclude contenttypes --exclude auth.permission > datos.json` en la copia vieja, y `python manage.py loaddata datos.json` en la nueva.
6. **Python en Plesk:** activa Python en el dominio con esta configuración:
   - raíz de la aplicación: `kpi-app/backend`;
   - archivo de inicio: `passenger_wsgi.py`;
   - entorno virtual: `kpi-app/venv`.
7. **SSL:** activa **Let's Encrypt** en el subdominio. Sin HTTPS, el celular no deja instalar la app.
8. **Tarea programada diaria (7:00 a. m.):** `cd /var/www/vhosts/adzone.marketing/kpi-app/backend && ../venv/bin/python manage.py tareas_diarias`. Crea las tareas recurrentes de la semana, avisa lo que vence al día siguiente y ejecuta las automatizaciones de vencidas (órdenes, tareas y facturas). Sin esta tarea, las recurrentes igual se crean cuando alguien abre sus tareas, pero los avisos de vencidas no salen.
9. **Archivos privados:** `MEDIA_ROOT` guarda evidencias, archivos de órdenes y comprobantes de gastos. Tiene que estar fuera de la carpeta pública e incluirse en el respaldo diario junto con la base de datos.
10. **n8n (opcional):** define `AUTOMATIZACIONES_SECRETO` en `.env` y usa la misma clave en n8n para verificar la cabecera `X-Adzone-Firma`.

## 3 · Comprobar

- Abrir `https://kpi.adzone.marketing`: debe salir la pantalla «Entrar».
- `https://kpi.adzone.marketing/media/` no debe mostrar nada: las fotos solo se ven dentro de la app.
- Instalar en un Android (Chrome → ⋮ → Instalar aplicación) y en un iPhone (Safari → Compartir → Agregar a pantalla de inicio).

## Actualizar más adelante

Con GitHub: en el servidor, `git pull` en la carpeta del proyecto (o sube los archivos nuevos) y luego:

```bash
pip install -r backend/requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

Después, reiniciar la app en Plesk.

### Organigrama 2026 (versión 6.1)

Después de `migrate` (que también carga el cronograma de producción):

```bash
python manage.py departamentos_oficiales --aplicar   # crea Comercial y Gestión del Talento
python manage.py organigrama_2026                    # muestra lo que haría
python manage.py organigrama_2026 --aplicar          # lo hace
```

Luego, en **Personas**, asigna a cada persona su puesto del organigrama (los puestos nuevos llegan vacíos).

### Si vienes de la versión 5

`migrate` crea las tablas de Órdenes de Área, traspasos, actas, cambios, almacén y Cashflow, y los accesos «Coordinación» y «Almacén». Después:

1. En **Personas**, da el acceso **Coordinación** a quien coordina producción y **Almacén** a quien despacha materiales.
2. En **Áreas y tiempos**, revisa quién supervisa cada área (si no se asigna, es el gerente del departamento) y carga la tabla de tiempos estándar.
3. En **Almacén → Materiales**, carga el catálogo con su existencia inicial (o con una entrada).
4. Cashflow: ver la sección siguiente.

La versión 5 no llegó a publicarse con órdenes reales, por eso sus migraciones de órdenes se rehicieron. Si llegaste a cargar órdenes de prueba en la v5, empieza desde una base de la v4 (o borra esas tablas) antes de `migrate`.

### Conectar Cashflow

1. En Cashflow → **Generador de API KEY**, genera la clave de la aplicación «API-CASHFLOW».
2. En el servidor, en `backend/.env` (nunca en GitHub ni en un chat):
   ```
   CASHFLOW_API_KEY=la-clave
   ```
   Si la documentación de desarrolladores de Cashflow indica otra dirección o cabecera, ajusta también `CASHFLOW_API_URL`, `CASHFLOW_AUTH_HEADER` y `CASHFLOW_AUTH_PREFIX` (ver `.env.example`).
3. Reinicia la app y prueba: `python manage.py sincronizar_cashflow --probar`, o **Finanzas → Cashflow → Probar conexión**.
4. Si algo responde 404 o 422, ajusta las rutas o los campos en `backend/apps/integraciones/cashflow/rutas.py` y `mapeo.py` según la documentación oficial (el README de esa carpeta explica cada operación). La bitácora en Finanzas → Cashflow muestra el error de cada llamada.

La tarea programada diaria (`python manage.py tareas_diarias`) trae los pagos de Cashflow cuando la clave está puesta.

### Si vienes de la versión 4

`migrate` crea las tablas de clientes, proyectos, órdenes, tiempo, finanzas y automatizaciones, y carga las cuatro automatizaciones base. Vuelve a correr `python manage.py departamentos_oficiales --aplicar` para crear **Call Center**. Finanzas entra con cualquier persona del departamento Administración; también se puede crear el grupo «Finanzas» en el administrador.

### Si vienes de la versión «Adzone KPIs»

La base de datos sirve tal cual: las migraciones nuevas solo agregan columnas (colores de departamento, cliente, compañeros y pasos). Después de `migrate`, corre una vez:

```bash
python manage.py departamentos_oficiales            # muestra cómo quedará cada puesto
python manage.py departamentos_oficiales --aplicar  # lo hace
```

Pasa los puestos a los departamentos oficiales y borra los departamentos viejos que queden vacíos (los que tengan Empleados del Mes guardados se conservan). Haz un respaldo de la base antes.
