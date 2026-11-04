// Ubicación del celular SOLO en el momento de marcar (la plataforma no sigue a nadie).
export function obtenerUbicacion(espera = 12000) {
  return new Promise((resolver) => {
    if (!navigator.geolocation) return resolver(null);
    navigator.geolocation.getCurrentPosition(
      (p) => resolver({ latitud: p.coords.latitude, longitud: p.coords.longitude, precision: Math.round(p.coords.accuracy) }),
      () => resolver(null),
      { enableHighAccuracy: true, timeout: espera, maximumAge: 30000 },
    );
  });
}

/** Lo que se manda al marcar: la ubicación si la persona debe marcar en la oficina o en la calle. */
export async function datosDeLugar(dondeMarca) {
  if (!dondeMarca || dondeMarca === "LIBRE") return {};
  return (await obtenerUbicacion()) || {};
}
