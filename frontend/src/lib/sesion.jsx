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

  const login = async (credenciales) => {
    const datos = await entrar(credenciales);
    setUsuario(datos.user);
    return datos.user;
  };
  const logout = async () => {
    try { await salir(); } finally { setUsuario(null); }
  };

  const lista = new Set(usuario?.permisos || []);
  const tiene = (codigo) => lista.has(codigo);
  const valor = {
    usuario,
    tiene,
    veMonitoreo: tiene("monitoreo.ver"),
    veCapturas: tiene("monitoreo.capturas"),
    configuraMonitoreo: tiene("monitoreo.configurar"),
    gestionaPersonas: tiene("personal.usuarios"),
    veSalarios: tiene("personal.salarios"),
    veAuditoria: tiene("auditoria.ver"),
    configuraSistema: tiene("sistema.configurar"),
    veAsistenciaEquipo: !!usuario?.ve_asistencia_equipo,
    puedeAsignar: !!usuario?.puede_asignar,
    cargando,
    login,
    logout,
    recargar,
    esAdmin: !!usuario?.es_administrador,
    puedeValidar: !!usuario?.puede_validar,
    esFinanzas: !!usuario?.es_finanzas,
    esTecnologia: !!usuario?.es_tecnologia,
    esRRHH: !!usuario?.es_rrhh,
    gestionaActivos: !!usuario?.gestiona_activos,
    gestiona: !!usuario?.gestiona,
    esCoordinacion: !!usuario?.es_coordinacion,
    esAlmacen: !!usuario?.es_almacen,
    misAreas: usuario?.mis_areas || [],
    esAgente: !!usuario?.es_agente,
    gestionaCallCenter: !!usuario?.gestiona_call_center,
  };
  return <SesionCtx.Provider value={valor}>{children}</SesionCtx.Provider>;
}

export const useSesion = () => useContext(SesionCtx);
