// Service worker de Adzone Team: permite instalar la app y abrirla aunque la señal sea mala.
// Estrategia "red primero": siempre se intenta traer lo más reciente; la caché solo
// se usa sin conexión. Los datos (/api) y las evidencias (/media) nunca se guardan.
const CACHE = "adzone-team-v6";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((claves) => Promise.all(claves.filter((c) => c !== CACHE).map((c) => caches.delete(c))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;
  if (["/api/", "/admin/", "/static/", "/media"].some((r) => url.pathname.startsWith(r))) return;

  event.respondWith(
    fetch(request)
      .then((respuesta) => {
        if (respuesta.ok) {
          const copia = respuesta.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copia));
        }
        return respuesta;
      })
      .catch(() =>
        caches.match(request).then((enCache) => enCache || (request.mode === "navigate" ? caches.match("/") : undefined))
      )
  );
});

// Avisos en el celular: cada aviso de la campanita llega como notificación, aunque la app esté cerrada.
self.addEventListener("push", (event) => {
  let d = {};
  try { d = event.data ? event.data.json() : {}; } catch { d = { titulo: event.data && event.data.text() }; }
  event.waitUntil(self.registration.showNotification(d.titulo || "Adzone Team", {
    body: d.mensaje || "", icon: "/icono-192.png", badge: "/icono-192.png", data: { enlace: d.enlace || "/" }, tag: d.enlace || undefined,
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const destino = new URL(event.notification.data?.enlace || "/", self.location.origin).href;
  event.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((ventanas) => {
    const abierta = ventanas.find((v) => v.url.startsWith(self.location.origin));
    if (abierta) { abierta.focus(); return abierta.navigate(destino); }
    return self.clients.openWindow(destino);
  }));
});
