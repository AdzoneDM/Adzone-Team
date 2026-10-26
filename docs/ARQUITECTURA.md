# Arquitectura

Una sola aplicación: **Django** sirve la API bajo `/api/` y, en producción, también la app web compilada (WhiteNoise). Mismo dominio, misma sesión (cookie + CSRF), sin CORS.

## Backend (`backend/apps/`)

| App | Qué guarda | Notas |
| --- | --- | --- |
| `core` | Departamento (nombre, colores, orden) | `departamentos_oficiales` deja los 7 oficiales. |
| `organizacion` | PuestoDeTrabajo (supervisor → árbol), PerfilUsuario | `cargar_puestos`, `cargar_equipo`. |
| `kpis` | PlantillaKPI, KPIAsignado (puesto, meta, peso, manual/automático) | |
| `desempeno` | Tarea, PasoTarea, EvidenciaArchivo, HistorialTarea, Notificacion, TareaRecurrente, ResultadoKPI, EmpleadoDelMes, ConfiguracionDesempeno | Tareas, validación, avisos y puntaje. |
| `operaciones` | Cliente, Proyecto, OrdenTrabajo, EventoOrden, ArchivoOrden, Comentario | `formularios.py` define el formulario y los pasos de cada área. `permisos.py`: quién ve y gestiona. |
| `tiempo` | RegistroTiempo | Cronómetro (uno por persona), carga semanal y reporte. |
| `finanzas` | Cotizacion, Factura (+ líneas), Pago, Gasto | Solo Finanzas y dirección. ITBIS 18 % por línea. |
| `automatizaciones` | Regla, Ejecucion | `motor.disparar(evento, objeto)`; acciones AVISAR, CREAR_TAREA y WEBHOOK. |

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

### Órdenes de trabajo

`SOLICITADA → APROBADA → EN_PRODUCCION → CONTROL_CALIDAD → LISTA → ENTREGADA`, más `EN_PAUSA` y `CANCELADA`. Las transiciones válidas están en `OrdenTrabajo.TRANSICIONES` y todo cambio pasa por `operaciones/servicios.cambiar_estado`, que deja historial, envía avisos y dispara las automatizaciones. Al aprobar se crea la tarea de producción. Después, `sincronizar_desde_tareas` mueve la orden según sus tareas: empezar la lleva a producción, entregar a control de calidad y validar todas a lista. Desde `desempeno.servicios.tras_cambio` se llama en cada cambio de una tarea.

### Permisos de operación

- Ven todo: administradores y Finanzas, que es el departamento Administración o el grupo «Finanzas».
- Quien supervisa gestiona los departamentos de los puestos que dependen del suyo (`departamentos_a_cargo`).
- Cada persona ve el tablero de su departamento, lo que pidió o trabaja y lo que pidió su gente.
- Los montos se ocultan en el serializador a quien no corresponde (`ve_montos`).

## Tareas programadas

`python manage.py tareas_diarias` (una vez al día): crea las recurrentes de la semana, avisa lo que vence mañana y ejecuta las automatizaciones de órdenes, tareas y facturas vencidas.

## n8n e IA

- **De la plataforma a n8n:** las automatizaciones con acción WEBHOOK envían `{evento, regla, fecha, datos}` en JSON. Con `AUTOMATIZACIONES_SECRETO` llevan la firma `X-Adzone-Firma` (HMAC-SHA256 del cuerpo).
- **De n8n a la plataforma (siguiente paso):** conviene un usuario técnico con token y permisos mínimos, en lugar de la cuenta de una persona.
