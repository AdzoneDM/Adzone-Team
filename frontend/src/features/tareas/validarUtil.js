// Cálculos de la pantalla «Por validar»: cuándo se entregó, qué tan urgente es revisarla, cómo cumplió y qué evidencia trae.

export const ESCALA_CALIDAD = [
  { valor: 1, etiqueta: "Muy por debajo", detalle: "No cumple lo pedido", tono: "border-[#d92d20] bg-[#fef3f2] text-[#b42318]" },
  { valor: 2, etiqueta: "Por debajo", detalle: "Le falta algo importante", tono: "border-[#f79009] bg-[#fffaeb] text-[#b54708]" },
  { valor: 3, etiqueta: "Cumple", detalle: "Hecho como se pidió", tono: "border-[#eaaa08] bg-[#fefdf0] text-[#854a0e]" },
  { valor: 4, etiqueta: "Bueno", detalle: "Bien hecho y cuidado", tono: "border-[#47cd89] bg-[#ecfdf3] text-[#067647]" },
  { valor: 5, etiqueta: "Excelente", detalle: "Supera lo esperado", tono: "border-[#12b76a] bg-[#d1fadf] text-[#054f31]" },
];

const MS_HORA = 3600000;
export const HORAS_NUEVA = 4;      // entregada hace menos de esto: «recién entregada»
export const HORAS_URGENTE = 48;   // esperando validación hace más de esto: «lleva mucho esperando»

/** Momento exacto de la entrega (la hora real si el servidor la guardó; si no, la última modificación). */
export const entregaDe = (t) => t.fecha_entrega_real || t.fecha_modificacion;
export const horasEsperando = (t, ahora = Date.now()) => Math.max(0, (ahora - new Date(entregaDe(t)).getTime()) / MS_HORA);

/** Urgencia de revisarla: nueva (recién llegó), normal, o larga (lleva más de dos días esperando). */
export function urgencia(t, ahora = Date.now()) {
  const h = horasEsperando(t, ahora);
  return h < HORAS_NUEVA ? "nueva" : h >= HORAS_URGENTE ? "larga" : "normal";
}

const aFecha = (iso) => new Date(`${String(iso).slice(0, 10)}T00:00:00`);
/** Días de atraso de la entrega respecto al límite (0 si llegó a tiempo). */
export function diasTarde(t) {
  if (!t.fecha_completada || !t.fecha_limite) return 0;
  return Math.max(0, Math.round((aFecha(t.fecha_completada) - aFecha(t.fecha_limite)) / 86400000));
}
export const aTiempo = (t) => diasTarde(t) === 0;

export const textoEspera = (t, ahora = Date.now()) => {
  const h = horasEsperando(t, ahora);
  if (h < 1) return "hace menos de una hora";
  if (h < 24) return `hace ${Math.floor(h)} h`;
  const d = Math.floor(h / 24);
  return `hace ${d} ${d === 1 ? "día" : "días"}`;
};

export const PESO_PRIORIDAD = { URGENTE: 4, ALTA: 3, MEDIA: 2, BAJA: 1 };

/** Clasifica un archivo de evidencia para mostrarlo: imagen, video, PDF o documento. */
export function tipoDeArchivo(e) {
  const ext = (e.nombre_original || "").split(".").pop().toLowerCase();
  if (e.es_imagen) return { clave: "imagen", nombre: "Imagen", ext };
  if (e.es_video) return { clave: "video", nombre: "Video", ext };
  if (ext === "pdf") return { clave: "pdf", nombre: "PDF", ext };
  return { clave: "documento", nombre: "Documento", ext };
}

/** La evidencia de la entrega actual (la última ronda), que es la que se revisa. */
export function evidenciaActual(t) {
  const lista = t.evidencias || [];
  if (!lista.length) return [];
  const ultima = Math.max(...lista.map((e) => e.ronda));
  return lista.filter((e) => e.ronda === ultima);
}

/** «2 imágenes · 1 PDF · 1 video» para las tarjetas. */
export function resumenEvidencia(t) {
  const cuenta = { imagen: 0, video: 0, pdf: 0, documento: 0 };
  evidenciaActual(t).forEach((e) => { cuenta[tipoDeArchivo(e).clave] += 1; });
  const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;
  return [
    cuenta.imagen && { clave: "imagen", texto: plural(cuenta.imagen, "imagen", "imágenes") },
    cuenta.video && { clave: "video", texto: plural(cuenta.video, "video", "videos") },
    cuenta.pdf && { clave: "pdf", texto: plural(cuenta.pdf, "PDF", "PDF") },
    cuenta.documento && { clave: "documento", texto: plural(cuenta.documento, "documento", "documentos") },
    t.evidencia_enlace && { clave: "enlace", texto: "enlace" },
    t.evidencia_nota?.trim() && { clave: "nota", texto: "nota" },
  ].filter(Boolean);
}

export const tamanoLegible = (bytes) => {
  if (!bytes) return "";
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(bytes < 10 * 1024 * 1024 ? 1 : 0)} MB`;
};
