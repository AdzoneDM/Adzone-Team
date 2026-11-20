// Avisos del sistema operativo (Windows, Linux, Mac, celular): ayudas para que salgan aunque la app esté en segundo plano.
import { suscripcionActual } from "@/lib/push";

export const permisoNotificaciones = () => (typeof Notification === "undefined" ? "no-soportado" : Notification.permission);

/** ¿Este dispositivo recibe los avisos por el servidor (push)? Si sí, el sistema ya los muestra solo. */
export async function recibePush() {
  try { return !!(await suscripcionActual()); } catch { return false; }
}

/** Muestra un aviso del sistema desde la propia app (respaldo cuando este dispositivo no tiene push). */
export async function mostrarAvisoLocal(aviso, importante) {
  try {
    if (permisoNotificaciones() !== "granted") return;
    const reg = await navigator.serviceWorker?.getRegistration();
    const opciones = {
      body: aviso.mensaje || "", icon: "/icono-192.png", badge: "/icono-192.png", data: { enlace: aviso.enlace || "/" },
      tag: `aviso-${aviso.id}`, renotify: true, silent: false, requireInteraction: !!importante,
    };
    if (reg) await reg.showNotification(aviso.titulo || "Adzone Team", opciones);
    else new Notification(aviso.titulo || "Adzone Team", opciones);
  } catch { /* el sistema no lo permite */ }
}
