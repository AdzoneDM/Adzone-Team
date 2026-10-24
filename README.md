# Adzone Team

La plataforma de trabajo de ADZONE: **tareas, KPIs y reconocimiento en un solo lugar**. Une lo que antes eran dos sistemas, *Adzone Team* (tablero de tareas del equipo) y *Adzone KPIs* (medición del desempeño).

- **Tareas:** se asignan a una persona o a varias (compañeros), con cliente, pasos para marcar y fecha límite. Se entregan con fotos, PDF, enlace o nota.
- **Validación:** solo cuenta lo que valida quien supervisa (con estrellas) o lo que devuelve con comentarios. Nadie valida su propio trabajo.
- **Mi equipo · Ahora:** en qué está cada persona (vencida, trabajando, por empezar, esperando validación, sin tareas o pidiendo más trabajo), con «Recordar» y «Asignar tarea» a un toque.
- **KPIs por puesto:** se llenan solos con las tareas validadas o se anotan cada mes en una planilla.
- **Puntaje y reconocimiento:** puntaje mensual, ranking, bono sugerido configurable, Empleado del Mes y Muro de Honor.

Se usa en la **PC** (menú lateral y tablas) y en el **celular** (barra inferior; se instala como app).

## Estructura del repositorio

```
adzone-team/
├── backend/                     Django + Django REST Framework
│   ├── config/                  ajustes, URLs y arranque (settings, wsgi, passenger_wsgi)
│   ├── apps/
│   │   ├── core/                departamentos, sesión y comando departamentos_oficiales
│   │   ├── organizacion/        puestos, organigrama, personas y comandos de carga
│   │   ├── kpis/                plantillas de KPI y KPIs asignados a cada puesto
│   │   └── desempeno/           tareas, pasos, evidencias, avisos, puntaje, ranking y Empleado del Mes
│   ├── datos_iniciales/         organigrama oficial y ejemplo de equipo (sin datos personales)
│   └── datos_privados/          datos reales del equipo · NO se sube (ver LEEME.md)
├── frontend/                    React 19 + Vite + Tailwind CSS 4 (PWA)
│   └── src/
│       ├── app/                 rutas y estructura (menú, campanita, recordatorios)
│       ├── components/          piezas comunes (botones, ventanas, marca…)
│       ├── features/            una carpeta por área: tareas, equipo, desempeno, kpis, organizacion, cuenta, inicio
│       └── lib/                 API, sesión y formatos
├── docs/                        despliegue y arquitectura
└── .github/workflows/ci.yml     revisión automática en cada cambio
```

En el frontend, los imports usan `@/` para `src/` (`import { api } from "@/lib/api"`).

## Trabajar en tu computadora

Necesitas **Python 3.12+** y **Node 22+**.

```bash
# Backend
cd backend
python -m venv venv
venv\Scripts\activate            # Windows   (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
python manage.py migrate
python manage.py departamentos_oficiales --aplicar             # los 7 departamentos con sus colores
python manage.py cargar_puestos datos_iniciales/organigrama_adzone.json
python manage.py createsuperuser
python manage.py runserver       # http://127.0.0.1:8000

# Frontend (otra terminal)
cd frontend
npm install
npm run dev                      # http://localhost:5173 (usa el backend por proxy)
```

Sin `backend/.env`, el backend arranca en modo desarrollo con SQLite. Para el servidor, ver [`docs/DESPLIEGUE.md`](docs/DESPLIEGUE.md).

## Pruebas

```bash
cd backend && python manage.py test apps     # 47 pruebas: puntaje, permisos, flujo, compañeros, pasos, carga del equipo…
cd frontend && npm run lint && npm run build
```

GitHub las corre solas en cada Pull Request (ver [`CONTRIBUTING.md`](CONTRIBUTING.md)).

## Roles

| Rol | Quién | Qué hace |
| --- | --- | --- |
| Colaborador | Todo el equipo | Ve sus tareas (propias y compartidas), marca pasos, entrega con evidencia, pide más trabajo y consulta su avance, puntaje y KPIs. |
| Supervisor | Quien ocupa un puesto del que dependen otros (organigrama) | Ve a todo lo que cuelga de su puesto, en cascada. Asigna, programa recurrentes, recuerda, valida o devuelve. |
| Administrador | Dirección | Todo, para toda la empresa. Además configura organigrama, personas, KPIs, reglas del puntaje y declara el Empleado del Mes. |

## Departamentos oficiales

Gerencia · Marketing · Audiovisual · Adzone TV · Impresión · Administración · Tecnología. Cada uno con su color, que se ve en el tablero del equipo y en los puestos.

## Seguridad

- No subas nunca la base de datos, la carpeta `media/`, el archivo `.env` ni `datos_privados/`. El `.gitignore` ya los excluye.
- Las fotos de evidencia no son públicas: se descargan por la API, que revisa permisos.

Ver [`CAMBIOS.md`](CAMBIOS.md) para el historial de versiones.

---
© 2026 Ad Zone Digital Marketing SRL. Uso interno.
