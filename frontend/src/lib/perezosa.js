// Carga de pantallas bajo demanda que sobrevive a las actualizaciones.
// Cada versión nueva cambia los nombres de los archivos de la app. Una pestaña que ya estaba abierta intenta cargar una
// pantalla con el nombre viejo (que ya no existe) y quedaba cargando hasta recargar a mano. Ahora, si un archivo no se
// puede cargar, la app se recarga sola UNA vez (trae la versión nueva); si sigue fallando, muestra el error en pantalla.
import { lazy } from "react";

const LLAVE = "adzone:recarga-por-version";
const ESPERA_MS = 20000; // no más de una recarga automática cada 20 s (evita un bucle si el servidor está caído)

let recargando = false;

/** Recarga sola si no lo hizo hace poco. Devuelve true si inició la recarga. */
export function recargarPorVersionNueva() {
  if (recargando) return true;
  try {
    const antes = Number(sessionStorage.getItem(LLAVE) || 0);
    if (Date.now() - antes < ESPERA_MS) return false;
    sessionStorage.setItem(LLAVE, String(Date.now()));
  } catch { /* sin almacenamiento: se intenta igual */ }
  recargando = true;
  window.location.reload();
  return true;
}

/** Igual que React.lazy, pero ante un archivo que ya no existe recarga la app una vez. */
export function perezosa(importador) {
  return lazy(() => importador().catch((error) => {
    if (recargarPorVersionNueva()) return new Promise(() => {}); // la página se está recargando: no se muestra nada intermedio
    if (error && typeof error === "object") error.deVersionNueva = true; // para que el aviso lo explique
    throw error; // ya se recargó hace poco: lo atrapa el límite de errores
  }));
}

// Vite avisa con este evento cuando falla la precarga de un archivo (mismo caso: versión nueva publicada)
if (typeof window !== "undefined") {
  // (sin «preventDefault»: Vite debe seguir lanzando el error para que no se cargue una pantalla vacía)
  window.addEventListener("vite:preloadError", () => { recargarPorVersionNueva(); });
}
