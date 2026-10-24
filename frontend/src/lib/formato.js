// Fechas, nombres y textos que se repiten en todas las pantallas.

/** Fecha local de hoy como AAAA-MM-DD (sin desfase por zona horaria). */
export const hoyISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

export const mesActual = () => hoyISO().slice(0, 7);

const aFecha = (iso) => {
  const [a, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(a, m - 1, d || 1);
};

/** "2026-10" → "octubre 2026" */
export const nombreMes = (periodo) => aFecha(periodo.slice(0, 7) + "-01").toLocaleDateString("es-DO", { month: "long", year: "numeric" });

/** "2026-10-24" → "24 oct." ; con año si no es el actual */
export const fechaCorta = (iso) => {
  if (!iso) return "";
  const f = aFecha(iso);
  const opciones = { day: "numeric", month: "short" };
  if (f.getFullYear() !== new Date().getFullYear()) opciones.year = "numeric";
  return f.toLocaleDateString("es-DO", opciones);
};

export const fechaHora = (iso) =>
  iso ? new Date(iso).toLocaleString("es-DO", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) : "";

/** Días desde hoy hasta la fecha (negativo = ya pasó). */
export const diasHasta = (iso) => Math.round((aFecha(iso) - aFecha(hoyISO())) / 86400000);

/** Texto de vencimiento para tareas abiertas. */
export function vencimiento(iso) {
  const d = diasHasta(iso);
  if (d < -1) return { texto: `Venció hace ${-d} días`, tono: "rojo" };
  if (d === -1) return { texto: "Venció ayer", tono: "rojo" };
  if (d === 0) return { texto: "Vence hoy", tono: "amarillo" };
  if (d === 1) return { texto: "Vence mañana", tono: "amarillo" };
  if (d <= 6) return { texto: `Vence en ${d} días`, tono: "neutro" };
  return { texto: `Entrega ${fechaCorta(iso)}`, tono: "neutro" };
}

export const hace = (iso) => {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "ahora";
  if (s < 3600) return `hace ${Math.floor(s / 60)} min`;
  if (s < 86400) return `hace ${Math.floor(s / 3600)} h`;
  const d = Math.floor(s / 86400);
  return d === 1 ? "ayer" : d < 7 ? `hace ${d} días` : fechaCorta(iso);
};

export const iniciales = (nombre = "") =>
  nombre.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join("") || "?";

export const primerNombre = (nombre = "") => nombre.split(/\s+/)[0] || nombre;

export const ESTADOS = {
  PENDIENTE: "Por empezar",
  EN_PROGRESO: "En curso",
  EN_REVISION: "En revisión",
  COMPLETADA: "Validada",
  CANCELADA: "Cancelada",
};

export const PRIORIDADES = { ALTA: "Alta", MEDIA: "Media", BAJA: "Baja" };

export const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;

export const puntos = (n, dec = 0) => (n == null ? "—" : Number(n).toLocaleString("es-DO", { maximumFractionDigits: dec, minimumFractionDigits: 0 }));
