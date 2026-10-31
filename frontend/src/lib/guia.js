// Contenido de la guía paso a paso: el recorrido de bienvenida, la guía de cada pantalla y los «¿Cómo hago…?».
// Cada paso: { titulo, texto, objetivo?, ruta? }.
//  - objetivo: selector CSS (o lista de selectores) de lo que se resalta; se usa el primero que se vea en pantalla.
//    Si no hay ninguno visible, el paso sale centrado.
//  - ruta: la pantalla a la que se va antes de mostrar el paso.
//  - para: (sesion) => bool, para mostrar el paso, la guía o la receta solo a quien le toca.

const MENU = ["[data-guia=menu]", "[data-guia=menu-movil]"];
const PESTANAS = "main [role=tablist]";
const TITULO = "main h1";

export function recorridoGeneral(sesion) {
  const nombre = (sesion.usuario?.nombre || "").split(" ")[0];
  if (sesion.esAgente) return [
    { titulo: `¡Bienvenido${nombre ? `, ${nombre}` : ""}!`, texto: "Esta es tu pantalla del call center. Te mostramos en un minuto lo que vas a usar. Puedes volver a ver esta guía desde el botón ? de arriba." },
    { ruta: "/call-center", objetivo: TITULO, titulo: "Tu mes", texto: "Tu puntaje del mes sale de tus KPIs: contactos efectivos contra la meta, conversión o resolución, calidad del monitoreo y adherencia al horario." },
    { ruta: "/call-center", titulo: "Tu campaña", texto: "Cada campaña muestra para quién trabajas, el horario, los canales y tus metas del día. Abre «Guion y protocolos» para tenerlo a mano durante las llamadas." },
    { objetivo: "[data-guia=avisos]", titulo: "Avisos", texto: "La campanita te avisa cuando te asignan una campaña o tu supervisor te manda un recordatorio." },
    { objetivo: "[data-guia=ayuda]", titulo: "¿Dudas? Toca ?", texto: "Aquí vuelves a ver esta guía. ¡Éxitos en tu turno!" },
  ];
  const pasos = [
    { titulo: `¡Bienvenido${nombre ? `, ${nombre}` : ""}!`, texto: "Te enseñamos en un par de minutos dónde está todo y cómo se trabaja en Adzone Team. Avanza con «Siguiente» (o las flechas del teclado). Puedes salir cuando quieras y volver a verlo desde el botón ? de arriba." },
    { ruta: "/", objetivo: MENU, titulo: "El menú", texto: "Aquí están todas las pantallas. «Mi trabajo» es lo tuyo del día a día; «Operación», las órdenes, proyectos y clientes. En el celular el menú está abajo y el resto aparece en «Más»." },
    { ruta: "/", objetivo: TITULO, titulo: "Inicio: tu mes de un vistazo", texto: "Lo primero que ves al entrar: cuántas tareas llevas validadas, cuántas esperan revisión, cuáles se vencen y qué te toca hoy." },
    { ruta: "/mis-tareas", objetivo: PESTANAS, titulo: "Mis tareas", texto: "Todo lo que te asignan. «Por hacer» es lo pendiente, «En revisión» lo que ya entregaste y espera a tu supervisor, «Validadas» lo que ya cuenta para tu puntaje." },
    { ruta: "/mis-tareas", objetivo: ["[data-guia=tarea]", PESTANAS], titulo: "Cómo se trabaja una tarea", texto: "1. Toca «Empezar»: el cronómetro empieza a contar.\n2. Abre la tarea para ver los pasos y marcarlos.\n3. Al terminar toca «Entregar» y adjunta la evidencia (foto, archivo o enlace).\n4. Tu supervisor la valida o te la devuelve con lo que hay que corregir (sale en rojo)." },
    { ruta: "/tiempo", objetivo: ["[data-guia=cronometro]", TITULO], titulo: "Tiempo", texto: "El cronómetro registra cuánto toma cada trabajo. Si se te olvidó ponerlo, usa «Anotar tiempo». Mientras corre, lo ves arriba en rojo desde cualquier pantalla y lo detienes con el cuadrito." },
    { ruta: "/ordenes", objetivo: [PESTANAS, TITULO], titulo: "Órdenes de trabajo (OT)", texto: "Cada trabajo de un cliente es una OT. Aquí ves las que pasan por tu área: en tablero por etapa, «Por área» (la cola de cada área), en tabla o en calendario. Toca una para ver su detalle." },
    { objetivo: ["[data-guia=buscar]", "[data-guia=buscar-movil]"], titulo: "Buscar", texto: "Encuentra una OT por su número, un cliente, un proyecto o una tarea. Atajo en la PC: Ctrl + K o la tecla /." },
    { objetivo: "[data-guia=crear]", titulo: "Crear", texto: "Lo que más se hace, a un toque desde cualquier pantalla: una orden de trabajo, una tarea para tu equipo, un proyecto o un cliente." },
    { objetivo: "[data-guia=avisos]", titulo: "Avisos", texto: "La campanita te avisa cuando te asignan algo, te devuelven una tarea o te mencionan con @. El número rojo son los avisos sin leer. Los «Recordatorios» de tu supervisor salen en grande y suenan." },
  ];
  if (sesion.puedeValidar) {
    pasos.push(
      { ruta: "/validar", objetivo: TITULO, titulo: "Por validar (supervisores)", texto: "Las tareas que tu equipo entregó. Revisa la evidencia, califica la calidad con estrellas y toca «Validar», o «Devolver» con lo que hay que corregir. Una tarea solo suma al puntaje cuando la validas." },
      { ruta: "/equipo", objetivo: [PESTANAS, TITULO], titulo: "Mi equipo", texto: "«Ahora» muestra en qué está cada quien. En «Tareas» creas y das seguimiento (con «Recordar» le llega un aviso que suena). «Recurrentes» son las que se repiten solas cada día, semana o mes." },
    );
  }
  if (sesion.gestionaCallCenter) {
    pasos.push({ ruta: "/call-center", objetivo: [PESTANAS, TITULO], titulo: "Call Center", texto: "Las campañas con sus metas y los agentes que las atienden. Los agentes tienen su propia pantalla y se evalúan en un ranking aparte." });
  }
  if (sesion.esFinanzas) {
    pasos.push({ ruta: "/finanzas", objetivo: [PESTANAS, TITULO], titulo: "Finanzas", texto: "Cotizaciones, facturas, cobros, gastos y rentabilidad, conectados a las OT. La factura fiscal (NCF / e-CF) se emite en Cashflow desde la pestaña del mismo nombre." });
  }
  if (sesion.esAdmin) {
    pasos.push({ ruta: "/", objetivo: MENU, titulo: "Resultados y Administración", texto: "Como administrador, abajo en el menú tienes el desempeño y ranking, los KPIs del mes, el organigrama, los puestos, las personas, las plantillas de KPI, las reglas del puntaje y las automatizaciones." });
  }
  pasos.push(
    { objetivo: ["[data-guia=cuenta]", "[data-guia=ayuda]"], titulo: "Tu cuenta", texto: "En «Mi cuenta» cambias tu contraseña. «Salir» cierra la sesión en este equipo." },
    { objetivo: "[data-guia=ayuda]", titulo: "¿Dudas? Toca ?", texto: "Este botón abre la ayuda: la guía de la pantalla en la que estés y el paso a paso de lo más común (entregar una tarea, crear una OT, validar…). ¡Listo, ya puedes empezar!" },
  );
  return pasos;
}

/** Guía de cada pantalla. `ruta` es una expresión regular sobre la dirección. */
export const GUIAS_PANTALLA = [
  { id: "inicio", ruta: /^\/$/, nombre: "Inicio", pasos: [
    { objetivo: TITULO, titulo: "Tu mes", texto: "La franja de colores es tu mes hecho de tareas: amarillo lleno validadas, borde amarillo en revisión, rojo vencidas y gris pendientes." },
    { titulo: "Qué hacer desde aquí", texto: "Abajo ves lo que te toca hoy y lo que se vence pronto. Toca cualquier tarea para abrirla. Si supervisas, aparece también lo que tu equipo te entregó para revisar." },
  ] },
  { id: "mis-tareas", ruta: /^\/mis-tareas$/, nombre: "Mis tareas", pasos: [
    { objetivo: PESTANAS, titulo: "Tres listas", texto: "«Por hacer»: pendientes y en curso. «En revisión»: entregadas, esperando a tu supervisor. «Validadas»: las que ya cuentan; elige el mes para ver las anteriores." },
    { objetivo: ["[data-guia=tarea]", PESTANAS], titulo: "Empezar y entregar", texto: "«Empezar» pone el cronómetro; luego el mismo botón lo pausa y lo retoma. «Entregar» pide la evidencia y manda la tarea a revisión. Si te la devuelven, sale con borde rojo y el comentario de qué corregir: arréglalo y toca «Entregar de nuevo»." },
    { titulo: "¿Sin tareas?", texto: "Si estás al día, toca «Pedir más trabajo»: a tu supervisor le llega el aviso." },
  ] },
  { id: "tiempo", ruta: /^\/tiempo$/, nombre: "Tiempo", pasos: [
    { objetivo: ["[data-guia=cronometro]", TITULO], titulo: "El cronómetro", texto: "Escribe en qué trabajas y toca «Empezar», o empiézalo desde una tarea. Solo corre uno a la vez: al empezar otro, el anterior se detiene." },
    { titulo: "Tu semana", texto: "Debajo ves las horas de cada día. Con «Anotar tiempo» agregas lo que no cronometraste, y tocando un registro lo corriges." },
    { para: (s) => s.puedeValidar || s.esFinanzas, objetivo: PESTANAS, titulo: "Carga y reporte", texto: "«Carga del equipo» muestra quién está libre y quién saturado. «Reporte de horas» suma el tiempo por persona, proyecto u OT." },
  ] },
  { id: "ordenes", ruta: /^\/ordenes$/, nombre: "Órdenes de trabajo", pasos: [
    { objetivo: TITULO, titulo: "El recorrido de una OT", texto: "Comercial llena la OT Maestra (F-01) → Coordinación la revisa (G0) y la numera → cada área recibe su Orden de Área (G1) → se ejecuta, se aprueba con el cliente (G4) y pasa control de calidad (G3) → se traspasa con doble firma → acta de entrega firmada → factura y cierre." },
    { objetivo: PESTANAS, titulo: "Cuatro vistas", texto: "«OT»: tablero por etapa. «Por área»: la cola de cada área. «Tabla» y «Calendario» para buscar por fecha. Los números de arriba (por revisar, vencidas, a tiempo…) filtran la lista al tocarlos." },
    { objetivo: ["[data-guia=nueva-ot]", "[data-guia=crear]"], titulo: "Nueva OT", texto: "Llena los datos del cliente, el alcance, las áreas en su orden y la fecha requerida. «Calcular» propone la fecha comprometida. Al guardar queda como solicitud S-AA-0000 y le llega a Coordinación." },
  ] },
  { id: "orden", ruta: /^\/ordenes\/\d+$/, nombre: "Detalle de la OT", pasos: [
    { objetivo: PESTANAS, titulo: "Pestañas de la OT", texto: "«F-01»: lo que se pidió y la lista G0. «Áreas»: cada Orden de Área y sus traspasos. «Entrega y cierre»: acta, facturas, costo real y margen. «Cambios»: solicitudes de cambio o retrabajo. «Conversación»: comentarios con @menciones." },
    { titulo: "Lo que toca ahora", texto: "Los botones de arriba cambian según la etapa y tu rol: liberar o rechazar (Coordinación), recibir, entregar, firmar el acta… Si no ves un botón, es que ese paso le toca a otra persona." },
  ] },
  { id: "orden-area", ruta: /^\/ordenes\/\d+\/areas\/\d+$/, nombre: "Orden de Área", pasos: [
    { titulo: "Las compuertas en una línea", texto: "G1 (recibir) → E3 (ejecución) → G4 (aprobación del cliente) → G3 (calidad) → G2 (traspaso). Lo que toca hacer ahora aparece arriba, resaltado." },
    { titulo: "Durante el trabajo", texto: "Llena la especificación del formato, marca las etapas, pide material con vale, anota incidencias o tiempos muertos y sube los archivos. Todo queda en el historial de la OT." },
  ] },
  { id: "proyectos", ruta: /^\/proyectos$/, nombre: "Proyectos", pasos: [
    { objetivo: [PESTANAS, TITULO], titulo: "Proyectos", texto: "Agrupan las tareas y órdenes de un trabajo grande. Míralos en tabla, en tablero o en cronograma (Gantt) con la línea de hoy. Toca uno para ver sus tareas, horas y conversación." },
  ] },
  { id: "clientes", ruta: /^\/clientes$/, nombre: "Clientes", pasos: [
    { objetivo: TITULO, titulo: "Clientes", texto: "El directorio: contacto, RNC, proyectos y órdenes de cada cliente. Finanzas ve además lo facturado, lo cobrado y el saldo. Con «Crear → Cliente» agregas uno nuevo." },
  ] },
  { id: "call-center", ruta: /^\/call-center$/, nombre: "Call Center", pasos: [
    { para: (s) => s.gestionaCallCenter, objetivo: [PESTANAS, TITULO], titulo: "Campañas y agentes", texto: "«Campañas»: qué se atiende, para qué cliente, horario, canales y metas diarias. «Agentes»: cada agente con sus campañas y su puntaje del mes." },
    { para: (s) => s.gestionaCallCenter, titulo: "Agentes aparte", texto: "Un agente es una persona con el acceso «Agente de call center» (Personas → editar). Solo ve su pantalla y se evalúa en Desempeño → Call Center, fuera del ranking del resto del equipo." },
    { para: (s) => s.esAgente, objetivo: TITULO, titulo: "Tu pantalla", texto: "Tu puntaje del mes, tus campañas con sus metas y el guion, y tus KPIs. Si no ves campaña, pídele a tu supervisor que te asigne una." },
  ] },
  { id: "almacen", ruta: /^\/almacen$/, nombre: "Almacén", pasos: [
    { objetivo: [PESTANAS, TITULO], titulo: "Vales y materiales", texto: "Sin vale no sale material. El área lo pide, Coordinación lo autoriza, Almacén lo despacha (se descuenta al momento) y quien recibe lo firma. Al terminar se registra la devolución y el desperdicio con su causa." },
  ] },
  { id: "validar", ruta: /^\/validar$/, nombre: "Por validar", pasos: [
    { objetivo: TITULO, titulo: "Revisar lo entregado", texto: "Abre cada tarea, mira la evidencia y califica la calidad con estrellas. «Validar» la cierra y suma al puntaje de la persona; «Devolver» se la regresa con tu comentario de qué corregir." },
  ] },
  { id: "equipo", ruta: /^\/equipo$/, nombre: "Mi equipo", pasos: [
    { objetivo: PESTANAS, titulo: "Ahora, Tareas y Recurrentes", texto: "«Ahora»: en qué está cada quien en este momento. «Tareas»: todas las de tu equipo con filtros. «Recurrentes»: las que se crean solas cada día, semana o mes." },
    { objetivo: ["[data-guia=nueva-tarea]", TITULO], titulo: "Asignar una tarea", texto: "«Nueva tarea»: título, responsable, fecha, prioridad y los pasos. Si va ligada a un KPI, al validarla suma a ese KPI. Abre una tarea para editarla, recordarla, reabrirla o cancelarla." },
  ] },
  { id: "finanzas", ruta: /^\/finanzas$/, nombre: "Finanzas", pasos: [
    { objetivo: PESTANAS, titulo: "Finanzas", texto: "Resumen del mes, cotizaciones (con ITBIS calculado), facturas, gastos, rentabilidad por proyecto u OT, y la conexión con Cashflow. Una cotización aprobada puede convertirse en OT de un toque." },
    { titulo: "Facturar una OT", texto: "Anticipo: desde la OT, «Factura de anticipo». Final: con el acta firmada, «Facturar» crea el borrador por lo que falta y «Emitir en Cashflow (NCF)» asigna el comprobante fiscal." },
  ] },
  { id: "organigrama", ruta: /^\/organigrama$/, nombre: "Organigrama", pasos: [
    { objetivo: TITULO, titulo: "Quién reporta a quién", texto: "Tu supervisor es quien ocupa el puesto del que depende el tuyo: es quien te asigna y valida las tareas." },
  ] },
  { id: "personas", ruta: /^\/personas$/, nombre: "Personas", pasos: [
    { objetivo: TITULO, titulo: "Cuentas del equipo", texto: "Crea la cuenta de cada persona y asígnale su puesto. En «editar → Accesos adicionales» das los permisos de Coordinación, Almacén o Finanzas." },
  ] },
  { id: "puestos", ruta: /^\/puestos/, nombre: "Departamentos y puestos", pasos: [
    { objetivo: TITULO, titulo: "Puestos", texto: "Cada puesto tiene su departamento, a quién reporta, sus funciones y sus KPIs con meta y peso. De aquí sale el organigrama." },
  ] },
  { id: "plantillas-kpi", ruta: /^\/plantillas-kpi$/, nombre: "Plantillas de KPI", pasos: [
    { objetivo: TITULO, titulo: "KPIs", texto: "Define cada KPI una vez (automático con tareas validadas, o manual) y luego asígnalo a uno o varios puestos con su meta y su peso." },
  ] },
  { id: "kpis-del-mes", ruta: /^\/kpis-del-mes$/, nombre: "KPIs del mes", pasos: [
    { objetivo: TITULO, titulo: "Anotar resultados", texto: "Escribe aquí los KPIs que vienen de fuera (ventas, seguidores, conversión). Los automáticos se llenan solos con las tareas validadas." },
  ] },
  { id: "desempeno", ruta: /^\/desempeno$/, nombre: "Desempeño y ranking", pasos: [
    { objetivo: TITULO, titulo: "Desempeño", texto: "El puntaje mensual de cada persona según sus tareas validadas, su calidad y sus KPIs, con el ranking del equipo y el bono sugerido." },
  ] },
  { id: "configuracion", ruta: /^\/configuracion$/, nombre: "Reglas del puntaje", pasos: [
    { objetivo: TITULO, titulo: "Reglas", texto: "Cómo se calcula el puntaje mensual y el bono sugerido. Los cambios aplican a todos los meses que se consulten." },
  ] },
  { id: "automatizaciones", ruta: /^\/automatizaciones$/, nombre: "Automatizaciones", pasos: [
    { objetivo: TITULO, titulo: "Cuando pase X, haz Y", texto: "Reglas que avisan a la persona correcta, crean una tarea de seguimiento o envían los datos a n8n (WhatsApp, correo, Google Sheets, IA). Se pueden filtrar por área." },
  ] },
  { id: "ajustes-produccion", ruta: /^\/produccion\/ajustes$/, nombre: "Áreas y tiempos", pasos: [
    { objetivo: TITULO, titulo: "Áreas y tiempos", texto: "Quién recibe cada Orden de Área (G1) y firma la calidad (G3) en cada área, y la tabla de tiempos estándar que usa el formulario de la OT para proponer fechas." },
  ] },
  { id: "mi-cuenta", ruta: /^\/mi-cuenta$/, nombre: "Mi cuenta", pasos: [
    { objetivo: TITULO, titulo: "Tu cuenta", texto: "Aquí cambias tu contraseña. Si la olvidas, pídele a Administración que te la restablezca." },
  ] },
];

export const guiaDePantalla = (ruta) => GUIAS_PANTALLA.find((g) => g.ruta.test(ruta));

/** «¿Cómo hago…?»: tareas comunes explicadas paso a paso, cada una lleva a su pantalla. */
export const RECETAS = [
  { id: "entregar", titulo: "Entregar una tarea", pasos: [
    { ruta: "/mis-tareas", objetivo: PESTANAS, titulo: "1. Busca la tarea", texto: "En «Mis tareas → Por hacer» están tus pendientes." },
    { ruta: "/mis-tareas", objetivo: ["[data-guia=tarea]", PESTANAS], titulo: "2. Entrega", texto: "Toca «Entregar», describe lo que hiciste y adjunta la evidencia (foto, archivo o enlace). La tarea pasa a «En revisión» y tu supervisor recibe el aviso." },
    { titulo: "3. Espera la validación", texto: "Si la validan, suma a tu puntaje. Si te la devuelven, vuelve a «Por hacer» con borde rojo y el comentario: corrige y toca «Entregar de nuevo»." },
  ] },
  { id: "cronometro", titulo: "Usar el cronómetro", pasos: [
    { ruta: "/mis-tareas", objetivo: ["[data-guia=tarea]", PESTANAS], titulo: "Desde una tarea", texto: "«Empezar» pone el cronómetro de esa tarea. El mismo botón lo pausa y lo retoma." },
    { ruta: "/tiempo", objetivo: ["[data-guia=cronometro]", TITULO], titulo: "Sin tarea", texto: "En «Tiempo» escribe en qué trabajas y toca «Empezar». Si se te olvidó, «Anotar tiempo» lo agrega después." },
  ] },
  { id: "nueva-ot", titulo: "Crear una orden de trabajo", pasos: [
    { ruta: "/ordenes", objetivo: ["[data-guia=nueva-ot]", "[data-guia=crear]"], titulo: "1. Nueva OT", texto: "Toca «Nueva OT» (o «Crear → Orden de trabajo» desde cualquier pantalla)." },
    { titulo: "2. Llena el F-01", texto: "Cliente, alcance y exclusiones, áreas que intervienen en su orden (las de igual número trabajan a la vez), fecha requerida, prioridad, monto y anticipo. «Calcular» propone la fecha comprometida." },
    { titulo: "3. Guarda", texto: "Queda como solicitud S-AA-0000 y le llega a Coordinación. Si falta algo te la devuelve con la causa: corrige y reenvíala. Al liberarla recibe su número OT-AA-0000." },
  ] },
  { id: "validar", para: (s) => s.puedeValidar, titulo: "Validar o devolver una tarea", pasos: [
    { ruta: "/validar", objetivo: TITULO, titulo: "1. Abre «Por validar»", texto: "El número amarillo del menú dice cuántas esperan. Abre una para ver la evidencia." },
    { titulo: "2. Decide", texto: "Califica la calidad con estrellas y toca «Validar». Si falta algo, «Devolver» con un comentario claro de qué corregir." },
  ] },
  { id: "asignar", para: (s) => s.puedeValidar, titulo: "Asignar una tarea a mi equipo", pasos: [
    { ruta: "/equipo", objetivo: ["[data-guia=nueva-tarea]", TITULO], titulo: "1. Nueva tarea", texto: "En «Mi equipo» toca «Nueva tarea» (o «Crear → Tarea para mi equipo»)." },
    { titulo: "2. Detalles", texto: "Título, responsable, fecha, prioridad y los pasos. Si debe repetirse, créala en «Recurrentes». A la persona le llega el aviso al momento." },
  ] },
  { id: "avisos", titulo: "Ver mis avisos", pasos: [
    { objetivo: "[data-guia=avisos]", titulo: "La campanita", texto: "Tócala para ver tus avisos; al abrir uno te lleva a lo que se refiere. «Marcar todo como leído» limpia el número rojo." },
  ] },
  { id: "buscar", titulo: "Encontrar algo rápido", pasos: [
    { objetivo: ["[data-guia=buscar]", "[data-guia=buscar-movil]"], titulo: "Buscar", texto: "Escribe el número de OT, el nombre del cliente, un proyecto o una tarea. En la PC: Ctrl + K o /." },
  ] },
  { id: "instalar", titulo: "Instalar la app en el celular", pasos: [
    { titulo: "Como una app", texto: "En Android (Chrome): menú ⋮ → «Instalar app» o «Agregar a la pantalla principal». En iPhone (Safari): botón Compartir → «Agregar a inicio». Así abres Adzone Team con un toque y recibes los avisos más rápido." },
  ] },
  { id: "contrasena", titulo: "Cambiar mi contraseña", pasos: [
    { ruta: "/mi-cuenta", objetivo: TITULO, titulo: "Mi cuenta", texto: "Escribe tu contraseña actual y la nueva dos veces. En la PC, «Mi cuenta» está abajo a la izquierda; en el celular, en «Más»." },
  ] },
];
