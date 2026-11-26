// Aviso al cerrar la plataforma con la jornada abierta («¿Estás seguro de cerrar la plataforma? No has marcado tu salida…»).
// Al cerrar la pestaña o el navegador, el navegador solo deja pedir confirmación con SU ventana (no admite texto propio);
// el texto exacto se muestra en nuestra ventana al tocar «Salir» de la plataforma.
let mensaje = null;
let omitir = false;

export const TITULO_CIERRE = "¿Estás seguro de cerrar la plataforma?";

/** El texto según el estado de la jornada (null si no hay nada pendiente). */
export function textoCierre(estado) {
  if (estado?.estado === "EN_PAUSA") {
    return estado.en_almuerzo ? "Estás en tu almuerzo: no has marcado el fin del almuerzo ni tu salida."
      : "Estás en pausa y no has marcado tu salida.";
  }
  if (estado?.estado !== "TRABAJANDO") return null;
  const almorzo = (estado.hoy?.almuerzo_seg || 0) > 0;
  const tieneAlmuerzo = !!(estado.limites?.almuerzo_inicio || estado.limites?.almuerzo_horario);
  return !almorzo && tieneAlmuerzo ? "No has marcado tu salida ni tu almuerzo." : "No has marcado tu salida.";
}

export const fijarMensajeCierre = (m) => { mensaje = m || null; };
export const mensajeCierre = () => mensaje;

/** Para recargas automáticas (versión nueva, reintento): sin preguntar. */
export function recargarSinAviso() {
  omitir = true;
  window.location.reload();
}

// Recargar con el teclado (F5, Ctrl + R, Ctrl + Mayús + R, Cmd + R) no es cerrar: no se pregunta.
// (El botón de recargar del navegador no se puede distinguir de cerrar: el navegador no lo dice.)
let recargando = 0;
if (typeof window !== "undefined") {
  window.addEventListener("keydown", (e) => {
    const r = e.key === "F5" || ((e.ctrlKey || e.metaKey) && !e.altKey && (e.key === "r" || e.key === "R"));
    if (r) recargando = Date.now();
  }, true);
}

/** Escucha el cierre de la pestaña/navegador mientras haya algo pendiente. */
export function alCerrarPestana(e) {
  if (!mensaje || omitir || Date.now() - recargando < 3000) return undefined;
  e.preventDefault();
  e.returnValue = `${TITULO_CIERRE} ${mensaje}`;   // los navegadores muestran su texto propio, pero lo exigen para preguntar
  return e.returnValue;
}
