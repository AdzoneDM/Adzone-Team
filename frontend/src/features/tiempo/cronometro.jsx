// Cronómetro global: uno por persona. Vive en la barra de arriba y se puede iniciar desde una tarea o una orden.
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { cronometroActivo, detenerCronometro, iniciarCronometro } from "@/lib/api";
import { horas } from "@/lib/formato";
import { useAviso } from "@/components/ui";

const Ctx = createContext(null);

export function CronometroProvider({ children }) {
  const avisar = useAviso();
  const [activo, setActivo] = useState(null);
  const [, setTic] = useState(0);
  const refrescar = useCallback(() => cronometroActivo().then((r) => setActivo(r.activo)).catch(() => {}), []);
  useEffect(() => { refrescar(); }, [refrescar]);
  useEffect(() => {
    if (!activo) return undefined;
    const t = setInterval(() => setTic((x) => x + 1), 15000);
    return () => clearInterval(t);
  }, [activo]);
  useEffect(() => {
    const alVolver = () => document.visibilityState === "visible" && refrescar();
    document.addEventListener("visibilitychange", alVolver);
    return () => document.removeEventListener("visibilitychange", alVolver);
  }, [refrescar]);

  const iniciar = async (datos) => {
    try {
      const r = await iniciarCronometro(datos);
      setActivo(r.activo);
      avisar(r.detenido ? `Cronómetro cambiado. Se guardaron ${horas(r.detenido.minutos)} en lo anterior.` : "Cronómetro en marcha.");
      return r.activo;
    } catch (e) { avisar(e.message, "rojo"); return null; }
  };
  const detener = async () => {
    try {
      const r = await detenerCronometro();
      setActivo(null);
      avisar(`Guardado: ${horas(r.minutos)}${r.tarea_titulo ? ` en «${r.tarea_titulo}»` : r.orden_numero ? ` en ${r.orden_numero}` : ""}.`);
      window.dispatchEvent(new Event("adzone:tiempo"));
      return r;
    } catch (e) { avisar(e.message, "rojo"); return null; }
  };
  const minutos = activo ? Math.max(0, Math.floor((Date.now() - new Date(activo.inicio).getTime()) / 60000)) : 0;
  return <Ctx.Provider value={{ activo, minutos, iniciar, detener, refrescar }}>{children}</Ctx.Provider>;
}

export const useCronometro = () => useContext(Ctx);

export const nombreRegistro = (r) => r?.tarea_titulo || (r?.orden_numero ? `${r.orden_numero} · ${r.orden_titulo}` : null) || r?.proyecto_nombre || r?.descripcion || "Trabajo";
