// Cliente de la API de Adzone Team. Misma sesión (cookie) y token CSRF en todas las llamadas.

export function getCookie(name) {
  const match = document.cookie.split(";").map((c) => c.trim()).find((c) => c.startsWith(name + "="));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

/** Convierte las respuestas de error de Django REST en un mensaje legible. */
function mensajeDeError(data, status) {
  if (status === 403) return data?.detail || "No tienes permiso para hacer esto.";
  if (status === 404) return "No se encontró. Puede que ya no exista o no tengas acceso.";
  if (status === 429) return "Demasiados intentos. Espera un minuto y vuelve a probar.";
  if (status >= 500) return "El servidor tuvo un problema. Inténtalo de nuevo en un momento.";
  if (data && typeof data === "object") {
    const partes = Object.entries(data).map(([clave, valor]) => {
      const texto = Array.isArray(valor) ? valor.join(" ")
        : valor && typeof valor === "object" ? Object.values(valor).flat().join(" ") : valor;
      return ["detail", "non_field_errors", "error"].includes(clave) ? texto : `${CAMPOS[clave] || clave}: ${texto}`;
    });
    if (partes.length) return partes.join(" ");
  }
  return `Error ${status}`;
}

const CAMPOS = {
  titulo: "Título", colaborador: "Colaborador", fecha_limite: "Fecha límite", kpi_asignado: "KPI",
  password: "Contraseña", email: "Correo", username: "Usuario", nombre: "Nombre", meta_numerica: "Meta mensual",
  ponderacion: "Peso", supervisor: "Supervisor", departamento: "Departamento", dia_mes: "Día del mes",
  comentario_revision: "Comentario", calificacion_calidad: "Calidad", archivos: "Archivos", actual: "Contraseña actual",
  nueva: "Contraseña nueva", peso_tareas: "Peso de tareas", nota_tarde: "Nota por entrega tarde", tramos_bono: "Tramos del bono",
  detalles: "Datos de la orden", cliente: "Cliente", proyecto: "Proyecto", responsable: "Responsable",
  fecha_compromiso: "Fecha comprometida", recibido_por: "Recibido por", motivo: "Motivo", lineas: "Líneas", monto: "Monto",
  minutos: "Tiempo", fecha: "Fecha", fecha_inicio: "Inicio", fecha_fin: "Entrega", concepto: "Concepto", parametros: "Acción",
  condiciones: "Condición", comprobante: "Comprobante", texto: "Comentario",
};

export class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

// Cierre por inactividad: el servidor solo cuenta como actividad lo que la persona hace (no los avisos que la app consulta sola).
let ultimaInteraccion = Date.now();
if (typeof window !== "undefined") {
  for (const ev of ["pointerdown", "keydown", "touchstart", "wheel"]) window.addEventListener(ev, () => { ultimaInteraccion = Date.now(); }, { passive: true, capture: true });
}
export const EVENTO_SESION = "adzone:sesion";

export async function api(url, { method = "GET", body, signal } = {}) {
  const esFormulario = body instanceof FormData;
  const headers = { Accept: "application/json" };
  if (Date.now() - ultimaInteraccion < 60000) headers["X-Actividad"] = "1";
  if (method !== "GET") headers["X-CSRFToken"] = getCookie("csrftoken") || "";
  if (body && !esFormulario) headers["Content-Type"] = "application/json";
  let response;
  try {
    response = await fetch(url, {
      method, credentials: "same-origin", headers, signal,
      body: body ? (esFormulario ? body : JSON.stringify(body)) : undefined,
    });
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new ApiError("Sin conexión. Revisa el internet e inténtalo de nuevo.", 0);
  }
  if (response.status === 204) return null;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    // La sesión se cerró (inactividad, código pendiente) o falta activar los dos pasos: la app se entera y reacciona
    if ((response.status === 401 && data?.detail) || data?.activar_dos_pasos) {
      window.dispatchEvent(new CustomEvent(EVENTO_SESION, { detail: { estado: response.status, ...data } }));
    }
    throw new ApiError(mensajeDeError(data, response.status), response.status, data);
  }
  return data;
}

const q = (params = {}) => {
  const limpio = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== "" && v != null));
  const s = new URLSearchParams(limpio).toString();
  return s ? `?${s}` : "";
};

const D = "/api/desempeno";

// Sesión
export const sesion = () => api("/api/auth/session/");
// Credenciales: { username, password, remember_me } o, desde el directorio, { user_id, password, remember_me }
export const entrar = (credenciales) => api("/api/auth/login/", { method: "POST", body: credenciales });
export const entrarConCodigo = (codigo) => api("/api/auth/dos-pasos/", { method: "POST", body: { codigo } });
export const dosPasos = () => api("/api/cuenta/dos-pasos/");
export const iniciarDosPasos = (clave) => api("/api/cuenta/dos-pasos/iniciar/", { method: "POST", body: clave ? { clave } : {} });
export const confirmarDosPasos = (codigo) => api("/api/cuenta/dos-pasos/confirmar/", { method: "POST", body: { codigo } });
export const nuevosCodigosRespaldo = (codigo) => api("/api/cuenta/dos-pasos/respaldo/", { method: "POST", body: { codigo } });
export const desactivarDosPasos = (clave) => api("/api/cuenta/dos-pasos/desactivar/", { method: "POST", body: { clave } });
export const reiniciarDosPasos = (id) => api(`/api/accesos/personas/${id}/dos-pasos/`, { method: "DELETE" });
export const respaldos = () => api("/api/respaldos/");
export const abrirEquipo = (clave) => api("/api/auth/equipo/", { method: "POST", body: { clave } });
export const directorioEntrada = () => api("/api/auth/directorio/");
export const cambiarClaveEquipo = (nueva) => api("/api/auth/clave-equipo/", { method: "POST", body: { nueva } });
export const salir = () => api("/api/auth/logout/", { method: "POST" });
export const cambiarClave = (actual, nueva) => api("/api/auth/cambiar-clave/", { method: "POST", body: { actual, nueva } });

// Tareas
export const listarTareas = (params) => api(`${D}/tareas/${q(params)}`);
export const obtenerTarea = (id) => api(`${D}/tareas/${id}/`);
export const guardarTarea = (t) => (t.id ? api(`${D}/tareas/${t.id}/`, { method: "PATCH", body: t }) : api(`${D}/tareas/`, { method: "POST", body: t }));
export const eliminarTarea = (id) => api(`${D}/tareas/${id}/`, { method: "DELETE" });
export const historialTarea = (id) => api(`${D}/tareas/${id}/historial/`);
export const iniciarTarea = (id) => api(`${D}/tareas/${id}/iniciar/`, { method: "POST" });
export const entregarTarea = (id, { nota, enlace, archivos = [] }) => {
  const f = new FormData();
  if (nota) f.append("evidencia_nota", nota);
  if (enlace) f.append("evidencia_enlace", enlace);
  archivos.forEach((a) => f.append("archivos", a, a.name));
  return api(`${D}/tareas/${id}/entregar/`, { method: "POST", body: f });
};
export const validarTarea = (id, calificacion_calidad, comentario_evaluacion, extra = {}) =>
  api(`${D}/tareas/${id}/validar/`, { method: "POST", body: { calificacion_calidad, comentario_evaluacion, ...extra } });
export const devolverTarea = (id, comentario_revision, extra = {}) => api(`${D}/tareas/${id}/rechazar/`, { method: "POST", body: { comentario_revision, ...extra } });
export const reabrirTarea = (id, motivo) => api(`${D}/tareas/${id}/reabrir/`, { method: "POST", body: { motivo } });
export const cancelarTarea = (id, motivo) => api(`${D}/tareas/${id}/cancelar/`, { method: "POST", body: { motivo } });
export const recordarTarea = (id, mensaje) => api(`${D}/tareas/${id}/recordar/`, { method: "POST", body: { mensaje } });
export const pedirTrabajo = () => api(`${D}/pedir-trabajo/`, { method: "POST" });
export const marcarPaso = (id, pasoId, hecho) => api(`${D}/tareas/${id}/pasos/${pasoId}/`, { method: "POST", body: { hecho } });

// Recurrentes
export const listarRecurrentes = () => api(`${D}/recurrentes/`);
export const guardarRecurrente = (r) => (r.id ? api(`${D}/recurrentes/${r.id}/`, { method: "PATCH", body: r }) : api(`${D}/recurrentes/`, { method: "POST", body: r }));
export const eliminarRecurrente = (id) => api(`${D}/recurrentes/${id}/`, { method: "DELETE" });

// Resumen, tablero, equipo
export const miResumen = (mes) => api(`${D}/mi-resumen/${q({ mes })}`);
export const tablero = (mes) => api(`${D}/tablero/${q({ mes })}`);
export const equipo = () => api(`${D}/equipo/`);
export const cargaEquipo = () => api(`${D}/equipo/carga/`);

// KPIs manuales
export const planillaKPI = (mes, departamento) => api(`${D}/resultados-kpi/planilla/${q({ mes, departamento })}`);
export const guardarPlanilla = (mes, resultados) => api(`${D}/resultados-kpi/lote/`, { method: "POST", body: { mes, resultados } });

// Ranking y reconocimiento
export const ranking = (mes, grupo) => api(`${D}/ranking/${q({ mes, grupo })}`);
export const urlExportarRanking = (mes, grupo) => `${D}/ranking/exportar/${q({ mes, grupo })}`;
export const empleadosDelMes = (params) => api(`${D}/empleados-del-mes/${q(params)}`);
export const declararEmpleado = (datos) => api(`${D}/empleados-del-mes/`, { method: "POST", body: datos });
export const anularEmpleado = (id) => api(`${D}/empleados-del-mes/${id}/`, { method: "DELETE" });

// Avisos y configuración
export const avisos = () => api(`${D}/notificaciones/`);
export const leerAvisos = (ids) => api(`${D}/notificaciones/leer/`, { method: "POST", body: { ids } });
export const configuracion = () => api(`${D}/configuracion/`);
export const guardarConfiguracion = (datos) => api(`${D}/configuracion/`, { method: "PATCH", body: datos });

// Organización
export const departamentos = () => api("/api/departamentos/");
export const guardarDepartamento = (d) => (d.id ? api(`/api/departamentos/${d.id}/`, { method: "PATCH", body: d }) : api("/api/departamentos/", { method: "POST", body: d }));
export const eliminarDepartamento = (id) => api(`/api/departamentos/${id}/`, { method: "DELETE" });
export const puestos = (params) => api(`/api/organizacion/puestos-trabajo/${q(params)}`);
export const puesto = (id) => api(`/api/organizacion/puestos-trabajo/${id}/`);
export const guardarPuesto = (p) => (p.id ? api(`/api/organizacion/puestos-trabajo/${p.id}/`, { method: "PATCH", body: p }) : api("/api/organizacion/puestos-trabajo/", { method: "POST", body: p }));
export const eliminarPuesto = (id) => api(`/api/organizacion/puestos-trabajo/${id}/`, { method: "DELETE" });
export const organigrama = () => api("/api/organizacion/organigrama/");
export const usuarios = () => api("/api/organizacion/usuarios/");
export const guardarUsuario = (u) => (u.id ? api(`/api/organizacion/usuarios/${u.id}/`, { method: "PATCH", body: u }) : api("/api/organizacion/usuarios/", { method: "POST", body: u }));
export const eliminarUsuario = (id) => api(`/api/organizacion/usuarios/${id}/`, { method: "DELETE" });

// KPIs
export const plantillas = () => api("/api/kpis/plantillas-kpi/");
export const guardarPlantilla = (p) => (p.id ? api(`/api/kpis/plantillas-kpi/${p.id}/`, { method: "PATCH", body: p }) : api("/api/kpis/plantillas-kpi/", { method: "POST", body: p }));
export const eliminarPlantilla = (id) => api(`/api/kpis/plantillas-kpi/${id}/`, { method: "DELETE" });
export const kpisAsignados = (params) => api(`/api/kpis/kpis-asignados/${q(params)}`);
export const guardarKpiAsignado = (k) => (k.id ? api(`/api/kpis/kpis-asignados/${k.id}/`, { method: "PATCH", body: k }) : api("/api/kpis/kpis-asignados/", { method: "POST", body: k }));
export const eliminarKpiAsignado = (id) => api(`/api/kpis/kpis-asignados/${id}/`, { method: "DELETE" });

// Operación: clientes, proyectos y órdenes de trabajo
const O = "/api/operaciones";
export const catalogoOrdenes = () => api(`${O}/ordenes/catalogo/`);
export const listarOrdenes = (params) => api(`${O}/ordenes/${q(params)}`);
export const resumenOrdenes = (params) => api(`${O}/ordenes/resumen/${q(params)}`);
export const ordenCompleta = (id) => api(`${O}/ordenes/${id}/completo/`);
export const guardarOrden = (o) => (o.id ? api(`${O}/ordenes/${o.id}/`, { method: "PATCH", body: o }) : api(`${O}/ordenes/`, { method: "POST", body: o }));
export const eliminarOrden = (id) => api(`${O}/ordenes/${id}/`, { method: "DELETE" });
const accionOT = (id, accion, body) => api(`${O}/ordenes/${id}/${accion}/`, { method: "POST", body });
export const liberarOrden = (id, datos = {}) => accionOT(id, "liberar", datos);
export const rechazarG0 = (id, causa, devuelto_a) => accionOT(id, "rechazar_g0", { causa, devuelto_a });
export const reenviarOrden = (id) => accionOT(id, "reenviar");
export const confirmarAnticipo = (id) => accionOT(id, "confirmar_anticipo");
export const excepcionG0 = (id, motivo) => accionOT(id, "excepcion", { motivo });
export const agregarArea = (id, fila) => accionOT(id, "agregar_area", fila);
export const pausarOrden = (id, motivo) => accionOT(id, "pausar", { motivo });
export const reanudarOrden = (id) => accionOT(id, "reanudar");
export const cancelarOrden = (id, motivo) => accionOT(id, "cancelar", { motivo });
export const cerrarOrden = (id) => accionOT(id, "cerrar");
export const calcularCompromiso = (datos) => api(`${O}/ordenes/calcular/`, { method: "POST", body: datos });
export const costosOrden = (id) => api(`${O}/ordenes/${id}/costos/`);
export const crearActa = (id, datos) => accionOT(id, "actas", datos);
export const crearCambio = (id, datos) => accionOT(id, "cambios", datos);
export const indicadoresProduccion = (params) => api(`${O}/ordenes/indicadores/${q(params)}`);
export const urlBitacora = (params) => `${O}/ordenes/bitacora/${q(params)}`;
// Órdenes de Área (F-02 a F-10)
export const listarAreas = (params) => api(`${O}/areas/${q(params)}`);
export const areaCompleta = (id) => api(`${O}/areas/${id}/completo/`);
export const guardarArea = (id, datos) => api(`${O}/areas/${id}/`, { method: "PATCH", body: datos });
export const accionArea = (id, accion, body) => api(`${O}/areas/${id}/${accion}/`, { method: "POST", body });
export const incidenciaArea = (id, datos) => accionArea(id, "incidencias", datos);
export const costosArea = (id) => api(`${O}/areas/${id}/costos/`);
export const listarTraspasos = (params) => api(`${O}/traspasos/${q(params)}`);
export const recibirTraspaso = (id, datos) => api(`${O}/traspasos/${id}/recibir/`, { method: "POST", body: datos });
export const guardarActa = (id, datos) => api(`${O}/actas/${id}/`, { method: "PATCH", body: datos });
export const accionActa = (id, accion, body) => api(`${O}/actas/${id}/${accion}/`, { method: "POST", body });
export const obtenerActa = (id) => api(`${O}/actas/${id}/`);
export const listarCambios = (params) => api(`${O}/cambios/${q(params)}`);
export const accionCambio = (id, accion, body) => api(`${O}/cambios/${id}/${accion}/`, { method: "POST", body });
export const configAreas = () => api(`${O}/config-areas/`);
export const guardarConfigArea = (id, datos) => api(`${O}/config-areas/${id}/`, { method: "PATCH", body: datos });
export const tiemposEstandar = () => api(`${O}/tiempos/`);
export const guardarTiempo = (t) => (t.id ? api(`${O}/tiempos/${t.id}/`, { method: "PATCH", body: t }) : api(`${O}/tiempos/`, { method: "POST", body: t }));
export const eliminarTiempo = (id) => api(`${O}/tiempos/${id}/`, { method: "DELETE" });
export const comentarOrden = (id, texto) => api(`${O}/ordenes/${id}/comentarios/`, { method: "POST", body: { texto } });
export const subirArchivosOrden = (id, archivos, extra = {}) => {
  const fd = new FormData();
  archivos.forEach((a) => fd.append("archivos", a));
  Object.entries(extra).forEach(([k, v]) => v != null && v !== "" && fd.append(k, v));
  return api(`${O}/ordenes/${id}/archivos/`, { method: "POST", body: fd });
};
export const quitarArchivo = (id) => api(`${O}/archivos/${id}/`, { method: "DELETE" });
export const listarClientes = (params) => api(`${O}/clientes/${q(params)}`);
export const obtenerCliente = (id) => api(`${O}/clientes/${id}/`);
export const resumenCliente = (id) => api(`${O}/clientes/${id}/resumen/`);
export const guardarCliente = (c) => (c.id ? api(`${O}/clientes/${c.id}/`, { method: "PATCH", body: c }) : api(`${O}/clientes/`, { method: "POST", body: c }));
export const eliminarCliente = (id) => api(`${O}/clientes/${id}/`, { method: "DELETE" });
export const listarProyectos = (params) => api(`${O}/proyectos/${q(params)}`);
export const obtenerProyecto = (id) => api(`${O}/proyectos/${id}/`);
export const detalleProyecto = (id) => api(`${O}/proyectos/${id}/detalle/`);
export const guardarProyecto = (p) => (p.id ? api(`${O}/proyectos/${p.id}/`, { method: "PATCH", body: p }) : api(`${O}/proyectos/`, { method: "POST", body: p }));
export const eliminarProyecto = (id) => api(`${O}/proyectos/${id}/`, { method: "DELETE" });
export const comentariosProyecto = (id) => api(`${O}/proyectos/${id}/comentarios/`);
export const comentarProyecto = (id, texto) => api(`${O}/proyectos/${id}/comentarios/`, { method: "POST", body: { texto } });
export const directorio = () => api(`${O}/directorio/`);
export const buscar = (texto, signal) => api(`${O}/buscar/${q({ q: texto })}`, { signal });

// Tiempo
const T = "/api/tiempo";
export const cronometroActivo = () => api(`${T}/activo/`);
export const iniciarCronometro = (datos) => api(`${T}/iniciar/`, { method: "POST", body: datos });
export const detenerCronometro = () => api(`${T}/detener/`, { method: "POST" });
export const miSemana = (fecha) => api(`${T}/semana/${q({ fecha })}`);
export const guardarRegistro = (r) => (r.id ? api(`${T}/registros/${r.id}/`, { method: "PATCH", body: r }) : api(`${T}/registros/`, { method: "POST", body: r }));
export const eliminarRegistro = (id) => api(`${T}/registros/${id}/`, { method: "DELETE" });
export const cargaSemanal = (fecha) => api(`${T}/equipo/${q({ fecha })}`);
export const reporteTiempo = (params) => api(`${T}/reporte/${q(params)}`);

// Finanzas
const F = "/api/finanzas";
export const resumenFinanzas = (mes) => api(`${F}/resumen/${q({ mes })}`);
export const rentabilidad = (params) => api(`${F}/rentabilidad/${q(params)}`);
export const listarDocumentos = (tipo, params) => api(`${F}/${tipo}/${q(params)}`);
export const obtenerDocumento = (tipo, id) => api(`${F}/${tipo}/${id}/`);
export const guardarDocumento = (tipo, d) => (d.id ? api(`${F}/${tipo}/${d.id}/`, { method: "PATCH", body: d }) : api(`${F}/${tipo}/`, { method: "POST", body: d }));
export const eliminarDocumento = (tipo, id) => api(`${F}/${tipo}/${id}/`, { method: "DELETE" });
export const accionDocumento = (tipo, id, accion, body) => api(`${F}/${tipo}/${id}/${accion}/`, { method: "POST", body });
export const facturarOrden = (orden, extra = {}) => api(`${F}/facturas/desde_orden/`, { method: "POST", body: { orden, ...extra } });
export const registrarPago = (factura, pago) => api(`${F}/facturas/${factura}/pagos/`, { method: "POST", body: pago });
export const borrarPago = (id) => api(`${F}/pagos/${id}/`, { method: "DELETE" });
export const guardarGasto = (g, comprobante) => {
  if (!comprobante) return g.id ? api(`${F}/gastos/${g.id}/`, { method: "PATCH", body: g }) : api(`${F}/gastos/`, { method: "POST", body: g });
  const fd = new FormData();
  Object.entries(g).forEach(([k, v]) => { if (v !== null && v !== undefined && k !== "id") fd.append(k, v); });
  fd.append("comprobante", comprobante);
  return g.id ? api(`${F}/gastos/${g.id}/`, { method: "PATCH", body: fd }) : api(`${F}/gastos/`, { method: "POST", body: fd });
};

// Automatizaciones
const A = "/api/automatizaciones";
export const catalogoAutomatizaciones = () => api(`${A}/catalogo/`);
export const listarReglas = () => api(`${A}/reglas/`);
export const guardarRegla = (r) => (r.id ? api(`${A}/reglas/${r.id}/`, { method: "PATCH", body: r }) : api(`${A}/reglas/`, { method: "POST", body: r }));
export const eliminarRegla = (id) => api(`${A}/reglas/${id}/`, { method: "DELETE" });
export const ejecuciones = () => api(`${A}/ejecuciones/`);

// Almacén (F-11)
const AL = "/api/almacen";
export const listarMateriales = (params) => api(`${AL}/materiales/${q(params)}`);
export const guardarMaterial = (m) => (m.id ? api(`${AL}/materiales/${m.id}/`, { method: "PATCH", body: m }) : api(`${AL}/materiales/`, { method: "POST", body: m }));
export const accionMaterial = (id, accion, body) => api(`${AL}/materiales/${id}/${accion}/`, { method: "POST", body });
export const movimientosMaterial = (id) => api(`${AL}/materiales/${id}/movimientos/`);
export const listarVales = (params) => api(`${AL}/vales/${q(params)}`);
export const resumenVales = () => api(`${AL}/vales/resumen/`);
export const pedirVale = (datos) => api(`${AL}/vales/`, { method: "POST", body: datos });
export const accionVale = (id, accion, body) => api(`${AL}/vales/${id}/${accion}/`, { method: "POST", body });

// Integración con Cashflow
const CF = "/api/integraciones/cashflow";
export const estadoCashflow = () => api(`${CF}/`);
export const probarCashflow = () => api(`${CF}/probar/`, { method: "POST" });
export const sincronizarCashflow = () => api(`${CF}/sincronizar/`, { method: "POST" });
export const clienteACashflow = (id) => api(`${CF}/clientes/${id}/`, { method: "POST" });

// Call Center: campañas y agentes (los agentes se evalúan aparte)
const CC = "/api/callcenter";
export const resumenCallCenter = () => api(`${CC}/resumen/`);
export const listarCampanas = (params) => api(`${CC}/campanas/${q(params)}`);
export const guardarCampana = (c) => (c.id ? api(`${CC}/campanas/${c.id}/`, { method: "PATCH", body: c }) : api(`${CC}/campanas/`, { method: "POST", body: c }));
export const eliminarCampana = (id) => api(`${CC}/campanas/${id}/`, { method: "DELETE" });

// Control de horario
const AS = "/api/asistencia";
export const estadoJornada = () => api(`${AS}/estado/`);
export const marcarJornada = (tipo, extra = {}) => api(`${AS}/marcar/`, { method: "POST", body: { tipo, ...extra } });
export const asistenciaMes = (params) => api(`${AS}/mes/${q(params)}`);
export const asistenciaHoy = () => api(`${AS}/hoy/`);
export const asistenciaReporte = (mes) => api(`${AS}/reporte/${q({ mes })}`);
export const urlAsistenciaCsv = (mes) => `${AS}/reporte/${q({ mes, formato: "csv" })}`;
export const corregirMarcaje = (m) => api(`${AS}/marcajes/`, { method: "POST", body: m });
export const borrarMarcaje = (id) => api(`${AS}/marcajes/${id}/`, { method: "DELETE" });
export const horarios = () => api(`${AS}/horarios/`);
export const guardarHorario = (h) => (h.id ? api(`${AS}/horarios/${h.id}/`, { method: "PATCH", body: h }) : api(`${AS}/horarios/`, { method: "POST", body: h }));
export const borrarHorario = (id) => api(`${AS}/horarios/${id}/`, { method: "DELETE" });
export const asignacionesHorario = () => api(`${AS}/asignaciones/`);
export const asignarHorario = (datos) => api(`${AS}/asignaciones/`, { method: "POST", body: datos });
export const feriados = () => api(`${AS}/feriados/`);
export const guardarFeriado = (f) => api(`${AS}/feriados/`, { method: "POST", body: f });
export const borrarFeriado = (id) => api(`${AS}/feriados/${id}/`, { method: "DELETE" });
export const ausencias = (ver) => api(`${AS}/ausencias/${q({ ver })}`);
export const pedirAusencia = (a) => api(`${AS}/ausencias/`, { method: "POST", body: a });
export const retirarAusencia = (id) => api(`${AS}/ausencias/${id}/`, { method: "DELETE" });
export const revisarAusencia = (id, aprobar, comentario) => api(`${AS}/ausencias/${id}/revisar/`, { method: "POST", body: { aprobar, comentario } });

// Monitoreo de actividad
const MO = "/api/monitoreo";
export const monitoreoDia = (params) => api(`${MO}/dia/${q(params)}`);
export const monitoreoPeriodo = (params) => api(`${MO}/periodo/${q(params)}`);
export const monitoreoEquipo = (fecha) => api(`${MO}/equipo/${q({ fecha })}`);
export const politicaMonitoreo = () => api(`${MO}/politica/`);
export const aceptarPolitica = () => api(`${MO}/politica/`, { method: "POST" });
export const dispositivos = () => api(`${MO}/dispositivos/`);
export const vincularDispositivo = (datos) => api(`${MO}/dispositivos/`, { method: "POST", body: datos });
export const editarDispositivo = (id, datos) => api(`${MO}/dispositivos/${id}/`, { method: "PATCH", body: datos });
export const quitarDispositivo = (id) => api(`${MO}/dispositivos/${id}/`, { method: "DELETE" });
export const reglasProductividad = () => api(`${MO}/reglas/`);
export const guardarReglaProductividad = (r) => (r.id ? api(`${MO}/reglas/${r.id}/`, { method: "PATCH", body: r }) : api(`${MO}/reglas/`, { method: "POST", body: r }));
export const borrarReglaProductividad = (id) => api(`${MO}/reglas/${id}/`, { method: "DELETE" });
export const configMonitoreo = () => api(`${MO}/configuracion/`);
export const guardarConfigMonitoreo = (d) => api(`${MO}/configuracion/`, { method: "PATCH", body: d });
export const reclasificar = () => api(`${MO}/reclasificar/`, { method: "POST", body: { dias: 30 } });
export const urlCaptura = (id) => `${MO}/capturas/${id}/`;

// Ficha de productividad
export const fichaProductividad = (params) => api(`${D}/ficha/${q(params)}`);

// Productividad por proyecto y OT, y justificaciones de la computadora
export const productividadProyectos = (mes) => api(`${MO}/proyectos/${q({ mes })}`);
export const justificaciones = (params) => api(`${MO}/justificaciones/${q(params)}`);
export const justificar = (d) => api(`${MO}/justificaciones/`, { method: "POST", body: d });
export const revisarJustificacion = (id, aprobar, nota) => api(`${MO}/justificaciones/${id}/revisar/`, { method: "POST", body: { aprobar, nota } });

// Panel gerencial
export const panelGerencial = (mes) => api(`${D}/panel/${q({ mes })}`);
export const urlExportarPanel = (mes) => `${D}/panel/exportar/${q({ mes })}`;

// Talento: evaluaciones 360°, planes de mejora, expediente y auditoría
const TA = "/api/talento";
export const ciclosEvaluacion = () => api(`${TA}/ciclos/`);
export const crearCiclo = (c) => api(`${TA}/ciclos/`, { method: "POST", body: c });
export const editarCiclo = (id, c) => api(`${TA}/ciclos/${id}/`, { method: "PATCH", body: c });
export const misEvaluaciones = () => api(`${TA}/evaluaciones/`);
export const enviarEvaluacion = (id, d) => api(`${TA}/evaluaciones/${id}/enviar/`, { method: "POST", body: d });
export const evaluacionesPorRevisar = () => api(`${TA}/evaluaciones/por-revisar/`);
export const confirmarEvaluacion = (id, d) => api(`${TA}/evaluaciones/${id}/confirmar/`, { method: "POST", body: d });
export const resultadosEvaluacion = (usuario, ciclo) => api(`${TA}/resultados/${q({ usuario, ciclo })}`);
export const avanceEvaluacion = (ciclo) => api(`${TA}/avance/${q({ ciclo })}`);
export const planesMejora = (usuario) => api(`${TA}/planes/${q({ usuario })}`);
export const guardarPlan = (p) => (p.id ? api(`${TA}/planes/${p.id}/`, { method: "PATCH", body: p }) : api(`${TA}/planes/`, { method: "POST", body: p }));
export const expediente = (usuario) => api(`${TA}/expediente/${q({ usuario })}`);
export const guardarEvento = (e) => (e.id ? api(`${TA}/expediente/${e.id}/`, { method: "PATCH", body: e }) : api(`${TA}/expediente/`, { method: "POST", body: e }));
export const borrarEvento = (id) => api(`${TA}/expediente/${id}/`, { method: "DELETE" });
export const historialSalarios = (usuario) => api(`${TA}/salarios/${q({ usuario })}`);
export const auditoria = (params) => api(`${TA}/auditoria/${q(params)}`);

// Monitoreo v10: resumen, incidencias, reglas de comportamiento, perfiles, pantallas y computadoras
export const resumenMonitoreo = (params) => api(`${MO}/resumen/${q(params)}`);
export const incidencias = (params) => api(`${MO}/incidencias/${q(params)}`);
export const revisarIncidencia = (id, d) => api(`${MO}/incidencias/${id}/`, { method: "PATCH", body: d });
export const reglasComportamiento = () => api(`${MO}/reglas-comportamiento/`);
export const guardarReglaComportamiento = (r) => (r.id ? api(`${MO}/reglas-comportamiento/${r.id}/`, { method: "PATCH", body: r }) : api(`${MO}/reglas-comportamiento/`, { method: "POST", body: r }));
export const borrarReglaComportamiento = (id) => api(`${MO}/reglas-comportamiento/${id}/`, { method: "DELETE" });
export const perfilesMonitoreo = () => api(`${MO}/perfiles/`);
export const guardarPerfilMonitoreo = (p) => (p.id ? api(`${MO}/perfiles/${p.id}/`, { method: "PATCH", body: p }) : api(`${MO}/perfiles/`, { method: "POST", body: p }));
export const borrarPerfilMonitoreo = (id) => api(`${MO}/perfiles/${id}/`, { method: "DELETE" });
export const pantallasEnVivo = () => api(`${MO}/pantallas/`);
export const computadoras = () => api(`${MO}/computadoras/`);
export const reaplicarReglas = () => api(`${MO}/reglas-comportamiento/reaplicar/`, { method: "POST" });

// Políticas y documentos del expediente
export const politicas = () => api(`${TA}/politicas/`);
export const politica = (id) => api(`${TA}/politicas/${id}/`);
export const guardarPolitica = (p) => (p.id ? api(`${TA}/politicas/${p.id}/`, { method: "PATCH", body: p }) : api(`${TA}/politicas/`, { method: "POST", body: p }));
export const borrarPolitica = (id) => api(`${TA}/politicas/${id}/`, { method: "DELETE" });
export const aceptarPoliticaEmpresa = (id, version) => api(`${TA}/politicas/${id}/aceptar/`, { method: "POST", body: { version } });
export const nuevaVersionPolitica = (id, d) => api(`${TA}/politicas/${id}/nueva-version/`, { method: "POST", body: d });
export const versionesPolitica = (id) => api(`${TA}/politicas/${id}/versiones/`);
export const constanciaPolitica = (id, usuario) => api(`${TA}/politicas/${id}/constancia/${q({ usuario })}`);
export const cumplimientoPoliticas = () => api(`${TA}/politicas/cumplimiento/`);
export const urlCumplimientoCsv = () => `${TA}/politicas/cumplimiento/?formato=csv`;
export const documentosEmpleado = (usuario) => api(`${TA}/documentos/${q({ usuario })}`);
export const estadoDocumentos = () => api(`${TA}/documentos/estado/`);
export const editarDocumento = (id, d) => api(`${TA}/documentos/${id}/`, { method: "PATCH", body: d });
export const borrarDocumento = (id) => api(`${TA}/documentos/${id}/`, { method: "DELETE" });
export const urlDocumento = (id) => `${TA}/documentos/${id}/archivo/`;
export const subirDocumento = (d, archivo) => {
  const fd = new FormData();
  Object.entries(d).forEach(([k, v]) => { if (v !== "" && v != null) fd.append(k, typeof v === "boolean" ? (v ? "true" : "false") : v); });
  fd.append("archivo", archivo);
  return api(`${TA}/documentos/`, { method: "POST", body: fd });
};

// Rentabilidad por OT, cliente y departamento; tasas de cambio
export const rentabilidadOrdenes = (params) => api(`/api/finanzas/rentabilidad/ordenes/${q(params)}`);
export const urlRentabilidadCsv = (params) => `/api/finanzas/rentabilidad/ordenes/${q({ ...params, formato: "csv" })}`;
export const rentabilidadOrden = (id) => api(`/api/finanzas/rentabilidad/ordenes/${id}/`);
export const tasasCambio = () => api("/api/finanzas/tasas/");
export const guardarTasa = (t) => api("/api/finanzas/tasas/", { method: "POST", body: t });
export const borrarTasa = (id) => api(`/api/finanzas/tasas/${id}/`, { method: "DELETE" });

// Activos y equipos
const AC = "/api/activos";
export const activos = (params) => api(`${AC}/${q(params)}`);
export const guardarActivo = (a) => (a.id ? api(`${AC}/${a.id}/`, { method: "PATCH", body: a }) : api(`${AC}/`, { method: "POST", body: a }));
export const borrarActivo = (id) => api(`${AC}/${id}/`, { method: "DELETE" });
export const historialActivo = (id) => api(`${AC}/${id}/historial/`);
export const moverActivo = (id, d) => api(`${AC}/${id}/mover/`, { method: "POST", body: d });
export const reportarActivo = (id, nota) => api(`${AC}/${id}/reportar/`, { method: "POST", body: { nota } });
export const resumenActivos = () => api(`${AC}/resumen/`);

// Accesos y permisos (mínimo privilegio)
export const accesos = () => api("/api/accesos/");
export const accesosPersonas = () => api("/api/accesos/personas/");
export const crearPerfilAcceso = (p) => api("/api/accesos/perfiles/", { method: "POST", body: p });
export const guardarPerfilAcceso = (id, p) => api(`/api/accesos/perfiles/${id}/`, { method: "PATCH", body: p });
export const borrarPerfilAcceso = (id) => api(`/api/accesos/perfiles/${id}/`, { method: "DELETE" });
export const perfilesDePersona = (id, perfiles) => api(`/api/accesos/personas/${id}/perfiles/`, { method: "POST", body: { perfiles } });
export const crearExcepcion = (e) => api("/api/accesos/excepciones/", { method: "POST", body: e });
export const borrarExcepcion = (id) => api(`/api/accesos/excepciones/${id}/`, { method: "DELETE" });
export const crearEquipoExtra = (x) => api("/api/accesos/equipo-extra/", { method: "POST", body: x });
export const borrarEquipoExtra = (id) => api(`/api/accesos/equipo-extra/${id}/`, { method: "DELETE" });

// Calibración del piloto: lo que ninguna regla de productividad clasifica
export const calibracion = (dias = 7) => api(`/api/monitoreo/calibracion/?dias=${dias}`);
export const clasificar = (r) => api("/api/monitoreo/calibracion/", { method: "POST", body: r });
