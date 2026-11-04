// Avisos en el celular e instalación de la app.
import { useEffect, useState } from "react";
import { BellRing, Download, Share, X } from "lucide-react";
import { activarPush, desactivarPush, esIOS, instalada, pushSoportado, suscripcionActual } from "@/lib/push";
import { Alerta, Boton, Insignia, Panel, useAviso } from "@/components/ui";

function leer(clave) { try { return localStorage.getItem(clave); } catch { return null; } }
function guardar(clave, v) { try { localStorage.setItem(clave, v); } catch { /* modo privado */ } }

/** Panel de Mi cuenta: avisos en este celular o navegador. */
export default function AvisosCelularPanel() {
  const avisar = useAviso();
  const [activo, setActivo] = useState(null);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  useEffect(() => { suscripcionActual().then((s) => setActivo(!!s)).catch(() => setActivo(false)); }, []);
  const soportado = pushSoportado();
  const cambiar = async () => {
    setError(""); setEnviando(true);
    try {
      if (activo) { await desactivarPush(); setActivo(false); avisar("Avisos desactivados en este dispositivo"); }
      else { await activarPush(); setActivo(true); avisar("Avisos activados: te llegó uno de prueba"); }
    } catch (e) { setError(e.message); }
    setEnviando(false);
  };
  return (
    <Panel titulo="Avisos en este celular" accion={activo ? <Insignia tono="verde">Activos</Insignia> : null}>
      <div className="space-y-3">
        <p className="text-sm text-gris">Las tareas asignadas, entregas por validar, recordatorios y avisos de la campanita te llegan como notificación, aunque la app esté cerrada.</p>
        {error && <Alerta>{error}</Alerta>}
        {!soportado ? (
          <Alerta tono="amarillo">{esIOS() && !instalada() ? "En iPhone, primero instala la app: Safari → Compartir → «Agregar a inicio». Luego ábrela desde el ícono y activa los avisos aquí." : "Este navegador no permite notificaciones."}</Alerta>
        ) : activo !== null && (
          <Boton icono={BellRing} variante={activo ? "secundario" : "primario"} cargando={enviando} onClick={cambiar}>
            {activo ? "Desactivar en este dispositivo" : "Activar avisos en este dispositivo"}
          </Boton>
        )}
      </div>
    </Panel>
  );
}

/** Franja abajo de la cabecera: instalar la app y activar los avisos (se puede cerrar). */
export function SugerenciaApp() {
  const [evento, setEvento] = useState(() => window.__instalarApp || null);
  const [cerrada, setCerrada] = useState(() => leer("adzone:sugerencia-app") === "1");
  const [conAvisos, setConAvisos] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    const listo = () => setEvento(window.__instalarApp);
    window.addEventListener("adzone:instalable", listo);
    suscripcionActual().then((s) => setConAvisos(!!s || !pushSoportado() || Notification.permission === "denied")).catch(() => {});
    return () => window.removeEventListener("adzone:instalable", listo);
  }, []);
  const celular = window.matchMedia("(max-width: 767px)").matches;
  const iosSinInstalar = esIOS() && !instalada();
  const ofrecerInstalar = celular && !instalada() && (evento || iosSinInstalar);
  const ofrecerAvisos = !conAvisos && (instalada() || !esIOS());
  if (cerrada || (!ofrecerInstalar && !ofrecerAvisos)) return null;
  const cerrar = () => { guardar("adzone:sugerencia-app", "1"); setCerrada(true); };
  const instalar = async () => { evento.prompt(); await evento.userChoice.catch(() => {}); window.__instalarApp = null; setEvento(null); };
  const avisos = async () => { setError(""); try { await activarPush(); setConAvisos(true); } catch (e) { setError(e.message); } };
  return (
    <div className="mb-4 flex items-start gap-3 rounded-xl border border-azul/20 bg-azul/5 p-3 text-sm">
      {ofrecerInstalar ? <Download className="mt-0.5 size-5 shrink-0 text-azul" /> : <BellRing className="mt-0.5 size-5 shrink-0 text-azul" />}
      <div className="min-w-0 flex-1 space-y-2">
        {ofrecerInstalar ? (
          iosSinInstalar && !evento
            ? <p>Instala Adzone Team en tu iPhone: toca <Share className="inline size-4" aria-label="Compartir" /> en Safari y luego <b>«Agregar a inicio»</b>.</p>
            : <><p>Instala Adzone Team en tu celular: se abre como una app y te llegan los avisos.</p><Boton tam="sm" onClick={instalar}>Instalar la app</Boton></>
        ) : (
          <><p>Activa los avisos para enterarte de tus tareas y entregas aunque la app esté cerrada.</p><Boton tam="sm" onClick={avisos}>Activar avisos</Boton></>
        )}
        {error && <p className="text-rojo">{error}</p>}
      </div>
      <button type="button" className="rounded p-1 text-gris hover:bg-white" aria-label="Cerrar" onClick={cerrar}><X className="size-4" /></button>
    </div>
  );
}
