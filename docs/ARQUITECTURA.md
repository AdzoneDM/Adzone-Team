# Arquitectura

Una sola aplicación: **Django** sirve la API bajo `/api/` y, en producción, también la app web compilada (WhiteNoise). Mismo dominio, misma sesión (cookie + CSRF), sin CORS.

## Backend (`backend/apps/`)

| App | Qué guarda | Notas |
| --- | --- | --- |
| `core` | Departamento (nombre, colores, orden) | `departamentos_oficiales` deja los 7 oficiales. |
| `organizacion` | PuestoDeTrabajo (supervisor → árbol), PerfilUsuario | `cargar_puestos`, `cargar_equipo`. |
| `kpis` | PlantillaKPI, KPIAsignado (puesto, meta, peso, manual/automático) | |
| `desempeno` | Tarea, PasoTarea, EvidenciaArchivo, HistorialTarea, Notificacion, TareaRecurrente, ResultadoKPI, EmpleadoDelMes, ConfiguracionDesempeno | Toda la lógica del día a día. |

Las apps conservan su `label` original (`core`, `kpis`…), así que las tablas de la base de datos no cambiaron de nombre al reorganizar.

### Flujo de una tarea

`PENDIENTE → EN_PROGRESO → EN_REVISION → COMPLETADA` (o `CANCELADA`). Devolver la regresa a `EN_PROGRESO` y suma una ronda de revisión; reabrir una validada la regresa a `EN_REVISION`. Los cambios de estado solo ocurren con las acciones de la API (`iniciar`, `entregar`, `validar`, `rechazar`, `reabrir`, `cancelar`), que dejan historial y avisos.

- **Participantes:** el responsable (`colaborador`) y los `companeros`. Todos pueden iniciar, marcar pasos y entregar; ninguno puede validarla. Cuando se valida, cuenta para el puntaje y los KPIs de todos.
- **Supervisión en cascada:** quien ocupa un puesto gestiona a todos los puestos que cuelgan de él en el organigrama (`permisos.puestos_debajo`). Las entregas avisan al puesto inmediato superior con alguien; si no hay, a los administradores.

### Puntaje (`puntaje.py`)

Total = peso de tareas × nota de tareas + resto × cumplimiento de KPIs (60/40 por defecto, configurable). Nota de cada tarea = promedio de puntualidad (100 / tarde / 0) y calidad (estrellas), ponderado por prioridad. Bono sugerido solo con el mínimo de tareas validadas.

## Frontend (`frontend/src/`)

- `app/`: rutas (`App.jsx`) y estructura (`Estructura.jsx`: menú, campanita, franja de «Recordar» con sonido, consulta de avisos cada 30 s).
- `features/<área>/`: pantallas por área. `features/tareas/componentes.jsx` tiene las piezas comunes de tareas (detalle, pasos, entrega con fotos).
- `components/ui.jsx`: sistema de piezas (Boton, Modal, Campo, Insignia, TiraMes…). Colores en `index.css` (`@theme`).
- `lib/api.js`: todas las llamadas a la API.

## Tareas programadas

`python manage.py tareas_diarias` (una vez al día): crea las recurrentes de la semana y avisa lo que vence mañana.

## Hacia adelante (n8n / IA)

La API ya expone todo lo necesario (tareas, avisos, ranking). Para n8n conviene agregar un usuario técnico con token y permisos mínimos, en lugar de usar la cuenta de una persona.
