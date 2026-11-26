// Aviso al cerrar la plataforma con la jornada abierta («¿Estás seguro de cerrar la plataforma? No has marcado tu salida…»).
// Al cerrar la pestaña o el navegador, el navegador solo deja pedir confirmación con SU ventana (no admite texto propio);
// el texto exacto se muestra en nuestra ventana al tocar «Salir» de la plataforma.
let mensaje = null;
let omitir = false;

export const TITULO_CIERRE = "Primero cierra tu hora de salida para salir de la web";

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

// Recargar NO es cerrar: no se pregunta. El navegador no dice si es una recarga o un cierre (los dos disparan el mismo aviso),
// así que se deduce:
// - Teclado: F5, Ctrl + R, Ctrl + Mayús + R o Cmd + R.
// - Botón ⟳ del navegador: el ratón salió de la página por arriba, a la altura de los botones atrás/adelante/recargar
//   (a la izquierda, antes de las pestañas). Cerrar la pestaña (su X) o la ventana queda en otra posición.
// - Celular o tableta (sin ratón): ahí cerrar la pestaña no dispara el aviso y sí lo dispara deslizar para recargar,
//   así que no se pregunta (el texto exacto sale al tocar «Salir» de la plataforma).
let recargando = 0;
let fuera = null;   // dónde salió el ratón de la página { x, y }
let ultimoIntento = 0;
export const TEXTO_SALIDA = "Primero cierra tu hora de salida para salir de la web";
const soloTactil = () => typeof window !== "undefined" && window.matchMedia?.("(hover: none) and (pointer: coarse)").matches;
if (typeof window !== "undefined") {
  window.addEventListener("keydown", (e) => {
    const r = e.key === "F5" || e.code === "F5" || ((e.ctrlKey || e.metaKey) && !e.altKey && (e.key === "r" || e.key === "R" || e.code === "KeyR"));
    if (r) recargando = Date.now();
  }, true);
  document.addEventListener("mouseout", (e) => {
    if (e.relatedTarget) return;
    fuera = { x: e.clientX, y: e.clientY };
    // El ratón va hacia la X (arriba, fuera de la zona de atrás/recargar) con la jornada abierta: se avisa en la página con el texto
    // exacto, ANTES de cerrar (la ventana propia del navegador no admite texto propio)
    if (mensaje && !omitir && e.clientY <= 0 && !(e.clientX >= 60 && e.clientX <= 180) && Date.now() - ultimoIntento > 5 * 60000) {
      ultimoIntento = Date.now();
      window.dispatchEvent(new CustomEvent("adzone:intento-salida"));
    }
  }, true);
  document.addEventListener("mouseover", () => { fuera = null; }, true);
}
/** ¿Es una recarga? (exportada para las pruebas) */
export function esRecarga(ahora = Date.now()) {
  if (ahora - recargando < 4000) return true;
  if (fuera && fuera.y <= 0 && fuera.x >= 60 && fuera.x <= 180) return true;   // sobre el botón ⟳ (Windows, Linux y Mac)
  return false;
}

/** Escucha el cierre de la pestaña/navegador mientras haya algo pendiente. */
export function alCerrarPestana(e) {
  if (!mensaje || omitir || soloTactil() || esRecarga()) return undefined;
  e.preventDefault();
  e.returnValue = `${TITULO_CIERRE} ${mensaje}`;   // los navegadores muestran su texto propio, pero lo exigen para preguntar
  return e.returnValue;
}
