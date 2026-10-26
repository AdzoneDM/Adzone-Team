# Guía de operación: órdenes, proyectos, tiempo y finanzas

Cómo se trabaja en Adzone Team desde la versión 5. Para todo el equipo.

## El recorrido de un trabajo

1. **Se pide una orden de trabajo.** Cualquiera puede pedirla con **Crear → Orden de trabajo**: ventas, un gerente o quien atiende al cliente. Primero se elige el área y luego se llena el formulario de esa área. Una lona pide medidas y material; un podcast pide estudio y fecha de grabación. La orden llega a quien gestiona ese departamento.
2. **El gerente del área la aprueba.** Elige al responsable, al equipo y la **fecha comprometida**. Al aprobarla se crea sola la **tarea de producción** con los pasos del área, y esos pasos se pueden cambiar.
3. **El equipo la produce.** Empieza la tarea (o el cronómetro), marca los pasos y la entrega con evidencia. La orden avanza sola: **En producción**, luego **Control de calidad**.
4. **Se valida.** Cuando el gerente valida la tarea con estrellas, la orden queda **Lista para entregar**, quien la pidió recibe el aviso y la tarea cuenta para el puntaje y los KPIs.
5. **Se entrega.** Se anota quién recibió. Finanzas recibe el aviso **Por facturar**.
6. **Se factura y se cobra.** En **Finanzas → Resumen**, la orden aparece en «sin facturar». Con **Facturar** se crea la factura en borrador; después se emite y se registran los pagos.

La orden se puede **pausar** y **reanudar**, o **cancelar** con un motivo; al cancelarla se cancelan sus tareas. En el **Tablero** se arrastran las tarjetas entre etapas. Si se arrastra a «Aprobada», se abre la aprobación; si se arrastra a «Entregada», se pide quién recibe.

## Quién ve y quién hace qué

| Quién | Ve | Puede |
| --- | --- | --- |
| Colaborador | Las órdenes de su departamento, las que pidió y en las que trabaja | Pedir órdenes, comentar, subir archivos, trabajar y entregar sus tareas, usar el cronómetro |
| Gerente o encargado | Además, las de los departamentos que dependen de su puesto y las que pidió su gente | Aprobar, asignar, mover, pausar, entregar y cancelar órdenes; crear proyectos; ver montos y rentabilidad de sus proyectos |
| Finanzas (Administración) | Todo | Cotizaciones, facturas, cobros, gastos, rentabilidad; facturar órdenes |
| Dirección (administradores) | Todo | Además, configurar automatizaciones, personas, KPIs y reglas del puntaje |

Los montos (precio de una orden, monto vendido de un proyecto) solo los ven Finanzas, la dirección y quien gestiona.

## Proyectos

Un proyecto agrupa las tareas y órdenes de un mismo trabajo grande, por ejemplo el Torneo Superior o un sitio web con su tienda. Tiene tres vistas: **Tabla**, **Tablero** por estado y **Cronograma**. Dentro de cada proyecto están sus tareas (en tablero o cronograma), sus órdenes, una conversación y los números: horas trabajadas y, para quien gestiona, cuánto se vendió, cuánto se facturó y el margen.

## Tiempo y carga

- **Cronómetro:** se inicia desde una tarea, una orden o un proyecto, o escribiendo en qué se trabaja. Corre uno a la vez: si se empieza otro, el anterior se guarda. Mientras corre, se ve arriba en todas las pantallas. Si alguien lo olvida encendido, se cierra en 12 horas.
- **Anotar tiempo:** para lo que se hizo sin cronómetro, como una reunión o una visita. Se puede anotar hasta un mes hacia atrás.
- **Carga del equipo** (gerentes): para cada persona compara las horas que anotó en la semana más las horas estimadas de sus tareas pendientes con su capacidad, que es de 44 horas por defecto y se cambia en el perfil. Por encima del 100 % significa que está sobrecargada.
- **Reporte de horas:** horas por proyecto, cliente, orden, persona o departamento, y qué porcentaje fue facturable.

## Finanzas

- **Cotización → aprobada:** al marcarla aprobada se puede crear de una vez la orden de trabajo del área, con el monto ya puesto.
- **Facturas:** se crean desde una cotización aprobada, desde una orden lista o entregada, o desde cero. El ITBIS (18 %) se calcula por línea y hay líneas exentas. El **NCF o e-CF** se copia del sistema contable, porque la plataforma no emite comprobantes fiscales.
- **Pagos:** se registran pagos parciales; cuando el saldo llega a cero, la factura queda **Pagada**. No se puede cobrar de más.
- **Gastos:** con categoría, proveedor, proyecto y foto o PDF del comprobante.
- **Rentabilidad:** por proyecto o por cliente se calcula lo facturado sin ITBIS, menos los gastos, menos el costo de las horas trabajadas (horas por el costo por hora de cada persona).
- **Imprimir o PDF:** cada cotización y factura tiene una versión con la marca para imprimir o guardar como PDF.

## Automatizaciones (dirección)

Son reglas del tipo «cuando pase X, haz Y». La plataforma trae cuatro:

- Orden lista: avisar a quien la pidió.
- Orden entregada: avisar a Finanzas para facturar.
- Orden vencida: avisar al responsable y a su gerente.
- Factura vencida: avisar a Finanzas.

Cada regla puede **avisar**, **crear una tarea** o **enviar los datos a n8n** por webhook. Por n8n se conectan WhatsApp, el correo, Google Sheets o un asistente de IA. Las reglas de vencimiento se revisan con la tarea diaria (`python manage.py tareas_diarias`) y se ejecutan una sola vez por orden o factura.

## Buscar y crear rápido

- **Ctrl+K** (o la tecla **/**, o la lupa en el celular) busca órdenes, proyectos, clientes, tareas y, para Finanzas, facturas y cotizaciones.
- **Crear** (el botón amarillo de arriba) abre en un toque una orden, una tarea, un proyecto, un cliente o una cotización.
- En los comentarios, **@usuario** le avisa a esa persona.

## Formularios de cada área

Son formatos estándar. Se ajustan en `backend/apps/operaciones/formularios.py`: los campos, las opciones y los pasos de producción salen de ahí. No hace falta tocar la base de datos.

### Impresión y rotulación

Volantes, tarjetas, lonas, viniles, letreros, rotulación de vehículos e instalación. La recibe **Impresión**.

| Dato | Tipo | Obligatorio |
| --- | --- | --- |
| Qué se imprime | Una opción: Volantes, Tarjetas de presentación, Lona / banner, Vinil adhesivo, Vinil microperforado, Rotulación de vehículo, Letrero / valla, Roll-up, Gran formato, Etiquetas, Otro | Sí |
| Cantidad | Número | Sí |
| Ancho (cm) | Número |  |
| Alto (cm) | Número |  |
| Material | Una opción: Papel couché, Papel bond, Cartulina, Lona, Vinil adhesivo, Vinil microperforado, PVC / foam, Acrílico, Metal, Lo decide producción, Otro |  |
| Caras | Una opción: Una cara, Dos caras |  |
| Acabados | Varias opciones: Laminado mate, Laminado brillo, Corte a la medida, Ojales, Bastidor, Troquelado, Barniz UV |  |
| Arte | Una opción: Lo entrega el cliente, Lo diseña ADZONE, Ya está aprobado | Sí |
| ¿Lleva instalación? | Sí / no |  |
| Dirección de instalación o entrega | Texto largo |  |

**Pasos de producción al aprobarla:** Revisar el arte y las medidas → Prueba de color aprobada por el cliente → Impresión → Acabados → Control de calidad → Empaque, entrega o instalación.

### Adzone TV

Programas, podcasts, entrevistas, transmisiones en vivo, spots y publicaciones en adzone.tv. La recibe **Adzone TV**.

| Dato | Tipo | Obligatorio |
| --- | --- | --- |
| Producción | Una opción: Programa, Podcast, Entrevista, Transmisión en vivo, Cobertura de evento, Spot / comercial, Nota para el periódico digital | Sí |
| Programa o espacio | Texto |  |
| Grabación | Fecha y hora |  |
| Lugar | Una opción: Estudio 1, Estudio 2, Exterior / locación del cliente |  |
| Duración (minutos) | Número |  |
| Invitados o talento | Texto largo |  |
| Equipo técnico | Varias opciones: Cámaras, Iluminación, Audio / micrófonos, Teleprompter, Transmisión en vivo, Drone |  |
| Dónde se publica | Varias opciones: YouTube, Facebook, Instagram, TikTok, adzone.tv, Canal de TV |  |
| Patrocinador | Texto |  |

**Pasos de producción al aprobarla:** Guion y pauta → Confirmar invitados y estudio → Grabación → Edición → Revisión final → Publicación y difusión.

### Call center

Atención al cliente, ventas, cobros, soporte, encuestas y agendamiento. La recibe **Call Center**.

| Dato | Tipo | Obligatorio |
| --- | --- | --- |
| Servicio | Una opción: Atención al cliente, Ventas / telemercadeo, Cobros, Soporte técnico, Encuestas, Agendamiento de citas | Sí |
| Canales | Varias opciones: Llamadas entrantes, Llamadas salientes, WhatsApp, Correo, Chat web | Sí |
| Agentes | Número | Sí |
| Horario | Texto |  |
| Inicio de la campaña | Fecha |  |
| Fin de la campaña | Fecha |  |
| Guion | Una opción: Lo entrega el cliente, Lo prepara ADZONE, Ya está aprobado |  |
| Meta de contactos | Número |  |
| Meta de conversión (%) | Número |  |
| Base de datos y herramientas | Texto largo |  |

**Pasos de producción al aprobarla:** Recibir la base de datos y el guion → Capacitar a los agentes → Configurar líneas y herramientas → Arranque de la campaña → Informe de resultados.

### Marketing digital

Redes sociales, campañas pagadas, diseño gráfico, estrategia, SEO y relaciones públicas. La recibe **Marketing**.

| Dato | Tipo | Obligatorio |
| --- | --- | --- |
| Servicio | Una opción: Manejo de redes, Campaña pagada, Diseño gráfico, Estrategia / plan, Correo masivo, SEO, Relaciones públicas, Campaña política | Sí |
| Redes | Varias opciones: Instagram, Facebook, TikTok, LinkedIn, X, YouTube, Google, WhatsApp |  |
| Piezas | Número |  |
| Objetivo | Una opción: Alcance, Interacción, Tráfico, Mensajes, Clientes potenciales, Ventas |  |
| Presupuesto de pauta (RD$) | Monto |  |
| Primera publicación | Fecha |  |
| Público objetivo | Texto largo |  |

**Pasos de producción al aprobarla:** Brief con el cliente → Estrategia y calendario → Diseño y textos → Aprobación del cliente → Programación / publicación → Informe de resultados.

### Audiovisual

Videos, reels, spots, fotografía, cobertura de eventos, drone y animación 3D. La recibe **Audiovisual**.

| Dato | Tipo | Obligatorio |
| --- | --- | --- |
| Pieza | Una opción: Video corporativo, Reel / video corto, Spot, Fotografía de producto, Cobertura de evento, Animación 3D / VFX, Tomas con drone | Sí |
| Rodaje | Fecha y hora |  |
| Locación | Texto |  |
| Duración final (segundos) | Número |  |
| Formatos | Varias opciones: Horizontal 16:9, Vertical 9:16, Cuadrado 1:1, Retrato 4:5 |  |
| Música | Una opción: Con licencia, Original, La entrega el cliente, Sin música |  |
| Rondas de cambios incluidas | Número |  |
| Entregables | Texto largo |  |

**Pasos de producción al aprobarla:** Guion / storyboard → Preproducción → Rodaje → Edición y color → Revisión con el cliente → Entrega final.

### Desarrollo y tecnología

Sitios web, landing pages, apps, tiendas en línea, integraciones, automatizaciones y soporte. La recibe **Tecnología**.

| Dato | Tipo | Obligatorio |
| --- | --- | --- |
| Qué se desarrolla | Una opción: Sitio web, Landing page, App web, App móvil, Tienda en línea, Integración / automatización, Mantenimiento / soporte | Sí |
| Dominio | Texto |  |
| Hosting | Una opción: Servidor de ADZONE, Del cliente, Por definir |  |
| Integraciones | Varias opciones: WhatsApp, Pasarela de pago, CRM, n8n, Google Analytics, Meta Pixel, Correo |  |
| ¿El contenido está listo? | Una opción: Sí, Parcial, No |  |
| Lanzamiento | Fecha |  |
| Funciones principales | Texto largo |  |

**Pasos de producción al aprobarla:** Requerimientos → Diseño (maqueta) → Desarrollo → Pruebas → Aprobación del cliente → Publicación y capacitación.

### Administración y finanzas

Pagos a proveedores, compras, nómina, facturación, cobros, conciliaciones e impuestos. La recibe **Administración**.

| Dato | Tipo | Obligatorio |
| --- | --- | --- |
| Gestión | Una opción: Pago a proveedor, Compra de materiales, Nómina, Facturación a cliente, Cobro a cliente, Conciliación bancaria, Impuestos / declaración, Caja chica, Otro | Sí |
| Proveedor o beneficiario | Texto |  |
| Monto | Monto |  |
| Moneda | Una opción: RD$, US$ |  |
| Forma de pago | Una opción: Transferencia, Cheque, Efectivo, Tarjeta |  |
| ¿Requiere comprobante fiscal? | Sí / no |  |
| Detalle | Texto largo |  |

**Pasos de producción al aprobarla:** Revisar soporte y montos → Aprobación → Ejecutar el pago o la gestión → Archivar comprobante.

