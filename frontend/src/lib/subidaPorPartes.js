// Subida por partes de archivos grandes (ZIP y videos de cientos de MB) para adjuntarlos a las tareas.
// El nginx del servidor corta cada petición en 64 MB, así que el archivo se corta aquí en partes (el tamaño lo dice el servidor, ~8 MB),
// cada parte viaja en su propia petición y al final el servidor la junta, la revisa y devuelve un id que se manda con la tarea.
import { ApiError, api, getCookie } from "@/lib/api";

// Desde este tamaño el archivo se sube por partes (por debajo va en el mismo formulario de siempre)
export const UMBRAL_PARTES_MB = 40;
export const esGrande = (f) => (f?.size || 0) > UMBRAL_PARTES_MB * 1024 * 1024;

const REINTENTOS = 4;
const espera = (ms) => new Promise((r) => setTimeout(r, ms));

/** Manda una parte (cuerpo crudo) informando su avance (0 a 1). */
function enviarParte(url, trozo, alAvanzar, signal) {
  return new Promise((resolver, rechazar) => {
    const x = new XMLHttpRequest();
    x.open("PUT", url);
    x.withCredentials = true;
    x.timeout = 10 * 60000;
    x.setRequestHeader("Accept", "application/json");
    x.setRequestHeader("Content-Type", "application/octet-stream");
    x.setRequestHeader("X-CSRFToken", getCookie("csrftoken") || "");
    x.setRequestHeader("X-Actividad", "1");
    x.upload.onprogress = (e) => { if (e.lengthComputable) alAvanzar?.(e.loaded / e.total); };
    const cancelar = () => x.abort();
    signal?.addEventListener("abort", cancelar, { once: true });
    x.onload = () => {
      signal?.removeEventListener("abort", cancelar);
      let datos = null;
      try { datos = JSON.parse(x.responseText); } catch { /* sin cuerpo */ }
      if (x.status >= 200 && x.status < 300) return resolver(datos);
      rechazar(new ApiError(datos?.detail || (x.status >= 500 ? "El servidor tuvo un problema al recibir el archivo." : `Error ${x.status}`), x.status, datos));
    };
    x.onerror = () => rechazar(new ApiError("Sin conexión. Revisa el internet e inténtalo de nuevo.", 0));
    x.ontimeout = () => rechazar(new ApiError("Tardó demasiado en subir. Revisa tu internet e inténtalo de nuevo.", 0));
    x.onabort = () => rechazar(new DOMException("Subida cancelada", "AbortError"));
    x.send(trozo);
  });
}

/** Sube un archivo grande por partes y devuelve el id de la subida ya revisada. `alAvanzar(f)` recibe el avance de 0 a 1. */
export async function subirPorPartes(archivo, { alAvanzar, signal } = {}) {
  const { id, tamano_parte: parte, partes } = await api("/api/subidas/", { method: "POST", body: { nombre: archivo.name, tamano: archivo.size }, signal });
  try {
    for (let i = 0; i < partes; i++) {
      const desde = i * parte;
      const trozo = archivo.slice(desde, Math.min(archivo.size, desde + parte));
      for (let intento = 1; ; intento++) {
        try {
          await enviarParte(`/api/subidas/${id}/partes/${i}/`, trozo, (f) => alAvanzar?.((desde + f * trozo.size) / archivo.size), signal);
          break;
        } catch (e) {
          // Un corte de red o un error del servidor se reintenta (repetir una parte ya recibida no hace nada); lo demás, no
          if (e.name === "AbortError" || (e.status && e.status < 500) || intento >= REINTENTOS) throw e;
          await espera(1500 * intento);
        }
      }
    }
    alAvanzar?.(1);
    // Revisar un ZIP de cientos de MB con el antivirus tarda: se manda como formulario (vacío) para esperar lo que haga falta
    await api(`/api/subidas/${id}/completar/`, { method: "POST", body: new FormData(), signal });
    return id;
  } catch (e) {
    api(`/api/subidas/${id}/`, { method: "DELETE" }).catch(() => {}); // libera el espacio de lo que alcanzó a subir
    throw e;
  }
}

/** Separa los archivos grandes (los sube por partes, uno tras otro) de los chicos (van en el formulario como siempre).
 * `alAvanzar(f)` recibe el avance de las subidas grandes de 0 a 1. Devuelve { chicos, subidas: [ids] }. */
export async function prepararArchivos(archivos = [], alAvanzar) {
  const chicos = archivos.filter((a) => !esGrande(a));
  const grandes = archivos.filter(esGrande);
  const total = grandes.reduce((s, a) => s + a.size, 0) || 1;
  let listo = 0;
  const subidas = [];
  for (const a of grandes) {
    subidas.push(await subirPorPartes(a, { alAvanzar: (f) => alAvanzar?.((listo + f * a.size) / total) }));
    listo += a.size;
  }
  return { chicos, subidas };
}
