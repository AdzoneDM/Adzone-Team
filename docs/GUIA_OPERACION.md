# Guía de operación: formatos ADZONE, almacén, finanzas y Cashflow

Cómo se trabaja en Adzone Team desde la versión 6. Las OT siguen los **formatos controlados ADZONE** (F-01 a F-15): ahora se llenan, se firman y se consultan en la plataforma.

## El recorrido de un trabajo (E1 a E7)

1. **Comercial llena la OT Maestra (F-01)** con **Crear → Orden de trabajo**: datos del cliente, alcance y exclusiones, las **áreas que intervienen en su secuencia** (las que tienen el mismo número trabajan a la vez), fecha requerida, prioridad (Normal, Urgente, Emergencia), monto, anticipo y la lista **G0**. El botón **Calcular** propone la fecha comprometida: tiempo estándar + cola del área + aprobación del cliente (24 h × rondas) + colchón (20 %, emergencia 30 %). Al guardarla queda como **solicitud S-AA-0000** y le llega a Coordinación.
2. **G0 · Coordinación de Producción la recibe.** Si falta una casilla, la **rechaza** con la causa y vuelve a Comercial (que corrige y la **reenvía**). Sin anticipo confirmado no se numera, salvo **excepción de Gerencia General** (Administración recibe el aviso de regularizar en 24 horas). Al **liberarla** recibe su número **OT-AA-0000 (E1)** y se emite una **Orden de Área** por cada área: `OT-26-0001-DIS`, `OT-26-0001-IMP`…
3. **G1 · El supervisor del área la recibe** con su lista de entrada. Si falta algo, la rechaza (Coordinación la completa y la **reemite**). Al recibirla asigna al ejecutor y su apoyo: se crea la **tarea con las etapas del formato** (E2). Una área no recibe mientras la anterior en la secuencia no termina.
4. **E3 · Ejecución.** El ejecutor trabaja su tarea (cronómetro, etapas, evidencia), pide **material con vale (F-11)** y anota **incidencias y tiempos muertos**.
5. **Revisión interna (Diseño, Audiovisuales y Marketing).** Con la propuesta lista, el ejecutor toca **Pedir revisión interna**. El Gerente de Marketing la revisa con el **checklist de validación final** (marca, mensaje, calidad, trazabilidad, conversión y calendario) y da **visto bueno** o pide ajustes. Sin visto bueno no se envía al cliente; cada nueva versión que pida el cliente vuelve a pasar por aquí.
6. **G4 · Aprobación del cliente (E4)** en Diseño, Marketing, Audiovisual, Software y Call Center: **Enviar al cliente** y luego registrar la respuesta. Para aprobar hay que marcar por dónde aprobó por escrito (WhatsApp archivado, correo, firma). Si se agotan las rondas incluidas, la plataforma avisa que la siguiente se cobra con una **Solicitud de Cambio (F-14)**.
7. **G3 · Control de calidad.** El ejecutor entrega su tarea y el supervisor la **valida** marcando la lista G3 (en **Por validar** o en la Orden de Área). Sin G3 completo, o sin G4 cuando aplica, no se valida. Si la devuelve puede registrar la causa del **retrabajo**.
8. **G2/G5 · Traspaso con doble firma (F-13).** El área entrega con su lista de salida a la siguiente área (o a Coordinación si sale al cliente). **Quien recibe verifica y firma**; si rechaza, el trabajo vuelve al área con la causa y cuenta como retrabajo. Aceptado, la Orden de Área queda **terminada (E5)**. Cuando todas terminan, la OT queda **Lista para entregar**.
9. **Acta de entrega / instalación (F-12).** Coordinación (o el supervisor de Instalación) la prepara. **Administración libera la salida (G5)**: con saldo pagado, o con autorización escrita de Gerencia General. En el sitio se marca la verificación y **el cliente firma en la pantalla** del celular (o, si no puede, se suben fotos y su nombre). La OT queda **Entregada (E6)**.
10. **Factura y cierre (G6).** Sin acta firmada no se factura (salvo los anticipos y abonos). Administración factura —**en Cashflow, que asigna el NCF / e-CF**— y **cierra la OT (E7)**: la plataforma calcula el **costo real** (horas × costo por hora, materiales de los vales, servicios externos, retrabajos y gastos) y el **margen** contra lo cotizado.

La OT se puede **pausar**, **reanudar** o **cancelar** (Coordinación). Cualquiera que trabaje en ella puede registrar una **Solicitud de cambio o retrabajo (F-14)**; Coordinación la autoriza (si es sin costo para el cliente, Gerencia General). Al autorizar un cambio cobrable, el monto se suma a la OT y Administración recibe el aviso; si cambia la fecha, se actualiza la fecha comprometida.

## Tiempos: cronograma de producción y ventanas de anticipación

- En la OT, para Diseño y Audiovisuales se elige el **tipo de trabajo del cronograma estimado de producción** y la cantidad (por ejemplo, 3 flyers = 3 horas). La plataforma pone las horas, los días y lo que produce; todo se puede ajustar. Las horas pasan a la tarea del ejecutor y cuentan en la carga del equipo.
- **Ventanas de anticipación del contenido** (Marketing, Diseño, Audiovisuales): ideal 15 días calendario, seguro 10, emergencia 7 días hábiles (solo con plantillas, copys aprobados y automatizaciones estables). El formulario avisa cuando la fecha pedida queda por debajo del mínimo.
- La tabla completa está en **Áreas y tiempos**: horas, días y cómo lo dice el cronograma.

## Herramientas e IA

Cada Orden de Área muestra las **herramientas recomendadas** para esa área (Claude, Gemini y ChatGPT para pensar y documentar; Canva y Nano Banana para producir y visualizar; Veo 3, Flow, Runway, CapCut y Adobe para audiovisual; n8n y GitHub para el control). En la especificación se marcan las **herramientas usadas**. Regla: la IA propone, acelera y documenta; el equipo decide, valida y responde por la calidad. Los prototipos y piezas con IA se identifican y se aclaran al cliente (está en el control de calidad).

## Quién hace qué

| Quién | Hace |
| --- | --- |
| Comercial (quien vende) | Llena la OT Maestra, ve el monto de lo que vendió, reenvía si la devuelven, pide cambios |
| Coordinación de Producción (acceso «Coordinación») | G0: libera y numera o rechaza; reemite OA; agrega áreas; autoriza vales y cambios; recibe las salidas al cliente (G5); prepara el acta; pausa y cancela. Ve todas las OT |
| Supervisor de área (gerente del departamento, o los asignados en **Áreas y tiempos**) | G1: recibe y asigna; G3: valida; firma los traspasos que llegan a su área; anota costos externos |
| Ejecutor y apoyo | Trabajan la tarea, envían al cliente (G4), piden material, registran incidencias, entregan con traspaso |
| Almacén (acceso «Almacén») | Despacha vales (descuenta la existencia), cierra con devolución y desperdicio, registra entradas y ajustes |
| Administración / Finanzas | Confirma anticipos, libera la salida (G5), factura en Cashflow, cobra, cierra la OT (G6) |
| Gerencia General (administradores) | Excepción sin anticipo, salida con saldo, cambios sin costo; asigna supervisores de área |

Los accesos «Coordinación», «Almacén» y «Finanzas» se dan en **Personas → editar → Accesos adicionales**.

Cada colaborador ve las OT que pasan por las áreas de su departamento, las que pidió o vendió y en las que trabaja. Los montos solo los ven Administración, Coordinación, la dirección y quien vendió.

## Pantallas

- **Órdenes de trabajo:** tablero de OT por etapa, **Por área** (la cola de cada área con sus Órdenes de Área: E1 espera G1, E2, E3, E4, E5), tabla y calendario. Arriba, los números del día: por revisar en G0, devueltas, vencidas, listas para entregar, entregadas por cerrar y % a tiempo.
- **OT:** pestañas F-01 (lo que llenó Comercial y el G0), Áreas (con los vales de traspaso), Entrega y cierre (acta, facturas, costo real y margen), Cambios y Conversación.
- **Orden de Área:** las compuertas G1 → E3 → G4 → G3 → G2 en una línea, y lo que toca hacer ahora aparece arriba. Especificación del formato, etapas, materiales, incidencias, costos y archivos del área.
- **Imprimir:** F-01, cada Orden de Área (F-02 a F-10) y el acta F-12 salen llenas, listas para imprimir o guardar en PDF.
- **Bitácora F-15:** descarga en Excel (CSV) de todas las OT con fechas, áreas, rondas, retrabajos, monto, costo y margen.
- **Indicadores:** además de lo de abajo, **velocidad, calidad y control**: horas de brief a propuesta, % aprobado a la primera, ajustes en revisión interna y rendimiento (horas del cronograma ÷ horas reales). Por área y por semana: terminadas, % a tiempo, cola, vencidas, rechazos en G1, traspasos rechazados, retrabajos por causa, minutos perdidos, rondas de G4 y desperdicio. Y de las OT: solicitadas, liberadas, devueltas en G0, entregadas, a tiempo y margen de las cerradas.
- **Almacén:** vales por autorizar, por despachar y despachados; materiales con existencia, punto de reposición (avisa al llegar), costo promedio y kardex.
- **Áreas y tiempos:** supervisores de cada área y la tabla de tiempos estándar (Tabla 8.2), que el formulario de la OT sugiere al llenar los días.

## Finanzas y Cashflow

- **Cotización aprobada → OT:** al marcarla aprobada se puede crear la solicitud F-01 con el cliente, el monto y la casilla de cotización ya marcada.
- **Anticipo:** desde la OT, **Factura de anticipo**. Al registrar su pago (o al leerlo de Cashflow), la casilla de anticipo del G0 se marca sola. También se pueden facturar **abonos** antes de entregar.
- **Factura final:** con el acta firmada, **Facturar** crea el borrador por lo que falta (monto menos anticipos) y **Emitir en Cashflow (NCF)** la crea en Cashflow, que asigna el comprobante fiscal: crédito fiscal (31) si el cliente tiene RNC, consumo (32) si no, gubernamental (45).
- **Pagos:** se registran aquí o se traen de Cashflow (**Traer pagos de Cashflow**, o cada día con la tarea programada).
- **Finanzas → Cashflow:** estado de la conexión, **Probar conexión**, **Traer pagos ahora** y la bitácora de cada llamada. Sin API key funciona en **modo prueba**: NCF simulados y nada sale de la plataforma.
- Rentabilidad, gastos, cuentas por cobrar e impresión siguen como en la versión 5.

## Automatizaciones (dirección)

Reglas «cuando pase X, haz Y» que avisan, crean una tarea o envían los datos a **n8n**. Ahora se pueden filtrar por **área** (por ejemplo, «OT que pasan por Instalación»). La tarea diaria (`python manage.py tareas_diarias`) revisa vencimientos, avisa de las excepciones G0 sin regularizar y, si Cashflow está conectado, trae los pagos.

## Buscar y crear rápido

- **Ctrl+K** (o **/**) busca OT por número, solicitud o cliente, proyectos, clientes, tareas y, para Finanzas, facturas y cotizaciones.
- **Crear** abre una OT, una tarea, un proyecto, un cliente o una cotización.
- En los comentarios, **@usuario** le avisa a esa persona.

## Formatos de cada área

Cambiar un formato es cambiar `backend/apps/operaciones/formatos.py` (no hace falta tocar la base de datos).

### F-02 · Diseño (DIS)

Departamento: Marketing. Revisión interna con checklist de validación final antes del cliente. Requiere aprobación escrita del cliente (G4).

Herramientas recomendadas: Canva (Brand Kit) · Adobe · Nano Banana para mockups y variantes · ChatGPT para racionales y revisar contra marca · Runway.

- **G1 · entrada:** OT Maestra liberada (E1); Tipo de trabajo definido; Medidas y formato final; Cantidad de piezas; Textos definitivos del cliente; Logo vectorial recibido; Fotografías en resolución; Referencias visuales; Manual de marca del cliente; Destino de la pieza definido; Fecha interna aceptada.
- **Especificación:** Tipo de trabajo *, Pieza *, Formato / dimensiones, Resolución / sangrado, Perfil de color / códigos, Destino, Instrucciones creativas, concepto, colores, tipografías, referencias y restricciones, Archivos de salida requeridos, Nombre del archivo (inicia con No. OT), Versión entregada, Herramientas usadas.
- **Etapas:** Recepción del brief y del plan de contenido de Marketing → Revisión de requerimientos (reunión con el cliente si hace falta) → Desarrollo de la propuesta gráfica (cronómetro activo, arte subido a la plataforma) → Revisión interna del Gerente de Marketing → Validación del cliente → Correcciones → Arte final entregado al Community Manager para publicación.
- **G3 · calidad:** Ortografía revisada; Teléfonos correctos; Dirección correcta; Redes sociales; Código QR probado; Precios y fechas; Logo en versión correcta; Medidas contra la OT; Resolución de imágenes; Sangrado y márgenes; Perfil de color; Archivo nombrado con No. OT; Respaldo guardado; Prototipos o piezas hechas con IA identificados y aclarados al cliente.
- **G2/G5 · salida:** Arte final en el formato que exige el área receptora; Archivo editable respaldado; Aprobación del cliente adjunta; Medidas confirmadas; Cantidad de piezas confirmada.

### F-03 · Marketing digital y contenido (MKT)

Departamento: Marketing. Revisión interna con checklist de validación final antes del cliente. Requiere aprobación escrita del cliente (G4).

Herramientas recomendadas: Claude para briefs y racionales · Gemini para investigación y benchmarking · ChatGPT para copys y control de calidad · Canva · n8n para alertas y aprobaciones.

- **G1 · entrada:** OT o iguala vigente; Accesos a las cuentas del cliente; Manual de marca del cliente; Objetivos de la campaña definidos; Público objetivo definido; Calendario de fechas clave; Presupuesto de pauta confirmado; Fecha interna aceptada.
- **Especificación:** Período que cubre *, No. de posts, No. de historias, No. de reels / videos, Plataformas *, Ejes temáticos · Branding %, Servicios %, Ofertas %, Educación %, Otro %, Estrategia, mensajes clave, tono y llamados a la acción, Piezas solicitadas a otras áreas, Presupuesto de pauta (RD$), Herramientas usadas.
- **Etapas:** Recepción del brief: objetivos y estrategia → Creación del plan de contenido alineado al brief → Revisión interna y aprobación del cliente → Envío del plan a Diseño / Audiovisuales (coordinar fecha de grabación) → Recepción de artes y videos aprobados → Programación y publicación (Community Manager) → Monitoreo y comunidad → Reporte de resultados.
- **G3 · calidad:** Plan aprobado antes de producir; Piezas revisadas contra el manual de marca; Copys revisados y sin errores; Hashtags y menciones correctos; Horarios de publicación definidos; Pauta configurada y verificada; Enlaces probados; Reporte con métricas del período; Prototipos o piezas hechas con IA identificados y aclarados al cliente.
- **G2/G5 · salida:** Checklist de validación final aprobado antes de publicar; Piezas publicadas según calendario; Evidencia de publicación adjunta; Reporte de resultados entregado al cliente; Pauta liquidada y conciliada con Administración.

### F-04 · Audiovisuales (AUD)

Departamento: Audiovisual. Revisión interna con checklist de validación final antes del cliente. Requiere aprobación escrita del cliente (G4).

Herramientas recomendadas: Claude para guiones, escaletas y shot lists · Gemini para hooks · Nano Banana para miniaturas · Veo 3 para teasers demo · Flow para storyboard · Runway y CapCut / Adobe para el acabado.

- **G1 · entrada:** OT Maestra liberada; Plan de contenido o guion recibido; Fecha y hora de grabación confirmada con el cliente; Locación y acceso confirmados; Lista de tomas definida; Formato y duración de salida definidos; Equipo disponible y reservado; Fecha interna aceptada.
- **Especificación:** Tipo de trabajo *, Fecha y hora de grabación, Locación / dirección, Duración final, Formatos de salida, Equipo requerido, Guion, lista de tomas, personas o productos que aparecen, música y referencias, Respaldo del material (ubicación 1), Respaldo del material (ubicación 2), Herramientas usadas.
- **Etapas:** Recepción del brief, plan de contenido y fecha de grabación → Estudio del plan y preparación del equipo → Grabación del contenido (fotos y videos) → Respaldo del material (mismo día) → Desarrollo de la propuesta visual / edición (cronómetro activo, subida a la plataforma) → Revisión interna del Gerente de Marketing → Validación del cliente → Correcciones → Exportación final y entrega al Community Manager.
- **G3 · calidad:** Audio nivelado y sin ruido; Colorimetría consistente; Logos y textos correctos; Duración exacta por plataforma; Subtítulos si aplica; Derechos de música verificados; Exportado en todos los formatos; Doble respaldo confirmado; Miniatura generada; Hook claro en los primeros segundos; Prototipos o piezas hechas con IA identificados y aclarados al cliente.
- **G2/G5 · salida:** Piezas exportadas y nombradas con No. OT; Aprobación del cliente adjunta; Material bruto respaldado y ubicado; Entregado a Marketing para publicación.

### F-05 · Podcast · Adzone TV (POD)

Departamento: Adzone TV.

> Antes de grabar: prueba de audio, luz y encuadre 30 minutos antes; consentimiento de uso de imagen firmado por cada invitado.

- **G1 · entrada:** OT Maestra liberada; Tema y escaleta recibidos; Invitados confirmados con hora de llegada; Consentimiento de uso de imagen previsto; Duración objetivo definida; Cantidad de clips derivados definida; Arte de portada disponible o solicitado; Estudio reservado.
- **Especificación:** Episodio No., Título / tema *, Fecha y hora de grabación, Duración objetivo, Clips derivados, Invitado(s) · nombre y cargo exactos para rótulos, Moderador / host, Montaje técnico, Escaleta / bloques del episodio, Plataformas de destino.
- **Etapas:** Preparación y prueba de estudio → Grabación → Respaldo del material → Edición del episodio → Generación de clips → Revisión interna → Aprobación → Publicación / entrega.
- **G3 · calidad:** Niveles de audio por canal; Sincronía entre cámaras; Nombres y cargos correctos en rótulos; Duración de clips por plataforma; Portada y miniatura listas; Descripción y capítulos redactados; Consentimientos firmados archivados; Doble respaldo confirmado.
- **G2/G5 · salida:** Episodio máster exportado; Clips exportados por plataforma; Portada y descripción entregadas; Entregado a Marketing para publicación.

### F-06 · Impresión (IMP)

Departamento: Impresión.

> Prohibido corregir el arte en máquina. Todo error de archivo se devuelve a Diseño con el vale de traspaso marcado como rechazado.

- **G1 · entrada:** Arte final aprobado por el cliente (adjunto); PDF en curvas, escala declarada; Sangrado correcto para el equipo; Perfil de color definido; Medidas confirmadas contra la OT; Cantidad y caras definidas; Material y acabados especificados; Existencia confirmada con Almacén; Vale de material emitido; Fecha interna aceptada.
- **Especificación:** Producto, medidas y material *, Material / sustrato *, Marca / referencia, Espesor / gramaje, Color, Equipo asignado, Perfil / modo, Pasadas, Resolución, Secado / curado, Tinta blanca / barniz, Prueba de color, Corte y acabados.
- **Etapas:** Preprensa y verificación del archivo → Prueba de color → Impresión → Corte / acabado → Empaque → Entrega.
- **G3 · calidad:** Medidas verificadas con cinta; Cantidad completa; Color contra prueba aprobada; Sin bandas, rayas ni marcas; Laminado sin burbujas; Ojales y dobleces según especificación; Piezas limpias; Empaque protegido; Identificado con No. OT; Fotografías tomadas.
- **G2/G5 · salida:** Piezas contadas e identificadas con No. OT; Empacadas y protegidas; Sobrante de material devuelto a almacén; Consumo y desperdicio registrados; Liberación de Administración si sale al cliente (G5).

### F-07 · Letreros (LET)

Departamento: Impresión.

- **G1 · entrada:** Arte final aprobado con medidas reales; Levantamiento del sitio con fotografías; Tipo de letrero e iluminación definidos; Superficie de instalación confirmada; Voltaje y punto eléctrico confirmados; Altura y medio de acceso definidos; Permisos gestionados si aplica; Material disponible en almacén; Fecha interna aceptada.
- **Especificación:** Tipo de trabajo *, Iluminación, Piezas y medidas, Materiales principales, Frente, Retorno, Espesor / calibre, Estructura / bastidor, Acabado / color, Tipo de LED, Temperatura de color, Fuente de poder, Voltaje, Registro / acceso de mantenimiento, Superficie, Medio de acceso, Equipo de protección obligatorio, Sistema de fijación / plantilla, Horario permitido de instalación.
- **Etapas:** Diseño técnico y despiece → Corte / conformado → Encajonamiento → Pintura / acabado → Ensamble e iluminación → Pruebas de encendido → Embalaje → Instalación.
- **G3 · calidad:** Estructura firme; Soldaduras revisadas; LED probados por bloque; Fuente probada bajo carga; Cableado protegido; Iluminación uniforme; Acabado sin golpes; Medidas contra el levantamiento; Plantilla de fijación lista; Fotografías tomadas.
- **G2/G5 · salida:** Letrero probado encendido antes de salir; Piezas protegidas para transporte; Herramientas y equipo de seguridad cargados; Plantilla y tornillería incluidas; Liberación de Administración (G5).

### F-08 · Fabricación (FAB)

Departamento: Impresión.

- **G1 · entrada:** Plano o archivo de corte recibido; Material, espesor y calibre definidos; Tolerancias definidas; Tipo de unión y acabado definidos; Cantidad confirmada; Existencia de material confirmada; Vale de almacén emitido; Fecha interna aceptada.
- **Especificación:** Pieza, medidas y materiales *, Material principal *, Espesor / calibre, Marca / referencia, Color, Procesos requeridos, Equipo / máquina, Plano / archivo, Tolerancia / precisión, Tipo de unión / acabado, Seguridad obligatoria.
- **Etapas:** Preparación / trazado → Corte / mecanizado → Doblado / perforado → Soldadura / ensamble → Pintura / terminación → Empaque / entrega.
- **G3 · calidad:** Medidas dentro de tolerancia; Escuadra y nivelación; Soldaduras sin porosidad; Sin rebabas ni filos cortantes; Acabado uniforme; Cantidad completa; Empaque protegido para transporte; Identificado con No. OT; Fotografías tomadas.
- **G2/G5 · salida:** Piezas contadas y protegidas; Consumo y desperdicio registrados; Sobrante devuelto a almacén; Herrajes y tornillería incluidos; Entregado a Letreros / Eventos / Instalación.

### F-09 · Producción de eventos (EVT)

Departamento: Impresión.

- **G1 · entrada:** OT Maestra liberada; Fecha, hora de montaje y de inicio confirmadas; Dirección y contacto del local; Levantamiento del sitio con fotos y medidas; Cantidad de invitados; Listado de piezas y estructuras definido; Requerimientos eléctricos confirmados; Permisos y accesos gestionados; Hora límite de desmontaje acordada; Fecha de corte de producción fijada (48 h antes).
- **Especificación:** Tipo de evento *, Fecha del evento *, Hora de montaje, Hora de inicio, Invitados, Local / dirección exacta, Contacto en sitio (nombre y teléfono), Elementos del montaje, Piezas solicitadas a otras áreas (fecha de corte: 48 h antes del montaje), Vehículos asignados, Cuadrilla (cantidad y nombres), Supervisor en sitio, Hora de salida del taller, Herramientas y equipo, Plan de contingencia (lluvia, falla eléctrica, retraso del local).
- **Etapas:** Levantamiento del sitio → Plan de montaje por hora → Emisión de OA a las áreas → Recepción de piezas en almacén → Carga y traslado → Montaje → Supervisión durante el evento → Desmontaje → Retorno e inventario.
- **G3 · calidad:** Montaje conforme al plano; Estructuras aseguradas y ancladas; Pruebas eléctricas realizadas; Prueba de sonido y video; Branding alineado al manual del cliente; Área limpia antes de la entrega; Rutas de evacuación despejadas; Reporte fotográfico completo; Inventario de retorno verificado.
- **G2/G5 · salida:** Evento montado y aprobado por el cliente; Acta de conformidad firmada; Reporte fotográfico entregado; Material devuelto e inventariado; Daños o faltantes reportados a Coordinación.

### F-10 · Desarrollo de software y apps (SOF)

Departamento: Tecnología. Requiere aprobación escrita del cliente (G4).

> Cada entrega tiene su propio G4. Todo cambio pedido después de aceptada una entrega es cambio de alcance cobrable (F-14), no corrección.

- **G1 · entrada:** OT Maestra liberada; Documento de alcance funcional firmado; Criterios de aceptación escritos; Accesos y credenciales recibidos; Identidad visual del cliente recibida; Hosting, dominio y correo definidos; Responsable técnico del cliente identificado; Cronograma de entregas acordado.
- **Especificación:** Tipo de solución *, Tecnología / stack, Hosting / servidor, Dominio, Repositorio, Módulos y entregas, Fecha de puesta en producción, Capacitación al cliente, Manual entregado, Período de garantía, Credenciales entregadas a (nombre y cargo), Respaldo automático configurado (frecuencia).
- **Etapas:** Levantamiento funcional → Arquitectura y estimación → Desarrollo por entregas → Pruebas funcionales → Despliegue a ambiente de prueba → Aprobación del cliente → Despliegue a producción → Capacitación y entrega.
- **G3 · calidad:** Criterios de aceptación cumplidos uno por uno; Probado en móvil y escritorio; Velocidad de carga aceptable; Formularios probados con datos reales; Certificado SSL activo; Respaldo automático configurado; Accesos administrativos entregados; Código versionado en el repositorio; Manual de usuario entregado.
- **G2/G5 · salida:** Sistema en producción y funcionando; Acta de aceptación firmada por el cliente; Credenciales entregadas y registradas; Capacitación realizada; Garantía y soporte explicados por escrito.

### F-12 · Instalación (INS)

Departamento: Impresión.

- **G1 · entrada:** OT Maestra liberada; Piezas listas y liberadas por las áreas; Dirección del sitio y contacto confirmados; Acceso y horario confirmados con el cliente; Ruta, vehículo y chofer asignados; Permisos en mano si aplica.
- **Especificación:** Modalidad *, Dirección del sitio, Contacto en sitio, Fecha y hora.
- **Etapas:** Carga y verificación → Traslado → Instalación / entrega → Verificación con el cliente → Acta firmada.
- **G3 · calidad:** Medidas verificadas; Cantidad completa; Color y acabado correctos; Sin defectos ni golpes; Fijación segura y nivelada; Pruebas eléctricas realizadas; Iluminación probada; Funcionamiento verificado con el cliente; Área limpia; Material sobrante retirado; Fotografías antes / durante / después.
- **G2/G5 · salida:** Acta de entrega firmada por el cliente; Fotografías adjuntas; Material sobrante devuelto a almacén.

### CC-01 · Call Center (CCT)

Departamento: Call Center. Requiere aprobación escrita del cliente (G4).

- **G1 · entrada:** OT Maestra liberada; Base de datos de contactos recibida; Guion aprobado por el cliente; Líneas y herramientas configuradas; Agentes asignados y capacitados; Metas de contacto y conversión definidas; Fecha interna aceptada.
- **Especificación:** Servicio *, Canales *, Agentes *, Horario, Inicio de la campaña, Fin de la campaña, Meta de contactos, Meta de conversión (%), Base de datos y herramientas.
- **Etapas:** Recepción de base de datos y guion → Capacitación de agentes → Configuración de líneas → Arranque de la campaña → Seguimiento diario → Informe de resultados.
- **G3 · calidad:** Guion seguido en llamadas monitoreadas; Registro completo de cada contacto; Metas del período medidas; Quejas atendidas y documentadas; Datos del cliente protegidos.
- **G2/G5 · salida:** Informe de resultados entregado al cliente; Base de datos actualizada devuelta; Grabaciones respaldadas.

### AD-01 · Gestión administrativa (ADM)

Departamento: Administración.

- **G1 · entrada:** Soporte del gasto o gestión recibido; Monto y beneficiario confirmados; Presupuesto disponible; Fecha límite definida.
- **Especificación:** Gestión *, Proveedor o beneficiario, Monto, Moneda, Forma de pago, ¿Requiere comprobante fiscal?, Detalle.
- **Etapas:** Revisar soporte y montos → Aprobación → Ejecutar la gestión → Archivar comprobante.
- **G3 · calidad:** Montos verificados contra el soporte; Aprobación registrada; Comprobante archivado.
- **G2/G5 · salida:** Gestión registrada en el sistema contable; Soporte digital adjunto.

\* obligatorio para dar la especificación por completa.
