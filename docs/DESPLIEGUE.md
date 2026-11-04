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

### App de celular: avisos y marcaje con QR (versión 12.1)

```bash
venv/bin/pip install -r backend/requirements.txt   # agrega «pywebpush»
python manage.py migrate
python manage.py generar_vapid                      # copia las 3 líneas VAPID_… a backend/.env y reinicia la app
```

1. **Asistencia → Horarios → Lugares de marcaje → Lugar**: crea «Oficina Bonao». Estando en la oficina, toca «Usar mi ubicación actual».
2. Copia el **enlace de la pantalla** y ábrelo en una tablet o monitor de la recepción (pantalla completa, sin apagarse). No necesita entrar con usuario. Si el enlace se comparte por error, genera otro (↻).
3. En **Horario de cada persona → Dónde marca**: «En la oficina» para quien trabaja allí, «En la calle» para instalación, eventos y producción fuera.
4. Pide al equipo que instale la app y active los avisos (Mi cuenta → Avisos en este celular).

### Seguridad de las cuentas y respaldos cifrados (versión 12.0)

```bash
venv/bin/pip install -r backend/requirements.txt   # agrega «qrcode»
python manage.py migrate
```

En `backend/.env` del servidor:

1. **Claves nuevas** (obligatorio si el archivo `env-servidor` pasó por un chat o un correo): genera y reemplaza `DJANGO_SECRET_KEY` y `AUTOMATIZACIONES_SECRETO` (y pon la nueva en n8n):
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(50))"
   ```
   Cambiar la clave secreta cierra todas las sesiones abiertas: es lo esperado.
2. **`RESPALDO_CLAVE=`** con una clave larga (mismo comando). **Guárdala también fuera del servidor** (por ejemplo, impresa en la caja fuerte): sin ella no se abre ningún respaldo.
3. Opcional: `INACTIVIDAD_EMPRESA_MIN=30` y `INACTIVIDAD_MIN=720` (minutos sin usar la app antes de cerrar la sesión).

Después:
- La primera vez que entre cada persona de **Dirección, Administrador del sistema, Gestión del Talento o Finanzas**, la plataforma le pide **activar la verificación en dos pasos** con Google o Microsoft Authenticator y le entrega 10 códigos de respaldo. Sin eso no puede seguir. Para el resto es opcional (Mi cuenta).
- Si alguien pierde el celular y sus códigos: **Accesos y permisos → la persona → Reiniciar**. Si la pierde la única persona de Dirección, desde SSH: `python manage.py shell -c "from apps.core.models import DosPasos; DosPasos.objects.filter(usuario__username='USUARIO').delete()"`.
- La tarea del **respaldo de las 2:30** ahora cifra todo y guarda 30 días. Cada lunes la Dirección recibe un aviso para descargar el de la semana en **Administración → Respaldos** (y una alerta si anoche no se hizo).
- **Abrir un respaldo** (en tu computadora, con OpenSSL):
  ```bash
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -in base_FECHA.sql.gz.enc -out base_FECHA.sql.gz
  gunzip base_FECHA.sql.gz        # y luego: mysql adzone_team < base_FECHA.sql
  ```

### Accesos y permisos: mínimo privilegio (versión 11.0)

```bash
python manage.py migrate        # crea los perfiles y asigna uno a cada persona
```

La migración da a cada persona un perfil inicial: quien era administrador queda como **Administrador (Dirección)**; quien tiene gente a cargo en el organigrama, **Supervisor** (los gerentes conservan **Gerente de Departamento**); el jefe del área de Tecnología, **Tecnología**; el departamento de Gestión del Talento (y el antiguo grupo «RRHH»), **Gestión del Talento**; el resto, **Colaborador**.

Después de actualizar:
1. **Administración → Accesos y permisos → Personas**: revisa el perfil de cada una (filtra por perfil). Da **Administrador del sistema** a quien configura la plataforma sin ver salarios.
2. **Perfiles** (solo Dirección): ajusta qué permite cada perfil si hace falta.
3. Avisa a los supervisores: desde esta versión **ya no ven el monitoreo de su equipo** (lo ven Dirección y Tecnología); siguen viendo tareas, KPIs, asistencia y evaluaciones.

### Monitoreo avanzado, políticas, rentabilidad y activos (versión 10.0)

```bash
python manage.py migrate        # crea las 11 reglas de comportamiento y las 14 políticas en borrador
```

Tareas programadas nuevas en Plesk:

| Cada | Comando | Para qué |
|---|---|---|
| 1 vez al día, 7:30 | `python manage.py revisar_talento` | Documentos por vencer y recordatorio semanal de políticas pendientes |
| 1 vez al día, 7:35 | `python manage.py revisar_activos` | Mantenimientos de equipos vencidos o en los próximos 7 días |

Puesta en marcha:
1. **Políticas → Administrar**: revisa los 14 borradores (con su asesor legal), ajústalos y publícalos. Al publicar llega el aviso a cada persona.
2. **Políticas → Documentos**: sube contrato, copia de identificación y acuerdo de confidencialidad de cada persona.
3. **Monitoreo → Reglas → Comportamiento**: revisa las 11 reglas iniciales (sitios, minutos, riesgo, departamentos donde no aplican) y toca «Aplicar a 30 días».
4. **Monitoreo → Reglas → Perfiles**: crea los perfiles (p. ej. Dirección sin monitoreo, Call Center con capturas cada 10 minutos).
5. **Finanzas → Rentabilidad**: carga la tasa de cambio del Banco Central y registra los gastos de cada OT.
6. **Activos y equipos**: registra las computadoras, cámaras, luces, herramientas y vehículos y asígnalos.

### Talento, KPIs con ficha técnica y panel gerencial (versión 9.0)

```bash
python manage.py migrate
python manage.py puestos_oficiales --aplicar   # agrega los KPIs de seguimiento (8 a 15 por puesto) y su ficha técnica
```

La migración cambia las reglas del puntaje que estaban en 48/32/20 por **40 tareas / 35 KPIs / 15 calidad / 10 asistencia**. Si las habían cambiado a mano, quedan igual con calidad en 0; se ajustan en Reglas del puntaje.

Tarea programada nueva en Plesk:

| Cada | Comando | Para qué |
|---|---|---|
| Días 1 al 5 de cada mes, 7:00 | `python manage.py revisar_kpis` | Avisa al supervisor de cada KPI del mes anterior por debajo de su umbral (una vez por KPI) |

Puesta en marcha:
1. **Talento → Ciclos → Abrir ciclo** (por ejemplo «4.º trimestre 2026»): a cada persona le llega su autoevaluación, la de su equipo si supervisa y dos compañeros.
2. Revisa en **Puestos** el umbral de alerta de los KPIs (70 % por defecto) y la fórmula y responsable en **Plantillas de KPI**.
3. Pide a cada supervisor que use el **cronómetro** en las tareas vinculadas a una OT: así el monitoreo por proyecto y el costo de la mano de obra salen solos.
4. Revisa el **Panel gerencial** al cierre de cada mes.

### Control de horario y monitoreo (versión 8.0)

```bash
python manage.py migrate
python manage.py reglas_productividad          # reglas de productividad por departamento (si faltan)
python manage.py puestos_oficiales --aplicar   # deja activos los KPIs automáticos
```

Tareas programadas en Plesk:

| Cada | Comando | Para qué |
|---|---|---|
| 10 minutos, de 7:00 a 20:00 | `python manage.py revisar_jornadas` | Avisos de tardanza, sin marcar, inactividad, PC sin reportar, improductivo |
| 1 vez al día (madrugada) | `python manage.py limpiar_monitoreo` | Borra actividad de más de 90 días y capturas de más de 30 |

Puesta en marcha recomendada:
1. **Asistencia → Horarios**: revisa el horario de oficina, crea los del call center y asigna a cada persona. Desmarca «marca obligatoria» a la dirección si no marcará. Carga los feriados del año.
2. **Comunica la política** (Monitoreo → Mis equipos y política) y que cada persona la acepte. Agrega la cláusula de monitoreo al contrato o reglamento interno.
3. **Agente**: construye `AdzoneAgente.exe` con `agente/construir_windows.bat` en una PC con Windows, instálalo en cada computadora y vincúlala (Monitoreo → Mis equipos → Vincular computadora). Ver `agente/LEEME.md`.
4. Ajusta las **reglas de productividad** de cada departamento en las primeras dos semanas y aplícalas a los últimos 30 días.
5. Las **capturas** están apagadas: actívalas solo si hace falta, en Monitoreo → Configuración.

### Puestos oficiales y personal (versión 7.0)

Después de `migrate` y del organigrama (sección siguiente):

```bash
python manage.py puestos_oficiales --aplicar          # descripciones de puesto y KPIs con ponderación
# personal real: backend/datos_privados/personal_adzone_2026.json (no se sube a GitHub)
python manage.py cargar_equipo datos_privados/personal_adzone_2026.json           # muestra lo que haría
python manage.py cargar_equipo datos_privados/personal_adzone_2026.json --aplicar # crea las cuentas
```

Las contraseñas iniciales salen una sola vez en pantalla: guárdalas y entrégalas en persona. Antes de cargar, completa el
correo de cada quien en el archivo y asigna el puesto de quienes vienen «sin cargo» en la nómina.

En una base nueva (sin puestos todavía), el orden es: `departamentos_oficiales --aplicar` →
`cargar_puestos datos_iniciales/organigrama_adzone.json` → `organigrama_2026 --aplicar` → `puestos_oficiales --aplicar` →
`cargar_equipo … --aplicar`.

### Organigrama 2026 (versión 6.1)

Después de `migrate` (que también carga el cronograma de producción):

```bash
python manage.py departamentos_oficiales --aplicar   # crea Comercial y Gestión del Talento
python manage.py organigrama_2026                    # muestra lo que haría
python manage.py organigrama_2026 --aplicar          # lo hace
```

Los puestos nuevos llegan con su descripción de puesto y sus KPIs propuestos (`backend/apps/organizacion/descripciones_2026.py` y `kpis_2026.py`); revísalos en **Departamentos y puestos** y en **Plantillas de KPI**. Luego, en **Personas**, asigna a cada persona su puesto del organigrama.

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
