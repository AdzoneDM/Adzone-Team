// La app instalada (PWA) y las pestañas abiertas se ponen solas en la última versión.
// Cada 5 minutos, al volver a la app y al recuperar la conexión se compara el programa cargado con el publicado; si hay uno nuevo,
// se recarga en un momento tranquilo (sin texto a medio escribir ni ventanas abiertas), como un Ctrl+R que casi no se nota.
import { ocupado } from "@/lib/recargaSuave";
import { recargarSinAviso } from "@/lib/salida";

const CADA_MS = 5 * 60 * 1000;
const scriptActual = () => document.querySelector('script[type="module"][src*="/assets/"]')?.getAttribute("src") || null;

async function hayVersionNueva() {
  const actual = scriptActual();
  if (!actual) return false;
  try {
    const r = await fetch("/", { cache: "no-store", credentials: "same-origin", headers: { Accept: "text/html" } });
    if (!r.ok) return false;
    const html = await r.text();
    const publicado = html.match(/<script[^>]+type="module"[^>]+src="([^"]*\/assets\/[^"]+)"/)?.[1];
    return !!publicado && publicado !== actual;
  } catch { return false; }
}

let pendiente = false;
function recargarCuandoSePueda() {
  pendiente = true;
  const intentar = () => {
    if (document.visibilityState === "visible" && ocupado()) return setTimeout(intentar, 3000);
    sessionStorage.setItem("adzone:actualizada", "1");
    recargarSinAviso();
  };
  intentar();
}

async function revisar() {
  if (pendiente || !navigator.onLine) return;
  navigator.serviceWorker?.getRegistration().then((reg) => reg?.update()).catch(() => {});
  if (await hayVersionNueva()) recargarCuandoSePueda();
}

export function vigilarActualizaciones() {
  if (!import.meta.env.PROD) return;
  setInterval(revisar, CADA_MS);
  document.addEventListener("visibilitychange", () => document.visibilityState === "visible" && revisar());
  window.addEventListener("online", revisar);
  window.addEventListener("focus", revisar);
  // Cuando un service worker nuevo toma el control, la página ya puede usar la versión nueva
  navigator.serviceWorker?.addEventListener("controllerchange", () => revisar());
}

/** ¿Se acaba de actualizar? (para mostrar un aviso discreto una sola vez) */
export function seActualizo() {
  const v = sessionStorage.getItem("adzone:actualizada") === "1";
  sessionStorage.removeItem("adzone:actualizada");
  return v;
}
