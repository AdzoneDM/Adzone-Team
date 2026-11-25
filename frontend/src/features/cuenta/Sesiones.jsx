// Sesiones abiertas de la persona: en qué dispositivos está dentro, desde qué IP y desde cuándo. Puede cerrar cualquiera a distancia.
import { useCallback, useEffect, useState } from "react";
import { LogOut, MonitorSmartphone, ShieldAlert } from "lucide-react";
import { cerrarOtrasSesiones, cerrarSesion, misSesiones } from "@/lib/api";
import { Boton, Cargando, Insignia, Panel, useAviso, useConfirmar } from "@/components/ui";

const cuando = (iso) => new Date(iso).toLocaleString("es-DO", { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

export default function Sesiones() {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const [lista, setLista] = useState(null);
  const cargar = useCallback(() => misSesiones().then(setLista).catch(() => setLista([])), []);
  useEffect(() => { cargar(); }, [cargar]);
  const otras = (lista || []).filter((s) => !s.actual).length;
  const cerrar = async (s) => {
    if (!(await confirmar({ titulo: "¿Cerrar esta sesión?", mensaje: `${s.dispositivo} · ${s.ip || "IP desconocida"}. Ese dispositivo tendrá que volver a entrar con la contraseña.`, boton: "Cerrar sesión", peligro: true }))) return;
    try { await cerrarSesion(s.id); avisar("Sesión cerrada."); cargar(); } catch (e) { avisar(e.message, "rojo"); }
  };
  const cerrarOtras = async () => {
    if (!(await confirmar({ titulo: "¿Cerrar las demás sesiones?", mensaje: "Todos tus otros dispositivos tendrán que volver a entrar. Esta queda abierta.", boton: "Cerrar las demás", peligro: true }))) return;
    try { const r = await cerrarOtrasSesiones(); avisar(`Se cerraron ${r.cerradas} sesión(es).`); cargar(); } catch (e) { avisar(e.message, "rojo"); }
  };
  return (
    <Panel titulo="Sesiones abiertas" accion={otras > 0 && <Boton variante="secundario" tam="sm" icono={LogOut} onClick={cerrarOtras}>Cerrar las demás</Boton>}>
      <p className="mb-3 text-sm text-gris">Dónde está abierta tu cuenta ahora. Si ves un dispositivo o un lugar que no reconoces, ciérralo y cambia tu contraseña.</p>
      {!lista ? <Cargando /> : !lista.length ? <p className="text-sm text-gris">No hay sesiones registradas.</p> : (
        <ul className="divide-y divide-linea-suave">
          {lista.map((s) => (
            <li key={s.id} className="flex items-center gap-3 py-3">
              <MonitorSmartphone className="size-5 shrink-0 text-gris" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-2 text-sm font-medium">{s.dispositivo}
                  {s.actual && <Insignia tono="verde">Esta sesión</Insignia>}
                  {s.riesgo >= 2 && <Insignia tono="rojo"><ShieldAlert className="size-3" aria-hidden />Poco habitual</Insignia>}
                </p>
                <p className="text-xs text-gris">IP {s.ip || "desconocida"} · desde {cuando(s.desde)}{s.motivo ? ` · ${s.motivo}` : ""}</p>
              </div>
              {!s.actual && <Boton variante="secundario" tam="sm" onClick={() => cerrar(s)}>Cerrar</Boton>}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
