# Cambios

## 4.0 · 24/10/2026 · Adzone Team y KPIs, una sola plataforma

### Lo que llega de Adzone Team
- **Tareas compartidas:** una tarea puede tener responsable y compañeros. Todos la ven en «Mis tareas», la trabajan y la entregan; al validarla, cuenta para el puntaje y los KPIs de cada uno.
- **Pasos:** checklist dentro de la tarea. Quien la trabaja marca cada paso (queda quién y cuándo) y el supervisor ve el avance «2/4». Marcar el primero la pasa a «En curso».
- **Cliente** en cada tarea.
- **Mi equipo · Ahora:** una tarjeta por persona con lo que está haciendo: tarea vencida, trabajando, por empezar, esperando validación, sin tareas o **pidiendo más trabajo**. Desde ahí se recuerda o se asigna con un toque. Se actualiza solo cada minuto.
- **Recordar** llega como una franja fija arriba de la pantalla, con sonido y vibración en el celular, hasta que la persona toca «Entendido» o «Ver tarea». Los avisos se consultan cada 30 segundos.
- **Los 7 departamentos oficiales** (Gerencia, Marketing, Audiovisual, Adzone TV, Impresión, Administración, Tecnología) con sus colores. El comando `departamentos_oficiales` ubica cada puesto del organigrama.
- **Supervisión en cascada:** un gerente ve y gestiona a todo lo que cuelga de su puesto, no solo a quien le reporta directo.

### Un repositorio ordenado para GitHub
- Backend en `backend/config` + `backend/apps/{core,organizacion,kpis,desempeno}`. Las tablas no cambian de nombre.
- Frontend por áreas: `src/app`, `src/components`, `src/features/<área>`, `src/lib`, con imports `@/`.
- Revisión automática en GitHub (pruebas, migraciones, lint y compilación), guía `CONTRIBUTING.md`, `docs/ARQUITECTURA.md`.
- Los datos reales (base de datos, fotos, `.env`, lista del equipo) quedan fuera de GitHub. El equipo se carga con `cargar_equipo` desde un archivo privado.
- Nombre: **Adzone Team** en la app, el ícono instalado y el administrador.

### Pruebas
- Backend: 47 pruebas (10 nuevas: compañeros, pasos, cliente, carga del equipo, departamentos oficiales).
- Navegador: 39 comprobaciones de punta a punta en PC y celular.


## 24/10/2026 · Revisión completa: PC primero, celular también

### Diseño y navegación
- **Marca ADZONE** en toda la app:
  - Colores: azul #224b9a, azul noche #16336b y amarillo #fbc236.
  - Letras: Outfit en títulos y Inter en el texto. Las fuentes van dentro de la app, así que funcionan sin internet y sin depender de Google.
- **En la PC:** menú lateral fijo por secciones (Mi trabajo, Mi equipo, Resultados, Administración), tablas y vistas de dos columnas.
- **En el celular:** barra inferior con lo del día a día y «Más» para el resto. Las ventanas salen desde abajo y los botones tienen un tamaño cómodo para el dedo.
- **Inicio** ya no es una página de presentación: es un tablero según el rol.
  - El colaborador ve su mes, sus próximas tareas y los KPIs de su puesto.
  - El supervisor ve además a su equipo: lo que hay por validar, quién tiene tareas vencidas y los mejores puntajes.
  - El administrador ve además a toda la empresa, por departamento.
- **Tira del mes:** el avance es una franja con un segmento por tarea (validada, en revisión, vencida o pendiente).
- **Campanita de avisos** para tareas asignadas, entregas por validar, validadas, devueltas, reabiertas, por vencer y Empleado del Mes. También hay un número junto a «Por validar».
- Todas las pantallas se rehicieron con las mismas piezas: botones, ventanas, avisos y confirmaciones propias en vez de las del navegador.

### Funciones nuevas
- **Varias fotos o PDF por entrega**, hasta 6. Se pueden tomar con la cámara o elegir de la galería, y se achican en el celular antes de subir (máx. 1600 px).
- **Historial de cada tarea:** quién la creó, la inició, la entregó, la devolvió o la validó, y cuándo.
- **Rondas de revisión:** se cuenta cuántas veces se devolvió cada entrega. Un KPI automático «más bajo es mejor» (como «menos de 3 rondas de revisión») se calcula solo con esas rondas.
- **Tareas recurrentes** (semanales o mensuales): se crean una semana antes de su entrega. Por ejemplo, la programación semanal de Adzone TV.
- **Reabrir** una tarea validada por error (con motivo) y **cancelar** tareas. Una tarea validada ya no se edita ni se borra.
- **KPIs del mes en una planilla:** todo el equipo a la vez, agrupado por puesto, con guardado en lote.
- **Organigrama visual:** quién reporta a quién y quién ocupa cada puesto.
- **Reglas del puntaje configurables:**
  - el peso de las tareas frente a los KPIs (60/40 por defecto);
  - la nota de una entrega tarde;
  - las tareas mínimas para ser candidato;
  - los tramos del bono sugerido.
- **Ranking descargable en Excel (CSV)** con el bono sugerido. Solo hay candidato y bono con el mínimo de tareas validadas.
- **Personas:** tabla con buscador, rol explicado, contraseña inicial generada y avisos de quién no tiene puesto.
- **Entrar con usuario o correo.** Cada persona puede cambiar su contraseña en «Mi cuenta».

### Seguridad
- Antes, cualquier usuario con sesión podía crear, editar o borrar departamentos, puestos y asignaciones de KPI. Ahora solo el administrador.
- **Nadie valida, devuelve ni reabre su propia tarea**, ni siquiera un administrador.
- El formulario de edición ya no permite marcar una tarea como «Validada» saltándose la entrega.
- Las fotos de evidencia ya no son públicas (`/media/`): se descargan por la API, que revisa que sea el colaborador o quien lo supervisa. El archivo se guarda con un nombre aleatorio. Solo se aceptan fotos y PDF, de hasta 10 MB.
- **Contraseñas:** se validan al crearlas (mínimo 8 caracteres, que no sean comunes). El inicio de sesión tiene un límite de 10 intentos por minuto.
- No se puede quedar la empresa sin administradores: nadie se quita a sí mismo el rol ni se desactiva.
- **Organigrama sin ciclos:** un puesto no puede reportar a alguien que le reporta.
- **Configuración por entorno** (`.env`): la clave secreta ya no está en el código, el modo de depuración se apaga en el servidor y en producción hay cookies seguras, HTTPS y HSTS.
- Zona horaria de República Dominicana: «hoy» y «a tiempo» se cuentan en hora local.

### Para el servidor
- Django sirve la app web compilada (WhiteNoise) en el mismo dominio que la API.
- Funciona con MariaDB de Plesk (PyMySQL) o PostgreSQL. Incluye el archivo de inicio para Plesk (`passenger_wsgi.py`) y la tarea diaria `python manage.py tareas_diarias`.
- Guía paso a paso en `docs/DESPLIEGUE.md`.

### Pruebas
- **Backend:** 37 pruebas automáticas, 13 originales y 24 nuevas.
- **Navegador:** se recorrieron con datos de prueba los flujos de colaborador, supervisor y administrador, en PC (1440 px) y en celular (390 px): entregar con foto, validar, devolver, programar recurrentes, anotar KPIs, declarar Empleado del Mes y crear personas.

### Migración de datos
- La migración `desempeno/0003` pasa la foto única de las entregas anteriores a la nueva lista de evidencias. No se pierde nada.
