# Cambios

## 12.22 · 21/11/2026 · Nuevo permiso «Personas» (directorio, mínimo privilegio)

- Nuevo permiso independiente **Personas** en Accesos y permisos → Sobre toda la empresa: «Ver a todas las personas, crear usuarios nuevos y desactivar cuentas, sin poder modificar correos ni cambiar contraseñas». El permiso **Personas y accesos** no cambia.
- Con «Personas» (y sin «Personas y accesos»): ve el directorio completo, **crea cuentas nuevas** (entran como Colaborador, con su contraseña inicial) y **desactiva o reactiva** cuentas. En la API se bloquea (403) cambiar correos, contraseñas, usuario de entrada, perfiles de acceso, puesto y puestos adicionales, y borrar cuentas. En la interfaz la ficha de una persona existente solo muestra sus datos y el interruptor «Cuenta activa»; no aparecen correo, contraseña ni perfiles, y el menú no muestra «Accesos y permisos».
- Protección propia: no puede desactivar su cuenta ni cambiar sus propios perfiles. Sigue valiendo la regla de siempre: no toca cuentas con permisos que él no tiene.
- Quien tiene los dos permisos (y Dirección) conserva todo. Dirección recibe el permiso nuevo en el perfil Administrador. Como los demás permisos sensibles, exige verificación en dos pasos.
- El perfil que usa este permiso lo crea o ajusta la Dirección en Accesos y permisos.


## 12.21 · 21/11/2026 · Ponches de almuerzo y pausas con alerta, horarios por departamento y organigrama con zoom

**Control de asistencia**
- **Seis ponches**: entrada, salida, inicio y fin de almuerzo, inicio y fin de pausa. El almuerzo se marca aparte (botón «Iniciar almuerzo»); las pausas piden su motivo. Cada ponche guarda fecha, hora al segundo y quién lo hizo.
- **Contador de la pausa** en el botón de la jornada: «Almuerzo 0:23:10» / «Pausa 0:12:03». Se pone rojo y parpadea al pasar el límite, y se detiene al marcar el regreso.
- **Alerta automática**: cuando una pausa llega a su límite sin registrar el regreso, se avisa a la persona y a su supervisor, con el nombre y el tiempo transcurrido («Ana lleva 1:02:10 en pausa»). Se avisa una sola vez por pausa. No necesita tarea programada: se revisa cada vez que una pantalla abierta consulta sus avisos.
- **Límites configurables por horario**: «Pausa máxima» (60 min por defecto) y la duración del almuerzo, que son límites distintos (el almuerzo no usa el de las pausas).
- **Horarios por departamento y turnos**: cada horario puede asociarse a departamentos (quien no tiene horario propio usa el de su departamento; el horario personal siempre manda; si no hay ninguno, el general). Se puede marcar un horario como «turno especial» y fijar la hora del almuerzo.
- **Reportes**: Hoy muestra quién está en almuerzo o pausa y desde cuándo; el día a día y el reporte del mes (y su Excel) separan almuerzo y pausas y cuentan las que pasaron el límite. Corregir marcajes admite «Inicio de almuerzo».
- Lo marcado antes de esta versión no genera alertas; las pausas con motivo «Almuerzo» pasan a contarse como almuerzo.
- **No incluido**: los turnos del Call Center. Los agentes siguen con el horario general hasta que se definan sus turnos y se les asigne (Asistencia → Horarios).

**Organigrama**
- El organigrama es el de siempre, sin tarjetas ni paneles nuevos: al elegir un departamento (en la barra de colores o tocando su etiqueta en cualquier tarjeta) **el mismo gráfico se acerca con zoom** hasta esa parte y la centra; el resto se atenúa. «Ver todo el organigrama» regresa a la vista completa.

## 12.20 · 20/11/2026 · Ya no hay que recargar a mano después de una actualización

- **Causa** de «tengo que dar a recargar para entrar a /puestos»: cada versión nueva cambia los nombres de los archivos de la app. Una pestaña que ya estaba abierta intentaba cargar una pantalla que aún no había visitado (por ejemplo Puestos) con el nombre **viejo**, que ya no existe: el servidor respondía la página principal en vez del archivo y la pantalla se quedaba cargando hasta que recargabas.
- **Corrección**: si un archivo de pantalla no se puede cargar, la app **se recarga sola una vez** (trae la versión nueva y vuelve a la misma pantalla). Si aun así falla, en vez de dejar la pantalla en blanco muestra «Hay una versión nueva de Adzone Team — Recarga la página» y **el menú sigue funcionando** (puedes ir a otra pantalla). No entra en bucle: máximo una recarga automática cada 20 s.
- También se atrapan los errores al dibujar una pantalla: aparece «No se pudo abrir esta pantalla» con «Reintentar» y «Recargar la página», sin tumbar toda la aplicación.
- Solo frontend (`lib/perezosa.js`, `components/LimiteDeErrores.jsx`).
- Despliegue (servidor): las versiones nuevas conservan los archivos de las anteriores (`assets/`), para que las pestañas abiertas sigan funcionando hasta que se recarguen.

## 12.19 · 20/11/2026 · Organigrama sin «divisiones» y buscador con autocompletado en Mi equipo

- **Organigrama: un departamento se ve completo**. Causa: en el organigrama real, Marketing cuelga de una cadena larga (Presidente → Vicepresidente → CEO → Gerente de Marketing → Encargado de Creatividad → …) y el gráfico solo abría en fila los dos primeros niveles, así que todas las gerencias quedaban anidadas hacia abajo y Marketing aparecía partido. Ahora **la cadena de un solo puesto se dibuja en vertical y el abanico de áreas, en fila** (como un organigrama normal).
- Al elegir un departamento: aparece un **resumen con todas sus personas y puestos** (5 personas · 6 puestos · 3 vacantes…), cada uno con un clic para ir a su tarjeta; el gráfico **encuadra todas las tarjetas del departamento** (no solo la primera) y abre las ramas que lleven hasta él.
- **Mi equipo: buscador con autocompletado**, siempre arriba (en Ahora, Tareas y Recurrentes). Al escribir sugiere **personas** del equipo (nombre, puesto, departamento) y **tareas de cualquier mes** (con el responsable, el estado y la fecha); lo escrito se resalta aunque no pongas tildes. Elegir una persona muestra sus tareas; elegir una tarea la abre; **Enter** busca el texto en todas las tareas (queda una etiqueta «Búsqueda: …» que se quita con un clic). Funciona con teclado (flechas, Enter, Esc) y lectores de pantalla.
- Solo frontend, sin migraciones.

## 12.18 · 20/11/2026 · Rendimiento: pantallas más rápidas

Medido en producción con 38 personas (tiempos de servidor, ya "caliente"; la red no era el problema: ~70 ms y 0,25 s por solicitud):

- **KPIs asignados**: 3,6 s, **1.985 consultas** y 3 MB → una consulta por KPI de cada puesto, repitiendo la ficha completa del puesto (personas, subordinados) en cada fila. Ahora el puesto va resumido (la pantalla solo usa la plantilla) y lo demás se precarga. Afecta *Departamentos y puestos → puesto*.
- **Personas / usuarios** (lo usan Personas, Accesos y otras pantallas): 303 consultas, 0,7 s → se precargan puestos, personas por puesto y puestos adicionales. **Accesos y permisos**: 122 consultas → los permisos de cada persona se calculan en memoria con lo ya cargado.
- **Asistencia de hoy**: 239 consultas, 0,45 s → la jornada de todo el equipo se calcula en lote (6 consultas en total en vez de 6 por persona).
- **Compresión de la API**: el JSON grande (listas de personas, puestos, plantillas: 90–220 KB) se comprime (gzip), solo en `/api/` y nunca archivos.
- **Conexión a la base reutilizada** (`CONN_MAX_AGE=60`, con verificación): se deja de abrir una conexión nueva por cada petición.
- **Archivos de la app con huella** (`/assets/…`) se guardan un año en el navegador (antes, 1 hora): las visitas siguientes no vuelven a descargar la app.
- Prueba nueva (`apps/core/tests_rendimiento.py`): ninguna de esas pantallas puede hacer consultas en proporción a la cantidad de personas (con el código anterior fallaba: 23 → 87 consultas al pasar de 4 a 12 personas).
- Servidor (fuera del código): Gunicorn con hilos y reciclaje de procesos (`GUNICORN_CMD_ARGS`) y registro del tiempo de cada petición, para poder medir.

## 12.17 · 20/11/2026 · KPIs del mes rediseñado

- **Una tarjeta por persona** (agrupadas por puesto) con sus indicadores en filas: nombre del KPI, peso y unidad a la izquierda; *Logrado* y *Meta* con la unidad dentro del campo (%); y el **cumplimiento** con su barra de color a la derecha. Antes era una tabla enorme con «Logrado/Meta» repetido en cada celda y desplazamiento horizontal.
- **Avance del mes** arriba: «5 de 32 resultados anotados · 6 personas» con su barra, y por puesto «6 de 20 anotados» y por persona «4/5».
- **Búsqueda por persona**, filtro **Solo pendientes** (lo que falta por anotar) y atajos para saltar a cada puesto.
- Lo editado se marca en ámbar con «Sin guardar»; la barra inferior de guardar es más compacta en el celular. Tu propia tarjeta aparece desactivada («No puedes anotar tus propios resultados»).
- En el celular los campos se apilan con sus rótulos; en pantallas muy anchas, dos tarjetas por fila. Solo frontend, sin migraciones.

## 12.16 · 20/11/2026 · Al recargar o volver a entrar, te quedas donde estabas

- **Volver a entrar te devuelve a la misma pantalla**: si la sesión vence (o abres un enlace sin sesión), después de entrar vas a esa pantalla (con sus filtros en la dirección), no siempre al Inicio. Había un cruce que mandaba a Inicio antes de que se aplicara el regreso.
- **Recargar conserva el punto de la página**: se recuerda hasta dónde habías bajado en cada pantalla y, al recargar o volver atrás, vuelve ahí (espera a que la pantalla termine de cargar sus datos). Al abrir otra pantalla desde el menú o un enlace, empieza arriba como siempre.
- **El chat se recuerda**: si recargas con el chat abierto, se vuelve a abrir en la misma conversación; si estaba cerrado, sigue cerrado.
- Solo frontend (`lib/posicion.js`, `App.jsx`, `ChatFlotante.jsx`): sin migraciones.

## 12.15.1 · 20/11/2026 · «Comenzar» al entrar a la plataforma

- La pantalla que aparece al entrar en el día ahora tiene **un solo botón: «Comenzar»**. Al tocarlo se inicia la jornada (se marca la entrada y arranca el contador de tiempo) y la pantalla desaparece; el aviso dice «Jornada iniciada a las 8:40:12 a. m.». Se quitó «Más tarde».
- Si no se pudo iniciar (por ejemplo, la ubicación está bloqueada), se muestra el motivo y entonces sí aparece «Cerrar por ahora» para no dejar a la persona atrapada.

## 12.15 · 20/11/2026 · Sonido en los mensajes del chat

- **Cada mensaje nuevo suena**: un «pop» corto y suave (distinto al de las notificaciones), con una vibración leve en el celular. Suena en tres situaciones: con el **chat cerrado** (se revisa cada 15 s y el botón sube su contador), con la **conversación abierta** (cada 3 s) y con la **pestaña oculta o en otra ventana** (cada 30 s; además sale un aviso del sistema con el nombre y el texto, si diste permiso de notificaciones).
- **No molesta de más**: tus propios mensajes no suenan, ni los que ya estás viendo en otra conversación del mismo chat; un solo sonido por tanda de mensajes, aunque lleguen varios juntos.
- Solo frontend (`lib/sonido.js`, `features/chat/useChat.js`): sin migraciones.

## 12.14.1 · 20/11/2026 · Organigrama: te lleva solo al departamento y la barra queda fija

- Al elegir un departamento en la leyenda, el organigrama **se desplaza solo hasta él** (dentro del gráfico y en la página), centrándolo en pantalla, en lugar de dejarte buscar con el scroll mientras el resto se atenúa. Lo mismo al buscar: te lleva a la primera coincidencia (después de abrir las ramas que la contienen). Respeta «reducir movimiento» del sistema. Funciona también en la vista de lista.
- **La barra de búsqueda y departamentos queda fija arriba** mientras te desplazas, para cambiar de departamento sin tener que volver a subir. En el celular se fija la fila de departamentos (que se desliza de lado) y el buscador queda en su lugar.

## 12.14 · 20/11/2026 · Organigrama empresarial

- **Gráfico jerárquico de verdad**: la dirección arriba, sus áreas en fila unidas por conectores y los puestos de abajo en ramas verticales (para que no se haga eterno de ancho). Cada tarjeta lleva el departamento (con su color), el puesto, las personas con sus iniciales (o «Vacante»), y cuántos puestos y personas tiene a cargo, con botón para contraer o expandir esa rama.
- **Color por departamento** con una paleta sobria y estable, y una **leyenda** con el total de personas de cada uno: al elegir un departamento, el resto se atenúa.
- **Cifras arriba**: personas activas, puestos, departamentos y vacantes.
- **Búsqueda** por persona, puesto o departamento: abre las ramas con coincidencias, resalta las tarjetas y atenúa el resto (con el conteo de coincidencias).
- **Zoom** (−, +, porcentaje) y *Ajustar al ancho*; al abrir, el gráfico se ajusta solo para verse completo (nunca por debajo del 60 %, para que se lea). *Expandir todo* / *Contraer*.
- **Vista de lista** (la predeterminada en el celular y útil para lectores de pantalla), con las mismas búsquedas y colores.
- **Imprimir**: el botón prepara la hoja en horizontal, sin menús ni barras.
- Quien administra puestos sigue pudiendo abrir cada puesto desde su título. Sin cambios en el servidor.

## 12.13 · 20/11/2026 · Alertas a la izquierda y pantalla de Personas reorganizada

- **Alertas de tareas rediseñadas**: ya no ocupan el centro ni oscurecen la pantalla. Salen como **tarjetas abajo a la izquierda** (junto al contenido, sin tapar el menú), con barra de color e ícono según el tipo, quién la envió y cuándo, botón principal (*Ver tarea*, *Corregir ahora*…), *Entendido* y una X. Se apilan hasta tres y un contador «+N alertas más» indica las demás; en el celular se muestra solo la más reciente. Siguen sonando y los recordatorios, devoluciones y vencimientos insisten hasta atenderse. Se puede seguir trabajando mientras tanto.
- **Personas, reorganizada**:
  - **Filtros con conteo** en una sola fila: Activas, *Aún no entran*, Sin puesto, Desactivadas y Todas (y la búsqueda con botón para borrar y el filtro por departamento).
  - **Agrupada por departamento**, con el total de cada grupo y «Mostrando X de Y personas».
  - **Perfil** como etiqueta (Dirección destacada, «+n» si tiene varios), **último acceso** en lenguaje natural con un punto de color («hace 2 h»; «Nunca ha entrado» en ámbar) y **«Tú»** marcado.
  - En el celular, **tarjetas** en lugar de una tabla con columnas ocultas. La columna de salario solo aparece a quien puede verla.
  - Estado vacío con botón para volver a ver a todas las personas.
- Frontend: `PersonasLista.jsx` (lista, filtros y buscador) separado de `Personas.jsx` (formulario y datos).

## 12.12 · 20/11/2026 · Avisos del sistema con sonido (Windows, Linux, Mac y celular)

- **Notificaciones del sistema para todos**: al entrar, si la persona aún no las activó, sale una ventana *Activa las notificaciones* con un botón grande (el aviso chico que se podía cerrar ya no es la única vía). Si ya dio permiso en este navegador, este dispositivo se registra solo. Si las bloqueó, una ventana explica cómo permitirlas (candado → Notificaciones → Permitir). «Ahora no» vuelve a preguntar al día siguiente.
- **Salen aunque la app esté minimizada o cerrada**: cada aviso de la campanita llega como notificación del sistema. Las alertas importantes (recordatorio, devuelta, nueva tarea, por vencer, bloqueada, reabierta, modificada) se **quedan en pantalla hasta atenderlas**, vibran en el celular y cada aviso es único (no se pisan ni se repiten).
- **Sonido**: la notificación del sistema suena con el sonido de Windows/Linux/celular. Además, si hay una pestaña de Adzone abierta (aunque esté oculta o en otra ventana), la propia app reproduce su sonido: alerta fuerte para las importantes y dos tonos suaves para las demás.
- **Sin duplicados**: con la app abierta y a la vista no sale la notificación del sistema (ya se ve la alerta y suena).
- **Respaldo sin push**: si un dispositivo dio permiso pero no está registrado en el servidor, con la pestaña oculta la app muestra el aviso del sistema por sí sola (consultando cada 30 s).
- El aviso push ahora lleva `tipo` e `id`. Service worker `adzone-team-v7`. Prueba nueva en `tests_seguridad.py`.

## 12.11 · 20/11/2026 · Marcar entrada al iniciar sesión, sonido en notificaciones y recordatorios hasta 15 veces

- **Pantalla «Marcar entrada» al iniciar sesión**: si es día de trabajo, la marca es obligatoria para la persona y todavía no marcó, aparece a pantalla completa con la hora oficial del servidor al segundo, el saludo y un botón grande *Marcar entrada* (con su ubicación si el sitio lo pide). «Más tarde» la oculta 30 minutos. También se la muestra a quien aún no ha usado el control de horario, para que empiece. No aparece si ya marcó, en feriados o fines de semana, con permiso aprobado, ni a quien no tiene marca obligatoria.
- **Sonido en las notificaciones**: cada aviso nuevo en la campanita suena con dos tonos suaves (y una vibración corta en el celular); las alertas de tareas siguen con su sonido fuerte. El audio se desbloquea con el primer toque en la pantalla (regla de los navegadores).
- **Recordatorios hasta 15 veces por tarea**: se puede recordar la misma tarea hasta 15 veces (configurable en *Reglas del puntaje → Máximo de recordatorios por tarea*; 0 = sin límite). El mensaje dice «Van 3 de 15». Al llegar al máximo avisa claramente. La espera entre recordatorios sigue en 2 minutos (configurable).
- El estado de jornada ahora incluye `marca_obligatoria`. Migración `0021`. Pruebas nuevas en `tests_mejoras.py` y `tests_precision.py`.

## 12.10 · 20/11/2026 · Tareas propias con revisor (Helen u Osiris)

- **«Nueva tarea para mí»** en *Mis tareas*, para quien puede asignarse tareas (Dirección y quienes tienen ese permiso: Helen, Osiris, Enmanuel, José…). Pide título, fecha límite, prioridad, horas (opcional), referencias (opcional) y **quién la valida**.
- **Revisor de la tarea propia**: se elige entre los revisores configurados (inicialmente **Helen Castillo y Osiris Cruz**; nunca uno mismo). Cuando la persona entrega, el aviso «Por validar» le llega **solo a ese revisor**, y solo él o el otro revisor configurado pueden validarla, devolverla o reabrirla (otras personas de Dirección, como Rebeca o José, no). Helen se la asigna a Osiris y viceversa.
- **Configurable**: *Reglas del puntaje → Quién revisa las tareas propias* (casillas con las personas de Dirección). Sin marcar a nadie, puede revisar cualquiera de Dirección.
- Si otra persona le asigna la tarea, todo sigue igual: la valida su supervisor.
- El detalle de la tarea muestra «La valida». «Por validar» y su contador solo muestran lo que cada quien puede revisar.
- `Tarea.revisor`, `ConfiguracionDesempeno.revisores_propias` (migración `0020`, que deja a Helen y Osiris como revisores si existen), `GET /mis-revisores/`, `puede_autoasignar` en la sesión. 9 pruebas nuevas (`tests_propias.py`).

## 12.9 · 20/11/2026 · Referencias en las tareas (bocetos e imágenes del supervisor)

- **Al asignar**: en «Nueva tarea» hay un botón *Adjuntar boceto o imagen de referencia* (imágenes o PDF, hasta 6 por vez, 10 MB cada uno; las fotos se achican antes de subir). La persona recibe la alerta «Nueva tarea» con la nota «📎 Adjuntó N archivos de referencia».
- **Al devolver**: en *Por validar* hay *Adjuntar boceto o imagen para la corrección*; se envían junto con el comentario al pulsar *Devolver*, y la alerta «Tu entrega fue devuelta» lo dice.
- **En cualquier momento**: desde el detalle de la tarea, quien la asigna puede agregar más referencias mientras siga abierta.
- **Dónde se ven**: en el detalle de la tarea, sección *Referencias*, ordenadas: *Al asignar la tarea* y *Para corregir · devolución N*. Las imágenes abren en grande, los PDF se descargan, y en la lista se ve «📎 N referencias». Quien las subió, o quien asigna la tarea, puede quitarlas.
- **Privacidad**: solo quien trabaja la tarea, su equipo y quien la supervisa ven los archivos (se entregan por la API con permisos). Si se adjunta justo después de asignar, se suma al mismo aviso: no salen dos alertas.
- Nuevo modelo `ReferenciaArchivo` (migración `0019`), `POST /tareas/<id>/referencias/`, `GET|DELETE /referencias/<id>/archivo/`; `rechazar` acepta `archivos`. 7 pruebas nuevas (`tests_referencias.py`).

## 12.8 · 20/11/2026 · Alcance configurable: toda la empresa y tareas propias

Dos permisos nuevos, configurables desde *Accesos y permisos* (por perfil o como excepción de una persona):

- **Supervisar a toda la empresa** (`equipo.todos`): el «equipo» de quien lo tiene pasa a ser todo el personal activo, en todos los departamentos y sin depender del organigrama. Los permisos de equipo que tenga (asignar y validar tareas, ver ficha y asistencia, evaluar, expediente…) se ejercen sobre todos. También recibe los avisos de entregas y tardanzas de todos. Dirección queda fuera de su alcance, y nadie se valida a sí mismo.
- **Asignarse tareas a sí mismo** (`tareas.propias`): crear y programar tareas para uno mismo, sin necesidad de supervisar a nadie. La tarea la valida otra persona, nunca quien la hace. Aparece la opción «Asignar tareas» para quien no supervisa.
- La búsqueda de tareas en órdenes también respeta el nuevo alcance. 6 pruebas nuevas (`apps/desempeno/tests_alcance.py`).

**Tiempo marcado al segundo** (de ahí sale el pago):
- Antes cada tramo (entrada→pausa, regreso→salida) se redondeaba a minutos hacia abajo *antes* de sumar, y se podían perder hasta 59 s por tramo; la tardanza, la salida temprana y el tiempo extra también se truncaban. Ahora todo se calcula en **segundos exactos** y se convierte una sola vez, sobre el total. La jornada devuelve `trabajados_seg`, `pausa_seg`, `tardanza_seg`, `salida_temprana_seg`, `extra_seg` (y el resumen, `segundos_*`); los minutos siguen ahí, derivados del total.
- La tolerancia es estricta: pasada la tolerancia, la tardanza cuenta completa desde la hora de entrada, al segundo.
- **Hora oficial**: las pantallas se sincronizan con la hora del servidor (la que se estampa al marcar), no con el reloj de la computadora, y todas las horas se muestran en hora de República Dominicana aunque el equipo esté en otra zona. El panel de jornada muestra la «Hora oficial» al segundo; al marcar, el aviso dice la hora exacta guardada.
- Asistencia (tablas y tarjetas) muestra tiempos en `H:MM:SS` y las horas de marcaje con segundos. El CSV del reporte trae tiempo trabajado exacto (`H:MM:SS`, segundos y horas con 4 decimales) en vez de horas redondeadas a una décima.
- 6 pruebas nuevas (`apps/asistencia/tests_precision.py`).

**Recordatorios**: la espera para volver a enviar el recordatorio de una misma tarea bajó de **1 hora a 2 minutos** (solo evita enviarlo dos veces sin querer) y se configura en *Reglas del puntaje → Espera entre recordatorios* (0 = sin espera). Si aún no se puede, el mensaje dice cuánto falta. Y el recordatorio ahora sale en **rojo**.

**Alertas de tareas emergentes**: las alertas de tareas (recordatorio del supervisor, tarea nueva, devuelta, reabierta, modificada, bloqueada y por vencer) salen en una ventana grande a pantalla completa, con fondo desenfocado, ícono y color según el tipo, quién la envió y cuándo, botón principal grande (Ver tarea / Corregir ahora) y «Entendido». Con varias, se atienden una por una. Recordatorios, devoluciones y vencimientos insisten con sonido cada 30 s y el título de la pestaña parpadea hasta atenderlas.

## 12.7 · 20/11/2026 · Chats privados

- **Chat personal con cualquier compañero, ventana tipo Instagram**: en PC, tus chats a la izquierda (la sala de toda la empresa fijada arriba, con vista previa, hora y mensajes sin leer) y la conversación a la derecha: cambias de chat con un clic, sin salir de la ventana. El buscador de arriba encuentra compañeros por nombre, usuario, cargo o departamento y abre su chat al instante. Arriba de cada chat privado se ve el cargo y el departamento de la otra persona. En el celular, al tocar el icono se abre directo la conversación con una tira de tus chats arriba (Todos, y cada compañero con su contador) para cambiar de chat con un toque; «Buscar» o la flecha abren la lista completa con el buscador de compañeros.
- **Privacidad**: un chat privado solo lo ven sus dos participantes. Ni Dirección ni nadie más puede abrirlo (para ellos no existe); Dirección sigue moderando únicamente la sala de la empresa.
- El contador del botón suma los no leídos de todas las conversaciones. Los mensajes que ya había en la sala global se conservan (migraciones 0002–0004 de `apps/chat`).
- API: `/api/chat/conversaciones/`, `/conversaciones/<id>/mensajes/`, `/conversaciones/<id>/leido/`, `/personas/`. 12 pruebas.

## 12.6 · 20/11/2026 · Chat global

- **Chat de toda la plataforma**: botón flotante en la esquina inferior derecha (en el celular, sobre la barra de abajo) que abre una sala común. En PC es una ventana de 380 px; en el celular, pantalla completa.
- Contador de **no leídos** en el botón (consulta liviana cada 15 s con el chat cerrado; cada 3 s y solo con la pestaña visible cuando está abierto). Enlaces clicables, mensajes agrupados por persona y día, «Ver mensajes anteriores» y aviso de «Mensajes nuevos» si estás leyendo más arriba.
- Cada persona borra sus mensajes; Dirección puede moderar cualquiera (queda «Mensaje eliminado», sin perder el registro). Máximo 2000 caracteres y 20 mensajes por minuto por persona.
- **Contraseña base**: quien entra con la contraseña base («usuarios») ve primero una franja amarilla «Cambia tu contraseña base» con el formulario para cambiarla ahí mismo; desaparece al cambiarla. La contraseña base no se acepta como contraseña nueva. Se detecta al iniciar sesión (no se guarda nada extra).
- Nueva app `apps/chat` (modelos `Mensaje` y `Lectura`, API en `/api/chat/`, 7 pruebas) y módulo `features/chat` en el frontend.

## 12.5.1 · 19/11/2026 · Contador de jornada en vivo

- **Contador con segundos**: el tiempo trabajado del botón de jornada (arriba y en su panel) corre en vivo, `H:MM:SS`, mientras la persona está trabajando. En pausa o fuera de jornada se sigue mostrando en minutos. El servidor manda ahora `segundos_en_curso` para que el contador no pierda segundos entre consultas.
- **Simulación de un día de empresa** (`apps/desempeno/tests_simulacion.py`): gerencia, supervisor y empleados recorren por la API real entradas, pausas, tareas, bloqueos, validaciones, actividades, colaboración y permisos (83 comprobaciones).

## 12.5 · 16/11/2026 · Disponibilidad, colaboración y actividades adicionales

- **Tarea bloqueada**: quien trabaja una tarea (o quien la asigna) la marca «Bloqueada» con el motivo (espera de material, de una aprobación, de otra área…). Le llega el aviso al supervisor; si sigue bloqueada más de 2 días, la tarea diaria se lo recuerda una vez al día. «Ya puedo seguir» la devuelve a «En curso».
- **En espera de asignación**: «Pedir más trabajo» deja a la persona en espera hasta que le asignen una tarea (antes solo contaba el aviso del día). En *Mi equipo → Ahora* se ve desde qué hora espera; al asignarle una tarea, la espera termina y queda registrada. Las tareas bloqueadas no impiden avisar.
- **Actividades adicionales** (*Colaboración → Mis actividades*): documentación, estudio de políticas y procedimientos, capacitación, apoyo, colaboración con otro departamento, mejoras de procesos u otras. El supervisor las valida o no (con motivo).
- **Colaboración entre compañeros** (*Colaboración → Apoyos*): pedir apoyo a un compañero (aceptar / no puedo / terminé, con resultado y tiempo) o registrar un apoyo ya dado. Queda quién pidió, quién ayudó, la tarea y el resultado; lo valida el supervisor de quien ayudó. Entre departamentos solo lo coordina un supervisor o la administración (las áreas siguen aisladas).
- **Avisos nuevos**: tarea modificada (fecha, título, descripción, prioridad, pasos…), tarea bloqueada y desbloqueada, pedido y resultado de colaboración, actividad validada.
- **Mi equipo → Ahora**: estados «Con tareas bloqueadas» y «En espera de asignación», motivo del bloqueo en la tarjeta, avisos de bloqueadas y filtro por departamento.
- **KPIs automáticos nuevos** (plantilla de KPI → fuente), para usarlos solo en los puestos donde tienen sentido: tareas fuera de plazo, días de ejecución (desde que empieza hasta que entrega), actividades adicionales validadas y apoyos a compañeros validados. El puntaje existente no cambia hasta que se asignen.
- La tarea guarda cuándo se empezó a trabajar y la fecha y hora exacta de entrega (para el tiempo de ejecución).

## 12.4.1 · 07/11/2026 · Une la versión local 12.3.1

- Trae los cambios hechos en la copia local: verificación en dos pasos **opcional** (`DOS_PASOS_OBLIGATORIA=1` para exigirla), la llamada a la IA sin `temperature` y las pruebas que nunca llaman a la API real.
- A quien maneja datos de la empresa y no tiene la verificación activa, un aviso arriba le recomienda activarla («Más tarde» lo oculta 30 días). La guía de instalación y DESPLIEGUE ya lo explican así.

## 12.4 · 07/11/2026 · Espacio de cada departamento

- **Menú «Departamentos»** (o «Mi departamento»): cada área tiene su propio espacio con siete pestañas:
  - **Resumen**: qué hace el área, sus objetivos y su estructura (encargado, supervisores y personal, tomados del organigrama). La Dirección, Gestión del Talento o el encargado del área editan la descripción y los objetivos.
  - **KPIs**: como el tablero de ADZONE KPIs, por mes o por trimestre, con el resumen del periodo y una tarjeta por KPI (meta cumplida en verde, cerca en amarillo, bajo la meta en rojo). Lo que no tiene dato aparece como **«Sin dato»**, no como «0 · Bajo la meta».
  - **Personal**: cada persona con su cargo, a quién reporta, las funciones de su puesto (de la descripción de puesto), su puntaje y sus KPIs.
  - **Políticas**: las del área y las de toda la empresa, con su **código (POL-001…)**, versión, a quién aplica, responsable, cuántos las aceptaron y quién falta. Cada empleado ve si a él le aplica y si ya la aceptó.
  - **Procesos**: procedimientos paso a paso del área, con código (PRO-001…) y versión.
  - **Documentos**: manuales, formularios, reportes y archivos (PDF, Word, Excel, imágenes…), con código (MAN-, FOR-, REP-). Se puede marcar un documento como «solo encargados».
  - **Evaluaciones**: por persona, tareas abiertas, vencidas, por validar, validadas, % a tiempo, evaluaciones pendientes, la última evaluación del supervisor (promedio de 1 a 5) y si tiene un plan de mejora en curso.
- **Quién ve qué**: la Dirección y Gestión del Talento ven todos los departamentos completos; quien tiene equipo ve su departamento con el detalle de su gente; cada empleado entra a su propio departamento y ve la información del área, a sus compañeros (cargo, funciones y supervisor), las políticas, los procesos y los documentos, pero de KPIs y seguimiento solo lo suyo. Los salarios, solo con el permiso de salarios; los KPIs que salen de la computadora, solo con el permiso de monitoreo.
- Las **políticas** tienen ahora código automático (POL-001, POL-002…) y **responsable**, que se edita en Políticas → Administrar.
- **Personas**: filtro por departamento.
- Desde el tablero: **Ingresar datos** (KPIs del mes), **Gestionar metas** y **Nuevo integrante**, según los permisos de cada quien.

## 12.3.1 · 04/11/2026 · Verificación en dos pasos opcional

- La **verificación en dos pasos ya no es obligatoria**: cada persona la activa cuando quiera en **Mi cuenta → Verificación en dos pasos → «Activar con mi celular»**, y la puede desactivar con su contraseña.
- Para volver a exigirla a quien maneja datos de la empresa (Dirección, personas y accesos, Gestión del Talento, salarios y configuración), poner `DOS_PASOS_OBLIGATORIA=1` en `backend/.env` y reiniciar.
- Quien ya la tiene activa sigue usando su código al entrar. El cierre por inactividad de 30 minutos para las cuentas de empresa no cambia.

## 12.3 · 04/11/2026 · Inteligencia en el día a día

- **Resumen de la semana** (Resultados, Dirección): cada lunes, cómo fue la semana anterior (tareas validadas y a tiempo, vencidas, por validar), quién va bien y quién necesita apoyo, qué OT están en riesgo (vencidas o que vencen en 3 días, con sus partes listas) y dónde se pierde dinero (margen y OT con pérdida). Llega un aviso a la Dirección y queda el historial de semanas.
- **Sugerencia de a quién asignar**: al escribir una tarea nueva, la plataforma propone 3 personas del equipo con la razón (tareas abiertas y vencidas, % a tiempo, calidad y tareas parecidas que ya hizo). Un toque la asigna.
- **Borrador de la evaluación**: en la evaluación del supervisor (y la autoevaluación), «Borrador con los datos» llena fortalezas, qué mejorar y comentario con las tareas, KPIs y asistencia del mes. Siempre se revisa antes de enviar. No aplica a la evaluación de compañeros.
- **Cierres de la revisión de seguridad (12.1–12.3)**:
  - Los archivos que suben las personas (artes, documentos, evidencias) solo se muestran en el navegador si son imágenes comunes o PDF; un SVG o HTML se descarga y nunca ejecuta código con la sesión de nadie.
  - El portal del cliente solo entrega los artes de lo que espera su aprobación (no los archivos de trabajo); el enlace con *todas* las órdenes y facturas del cliente lo crea Coordinación o la Dirección; la firma del acta en el portal solo se habilita con la OT lista para entregar; se registra la IP real; al pedir cambios por encima de las rondas incluidas avisa a Coordinación.
  - Avisos en el celular: solo a los servicios de notificación de los navegadores (Google, Mozilla, Apple, Microsoft), sin redirecciones, hasta 5 dispositivos por persona; un dispositivo no se puede pasar a otra persona sin que la primera salga; al salir de la app, al reiniciar la verificación o al cerrar sus sesiones, ese celular deja de recibir los avisos.
  - **Red de la oficina** en cada lugar de marcaje (Asistencia → Horarios → Lugares, botón «Usar la de aquí»): con ella, el QR y la ubicación «en la oficina» solo valen conectados a su internet, así una foto del QR reenviada o una ubicación falsa desde la casa no sirven. El QR vale 60 segundos. El agente de escritorio respeta «dónde marca» cada persona.
  - A la API de Claude nunca va la actividad en la computadora; si la API falla, el resto de las tareas del día sigue; los borradores tienen un límite por hora.
- **Con la API de Claude** (`ANTHROPIC_API_KEY` en el servidor) el resumen y el borrador los redacta la IA, a partir de los números que calcula la plataforma; sin clave, o si la API falla, se arman automáticamente. A la API no se envían salarios, documentos ni la actividad en la computadora.

## 12.2 · 04/11/2026 · Portal del cliente

- **Enlace para el cliente** (en cada OT, para Coordinación, el comercial, el responsable y la Dirección): crea un enlace seguro, sin contraseña, para una OT o para todas las del cliente, y lo comparte por **WhatsApp** o **correo** con un mensaje listo. Vence a los 30 días (hasta 90), se puede revocar y muestra cuántas veces se abrió. Solo se guarda la huella del enlace.
- **Lo que ve el cliente** en su celular: el avance de cada orden (partes listas, fecha prevista o de entrega), sin montos internos ni comprobantes.
- **Aprobar artes (G4)**: ve el arte o el PDF que el equipo marcó como «Arte» y toca **Aprobar** o **Pedir cambios** con su nombre. Queda por escrito (nombre, fecha, hora e IP), con canal «Portal del cliente», y avisa al equipo. Pedir cambios devuelve la versión a la revisión interna.
- **Firmar la entrega (F-12)**: cuando Administración liberó la salida (G5), el cliente firma el acta con el dedo, indica si lo recibe conforme o con observaciones, y la OT pasa a **Entregada**; Finanzas recibe el aviso para facturar.
- **Facturas** emitidas del cliente, con lo pagado y lo pendiente.

## 12.1 · 04/11/2026 · App de celular: avisos y marcaje con QR o ubicación

- **Instalar la app**: en el celular aparece la sugerencia de instalar Adzone Team (Android: un toque; iPhone: Compartir → «Agregar a inicio»). Se abre como una app, sin la barra del navegador.
- **Avisos en el celular**: cada aviso de la campanita (tarea asignada, entrega por validar, recordatorio, devolución…) llega como notificación aunque la app esté cerrada; al tocarla se abre la pantalla del aviso. Se activa en Mi cuenta o en la sugerencia de arriba, por dispositivo. En iPhone funciona con la app instalada (iOS 16.4 o más nuevo).
- **Marcaje con el QR de la oficina**: una tablet o monitor en la recepción muestra un QR que cambia cada 30 segundos (Asistencia → Horarios → Lugares de marcaje → «Enlace de la pantalla»). La persona lo escanea con la cámara y marca entrada, pausa, regreso o salida. Una foto del QR deja de servir al minuto y medio.
- **Dónde marca cada persona** (Asistencia → Horarios): *Donde sea* (como hasta ahora), *En la oficina* (con el QR o estando dentro del radio del lugar según su celular) o *En la calle* (instalaciones, eventos: marca donde esté, pero el celular debe dar la ubicación y queda guardada con el marcaje). La ubicación solo se pide al marcar: la plataforma no sigue a nadie.

## 12.0 · 04/11/2026 · Seguridad de las cuentas y respaldos cifrados

- **Verificación en dos pasos** con Google o Microsoft Authenticator: obligatoria para quien maneja la empresa (Dirección, personas y accesos, Gestión del Talento, salarios y configuración); opcional para el resto en Mi cuenta. Se activa escaneando un QR y entrega 10 códigos de respaldo de un solo uso. Un código no sirve dos veces, y hay 5 intentos por entrada. También protege el panel de Django.
- **Bloqueo por persona**: 5 códigos equivocados seguidos bloquean la verificación 15 minutos (aunque se intente desde otras sesiones) y avisan a la persona. Cambiar de celular pide la contraseña, avisa y cierra las demás sesiones. El límite de intentos ahora cuenta la IP real detrás del proxy y aplica también a quien ya tiene una sesión abierta; el formulario de /admin tiene su propio límite.
- Quien perdió el celular: **Accesos y permisos → Reiniciar verificación** (con las mismas reglas anti-escalada; nunca la propia; un superusuario solo lo reinicia otro). Reiniciar cierra sus sesiones abiertas.
- **Cierre de sesión por inactividad**: 30 minutos sin usar la app para las cuentas de empresa y 12 horas para el resto (configurable). Los avisos que la app consulta sola no cuentan como actividad.
- **Aviso de dispositivo nuevo**: cuando alguien entra desde un navegador o celular donde nunca había entrado, le llega un aviso en la campanita.
- **Monitoreo → Calibración** (Tecnología y Dirección): las aplicaciones y sitios que el equipo usa y ninguna regla clasifica, del más usado al menos, con cuántas personas y de qué departamentos. Se deciden de un toque (productivo, neutral o improductivo, para toda la empresa o un departamento) y se aplican a los últimos 30 días. Muestra qué parte del tiempo ya tiene regla. Guía de la semana de prueba en `docs/PLAN_PILOTO.md`.
- **Respaldos cifrados**: cada noche base de datos, archivos privados y configuración, cifrados con AES-256 y guardados 30 días. **Administración → Respaldos** (Dirección) para descargarlos; aviso cada lunes y alerta si un respaldo no se hizo. Sin clave de respaldo no se hacen copias sin cifrar; cada copia lleva su huella SHA-256 y las copias sin cifrar de versiones anteriores se borran.

## 11.1 · 03/11/2026 · Puestos adicionales y paquete de despliegue

- **Puestos adicionales**: una persona puede cubrir además otro puesto (por ejemplo, un Community Manager que también hace de Gerente de Marketing). Recibe el equipo que depende de ese puesto (asignar, validar, avisos) y el perfil Supervisor; su puesto principal sigue mandando para KPIs, puntaje y nómina. Solo la Dirección lo asigna, en Personas → editar.
- **Cambiar la contraseña o dar de baja** cierra las sesiones abiertas de esa persona.
- **Carpeta `servidor/`**: `instalar.sh` (instalación y actualización en Plesk), `respaldo.sh` (base y archivos privados, cada noche) y la lista de tareas programadas.

## 11.0 · 02/11/2026 · Accesos y permisos: mínimo privilegio

- **Perfil + organigrama**: cada persona tiene uno o más perfiles que dicen **qué** puede hacer; el organigrama dice **sobre quién** (quienes dependen de su puesto), más su **equipo adicional**. Un colaborador solo cumple y ve lo suyo; un supervisor asigna, valida y evalúa solo a su equipo.
- **Perfiles iniciales**: Colaborador, Supervisor (automático con gente a cargo), Gerente de Departamento, Administrador (Dirección), Administrador del sistema, Tecnología, Gestión del Talento, Finanzas, Coordinación, Almacén y Agente Call Center. La Dirección ajusta qué permite cada uno y puede crear perfiles nuevos.
- **16 permisos concretos**: asignar tareas, validar, ver al equipo, evaluar, expediente y planes de mejora, asistencia del equipo, corregir marcajes, Dirección, ver el monitoreo, ver capturas, configurar el monitoreo, personas y accesos, salarios, Gestión del Talento, configuración del sistema y auditoría.
- **Dirección y Administrador del sistema separados**: la Dirección ve y decide todo el negocio; el Administrador del sistema configura personas, accesos, monitoreo e integraciones **sin ver salarios, expedientes ni documentos**.
- **Monitoreo solo para Dirección y Tecnología**: la actividad en la computadora, las capturas, las pantallas en vivo, las incidencias, las justificaciones y las alertas de otras personas ya no llegan a supervisores ni gerentes. Cada persona sigue viendo lo suyo. En la ficha de alguien de su equipo, el supervisor no ve su computadora y los KPIs que salen de la PC aparecen como «Reservado».
- **Nueva pantalla Administración → Accesos y permisos**: personas con sus perfiles y lo que pueden hacer hoy; **excepciones** (dar o quitar un permiso puntual, con motivo) y **equipo adicional** (con fecha de fin opcional); perfiles con su lista de permisos.
- **Anti-escalada**: nadie cambia sus propios accesos, nadie da ni quita permisos que no tiene, nadie cambia la contraseña, el estado o los perfiles de alguien con más permisos, y nadie valida su propio trabajo. Todo cambio queda en la auditoría.
- El menú, las pestañas y los campos se muestran según los permisos (por ejemplo, salarios solo con «Salarios y costo por hora»). Los avisos de OT, almacén, tardanzas y monitoreo van a quien tiene el permiso correspondiente.
- **Personas** ya no cambia perfiles: crea la cuenta como Colaborador y remite a Accesos y permisos.
- **Cierres de la revisión de seguridad**: nadie cambia su propio puesto (el organigrama da equipo); el perfil Supervisor por organigrama solo se da al cambiar el puesto y si quien hace el cambio puede darlo; el equipo adicional solo lo asigna quien tiene esos permisos de equipo y nadie queda a cargo de alguien con más permisos; la auditoría oculta salarios a quien no los maneja y el contenido de expedientes a quien no es Gestión del Talento; Finanzas ve horas y costos por OT pero no la productividad en la PC de cada persona; los KPIs y motivos que salen de la PC no llegan a supervisores; debe quedar al menos una persona en Dirección.
- **Activos y equipos** los gestionan Dirección, Almacén y quien configura el monitoreo (Tecnología, Administrador del sistema). **Por validar** y la confirmación de evaluaciones 360° pasan a Gestión del Talento (y Dirección).

## 10.2 · 02/11/2026 · Ficha de cada computadora

- **Monitoreo → Computadoras → una computadora** (o desde el día de una persona: «ver cómo usa su tiempo»): cómo se usó el tiempo en ese equipo en 7, 14, 30 días o fechas a medida, como el «Computer Details» de Teramind.
  - Encabezado: nombre, nombre del equipo en Windows o Mac, sistema, IP, versión del agente, en línea o última vez visto, persona y su activo del inventario.
  - **Actividad por día** (productivo, neutral, improductivo e inactivo), **mapa de teclado y ratón por día y hora**, tareas principales (del cronómetro), aplicaciones y sitios.
  - **Registro de actividad**: los minutos seguidos en la misma ventana se agrupan en una fila con inicio, persona, aplicación o sitio, tiempo (y cuánto activo), título de la ventana y tarea; con buscador.
  - **Alertas** (reglas de comportamiento, inactividad, computadora sin reportar), **capturas**, **pantalla en vivo** e **historial de IP**.
- **Encender o apagar el monitoreo de un equipo** (Tecnología y administración), con auditoría.
- La lista de computadoras se busca por nombre, equipo, persona o IP y se filtra por en línea, desconectadas, no monitoreadas o desvinculadas.
- El agente envía el nombre del equipo; cada conexión guarda su IP.

## 10.1 · 02/11/2026 · Descripción oficial de Soporte Técnico (TI)

- **Soporte Técnico (TI)** carga la descripción oficial «Soporte de Tecnología (TI)» (DP-TI de Gestión del Talento): objetivo, funciones por bloque (soporte a clientes y personal, soporte interno, incidentes y mantenimiento, documentación y control, cumplimiento y cultura), perfil ideal, compensación variable, beneficios y alineación cultural.
- **Reporta al Gerente de Tecnología y Desarrollo**, como dice el documento (antes al Encargado de Ciberseguridad y Desarrollo).
- **KPIs oficiales (100 %)**: incidencias resueltas dentro del SLA 25 %, satisfacción de usuarios internos y clientes 20 % (meta 90 %), resueltas en primer contacto (FCR) 20 %, registros y documentación técnica 15 %, cumplimiento de políticas 10 % y trabajo en equipo interdepartamental 10 %. Las metas de SLA (90 %) y FCR (70 %) son propuestas: el documento no las fija y se ajustan en el puesto. Los 4 KPIs provisionales se desactivan (su historial queda); los de seguimiento siguen.

## 10.0 · 02/11/2026 · Monitoreo al nivel de Teramind, políticas, rentabilidad real y activos

### Monitoreo al nivel de Teramind (con nuestro propio agente)
- **Resumen** con rango de fechas (7, 30, 90 días o a medida) y por departamento: tiempo activo y productivo frente al período anterior, actividad por persona, sitios y aplicaciones con su tiempo, reglas que se activaron, uso de IA y riesgo interno, más **«lo que hay que mirar»**: frases automáticas con lo importante (productividad que sube o baja, quién pasó horas en un sitio improductivo, personas con poca actividad, crecimiento del uso de IA).
- **Reglas de comportamiento** (como las Behavior Rules): si alguien usa un sitio, una aplicación o una ventana con cierto texto durante N minutos en el día, queda una **incidencia** con su riesgo (bajo, medio, alto o crítico) y, si la regla lo pide, se avisa al supervisor (y a Tecnología en seguridad o riesgo alto; a la dirección en crítico). Once reglas iniciales: contenido para adultos, apuestas, descargas P2P, acceso remoto (no aplica a Tecnología), VPN, envío de archivos a servicios externos, IA no aprobada, juegos, series, compras y redes sociales fuera de su función. Se pueden aplicar a los últimos 30 días.
- **Incidencias**: cada persona ve las suyas; el supervisor las marca como revisadas o las descarta (las descartadas no suman riesgo).
- **Riesgo interno** por persona: puntos según el riesgo de cada incidencia, con nivel y las reglas que más se activaron.
- **Uso de IA** (como AI Usage Control): tiempo por herramienta (ChatGPT, Claude, Gemini, Copilot, Perplexity, DeepSeek, Midjourney, ElevenLabs y más) y por persona.
- **Perfiles de monitoreo**: por departamento o por persona: registrar o no, capturas sí o no, cada cuánto, desenfoque y umbral de inactividad. La dirección puede quedar sin monitoreo.
- **Pantallas en vivo** (Live Montage): la última captura de cada persona, actualizada cada minuto (solo con perfiles que toman capturas).
- **Computadoras** (Tecnología y administración): cada persona con su estado de monitoreo (en línea, desconectado, sin computadora, sin aceptar la política, no monitoreado) y cada computadora con su sistema, versión del agente y último contacto.
- **Equipo en vivo** con la gráfica de la última hora por persona.
- Sigue sin registrarse contenido, teclas, archivos, mensajes, audio ni cámara.

### Políticas y documentos
- **14 políticas iniciales en borrador** (reglamento, asistencia, permisos, uso de computadoras, monitoreo, protección de datos, seguridad, equipos, trabajo remoto, IA, redes, vehículos, calidad y disciplina) para revisar con su asesor legal y publicar.
- Cada política aplica a toda la empresa o a departamentos y puestos; al publicarla llega un aviso; cada persona la lee y la **acepta** (queda fecha, hora, versión, IP y navegador) y tiene su **constancia imprimible**.
- **Versiones**: una política publicada no se edita en silencio; la nueva versión se publica y todos la aceptan de nuevo. El historial guarda el texto exacto de cada versión.
- **Cumplimiento**: quién falta por aceptar cada política, con Excel. Aviso fijo arriba a quien tiene políticas pendientes y recordatorio semanal.
- Aceptar la política de monitoreo cuenta también como el consentimiento que pide el agente.
- **Documentos del expediente**: contrato, copia de identificación, acuerdo de confidencialidad, títulos, certificaciones, cartas, actas y pólizas, con vencimiento. Solo los ven Gestión del Talento y la persona (los supervisores no). Expedientes incompletos y documentos por vencer, con aviso.

### Rentabilidad real
- **Por OT, por cliente y por departamento**: ingreso (lo facturado sin ITBIS o, si aún no se factura, lo vendido) menos mano de obra (horas × costo por hora), materiales despachados por almacén y gastos de la OT (equipos, freelance y pauta, transporte y otros). Utilidad, margen y alerta bajo el margen mínimo (30 %). Desglose de cada OT y Excel.
- **Tasa de cambio**: los montos en dólares se convierten con la tasa de su fecha; sin tasa no se inventa un valor y se avisa. La rentabilidad por proyecto también convierte dólares.
- El panel gerencial usa el costo completo de cada OT.

### Activos y equipos
- Inventario con código ACT-0001, categoría, marca, modelo, serie, ubicación, costo, garantía, vida útil y **valor actual** (depreciación en línea recta).
- **Asignar, recibir devolución, trasladar, mantenimiento, reparación, daño y baja**, con historial. Quien tiene un equipo lo ve en «Equipos asignados» y puede reportar un daño; le llega a Tecnología.
- Mantenimientos programados con aviso. Una computadora del inventario se vincula con la del monitoreo.
- Los equipos asignados salen en la ficha de cada persona.

### Panel gerencial
- Alertas nuevas: políticas sin aceptar, documentos por vencer, personas con riesgo alto en la computadora y equipos dañados o con mantenimiento vencido.

## 9.0 · 02/11/2026 · KPIs con ficha técnica, evaluación 360°, monitoreo por OT y panel gerencial

Fases 1 a 4 de la propuesta de evolución de Adzone Team.

### Puntaje del mes: 40 / 35 / 15 / 10
- **Cumplimiento de tareas 40 %**, **KPIs del puesto 35 %**, **calidad y satisfacción 15 %** y **asistencia y puntualidad 10 %**.
- **Calidad y satisfacción** es el promedio de las estrellas de las tareas, el % aprobado a la primera y la evaluación del supervisor del ciclo (cuando existe y ya está confirmada). Con calidad aparte, la nota de cada tarea es solo su puntualidad.
- **Asistencia** es la adherencia al horario (puntualidad, días y horas) y solo cuenta para quien marca su jornada.
- **La computadora ya no da puntos**: su actividad se muestra en la ficha y genera alertas.
- Reglas del puntaje con tres controles (tareas, calidad, asistencia); los KPIs se quedan con el resto. Ranking y Excel con columnas de calidad y asistencia.

### Fase 1 · Motor de KPIs
- Cada plantilla de KPI tiene **fórmula, fuente de datos y responsable de validar**; las 246 oficiales vienen llenas.
- **KPIs de seguimiento**: cada puesto queda con 8 a 15 KPIs. Los que tienen peso suman al puntaje; los de seguimiento (peso 0) se miden y alertan sin cambiar el puntaje. 497 KPIs activos, 242 de seguimiento.
- Seis fuentes automáticas nuevas: tareas validadas, % con correcciones, horas por tarea, % dentro de lo estimado, % de la jornada en tareas y horas extra.
- **Umbral de alerta** por KPI (70 % por defecto). Comando `revisar_kpis`: avisa al supervisor una vez por KPI y mes.
- **Auditoría de cambios**: quién cambió pesos, metas, umbrales, plantillas, reglas del puntaje, marcajes, horarios, permisos, puestos, salarios y la configuración del monitoreo, con el valor de antes y el de después (Talento → Auditoría). Los cambios de salario dejan además su historial.

### Fase 2 · Monitoreo por proyecto y OT
- Cada minuto de la computadora se une al **cronómetro** que corría (tarea, OT o proyecto); si las horas se anotan después, se unen al guardarlas.
- **Monitoreo → Por proyecto y OT**: horas del mes, estimado contra real (horas de las Órdenes de Área o de las tareas), % productivo en la computadora durante el cronómetro, tareas validadas, a la primera, correcciones y solicitudes de cambio, y por persona. Finanzas y la dirección ven el **costo de la mano de obra** (horas × costo por hora) contra el monto de la OT.
- **Justificaciones**: la persona explica un tramo (YouTube para referencias, WhatsApp con un proveedor) y su supervisor la aprueba: esos minutos pasan a productivos y no se reclasifican.
- **Desconexiones**: el día de cada persona muestra los tramos de 15+ minutos en jornada sin datos de la computadora.
- La alerta «marcó pero su computadora no reporta» llega también a **Tecnología**.

### Fase 3 · Ficha integral y talento
- **Evaluación 360°** por ciclos: autoevaluación, supervisor y dos compañeros del departamento (anónimos), con 8 competencias del 1 al 5, fortalezas y qué mejorar.
- **Validación humana**: una evaluación del supervisor por debajo de «Cumple» exige explicar qué mejorar y la confirma la dirección (o la devuelve) antes de que la vea la persona.
- **Planes de mejora** con objetivos, metas, fechas y fecha de revisión; los abre y sigue el supervisor.
- **Expediente**: reconocimientos, observaciones, amonestaciones, incidencias, capacitaciones (horas) y bonos (monto solo para la administración). Registros internos o visibles, y la persona puede escribir su descargo.
- **Ficha integral**: puntaje en cuatro partes, KPIs con fórmula y umbral, seguimiento aparte, evaluación 360°, planes, expediente, historial salarial (administración) y tendencia de 6 o 12 meses con el puntaje. Alerta si el puntaje baja tres meses seguidos.

### Fase 4 · Panel gerencial (Dirección)
- Personal activo, productividad general, OT completadas y a tiempo, tareas validadas y a tiempo, asistencia y calidad promedio.
- **Indicadores por área** con su tendencia de 6 meses, KPIs, calidad, asistencia, productividad en PC, tareas vencidas y horas.
- **Alertas gerenciales**: OT abiertas sobre sus horas presupuestadas, mano de obra sobre el 60 % del monto, áreas acumulando trabajo vencido, puntajes bajando tres meses y necesidades de capacitación (competencias flojas y KPIs bajo umbral en el área).
- Destacados, quién necesita atención y **Excel** del panel.

### Para después (fases 5 a 8 de la propuesta)
Rentabilidad completa por OT con materiales, alertas inteligentes, plan de capacitación con cursos y certificados, e integraciones (Cashflow, nómina, redes).

## 8.0 · 01/11/2026 · Control de horario, monitoreo de actividad y KPIs que se miden solos

Lo mejor de Time Doctor, Teramind, BambooHR y la guía de desempeño de Personio, dentro de Adzone Team.

### Control de horario (Asistencia)
- **Marcar jornada** desde cualquier pantalla (arriba, junto al buscador), en PC o celular, o desde el ícono del agente: entrada, pausa (almuerzo, diligencia, reunión fuera), regreso y salida.
- **Horarios por persona:** días, hora de entrada y salida por día, almuerzo y tolerancia. Arranca con «Oficina (L-V 8-5, sáb 8-12)» = 44 h. Cada persona puede tener su horario y se puede marcar quién no está obligado a marcar (dirección).
- **Cada día se calcula solo:** llegó a tiempo o tarde (minutos), salida temprana, horas trabajadas, pausa, horas extra (desde 15 min), días sin marcar salida, ausencias. El almuerzo no marcado se descuenta. Los días antes de empezar a usar el control no cuentan como ausencias.
- **Hoy** (supervisores): quién trabaja, en pausa, llegó tarde, no ha marcado o tiene permiso, y qué hace su computadora en este momento.
- **Equipo en el mes** con adherencia, puntualidad, asistencia, tardanzas, ausencias, horas y extra, y **Excel**.
- **Correcciones**: el supervisor agrega o borra marcajes con una nota; queda registrado quién lo hizo. Nadie se corrige a sí mismo.
- **Turnos que pasan de medianoche** (call center nocturno): la jornada sigue abierta hasta 16 h y las horas cuentan para el día en que entró. Un horario configurado no puede cruzar la medianoche todavía (se marca igual; solo no calcula la tardanza contra ese turno).
- **Permisos y vacaciones**: se piden en la plataforma, los aprueba el supervisor; los días aprobados no cuentan como ausencia. **Feriados**.

### Monitoreo de actividad (agente de escritorio)
- **Agente para Windows y Mac** (`agente/`): mide cada minuto la aplicación y la ventana en uso, el sitio si aparece, segundos activos e inactivos, nivel de actividad (teclado/ratón, sin guardar teclas) y cambios de ventana. Solo en jornada; visible en la barra de tareas; si se cae el internet guarda lo medido y lo reenvía (y deja de medir si no puede confirmar que la persona sigue en jornada).
- **Productivo, neutral o improductivo por departamento** (como los perfiles de Teramind): 164 reglas iniciales; Facebook, Instagram, TikTok y YouTube son trabajo en Marketing, Audiovisual y Adzone TV e improductivos en el resto. Se editan en Monitoreo → Reglas y se pueden volver a aplicar a los últimos 30 días.
- **Equipo en vivo**: quién está activo y en qué aplicación, tiempo activo, productivo, de foco, nivel de actividad y cambios de ventana por hora.
- **El día de cada persona**: línea de tiempo en bloques de 10 minutos, aplicaciones y sitios con su tiempo, tiempo de foco (bloques de 25+ minutos productivos) y capturas.
- **Capturas de pantalla opcionales** (apagadas por defecto), desenfocadas, borradas a los 30 días.
- **Avisos al supervisor**: llegó tarde, no ha marcado, X minutos inactivo en jornada, marcó pero su computadora no reporta, día con mucho tiempo improductivo. Comando `revisar_jornadas` cada 10 minutos.
- **Una computadora desvinculada se desactiva**, no se borra: nadie puede borrar su historial. Si una persona usa dos computadoras, cada minuto cuenta una sola vez.
- **Transparencia y Ley 172-13**: cada persona acepta la política en la plataforma antes de que su computadora registre, ve sus propios datos («Mi actividad») y solo la ven su cadena de supervisión y la administración. Retención 90 días (`limpiar_monitoreo`). Nunca teclas, contraseñas, mensajes, audio ni cámara.

### KPIs enriquecidos y ficha de productividad
- **KPIs que se miden solos**: 25 KPIs oficiales pasan a automáticos — adherencia al horario (Asistencia y puntualidad, Adherencia al horario), entregas a tiempo, aprobado a la primera y rondas de revisión salen de las tareas validadas. Las plantillas de KPI tienen «de dónde sale» para crear más (puntualidad, asistencia, horas, actividad o productividad en la computadora, calidad).
- **Puntaje con tres partes**: tareas 48 % + KPIs 32 % + **jornada 20 %** (adherencia al horario y productividad en la computadora contra la meta de 75 %). Tareas y KPIs siguen 60:40 entre sí; a quien le falta una parte, las demás se reparten el 100 %. La jornada solo cuenta para quien marca. Ajustable en Reglas del puntaje.
- **Ficha de productividad** (Mi ficha, o desde el ranking): puntaje y sus partes, lo que hay que atender (tardanzas, ausencias, baja actividad, interrupciones, sobrecarga de horas extra), KPIs con su origen, control de horario, computadora, tareas, tiempo registrado vs. jornada, aplicaciones más usadas y tendencia de 6 meses.
- Ranking con columna **Jornada** y el nombre lleva a la ficha.

Requiere `python manage.py migrate` (apps `asistencia` y `monitoreo`; `kpis 0005`, `desempeno 0011-0012`) y `python manage.py puestos_oficiales --aplicar` para que los KPIs automáticos queden activos.

## 7.1 · 31/10/2026 · DP y organigrama actualizados; listado de personal del 31/10

- **Descripciones de puesto del documento «DP ADZONE DIGITAL MARKETING»** (34 puestos). Puestos nuevos con su descripción y KPIs: **Control Master**, **Herrero**, **Gerente de Call Center**, **Analista de Calidad y Monitoreo** y los **agentes bilingüe y en español**. La **Coordinadora Financiera y Administrativa** trae su descripción y KPIs nuevos (flujo de caja, facturación y cobros, pagos, conciliaciones, presupuesto, cumplimiento fiscal y laboral, caja chica, reportes, controles).
- **KPIs oficiales:** 246 asignaciones en 34 puestos. Los KPIs propuestos para el Herrero y el call center se reemplazan por los del documento. Solo Presupuestos y Facturación, Legal, Soporte TI y el Consejo siguen con los propuestos (el documento no los trae).
- **Organigrama 2026 actualizado:** «Coordinador de Contenido y Podcast» pasa a **Coordinador de Estudio de TV y Contenido** (reporta a la Gerencia de Marketing; de él dependen Control Master, fotografía y video, edición y animación). «Supervisor de Calidad y Monitoreo» pasa a **Analista de Calidad y Monitoreo**. Encargado de Producción Audiovisual y Técnico de Servicios Generales salen del organigrama (el puesto queda, con su descripción).
- **Personal:** el archivo privado sigue el listado del 31/10/2026: 37 personas con su puesto y el salario de las nóminas de octubre. Quien ya no está en el listado se desactiva al cargar (si su cuenta existe) y nunca se crea.
- `cargar_equipo` acepta `"activo": false` para desactivar sin crear.

## 7.0 · 31/10/2026 · Personal real, descripciones de puesto y KPIs oficiales

- **Descripciones de puesto completas** (documento «Descripción de Puestos – ADZONE», 28 puestos): además de las funciones, cada puesto trae **objetivo, perfil ideal, compensación variable, beneficios y alineación con la cultura**. Se ven en la página del puesto y se editan en «Editar puesto».
- **KPIs oficiales con su ponderación** para los 28 puestos (205 asignaciones, 104 KPIs distintos). Los repetidos (políticas y procedimientos, trabajo en equipo, organización de archivos, entregas a tiempo…) usan una sola plantilla. Cada uno trae su meta numérica, unidad, si «menor es mejor» y su periodicidad (mensual, trimestral o anual). Las metas trimestrales se anotan como % de avance del plan del trimestre.
- **Organigrama:** entran **Encargado de Producción Audiovisual** (reporta a la Gerente de Marketing; de él depende el Coordinador de Contenido y Podcast) y **Técnico de Servicios Generales** (reporta al Coordinador de Eventos y Catering). «Encargado(a) de…» se renombra a «Encargado de…».
- **Bono según la política de las descripciones:** 100 % → 10 % del salario; de 80 % a 99 % → proporcional; menos de 80 % → no aplica. En Reglas del puntaje, cada tramo puede ser «proporcional al puntaje». Si los tramos seguían como venían de fábrica, se cambian solos al migrar.
- **Salario y nómina en cada persona** (solo administración): salario mensual, en qué nómina cobra y, si no se pone uno propio, el costo por hora se calcula del salario (÷ 23.83 días ÷ 8 h, como la nómina). En Personas hay una columna de salario.
- **Carga del personal:** `cargar_equipo` acepta `accesos`, `salario_mensual`, `nomina` y `horas_semana`; a los agentes les da el acceso de Call Center. El archivo con el personal real va en `datos_privados/` (no se sube a GitHub).
- Comando nuevo: `python manage.py puestos_oficiales --aplicar`.
- Requiere `python manage.py migrate` (organizacion 0005, desempeno 0010).

## 6.5 · 31/10/2026 · Call Center: campañas y agentes aparte

- **Agentes aparte del resto del equipo:** acceso nuevo «Agente de call center» (Personas → editar). Quien ya ocupa un puesto «Agente de Call Center…» lo recibe solo al migrar.
- **Pantalla del agente:** entra directo a **Call Center** y solo ve lo suyo: su puntaje del mes, sus campañas activas con metas, horario, canales y el guion, y sus KPIs. No ve tareas, órdenes ni el resto del menú.
- **Campañas** (gerencia del call center, supervisores de agentes y dirección): cliente, tipo (atención, ventas, cobros, soporte, encuestas, citas), idioma, canales, horario, fechas, metas diarias (contactos efectivos, conversión, calidad mínima), agentes asignados y guion. Se crean desde la pantalla o con **Crear → Campaña de call center**.
- **Ranking aparte:** en Desempeño, pestañas **Equipo** y **Call Center**. Los agentes salen del ranking general, de los «sin evaluar» y del Empleado del Mes; tienen su propio ranking, su desempeño mínimo y su Excel.
- Requiere `python manage.py migrate` (app `callcenter`).

## 6.4 · 31/10/2026 · Desempeño mínimo

- **Reglas del puntaje → Desempeño mínimo:** puntaje mínimo del mes (70 por defecto) y cuántas tareas hacen falta para juzgar (3 por defecto).
- **Desempeño:** cuadro nuevo con quién **cumple**, quién está **por debajo del mínimo** (con lo que le bajó el puntaje: vencidas, tardes, calidad, KPIs flojos), quién tiene **pocos datos** y quién está **sin evaluar** (tiene puesto pero no tiene tareas ni KPIs en el mes; sale con su supervisor). En el ranking, cada persona lleva su evaluación.
- **Excel del ranking:** columnas «Evaluación» y «Motivos», y al final las personas sin evaluar.
- Avisa si el mes no ha terminado o si hay entregas sin validar: no suman hasta que se validen.
- Requiere `python manage.py migrate` (migración `desempeno 0009`).

### Entregas con evidencia para la administración
- Al entregar una tarea (siempre con evidencia: nota, enlace o foto), además de su supervisor **los administradores reciben el aviso** «Por validar», con qué evidencia trae. El aviso abre la tarea directo en **Por validar**, donde la pueden validar.
- En **Por validar** cada entrega muestra su evidencia en la lista (archivos, enlace, nota).
- Desarrollo: `vite.config.js` acepta túneles `*.trycloudflare.com` (`cloudflared tunnel --url http://localhost:5173`; Django con `EXTRA_CSRF_ORIGINS="https://*.trycloudflare.com"`).

## 6.3 · 31/10/2026 · Guía paso a paso dentro de la plataforma

- **Recorrido de bienvenida:** la primera vez que alguien entra, la plataforma le muestra paso a paso dónde está todo (menú, Inicio, Mis tareas, Tiempo, Órdenes, buscar, crear y avisos), resaltando cada cosa en la pantalla. Se adapta al rol: supervisores ven también Por validar y Mi equipo; Finanzas y administración, lo suyo. Funciona en PC y celular.
- **Botón ? (Ayuda)** arriba a la derecha: vuelve a ver el recorrido, la guía de la pantalla en la que estás y **«¿Cómo hago…?»** (entregar una tarea, usar el cronómetro, crear una OT, validar, asignar tareas, avisos, buscar, instalar la app, cambiar la contraseña). Cada guía lleva a la pantalla que hace falta.
- **Primera vez en una pantalla:** aparece «¿Primera vez en …? Muéstrame». Se puede apagar desde la Ayuda.
- Lo que cada persona ya vio se recuerda en su navegador. Los textos de las guías están en `frontend/src/lib/guia.js`.

### Pantallas pequeñas: nada cortado
- **Tablet (768 a 1023 px):** el menú lateral ya no le quita espacio al contenido; se usa la barra inferior como en el celular. El menú lateral aparece desde 1024 px.
- **Pestañas** (Finanzas, Tiempo, Órdenes, Mi equipo…): en el celular se acomodan en filas en vez de quedar cortadas a la derecha.
- **Tablas anchas:** una sombra en el borde avisa que hay más columnas al deslizar. En «Áreas y tiempos» los textos del cronograma ya no se aplastan.
- **Filtros por área** en Órdenes: en el celular el último se desvanece (hay más deslizando); en tablet y PC bajan a otra línea.
- **Automatizaciones:** en el celular los controles bajan a otra línea y el texto de la regla se lee completo.
- **Mi equipo:** las tarjetas ya no cortan los nombres en tablet. El buscador de arriba ya no se parte en dos líneas.

## 6.2 · 27/10/2026 · Puestos nuevos del Organigrama 2026 completos

- Los 13 puestos que agrega el organigrama ya llegan con **descripción de puesto** (funciones principales al estilo ADZONE): Presidente y Vicepresidente/Secretario del Consejo, Director Comercial, Encargado de Ventas y Cuentas, Encargado de Gestión del Talento, Encargado de Presupuestos, Facturación y Cobros, Legal y Contratos, Herrero, **Soporte Técnico (TI)**, Gerente de Call Center, Supervisor de Calidad y Monitoreo y los agentes bilingüe y español.
- 11 de ellos llegan con **KPIs propuestos** y su ponderación (el Consejo no lleva KPIs): por ejemplo, Soporte Técnico se mide por tickets resueltos en el tiempo acordado, tiempo de respuesta, disponibilidad y mantenimientos preventivos. El Herrero tiene dos automáticos (trabajos validados y rondas de revisión).
- `organigrama_2026 --aplicar` los carga solo donde no hay nada: nunca pisa una descripción o unos KPIs ya escritos.

## 6.1 · 26/10/2026 · Organigrama 2026, cronograma de producción, flujogramas y uso estratégico de herramientas

### Organigrama 2026
- Comando `organigrama_2026`: crea los puestos nuevos (Dirección Comercial y Encargado de Ventas y Cuentas, Gestión del Talento, Presupuestos/Facturación y Cobros, Legal y Contratos, Herrero, Soporte Técnico, Supervisor de Calidad y Monitoreo, agentes bilingüe y español, el Consejo), renombra los que cambiaron (las personas se quedan en su puesto) y deja a cada uno con su supervisor.
- Departamentos nuevos: **Comercial** y **Gestión del Talento**.
- Con la nueva cadena, los encargados intermedios (Creatividad, Contenido y Podcast, Impresiones) validan a su gente y supervisan sus áreas.

### Cronograma estimado de producción (Diseño y Audiovisuales)
- Los 26 tipos de trabajo del cronograma se cargan como **tiempos estándar** (horas y días).
- En la OT, cada área de Diseño o Audiovisuales tiene **«Tipo de trabajo (cronograma)»** y **cantidad**: pone las horas, los días y «qué produce». Esas horas pasan a la tarea del ejecutor (carga del equipo).
- Indicador de **rendimiento**: horas del cronograma contra horas reales del cronómetro.

### Flujogramas de Diseño Gráfico y Audiovisuales
- Las etapas de las Órdenes de Área de Diseño, Audiovisuales y Marketing siguen el flujograma: brief y plan de Marketing → revisión de requerimientos → propuesta (cronómetro activo, arte en la plataforma) → **revisión interna del Gerente de Marketing** → validación del cliente → entrega al Community Manager.
- **Revisión interna obligatoria** antes de enviar al cliente: el ejecutor la pide, el Gerente de Marketing da visto bueno o pide ajustes. Cada nueva versión que pide el cliente vuelve a pasar por la revisión.

### Uso estratégico de IA y herramientas
- **Checklist de validación final** (marca, mensaje, calidad, trazabilidad, conversión, calendario) en la revisión interna: «si no hay revisión humana, no hay publicación».
- **Ventanas de anticipación** del contenido en la OT: ideal 15 días, seguro 10, emergencia 7 días hábiles; avisa si se pide por debajo del mínimo.
- **Herramientas recomendadas** por área en cada Orden de Área y campo «Herramientas usadas»; en el control de calidad, «prototipos o piezas con IA identificados y aclarados».
- **KPIs de adopción:** tiempo de brief a propuesta, % aprobado a la primera, ajustes en revisión interna y rendimiento contra el estándar.
- Automatizaciones nuevas para **n8n**: «una Orden de Área cambia de etapa» y «un área entrega a otra (handoff)».

## 6.0 · 26/10/2026 · Formatos ADZONE en digital, almacén y facturación con Cashflow

Las órdenes de trabajo ahora siguen al pie de la letra los formatos controlados de ADZONE (F-01 a F-15).

### OT Maestra y Órdenes de Área
- **F-01 completo:** datos del cliente, alcance y exclusiones, áreas que intervienen con su secuencia (en paralelo si comparten número), cálculo de la fecha comprometida (estándar + cola + aprobación × rondas + colchón 20/30 %), monto, anticipo y la compuerta **G0** de 11 casillas.
- **Numeración por Coordinación:** la solicitud (S-AA-0000) se vuelve **OT-AA-0000** solo al liberarla. Sin anticipo no se numera, salvo excepción de Gerencia General con aviso de regularizar en 24 h.
- **Una Orden de Área por área** (F-02 Diseño, F-03 Marketing, F-04 Audiovisuales, F-05 Podcast/Adzone TV, F-06 Impresión, F-07 Letreros, F-08 Fabricación, F-09 Eventos, F-10 Software, más Instalación, Call Center y Administración), cada una con su G1, su especificación, sus etapas, su G3 y su G2/G5.
- **Compuertas que no se saltan:** G1 al recibir (crea la tarea con las etapas), G4 con aprobación escrita del cliente y control de rondas, G3 al validar la tarea, y **traspasos con doble firma (F-13)**: quien recibe verifica, acepta o rechaza con causa.
- **Estados E1 a E7** visibles en cada OT, y tablero **Por área** con la cola de cada área.
- **Acta de entrega / instalación (F-12)** con liberación de salida G5 (saldo pagado o autorización de Gerencia), verificación en sitio y **firma del cliente en la pantalla**. Sin acta firmada no se factura ni se cierra.
- **Cierre G6** con costo real (horas, materiales, servicios externos, retrabajos y gastos) y margen contra lo cotizado.
- **Solicitudes de cambio y retrabajos (F-14)** con clasificación, impacto antes/después, acción preventiva y autorización.
- **Incidencias y tiempos muertos** por Orden de Área.
- **Bitácora F-15** en Excel e **indicadores semanales** por área.
- Formatos **imprimibles** y llenos: F-01, F-02 a F-10 y F-12.
- **Áreas y tiempos:** supervisores por área y tabla de tiempos estándar.

### Almacén (F-11)
- Catálogo de materiales con existencia, punto de reposición (avisa al llegar), costo promedio y kardex.
- Vale de salida: lo pide el área, lo **autoriza Coordinación**, lo **despacha Almacén** (descuenta en el momento), lo firma quien recibe, y se cierra con devolución y desperdicio con su causa. El costo pasa a la OT.

### Cashflow
- Conector con la API de Cashflow: sincroniza clientes (por RNC), envía cotizaciones, **emite la factura fiscal** (Cashflow asigna el NCF / e-CF) y **lee pagos y saldo**. Si el pago cubre el anticipo, el G0 se marca solo.
- Pantalla **Finanzas → Cashflow** con prueba de conexión, sincronización y bitácora de cada llamada. **Modo prueba** (simulador) mientras no haya API key.
- Las rutas y los nombres de campos de la API están en un solo archivo para ajustarlos a la documentación oficial sin tocar el resto.

### Otros
- Accesos nuevos en Personas: **Coordinación** y **Almacén**.
- Anticipos y abonos facturables antes de entregar; la factura final descuenta lo ya facturado.
- Automatizaciones filtrables por área. La tarea diaria también avisa excepciones G0 vencidas y trae pagos de Cashflow.

## 5.0 · 26/10/2026 · Operación completa: órdenes, proyectos, tiempo y finanzas

Adzone Team deja de ser solo tareas y KPIs: ahora lleva el trabajo diario de toda la agencia, de la cotización al cobro.

### Órdenes de trabajo
- **Siete áreas con su propio formulario:** impresión y rotulación, Adzone TV, call center, marketing digital, audiovisual, desarrollo y administración. Por ejemplo, impresión pide medidas, material, acabados e instalación; Adzone TV pide estudio, fecha de grabación, equipo y plataformas; call center pide canales, agentes y metas.
- **Recorrido completo:** solicitada → aprobada → en producción → control de calidad → lista → entregada, más pausa y cancelación con motivo. No se puede saltar etapas.
- **Al aprobar,** el gerente elige responsable, equipo y fecha comprometida, y se crea la **tarea de producción con los pasos del área**. La orden avanza sola con su tarea y, al validarla, queda lista.
- **Tablero arrastrable** (como Monday), tabla y calendario. Indicadores de órdenes abiertas, por aprobar, vencidas, entregadas en el mes y porcentaje a tiempo.
- **Archivos** protegidos (artes, PDF, fotos; hasta 25 MB), **conversación con @menciones** e historial completo.
- **Entrega con nombre de quien recibe.** Finanzas recibe el aviso para facturar.

### Proyectos y clientes
- **Clientes:** directorio con contacto, RNC, proyectos, órdenes y, para Finanzas, facturado, cobrado y saldo.
- **Proyectos:** tabla, tablero y **cronograma (Gantt)** con la línea de hoy. Cada proyecto tiene sus tareas en tablero o cronograma, sus órdenes, una conversación, horas trabajadas y, para quien gestiona, monto vendido, facturado y margen.
- Las tareas ahora tienen **proyecto, fecha de inicio y horas estimadas**.

### Tiempo y carga
- **Cronómetro** siempre visible en la barra superior: se inicia desde una tarea, una orden o un proyecto, y solo corre uno a la vez. Empezarlo en una tarea pendiente la marca como empezada.
- **Mi semana:** gráfico por día y registros, con opción de anotar tiempo a mano hasta un mes atrás.
- **Carga del equipo:** horas anotadas más horas pendientes estimadas, comparadas con la capacidad de cada persona (44 horas por defecto). Avisa de la sobrecarga.
- **Reporte de horas** por proyecto, cliente, orden, persona o departamento, con el porcentaje facturable.

### Finanzas operativas (Administración y dirección)
- **Cotizaciones** con ITBIS del 18 % calculado por línea y líneas exentas. Al aprobarlas se puede crear la orden de trabajo de una vez.
- **Facturas** desde una cotización, desde una orden o desde cero. Se emiten con días de crédito y se les anota el NCF o e-CF del sistema contable.
- **Pagos** parciales; la factura queda pagada sola y no se puede cobrar de más.
- **Gastos** por categoría, con proveedor, proyecto y comprobante.
- **Resumen del mes:** facturado, cobrado, gastos, resultado, por cobrar, vencido, **antigüedad de cuentas por cobrar**, clientes que deben y **órdenes sin facturar**.
- **Rentabilidad** por proyecto o cliente: facturado sin ITBIS, menos gastos, menos costo de las horas.
- Versión **para imprimir o PDF** de cotizaciones y facturas con la marca.

### Automatizaciones y n8n
- Reglas «cuando pase X, haz Y» con diez eventos: órdenes, tareas, cotizaciones, facturas y pagos. Las acciones son **avisar**, **crear una tarea** y **webhook a n8n**, firmado con HMAC si se configura `AUTOMATIZACIONES_SECRETO`.
- La plataforma trae cuatro reglas: orden lista, orden entregada (aviso a Finanzas), orden vencida y factura vencida.
- Una regla con error no frena el trabajo y queda en la bitácora. Las de vencimiento se ejecutan una sola vez por orden o factura.

### Para trabajar más rápido
- **Buscador global con Ctrl+K** (o la tecla /).
- Botón **Crear** en todas las pantallas.
- El inicio muestra las órdenes a tu cargo y, a quien gestiona, las que esperan aprobación y las vencidas.
- En el celular, la barra inferior tiene Inicio, Mis tareas, Órdenes y Validar (o Tiempo), y las acciones de cada orden quedan abajo, al alcance del pulgar.
- Nuevo departamento oficial: **Call Center**.

### Pruebas
- **Backend:** 70 pruebas automáticas, 23 de ellas nuevas para órdenes, permisos, flujo, tiempo, finanzas, automatizaciones y buscador.
- **Navegador:** se recorrió el ciclo completo de punta a punta (pedir → aprobar con arrastre → cronómetro → pasos → entregar → validar → entregar al cliente → facturar → cobrar), además del buscador y las automatizaciones, en PC y celular.


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
