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

export async function api(url, { method = "GET", body, signal } = {}) {
  const esFormulario = body instanceof FormData;
  const headers = { Accept: "application/json" };
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
  if (!response.ok) throw new ApiError(mensajeDeError(data, response.status), response.status, data);
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
export const entrar = (username, password, remember_me) => api("/api/auth/login/", { method: "POST", body: { username, password, remember_me } });
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
export const validarTarea = (id, calificacion_calidad, comentario_evaluacion) =>
  api(`${D}/tareas/${id}/validar/`, { method: "POST", body: { calificacion_calidad, comentario_evaluacion } });
export const devolverTarea = (id, comentario_revision) => api(`${D}/tareas/${id}/rechazar/`, { method: "POST", body: { comentario_revision } });
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
export const ranking = (mes) => api(`${D}/ranking/${q({ mes })}`);
export const urlExportarRanking = (mes) => `${D}/ranking/exportar/${q({ mes })}`;
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
export const aprobarOrden = (id, datos) => api(`${O}/ordenes/${id}/aprobar/`, { method: "POST", body: datos });
export const moverOrden = (id, estado, detalle = "") => api(`${O}/ordenes/${id}/mover/`, { method: "POST", body: { estado, detalle } });
export const reanudarOrden = (id) => api(`${O}/ordenes/${id}/reanudar/`, { method: "POST" });
export const entregarOrden = (id, recibido_por, nota) => api(`${O}/ordenes/${id}/entregar/`, { method: "POST", body: { recibido_por, nota } });
export const cancelarOrden = (id, motivo) => api(`${O}/ordenes/${id}/cancelar/`, { method: "POST", body: { motivo } });
export const comentarOrden = (id, texto) => api(`${O}/ordenes/${id}/comentarios/`, { method: "POST", body: { texto } });
export const subirArchivosOrden = (id, archivos) => {
  const fd = new FormData();
  archivos.forEach((a) => fd.append("archivos", a));
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
export const facturarOrden = (orden) => api(`${F}/facturas/desde_orden/`, { method: "POST", body: { orden } });
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
