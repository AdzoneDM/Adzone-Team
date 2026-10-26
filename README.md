# Adzone Team

La plataforma de trabajo de ADZONE: **tareas, KPIs y reconocimiento en un solo lugar**. Une lo que antes eran dos sistemas, *Adzone Team* (tablero de tareas del equipo) y *Adzone KPIs* (medición del desempeño).

- **Órdenes de trabajo por área:** impresión, Adzone TV, call center, marketing, audiovisual, desarrollo y administración. Cada área tiene su propio formulario. El recorrido es solicitud → aprobación → producción → control de calidad → lista → entrega, con tablero arrastrable, tabla y calendario.
- **Proyectos y clientes:** tabla, tablero y cronograma (Gantt). Cada proyecto reúne sus tareas, sus órdenes, sus horas, una conversación con @menciones y su rentabilidad.
- **Tareas:** se asignan a una persona o a varias, con pasos, cliente, proyecto, horas estimadas y fechas. Solo cuentan cuando quien supervisa las valida.
- **Tiempo y carga:** cronómetro siempre visible, tiempo anotado a mano, capacidad semanal de cada persona con aviso de sobrecarga y reporte de horas.
- **Finanzas operativas:** cotizaciones, facturas con ITBIS, cobros, gastos con comprobante, cuentas por cobrar por antigüedad, órdenes sin facturar y rentabilidad por proyecto o cliente.
- **Automatizaciones:** reglas «cuando pase X, haz Y» que avisan, crean tareas o envían datos a **n8n** por webhook firmado.
- **KPIs y reconocimiento:** puntaje mensual, ranking, bono sugerido, Empleado del Mes y Muro de Honor.
- **Mi equipo · Ahora:** en qué está cada persona, quién pide más trabajo, «Recordar» con sonido.
- **Buscador Ctrl+K** y botón **Crear** desde cualquier pantalla.

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
│   │   ├── desempeno/           tareas, pasos, evidencias, avisos, puntaje, ranking y Empleado del Mes
│   │   ├── operaciones/         clientes, proyectos, órdenes de trabajo (formularios.py: el formulario de cada área)
│   │   ├── tiempo/              cronómetro, registros de tiempo y carga
│   │   ├── finanzas/            cotizaciones, facturas, pagos, gastos y rentabilidad
│   │   └── automatizaciones/    reglas y webhooks a n8n
│   ├── datos_iniciales/         organigrama oficial y ejemplo de equipo (sin datos personales)
│   └── datos_privados/          datos reales del equipo · NO se sube (ver LEEME.md)
├── frontend/                    React 19 + Vite + Tailwind CSS 4 (PWA)
│   └── src/
│       ├── app/                 rutas y estructura (menú, campanita, recordatorios)
│       ├── components/          piezas comunes (botones, ventanas, marca…)
│       ├── features/            una carpeta por área: ordenes, proyectos, clientes, tiempo, finanzas, automatizaciones, tareas, equipo…
│       └── lib/                 API, sesión y formatos
├── docs/                        guía de operación, despliegue y arquitectura
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
python manage.py departamentos_oficiales --aplicar             # los 8 departamentos con sus colores
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
cd backend && python manage.py test apps     # 70 pruebas: órdenes, permisos, flujo, tiempo, finanzas, automatizaciones, puntaje…
cd frontend && npm run lint && npm run build
```

GitHub las corre solas en cada Pull Request (ver [`CONTRIBUTING.md`](CONTRIBUTING.md)).

## Roles

| Rol | Quién | Qué hace |
| --- | --- | --- |
| Colaborador | Todo el equipo | Ve sus tareas (propias y compartidas), marca pasos, entrega con evidencia, pide más trabajo y consulta su avance, puntaje y KPIs. |
| Supervisor | Quien ocupa un puesto del que dependen otros (organigrama) | Ve a todo lo que cuelga de su puesto, en cascada. Asigna, programa recurrentes, recuerda, valida o devuelve. |
| Finanzas | Departamento de Administración (o grupo «Finanzas») | Cotizaciones, facturas, cobros, gastos y rentabilidad de toda la empresa. |
| Administrador | Dirección | Todo, para toda la empresa. Además configura organigrama, personas, KPIs, reglas del puntaje, automatizaciones y declara el Empleado del Mes. |

Cómo se trabaja con órdenes, proyectos, tiempo y finanzas, paso a paso: [`docs/GUIA_OPERACION.md`](docs/GUIA_OPERACION.md).

## Departamentos oficiales

Gerencia · Marketing · Audiovisual · Adzone TV · Impresión · Administración · Tecnología · Call Center. Cada uno con su color, que se ve en el tablero del equipo y en los puestos.

## Seguridad

- No subas nunca la base de datos, la carpeta `media/`, el archivo `.env` ni `datos_privados/`. El `.gitignore` ya los excluye.
- Las fotos de evidencia no son públicas: se descargan por la API, que revisa permisos.

Ver [`CAMBIOS.md`](CAMBIOS.md) para el historial de versiones.

---
© 2026 Ad Zone Digital Marketing SRL. Uso interno.
