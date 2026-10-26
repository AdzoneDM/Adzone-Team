// Datos que casi no cambian (catálogo de órdenes, directorio, departamentos) se piden una vez por sesión.
import { useEffect, useState } from "react";
import { catalogoOrdenes, departamentos, directorio, listarClientes } from "@/lib/api";

const cache = new Map();
const CARGAS = {
  catalogo: catalogoOrdenes,
  directorio,
  departamentos,
  clientes: () => listarClientes({ activos: 1 }),
};

export function cargarRecurso(clave, forzar = false) {
  if (forzar || !cache.has(clave)) {
    const p = CARGAS[clave]().catch((e) => { cache.delete(clave); throw e; });
    cache.set(clave, p);
  }
  return cache.get(clave);
}

export const olvidarRecurso = (clave) => cache.delete(clave);

/** const [catalogo] = useRecurso("catalogo") */
export function useRecurso(clave) {
  const [datos, setDatos] = useState(null);
  const [version, setVersion] = useState(0);
  useEffect(() => {
    let vivo = true;
    cargarRecurso(clave).then((d) => vivo && setDatos(d)).catch(() => vivo && setDatos([]));
    return () => { vivo = false; };
  }, [clave, version]);
  const recargar = () => { olvidarRecurso(clave); setVersion((v) => v + 1); };
  return [datos, recargar];
}
