// Avisos en el celular (Web Push). En iPhone solo funciona con la app instalada en la pantalla de inicio (iOS 16.4+).
import { api } from "@/lib/api";

const base64aBytes = (b64) => {
  const relleno = "=".repeat((4 - (b64.length % 4)) % 4);
  const bin = atob((b64 + relleno).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
};

export const pushSoportado = () => typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
export const esIOS = () => /iPhone|iPad|iPod/.test(navigator.userAgent);
export const instalada = () => window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;

export async function suscripcionActual() {
  if (!pushSoportado()) return null;
  const reg = await navigator.serviceWorker.getRegistration();
  return reg ? reg.pushManager.getSubscription() : null;
}

export async function activarPush() {
  const estado = await api("/api/cuenta/push/");
  if (!estado.configurado) throw new Error("Las notificaciones todavía no están configuradas en el servidor.");
  const permiso = await Notification.requestPermission();
  if (permiso !== "granted") throw new Error("No diste permiso para las notificaciones. Puedes activarlo en los ajustes del navegador.");
  const reg = await navigator.serviceWorker.ready;
  const sus = (await reg.pushManager.getSubscription())
    || (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: base64aBytes(estado.publica) }));
  await api("/api/cuenta/push/", { method: "POST", body: { suscripcion: sus.toJSON() } });
  return true;
}

export async function desactivarPush() {
  const sus = await suscripcionActual();
  if (!sus) return;
  await api("/api/cuenta/push/", { method: "DELETE", body: { suscripcion: { endpoint: sus.endpoint } } });
  await sus.unsubscribe();
}
