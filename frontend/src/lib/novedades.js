// Actualización casi en tiempo real sin recargar la página.
// La campanita consulta los avisos cada pocos segundos; cuando llega uno nuevo avisa con
// «adzone:novedades» y las pantallas con listas (Mis tareas, Inicio, Mi equipo…) se recargan solas.
import { useEffect, useRef } from "react";

const EVENTO = "adzone:novedades";

export const anunciarNovedades = () => window.dispatchEvent(new Event(EVENTO));

/** Vuelve a ejecutar `cargar` al llegar novedades, al volver a la pestaña y cada `cada` ms mientras se ve. */
export function useNovedades(cargar, cada = 15000) {
  const ref = useRef(cargar);
  useEffect(() => { ref.current = cargar; }, [cargar]);
  useEffect(() => {
    const correr = () => document.visibilityState === "visible" && ref.current?.();
    const t = setInterval(correr, cada);
    window.addEventListener(EVENTO, correr);
    document.addEventListener("visibilitychange", correr);
    return () => { clearInterval(t); window.removeEventListener(EVENTO, correr); document.removeEventListener("visibilitychange", correr); };
  }, [cada]);
}
