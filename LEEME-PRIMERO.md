# Adzone Team 12.3 · Cómo trabajar con este proyecto

Este zip es el proyecto completo. Con él trabajas en **Visual Studio Code**, lo subes a **GitHub** y lo instalas en **Plesk**.
La app web ya va compilada en `frontend/dist`, así que para publicar no hace falta compilar nada.

```
adzone-team/
├── backend/        Django (API). Aquí va el .env del servidor (nunca en GitHub)
├── frontend/       React: src/ (código) y dist/ (compilada, lista para el servidor)
├── servidor/       instalar.sh · respaldo.sh (cifrado) · tareas-programadas.txt
├── agente/         agente de monitoreo para Windows y Mac
├── docs/           DESPLIEGUE · PLAN_PILOTO · ARQUITECTURA · GUIA_OPERACION · POLITICA_MONITOREO
├── .vscode/        configuración y extensiones recomendadas
└── CAMBIOS.md      qué trae cada versión
```

---

## 1 · Abrir en Visual Studio Code (tu computadora)

Necesitas **Python 3.12 o más nuevo**, **Node.js 20 o más nuevo** y **Git**.

1. Descomprime el zip y abre la carpeta `adzone-team` en VS Code (Archivo → Abrir carpeta). Acepta instalar las extensiones recomendadas.
2. En la terminal de VS Code (Terminal → Nueva terminal):

   ```bash
   # Backend
   cd backend
   python -m venv venv
   # Windows:  venv\Scripts\activate     ·     Mac/Linux:  source venv/bin/activate
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py createsuperuser
   python manage.py runserver            # http://127.0.0.1:8000
   ```

   ```bash
   # App web, en otra terminal (recarga sola al guardar)
   cd frontend
   npm install
   npm run dev                           # http://localhost:5173
   ```

   En tu computadora no hace falta `.env`: sin él arranca en modo desarrollo con una base SQLite propia.
3. **Pruebas** antes de publicar un cambio: `cd backend && python manage.py test apps` (y `cd frontend && npm run lint`).
4. **Compilar la app web** cuando cambies algo de `frontend/src`: `cd frontend && npm run build` (actualiza `frontend/dist`).

> En VS Code también puedes correr el backend o las pruebas con **F5** (menú «Ejecutar y depurar»).

---

## 2 · Subir a GitHub (repositorio privado `AdzoneDM/Adzone-Team`)

El historial de cambios ya viene incluido (carpeta oculta `.git`). Desde la carpeta `adzone-team`:

```bash
git remote add origin https://github.com/AdzoneDM/Adzone-Team.git
git push -u origin main
```

Si el repositorio ya tenía otra historia y GitHub rechaza el envío, crea uno nuevo vacío y súbelo ahí, o pídeme ayuda: no uses `--force` sin revisar.

**Nunca van a GitHub** (el `.gitignore` ya los deja fuera): la base de datos, `backend/.env`, `backend/media/`, `backend/datos_privados/` (datos del personal) ni `frontend/dist/`.
Antes de cada `git push`, revisa con `git status` que no aparezca ninguno.

Para trabajar después: haces cambios → `git add -A` → `git commit -m "qué cambiaste"` → `git push`.

---

## 3 · Publicar en Plesk (kpi.adzone.marketing)

> **Antes de nada:** vacía la carpeta del subdominio (tiene la puerta trasera de WordPress del 28/08/2026) y cambia las contraseñas de Plesk, FTP y SSH.

1. **En Plesk:** extensión Python (Passenger), base de datos MariaDB `adzone_team` y SSL Let's Encrypt.
2. **Sube la carpeta del proyecto** como `/var/www/vhosts/adzone.marketing/kpi-app/` (fuera de `httpdocs`). Bastan `backend/`, `frontend/dist/` y `servidor/`.
3. **`backend/.env`** en el servidor: copia `backend/.env.example` y complétalo. Genera cada clave con
   `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`:
   - `DJANGO_SECRET_KEY` y `AUTOMATIZACIONES_SECRETO` **nuevas** (las del paquete 11.1 pasaron por un chat).
   - `DB_ENGINE=mysql` y los datos de la base.
   - `RESPALDO_CLAVE`: guárdala también fuera del servidor, porque sin ella no se abre ningún respaldo.
   - Opcional: `ANTHROPIC_API_KEY` (IA) y `CASHFLOW_API_KEY`. Van **solo** en el servidor.
4. **Instala** por SSH:

   ```bash
   cd /var/www/vhosts/adzone.marketing/kpi-app
   bash servidor/instalar.sh                 # primera vez (si dejas ../datos.json del paquete 11.1, carga el equipo)
   rm -f ../datos.json
   cd backend && ../venv/bin/python manage.py generar_vapid   # copia las 3 líneas VAPID_… al .env
   ../venv/bin/python manage.py changepassword admin           # tu contraseña (larga y nueva)
   touch tmp/restart.txt
   ```

5. **Plesk → Python:** raíz `kpi-app/backend`, archivo de inicio `passenger_wsgi.py`, entorno `kpi-app/venv` → Reiniciar.
6. **Tareas programadas:** las 7 de `servidor/tareas-programadas.txt` (incluido el respaldo cifrado de las 2:30).
7. **Primera entrada:** la Dirección activa la verificación en dos pasos y guarda sus 10 códigos de respaldo.

**Actualizar más adelante:** sube la carpeta nueva encima (sin tocar `backend/.env` ni `venv/`) y corre
`bash servidor/instalar.sh --actualizar`.

Lo demás (lugares de marcaje con QR y red de la oficina, avisos en el celular, portal del cliente, IA, respaldos)
está paso a paso en **`docs/DESPLIEGUE.md`**. El piloto del monitoreo, en **`docs/PLAN_PILOTO.md`**.
