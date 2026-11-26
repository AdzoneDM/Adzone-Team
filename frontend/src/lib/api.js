// Cliente de la API de Adzone Team. Misma sesión (cookie) y token CSRF en todas las llamadas.

// Alguien (yo) validó, devolvió, reabrió o eliminó una tarea: las demás pestañas y ventanas abiertas se refrescan al instante
import { anunciarCambioTareas } from "@/lib/recargaSuave";
const tareasCambiaron = (r) => { anunciarCambioTareas(); return r; };

export function getCookie(name) {
  const match = document.cookie.split(";").map((c) => c.trim()).find((c) => c.startsWith(name + "="));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

/** Convierte las respuestas de error de Django REST en un mensaje legible. */
function mensajeDeError(data, status, espera) {
  if (status === 403) return data?.detail || "No tienes permiso para hacer esto.";
  if (status === 404) return "No se encontró. Puede que ya no exista o no tengas acceso.";
  // Límite de intentos del servidor (trae «Retry-After»): aviso corto con la espera real, en segundos.
  // Si el 429 lo explica la propia pantalla (recordatorio reciente, escribiendo muy rápido…), se muestra esa explicación.
  if (status === 429) return espera || !data?.detail ? `Demasiados intentos seguidos. Espera ${espera ? `${espera} s` : "unos segundos"} y vuelve a probar.` : data.detail;
  if (status >= 500) return "El servidor tuvo un problema. Inténtalo de nuevo en un momento.";
  if (data && typeof data === "object") {
    const partes = Object.entries(data).map(([clave, valor]) => {
      const texto = Array.isArray(valor) ? valor.join(" ")
        : valor && typeof valor === "object" ? Object.values(valor).flat().join(" ") : valor;
      return ["detail", "non_field_errors", "error", "archivo"].includes(clave) ? texto : `${CAMPOS[clave] || clave}: ${texto}`;
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

// Si el servidor o la red no responden, la petición se corta y se avisa (antes un botón podía quedarse «cargando» para siempre).
// Con archivos (videos) se espera mucho más: dependen de la velocidad de subida.
const ESPERA_MS = 45000;
const ESPERA_ARCHIVOS_MS = 20 * 60000;

export async function api(url, { method = "GET", body, signal: externa } = {}) {
  const esFormulario = body instanceof FormData;
  const control = new AbortController();
  let vencio = false;
  const reloj = setTimeout(() => { vencio = true; control.abort(); }, esFormulario ? ESPERA_ARCHIVOS_MS : ESPERA_MS);
  if (externa) { if (externa.aborted) control.abort(); else externa.addEventListener("abort", () => control.abort(), { once: true }); }
  const signal = control.signal;
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
    clearTimeout(reloj);
    if (vencio) throw new ApiError("Tardó demasiado en responder. Revisa tu internet; si era una validación o una entrega, mira si ya se aplicó antes de repetirla.", 0);
    if (e.name === "AbortError") throw e;
    throw new ApiError("Sin conexión. Revisa el internet e inténtalo de nuevo.", 0);
  }
  if (response.status === 204) { clearTimeout(reloj); return null; }
  let data;
  try { data = await response.json(); } catch { data = null; } finally { clearTimeout(reloj); }
  if (vencio && data === null) throw new ApiError("Tardó demasiado en responder. Revisa tu internet y vuelve a intentarlo.", 0);
  if (!response.ok) {
    // La sesión se cerró (inactividad, código pendiente) o falta activar los dos pasos: la app se entera y reacciona
    if ((response.status === 401 && data?.detail) || data?.activar_dos_pasos) {
      window.dispatchEvent(new CustomEvent(EVENTO_SESION, { detail: { estado: response.status, ...data } }));
    }
    throw new ApiError(mensajeDeError(data, response.status, Number(response.headers.get("Retry-After")) || 0), response.status, data);
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
export const salir = (pushEndpoint) => api("/api/auth/logout/", { method: "POST", body: pushEndpoint ? { push_endpoint: pushEndpoint } : {} });
export const cambiarClave = (actual, nueva) => api("/api/auth/cambiar-clave/", { method: "POST", body: { actual, nueva } });

// Tareas
export const listarTareas = (params) => api(`${D}/tareas/${q(params)}`);
export const obtenerTarea = (id) => api(`${D}/tareas/${id}/`);
export const guardarTarea = (t) => (t.id ? api(`${D}/tareas/${t.id}/`, { method: "PATCH", body: t }) : api(`${D}/tareas/`, { method: "POST", body: t }));
// Eliminación lógica: con motivo; la tarea deja de contar pero se conserva (historial) y se puede recuperar
export const eliminarTarea = (id, motivo) => api(`${D}/tareas/${id}/eliminar/`, { method: "POST", body: { motivo } }).then(tareasCambiaron);
export const tareasEliminadas = () => api(`${D}/tareas/eliminadas/`);
export const restaurarTarea = (id) => api(`${D}/tareas/${id}/restaurar/`, { method: "POST" }).then(tareasCambiaron);
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
  api(`${D}/tareas/${id}/validar/`, { method: "POST", body: { calificacion_calidad, comentario_evaluacion, ...extra } }).then(tareasCambiaron);
// Devolver una tarea; con «archivos» (bocetos, imágenes, PDF) viaja como formulario y quedan de referencia para la corrección
export const devolverTarea = (id, comentario_revision, extra = {}, archivos = []) => {
  if (!archivos.length) return api(`${D}/tareas/${id}/rechazar/`, { method: "POST", body: { comentario_revision, ...extra } }).then(tareasCambiaron);
  const f = new FormData();
  f.append("comentario_revision", comentario_revision);
  Object.entries(extra).forEach(([k, v]) => { if (v != null) f.append(k, typeof v === "object" ? JSON.stringify(v) : v); });
  archivos.forEach((a) => f.append("archivos", a, a.name));
  return api(`${D}/tareas/${id}/rechazar/`, { method: "POST", body: f }).then(tareasCambiaron);
};
// Referencias de una tarea: bocetos o imágenes que adjunta quien supervisa (al asignar o al corregir)
export const subirReferencias = (id, archivos, { nota = "", momento = "ASIGNACION" } = {}) => {
  const f = new FormData();
  archivos.forEach((a) => f.append("archivos", a, a.name));
  if (nota) f.append("nota", nota);
  f.append("momento", momento);
  return api(`${D}/tareas/${id}/referencias/`, { method: "POST", body: f });
};
export const misRevisores = () => api(`${D}/mis-revisores/`);
export const quitarReferencia = (url) => api(url, { method: "DELETE" });
// Reabrir en cualquier estado: { motivo, a: "REVISION" | "CORREGIR", fecha_limite?, descripcion? }
export const reabrirTarea = (id, datos) => api(`${D}/tareas/${id}/reabrir/`, { method: "POST", body: typeof datos === "string" ? { motivo: datos } : datos }).then(tareasCambiaron);
export const cancelarTarea = (id, motivo) => api(`${D}/tareas/${id}/cancelar/`, { method: "POST", body: { motivo } });
export const recordarTarea = (id, mensaje) => api(`${D}/tareas/${id}/recordar/`, { method: "POST", body: { mensaje } });
export const pedirTrabajo = () => api(`${D}/pedir-trabajo/`, { method: "POST" });
export const bloquearTarea = (id, motivo) => api(`${D}/tareas/${id}/bloquear/`, { method: "POST", body: { motivo } });
export const desbloquearTarea = (id, nota) => api(`${D}/tareas/${id}/desbloquear/`, { method: "POST", body: { nota } });
export const comentariosTarea = (id) => api(`${D}/tareas/${id}/comentarios/`);
export const comentarTarea = (id, texto, respondeA = null) => api(`${D}/tareas/${id}/comentarios/`, { method: "POST", body: { texto, responde_a: respondeA } });
export const resumenTareas = (params = {}) => api(`${D}/resumen-tareas/${q(params)}`);
export const disponibilidad = () => api(`${D}/disponibilidad/`);
export const historialTareas = (params = {}) => api(`${D}/historial-tareas/${q(params)}`);
export const urlHistorialCsv = (params = {}) => `${D}/historial-tareas/${q({ ...params, formato: "csv", pagina: "" })}`;
export const miDisponibilidad = () => api(`${D}/mi-disponibilidad/`);
// Actividades adicionales y colaboración (12.4)
export const listarActividades = (params = {}) => api(`${D}/actividades/${q(params)}`);
export const crearActividad = (datos) => api(`${D}/actividades/`, { method: "POST", body: datos });
export const borrarActividad = (id) => api(`${D}/actividades/${id}/`, { method: "DELETE" });
export const revisarActividad = (id, aprobar, comentario) =>
  api(`${D}/actividades/${id}/${aprobar ? "validar" : "rechazar"}/`, { method: "POST", body: { comentario } });
export const listarColaboraciones = (params = {}) => api(`${D}/colaboraciones/${q(params)}`);
export const crearColaboracion = (datos) => api(`${D}/colaboraciones/`, { method: "POST", body: datos });
export const retirarColaboracion = (id) => api(`${D}/colaboraciones/${id}/`, { method: "DELETE" });
export const pasoColaboracion = (id, accion, texto = "", minutos = 0) =>
  api(`${D}/colaboraciones/${id}/accion/`, { method: "POST", body: { accion, texto, minutos } });
export const personasColaborar = () => api(`${D}/personas/`);
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
export const matrizOrganigrama = () => api("/api/organizacion/organigrama/matriz/");
export const urlMatrizExcel = "/api/organizacion/organigrama/matriz/?formato=xlsx";
export const versionesOrganigrama = () => api("/api/organizacion/organigrama/versiones/");
export const aprobarOrganigrama = (datos) => api("/api/organizacion/organigrama/versiones/", { method: "POST", body: datos });
export const usuarios = () => api("/api/organizacion/usuarios/");
export const guardarUsuario = (u) => (u.id ? api(`/api/organizacion/usuarios/${u.id}/`, { method: "PATCH", body: u }) : api("/api/organizacion/usuarios/", { method: "POST", body: u }));
export const usuarioPendientes = (id) => api(`/api/organizacion/usuarios/${id}/pendientes/`);
export const usuarioEstado = (id, datos) => api(`/api/organizacion/usuarios/${id}/estado/`, { method: "POST", body: datos });
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
export const registrarPago = (factura, pago) => {
  const { comprobante, ...datos } = pago;
  if (!comprobante) return api(`${F}/facturas/${factura}/pagos/`, { method: "POST", body: datos });
  const f = new FormData(); // con comprobante (foto o PDF) el pago va como formulario
  Object.entries(datos).forEach(([k, v]) => f.append(k, v ?? ""));
  f.append("comprobante", comprobante);
  return api(`${F}/facturas/${factura}/pagos/`, { method: "POST", body: f });
};
// Imágenes y documentos de una factura, comprobante de cada pago y reporte descargable
export const subirAdjuntosFactura = (id, archivos, tipo = "OTRO", nota = "") => {
  const f = new FormData();
  [...archivos].forEach((a) => f.append("archivos", a));
  f.append("tipo", tipo);
  if (nota) f.append("nota", nota);
  return api(`${F}/facturas/${id}/adjuntos/`, { method: "POST", body: f });
};
// Recordatorios personales (solo los de quien consulta)
export const listarRecordatorios = () => api(`${D}/recordatorios/`);
export const guardarRecordatorio = (r) => (r.id ? api(`${D}/recordatorios/${r.id}/`, { method: "PATCH", body: r }) : api(`${D}/recordatorios/`, { method: "POST", body: r }));
export const borrarRecordatorio = (id) => api(`${D}/recordatorios/${id}/`, { method: "DELETE" });
export const accionRecordatorio = (id, accion, body = {}) => api(`${D}/recordatorios/${id}/${accion}/`, { method: "POST", body });
export const historialFactura = (id) => api(`${F}/facturas/${id}/historial/`);
export const cambiarAdjuntoFactura = (id, adjunto, datos) => api(`${F}/facturas/${id}/adjuntos/${adjunto}/`, { method: "PATCH", body: datos });
export const reemplazarAdjuntoFactura = (id, adjunto, archivo) => {
  const f = new FormData();
  f.append("archivo", archivo);
  return api(`${F}/facturas/${id}/adjuntos/${adjunto}/reemplazar/`, { method: "POST", body: f });
};
export const borrarAdjuntoFactura = (id, adjunto) => api(`${F}/facturas/${id}/adjuntos/${adjunto}/`, { method: "DELETE" });
export const urlAdjuntoFactura = (id, adjunto, descargar = false) => `${F}/facturas/${id}/adjuntos/${adjunto}/${descargar ? "?descargar=1" : ""}`;
export const urlComprobantePago = (id, descargar = false) => `${F}/pagos/${id}/comprobante/${descargar ? "?descargar=1" : ""}`;
export const subirComprobantePago = (id, archivo) => { const f = new FormData(); f.append("comprobante", archivo); return api(`${F}/pagos/${id}/comprobante/`, { method: "POST", body: f }); };
export const quitarComprobantePago = (id) => api(`${F}/pagos/${id}/comprobante/`, { method: "DELETE" });
export const urlReporteFacturas = (params = {}) => `${F}/facturas/reporte/${q(params)}`;
/** Totales y conteos de lo que incluiría el reporte con estos filtros (antes de descargarlo). */
export const resumenReporteFacturas = (params = {}) => api(`${F}/facturas/reporte/${q({ ...params, formato: "resumen" })}`);
/** Descarga el reporte (xlsx o pdf); si el servidor lo rechaza (por ejemplo, demasiadas facturas para un PDF) se lanza su mensaje en vez de bajar una página de error. */
export async function descargarReporteFacturas(params) {
  const r = await fetch(urlReporteFacturas(params), { credentials: "same-origin" });
  if (!r.ok) {
    let data = null;
    try { data = await r.json(); } catch { /* sin cuerpo legible */ }
    throw new ApiError(mensajeDeError(data, r.status), r.status, data);
  }
  const blob = await r.blob();
  const nombre = (r.headers.get("Content-Disposition") || "").match(/filename="?([^";]+)"?/)?.[1] || `facturas.${params.formato}`;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}
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
// Hora de almuerzo: fija (todos los días) o solo hoy; «más tarde» la pospone unos minutos; «visto» evita repetir el aviso
export const elegirAlmuerzo = (hora, soloHoy = false) => api(`${AS}/mi-almuerzo/`, { method: "POST", body: { hora, solo_hoy: soloHoy } });
export const posponerAlmuerzo = (minutos) => api(`${AS}/mi-almuerzo/`, { method: "POST", body: { posponer: minutos } });
export const almuerzoVisto = () => api(`${AS}/mi-almuerzo/`, { method: "POST", body: { visto: true } });
export const marcarJornada = (tipo, extra = {}) => api(`${AS}/marcar/`, { method: "POST", body: { tipo, ...extra } });
// Señal de vida: la plataforma sigue abierta (la jornada ya no se cierra sola: el cierre es manual)
export const senalPresencia = () => api(`${AS}/presencia/`, { method: "POST" });
export const asistenciaMes = (params) => api(`${AS}/mes/${q(params)}`);
export const asistenciaHoy = () => api(`${AS}/hoy/`);
export const asistenciaReporte = (mes) => api(`${AS}/reporte/${q({ mes })}`);
export const urlAsistenciaCsv = (mes) => `${AS}/reporte/${q({ mes, formato: "csv" })}`;
export const corregirMarcaje = (m) => api(`${AS}/marcajes/`, { method: "POST", body: m });
// Justificación de tardanzas (solo el supervisor de la persona; no se borran, al modificar queda el antes)
export const justificarTardanza = (j) => (j.id ? api(`${AS}/justificaciones/${j.id}/`, { method: "PATCH", body: { tipo: j.tipo, nota: j.nota } })
  : api(`${AS}/justificaciones/`, { method: "POST", body: j }));
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

// Ficha de productividad
export const fichaProductividad = (params) => api(`${D}/ficha/${q(params)}`);

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
// Seguridad: sesiones abiertas propias (verlas y cerrarlas) y bitácora de accesos (quien tiene «Ver la auditoría»)
export const misSesiones = () => api("/api/cuenta/sesiones/");
export const cerrarSesion = (id) => api(`/api/cuenta/sesiones/${id}/`, { method: "DELETE" });
export const cerrarOtrasSesiones = () => api("/api/cuenta/sesiones/cerrar-otras/", { method: "POST" });
export const bitacoraAccesos = (params) => api(`/api/seguridad/accesos/${q(params)}`);

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
export const alcanceDePersona = (id, datos) => api(`/api/accesos/personas/${id}/alcance/`, { method: "POST", body: datos });
export const perfilesDePersona = (id, perfiles) => api(`/api/accesos/personas/${id}/perfiles/`, { method: "POST", body: { perfiles } });
export const crearExcepcion = (e) => api("/api/accesos/excepciones/", { method: "POST", body: e });
export const borrarExcepcion = (id) => api(`/api/accesos/excepciones/${id}/`, { method: "DELETE" });
export const crearEquipoExtra = (x) => api("/api/accesos/equipo-extra/", { method: "POST", body: x });
export const borrarEquipoExtra = (id) => api(`/api/accesos/equipo-extra/${id}/`, { method: "DELETE" });

// Lugares de marcaje (oficina con pantalla de QR) y pantalla pública del QR
export const sitiosMarcaje = () => api(`${AS}/sitios/`);
export const guardarSitio = (s) => api(s.id ? `${AS}/sitios/${s.id}/` : `${AS}/sitios/`, { method: s.id ? "PATCH" : "POST", body: s });
export const borrarSitio = (id) => api(`${AS}/sitios/${id}/`, { method: "DELETE" });
export const nuevaClaveSitio = (id) => api(`${AS}/sitios/${id}/nueva-clave/`, { method: "POST" });
export const miIp = () => api(`${AS}/mi-ip/`);
export const pantallaQR = (clave) => api(`${AS}/pantalla/${encodeURIComponent(clave)}/`);

// Portal del cliente
export const enlacesCliente = (ordenId) => api(`/api/operaciones/ordenes/${ordenId}/enlaces-cliente/`);
export const crearEnlaceCliente = (ordenId, datos) => api(`/api/operaciones/ordenes/${ordenId}/enlaces-cliente/`, { method: "POST", body: datos });
export const revocarEnlaceCliente = (id) => api(`/api/operaciones/enlaces-cliente/${id}/revocar/`, { method: "POST" });
const PT = (t) => `/api/portal/${encodeURIComponent(t)}`;
export const portal = (t) => api(`${PT(t)}/`);
export const portalArchivo = (t, id) => `${PT(t)}/archivos/${id}/`;
export const portalAprobar = (t, oa, datos) => api(`${PT(t)}/aprobar/${oa}/`, { method: "POST", body: datos });
export const portalFirmar = (t, acta, datos) => api(`${PT(t)}/actas/${acta}/firmar/`, { method: "POST", body: datos });

// Inteligencia
export const resumenSemanal = () => api(`${D}/resumen-semanal/`);
export const regenerarResumen = () => api(`${D}/resumen-semanal/`, { method: "POST" });
export const sugerirAsignacion = (titulo, descripcion = "") => api(`${D}/sugerir-asignacion/`, { method: "POST", body: { titulo, descripcion } });
export const borradorEvaluacion = (id) => api(`/api/talento/evaluaciones/${id}/borrador/`, { method: "POST" });

// Tableros por departamento (KPIs, personal y políticas)
export const tablerosDepartamentos = () => api(`${D}/departamentos/`);
export const tableroDepartamento = (id, { anio, mes, vista }) => api(`${D}/departamentos/${id}/?anio=${anio}&mes=${mes}&vista=${vista}`);
export const guardarInfoDepartamento = (id, datos) => api(`${D}/departamentos/${id}/`, { method: "PATCH", body: datos });
export const guardarDocumentoArea = (deptoId, doc, archivo) => {
  const f = new FormData();
  ["tipo", "titulo", "resumen", "contenido"].forEach((k) => f.append(k, doc[k] ?? ""));
  f.append("solo_encargados", doc.solo_encargados ? "true" : "false");
  if (archivo) f.append("archivo", archivo);
  return api(doc.id ? `${D}/documentos-area/${doc.id}/` : `${D}/departamentos/${deptoId}/documentos/`, { method: doc.id ? "PATCH" : "POST", body: f });
};
export const borrarDocumentoArea = (id) => api(`${D}/documentos-area/${id}/`, { method: "DELETE" });
export const urlDocumentoArea = (id) => `${D}/documentos-area/${id}/`;

// Documentos compartidos: subir, organizar y enviar a personas o áreas
export const documentosLista = (params = {}, signal) => api(`/api/documentos/${q(params)}`, { signal });
export const documentosResumen = () => api("/api/documentos/resumen/");
export const documentoSubir = ({ archivo, destinatarios = [], areas = [], ...datos }) => {
  const f = new FormData();
  f.append("archivo", archivo);
  Object.entries(datos).forEach(([k, v]) => f.append(k, v ?? ""));
  destinatarios.forEach((id) => f.append("destinatarios", id));
  areas.forEach((id) => f.append("areas", id));
  return api("/api/documentos/", { method: "POST", body: f });
};
export const documentoEditar = (id, datos) => api(`/api/documentos/${id}/`, { method: "PATCH", body: datos });
export const documentoEliminar = (id) => api(`/api/documentos/${id}/`, { method: "DELETE" });
export const urlDocumentoCompartido = (id, descargar = false) => `/api/documentos/${id}/archivo/${descargar ? "?descargar=1" : ""}`;

// Chat: sala de la empresa y chats privados
export const chatConversaciones = (signal) => api("/api/chat/conversaciones/", { signal });
export const chatAbrir = (persona) => api("/api/chat/conversaciones/", { method: "POST", body: { persona } });
export const chatPersonas = (texto = "", signal) => api(`/api/chat/personas/${q({ q: texto })}`, { signal });
export const chatMensajes = (conversacion, params = {}, signal) => api(`/api/chat/conversaciones/${conversacion}/mensajes/${q(params)}`, { signal });
/** Sube un formulario con archivos informando el avance (0 a 1): `fetch` no lo permite, por eso XMLHttpRequest. Mismos encabezados y errores que `api`. */
function subirConProgreso(url, formulario, alAvanzar) {
  return new Promise((resolver, rechazar) => {
    const x = new XMLHttpRequest();
    x.open("POST", url);
    x.withCredentials = true;
    x.timeout = 20 * 60000;
    x.setRequestHeader("Accept", "application/json");
    x.setRequestHeader("X-CSRFToken", getCookie("csrftoken") || "");
    if (Date.now() - ultimaInteraccion < 60000) x.setRequestHeader("X-Actividad", "1");
    x.upload.onprogress = (e) => { if (e.lengthComputable) alAvanzar?.(e.loaded / e.total); };
    x.onload = () => {
      let datos = null;
      try { datos = JSON.parse(x.responseText); } catch { /* sin cuerpo */ }
      if (x.status >= 200 && x.status < 300) return resolver(datos);
      if ((x.status === 401 && datos?.detail) || datos?.activar_dos_pasos) window.dispatchEvent(new CustomEvent(EVENTO_SESION, { detail: { estado: x.status, ...datos } }));
      if (x.status === 413) return rechazar(new ApiError("El archivo es demasiado grande para el servidor.", 413, datos));
      rechazar(new ApiError(mensajeDeError(datos, x.status, Number(x.getResponseHeader("Retry-After")) || 0), x.status, datos));
    };
    x.onerror = () => rechazar(new ApiError("Sin conexión. Revisa el internet e inténtalo de nuevo.", 0));
    x.ontimeout = () => rechazar(new ApiError("Tardó demasiado en subir. Revisa tu internet e inténtalo de nuevo.", 0));
    x.send(formulario);
  });
}

export const chatEnviar = (conversacion, texto, archivo = null, alAvanzar = null, respondeA = null) => {
  if (!archivo) return api(`/api/chat/conversaciones/${conversacion}/mensajes/`, { method: "POST", body: { texto, ...(respondeA ? { responde_a: respondeA } : {}) } });
  const f = new FormData(); // con archivo (documento, imagen, video o ZIP) el mensaje va como formulario
  f.append("texto", texto || "");
  if (respondeA) f.append("responde_a", String(respondeA));
  f.append("archivo", archivo);
  return subirConProgreso(`/api/chat/conversaciones/${conversacion}/mensajes/`, f, alAvanzar);
};
export const urlArchivoChat = (mensaje, descargar = false) => `/api/chat/mensajes/${mensaje}/archivo/${descargar ? "?descargar=1" : ""}`;
export const chatGrupoCrear = (datos) => api("/api/chat/grupos/", { method: "POST", body: datos });
export const chatGrupo = (id) => api(`/api/chat/grupos/${id}/`);
export const chatGrupoEditar = (id, datos) => api(`/api/chat/grupos/${id}/`, { method: "PATCH", body: datos });
export const chatGrupoEliminar = (id) => api(`/api/chat/grupos/${id}/`, { method: "DELETE" });
export const chatBorrar = (id) => api(`/api/chat/mensajes/${id}/`, { method: "DELETE" });
// Editar tu mensaje (solo durante 5 minutos desde que lo enviaste: el servidor lo valida)
export const chatEditar = (id, texto) => api(`/api/chat/mensajes/${id}/`, { method: "PATCH", body: { texto } });
// Evidencia de lectura: quién vio el mensaje (y cuándo), quién lo tiene pendiente y quién abrió el archivo
export const chatVistos = (id) => api(`/api/chat/mensajes/${id}/vistos/`);
export const chatAbierto = (id) => api(`/api/chat/mensajes/${id}/abierto/`, { method: "POST" }).catch(() => {});
export const chatResumen = () => api("/api/chat/resumen/");
// Reacción rápida (una por persona; el mismo emoji la quita) y reenviar a otras conversaciones tuyas
export const chatReaccion = (id, emoji) => api(`/api/chat/mensajes/${id}/reaccion/`, { method: "POST", body: { emoji } });
export const chatReenviar = (id, conversaciones) => api(`/api/chat/mensajes/${id}/reenviar/`, { method: "POST", body: { conversaciones } });
export const chatLeido = (conversacion, hasta) => api(`/api/chat/conversaciones/${conversacion}/leido/`, { method: "POST", body: { hasta } });

// Oportunidades comerciales (Marketing) y solicitudes de servicio por departamento
const CM = "/api/comercial";
export const listarOportunidades = (params) => api(`${CM}/oportunidades/${q(params)}`);
export const resumenOportunidades = (params) => api(`${CM}/oportunidades/resumen/${q(params)}`);
export const obtenerOportunidad = (id) => api(`${CM}/oportunidades/${id}/`);
export const guardarOportunidad = (o) => (o.id ? api(`${CM}/oportunidades/${o.id}/`, { method: "PATCH", body: o }) : api(`${CM}/oportunidades/`, { method: "POST", body: o }));
export const comentarOportunidad = (id, texto) => api(`${CM}/oportunidades/${id}/comentar/`, { method: "POST", body: { texto } });
export const listarSolicitudes = (params) => api(`${CM}/solicitudes/${q(params)}`);
export const obtenerSolicitud = (id) => api(`${CM}/solicitudes/${id}/`);
export const guardarSolicitud = (s) => (s.id ? api(`${CM}/solicitudes/${s.id}/`, { method: "PATCH", body: s }) : api(`${CM}/solicitudes/`, { method: "POST", body: s }));
export const comentarSolicitud = (id, texto) => api(`${CM}/solicitudes/${id}/comentar/`, { method: "POST", body: { texto } });
export const convertirSolicitud = (id, datos = {}) => api(`${CM}/solicitudes/${id}/convertir/`, { method: "POST", body: datos });

// Asistente con IA (consulta los datos con los permisos de quien pregunta) y análisis del día
const IA = "/api/asistente";
export const asistenteEstado = () => api(`${IA}/estado/`);
export const asistenteConversaciones = () => api(`${IA}/conversaciones/`);
export const asistenteConversacion = (id) => api(`${IA}/conversaciones/${id}/`);
export const asistenteBorrar = (id) => api(`${IA}/conversaciones/${id}/`, { method: "DELETE" });
export const asistentePreguntar = (texto, conversacion) => api(`${IA}/preguntar/`, { method: "POST", body: { texto, ...(conversacion ? { conversacion } : {}) } });
export const asistenteInforme = () => api(`${IA}/informe/`);
export const asistenteActualizarInforme = () => api(`${IA}/informe/`, { method: "POST" });

// Casos operativos (incidencias, solicitudes y mejoras que centraliza Operaciones)
const CS = "/api/casos";
export const casosOpciones = () => api(`${CS}/opciones/`);
export const listarCasos = (params) => api(`${CS}/${q(params)}`);
export const obtenerCaso = (id) => api(`${CS}/${id}/`);
export const reportarCaso = (datos, archivos = []) => {
  const f = new FormData();
  Object.entries(datos).forEach(([k, v]) => { if (v != null && v !== "") f.append(k, v); });
  archivos.forEach((a) => f.append("evidencias", a));
  return api(`${CS}/`, { method: "POST", body: f });
};
export const accionCaso = (id, datos, archivos = []) => {
  if (!archivos.length) return api(`${CS}/${id}/accion/`, { method: "POST", body: datos });
  const f = new FormData();
  Object.entries(datos).forEach(([k, v]) => { if (v != null && v !== "") f.append(k, v); });
  archivos.forEach((a) => f.append("evidencias", a));
  return api(`${CS}/${id}/accion/`, { method: "POST", body: f });
};
export const urlEvidenciaCaso = (id, eid, descargar = false) => `${CS}/${id}/evidencias/${eid}/${descargar ? "?descargar=1" : ""}`;
