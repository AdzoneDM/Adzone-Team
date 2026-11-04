import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { EVENTO_SESION, entrar, entrarConCodigo, salir, sesion } from "@/lib/api";
import { suscripcionActual } from "@/lib/push";

const SesionCtx = createContext(null);

export function SesionProvider({ children }) {
  const [usuario, setUsuario] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [aviso, setAviso] = useState(""); // por qué se cerró la sesión (se muestra en «Entrar»)

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

  // Si la sesión se cierra en el servidor (inactividad) o falta activar los dos pasos, la app vuelve a preguntar
  useEffect(() => {
    const alCambiar = (e) => {
      if (e.detail?.activar_dos_pasos) recargar();
      else if (e.detail?.estado === 401) { setAviso(e.detail.detail || ""); setUsuario(null); }
    };
    window.addEventListener(EVENTO_SESION, alCambiar);
    return () => window.removeEventListener(EVENTO_SESION, alCambiar);
  }, [recargar]);

  /** Devuelve { dosPasos: true } si falta el código de la app; si no, entra. */
  const login = async (credenciales) => {
    const datos = await entrar(credenciales);
    if (datos.dos_pasos) return { dosPasos: true };
    setAviso("");
    setUsuario(datos.user);
    return datos.user;
  };
  const verificarCodigo = async (codigo) => {
    const datos = await entrarConCodigo(codigo);
    setAviso("");
    setUsuario(datos.user);
    return datos.user;
  };
  const logout = async () => {
    // Al salir, este celular deja de recibir los avisos de esta persona (por si otra lo usa después)
    let sus = null;
    try { sus = await suscripcionActual(); } catch { /* sin avisos */ }
    try { await salir(sus?.endpoint); } finally { try { await sus?.unsubscribe(); } catch { /* ya no estaba */ } setUsuario(null); }
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
    verificarCodigo,
    avisoSesion: aviso,
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
