# Cambios

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
