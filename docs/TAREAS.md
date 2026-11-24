# Módulo de tareas · guía de funcionamiento (Requerimiento #8)

Resumen de cómo funciona hoy el módulo (todo se mejoró sobre lo existente; no se reemplazó nada).

## Quién ve qué
- Cada persona ve **sus tareas** y aquellas en las que participa. Su supervisor ve las de su equipo; Dirección ve todas.
- Una tarea pedida a otra área (aporte entre áreas) la ve también quien la pidió; las áreas de servicio (Tecnología) reciben tareas de otras áreas.
- El **historial**, los **comentarios** y la **evidencia** de una tarea solo los ve quien ve la tarea; el resto recibe «no encontrada». Se valida siempre en el servidor.

## Estados
Por empezar → En progreso → (Bloqueada) → Por validar → Validada. «Devuelta» es En progreso con rondas de revisión; «Vencida» se calcula por la fecha límite; también existe Cancelada. Una tarea validada no se edita (hay que reabrirla). Quien se asigna una tarea propia puede autovalidarla y queda registrado como «Autovalidada».

## Asignación
Responsable, quienes colaboran, cliente (con catálogo), proyecto, fechas, horas estimadas, pasos, KPI al que suma y **prioridad** (Urgente ⚡ peso 4, Alta 3, Media 2, Baja 1 en el puntaje). Referencias y evidencia admiten imágenes, PDF, documentos de oficina, ZIP revisados con antivirus y videos (ver `DESPLIEGUE.md`).

## Comentarios (etapa 2)
`GET/POST /api/desempeno/tareas/<id>/comentarios/` · hasta 2 000 caracteres · responder a otro comentario de la misma tarea · menciones con `@usuario` solo a quien ve la tarea · no se editan ni se borran · quedan en el historial como «Comentó» · un solo aviso sin leer por persona y tarea (el más reciente) para no saturar la campanita.

## Trazabilidad (etapa 3)
- Cambiar **fecha de entrega, fecha de inicio, prioridad o responsable** exige un `motivo` (mínimo 5 letras) en el `PATCH`; sin él responde 400.
- El historial guarda «campo: antes → después» y el motivo; se muestra en el detalle de la tarea y en «Historial de tareas».
- El motivo se incluye en el aviso a quienes participan.

## Para otras personas que continúen
- Backend: `apps/desempeno/` (`models.py`, `views.py`, `servicios.py` con `comentar_tarea`, `detalle_de_cambios`, `CAMPOS_CON_MOTIVO`; permisos en `permisos.py`).
- Frontend: `frontend/src/features/tareas/` (`componentes.jsx` con `ConversacionTarea` e `Historial`, `FormTarea.jsx`) y `components/Comentarios.jsx` (compartido con órdenes y proyectos).
- Pruebas: `python manage.py test apps.desempeno` (incluye `tests_comentarios_tarea` y `tests_trazabilidad`).
- Migraciones del requerimiento: `0025`–`0029` (todas aditivas; no tocan datos existentes).
