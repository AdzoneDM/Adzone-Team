// Service worker de Adzone Team: permite instalar la app y abrirla aunque la señal sea mala.
// Estrategia "red primero": siempre se intenta traer lo más reciente; la caché solo
// se usa sin conexión. Los datos (/api) y las evidencias (/media) nunca se guardan.
const CACHE = "adzone-team-v5";

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
