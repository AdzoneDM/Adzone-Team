import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { entrar, salir, sesion } from "@/lib/api";

const SesionCtx = createContext(null);

export function SesionProvider({ children }) {
  const [usuario, setUsuario] = useState(null);
  const [cargando, setCargando] = useState(true);

  const recargar = useCallback(async () => {
    try {
      const datos = await sesion();
      setUsuario(datos?.isAuthenticated ? datos.user : null);
    } catch {
      setUsuario(null);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => { recargar(); }, [recargar]);

  // Si la sesión vence mientras la app está abierta, vuelve a la entrada.
  useEffect(() => {
    const alVolver = () => { if (document.visibilityState === "visible" && usuario) recargar(); };
    document.addEventListener("visibilitychange", alVolver);
    return () => document.removeEventListener("visibilitychange", alVolver);
  }, [usuario, recargar]);

  const login = async (identificador, clave, recordar) => {
    const datos = await entrar(identificador, clave, recordar);
    setUsuario(datos.user);
    return datos.user;
  };
  const logout = async () => {
    try { await salir(); } finally { setUsuario(null); }
  };

  const valor = {
    usuario,
    cargando,
    login,
    logout,
    recargar,
    esAdmin: !!usuario?.es_administrador,
    puedeValidar: !!usuario?.puede_validar,
  };
  return <SesionCtx.Provider value={valor}>{children}</SesionCtx.Provider>;
}

export const useSesion = () => useContext(SesionCtx);
