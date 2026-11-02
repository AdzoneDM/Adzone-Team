# Cambios

## 8.0 · 01/11/2026 · Control de horario, monitoreo de actividad y KPIs que se miden solos

Lo mejor de Time Doctor, Teramind, BambooHR y la guía de desempeño de Personio, dentro de Adzone Team.

### Control de horario (Asistencia)
- **Marcar jornada** desde cualquier pantalla (arriba, junto al buscador), en PC o celular, o desde el ícono del agente: entrada, pausa (almuerzo, diligencia, reunión fuera), regreso y salida.
- **Horarios por persona:** días, hora de entrada y salida por día, almuerzo y tolerancia. Arranca con «Oficina (L-V 8-5, sáb 8-12)» = 44 h. Cada persona puede tener su horario y se puede marcar quién no está obligado a marcar (dirección).
- **Cada día se calcula solo:** llegó a tiempo o tarde (minutos), salida temprana, horas trabajadas, pausa, horas extra (desde 15 min), días sin marcar salida, ausencias. El almuerzo no marcado se descuenta. Los días antes de empezar a usar el control no cuentan como ausencias.
- **Hoy** (supervisores): quién trabaja, en pausa, llegó tarde, no ha marcado o tiene permiso, y qué hace su computadora en este momento.
- **Equipo en el mes** con adherencia, puntualidad, asistencia, tardanzas, ausencias, horas y extra, y **Excel**.
- **Correcciones**: el supervisor agrega o borra marcajes con una nota; queda registrado quién lo hizo. Nadie se corrige a sí mismo.
- **Permisos y vacaciones**: se piden en la plataforma, los aprueba el supervisor; los días aprobados no cuentan como ausencia. **Feriados**.

### Monitoreo de actividad (agente de escritorio)
- **Agente para Windows y Mac** (`agente/`): mide cada minuto la aplicación y la ventana en uso, el sitio si aparece, segundos activos e inactivos, nivel de actividad (teclado/ratón, sin guardar teclas) y cambios de ventana. Solo en jornada; visible en la barra de tareas; sigue funcionando sin internet y reenvía después.
- **Productivo, neutral o improductivo por departamento** (como los perfiles de Teramind): 164 reglas iniciales; Facebook, Instagram, TikTok y YouTube son trabajo en Marketing, Audiovisual y Adzone TV e improductivos en el resto. Se editan en Monitoreo → Reglas y se pueden volver a aplicar a los últimos 30 días.
- **Equipo en vivo**: quién está activo y en qué aplicación, tiempo activo, productivo, de foco, nivel de actividad y cambios de ventana por hora.
- **El día de cada persona**: línea de tiempo en bloques de 10 minutos, aplicaciones y sitios con su tiempo, tiempo de foco (bloques de 25+ minutos productivos) y capturas.
- **Capturas de pantalla opcionales** (apagadas por defecto), desenfocadas, borradas a los 30 días.
- **Avisos al supervisor**: llegó tarde, no ha marcado, X minutos inactivo en jornada, marcó pero su computadora no reporta, día con mucho tiempo improductivo. Comando `revisar_jornadas` cada 10 minutos.
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
