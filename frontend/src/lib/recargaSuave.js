// «Recarga suave» (como Ctrl+R, pero casi sin notarse): cuando alguien entrega, valida o devuelve una tarea,
// la pantalla abierta se vuelve a montar con datos nuevos, sin recargar la página ni perder la sesión.
// No interrumpe: si estás escribiendo, tienes una ventana abierta o texto seleccionado, espera a que termines.
import { useCallback, useEffect, useRef, useState } from "react";

const EVENTO = "adzone:recarga-suave";
let excluidas = 0;   // pantallas que ya se actualizan solas con cuidado (p. ej. «Por validar»)

export const pedirRecargaSuave = () => window.dispatchEvent(new Event(EVENTO));

// Las otras pestañas y ventanas (la app instalada y el navegador) de este equipo se enteran al instante, sin esperar al servidor
const canal = typeof BroadcastChannel !== "undefined" ? new BroadcastChannel("adzone-tareas") : null;
if (canal) canal.onmessage = () => { pedirRecargaSuave(); window.dispatchEvent(new Event("adzone:refrescar-avisos")); };

/** Llamar después de validar, devolver, reabrir o eliminar: refresca esta pantalla y las demás ventanas abiertas. */
export function anunciarCambioTareas() {
  pedirRecargaSuave();
  window.dispatchEvent(new Event("adzone:refrescar-avisos"));
  try { canal?.postMessage("cambio"); } catch { /* sin canal: llegará con el siguiente aviso del servidor */ }
}

/** Para pantallas que no deben volver a montarse (guardan lo que estás revisando y ya se refrescan solas). */
export function useSinRecargaSuave() {
  useEffect(() => { excluidas += 1; return () => { excluidas -= 1; }; }, []);
}

export function ocupado() {
  if (excluidas > 0) return true;
  const a = document.activeElement;
  if (a && (/^(input|textarea|select)$/i.test(a.tagName) || a.isContentEditable)) return true;
  if (document.querySelector("dialog[open], [role='dialog'], [aria-modal='true']")) return true;
  const sel = window.getSelection?.();
  return !!(sel && !sel.isCollapsed && String(sel).trim());
}

/** Devuelve una clave que cambia en cada recarga suave: úsala como `key` del contenedor de la pantalla. */
export function useRecargaSuave(ruta) {
  const [vuelta, setVuelta] = useState(0);
  const pendiente = useRef(false);
  // Al cambiar de pantalla, la nueva ya trae datos frescos: lo pendiente se descarta
  useEffect(() => { pendiente.current = false; }, [ruta]);
  const recargar = useCallback(() => {
    if (document.visibilityState !== "visible" || ocupado()) { pendiente.current = true; return; }
    pendiente.current = false;
    const y = window.scrollY;
    setVuelta((v) => v + 1);
    // Vuelve a la misma altura cuando la pantalla termine de cargar (hasta 2 s)
    if (y > 0) {
      let intentos = 0;
      const volver = () => {
        intentos += 1;
        if (document.documentElement.scrollHeight - window.innerHeight >= y || intentos > 40) window.scrollTo(0, y);
        else setTimeout(volver, 50);
      };
      requestAnimationFrame(volver);
    }
  }, []);
  useEffect(() => {
    window.addEventListener(EVENTO, recargar);
    // Si estabas ocupado, se reintenta cada 3 s y al volver a la pestaña
    const t = setInterval(() => pendiente.current && recargar(), 3000);
    const alVolver = () => pendiente.current && recargar();
    document.addEventListener("visibilitychange", alVolver);
    return () => { window.removeEventListener(EVENTO, recargar); clearInterval(t); document.removeEventListener("visibilitychange", alVolver); };
  }, [recargar]);
  return vuelta;
}
