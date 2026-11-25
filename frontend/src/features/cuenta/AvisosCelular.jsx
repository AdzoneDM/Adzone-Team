// Avisos en el celular e instalación de la app.
import { useEffect, useState } from "react";
import { BellRing, Download, Share, X } from "lucide-react";
import { activarPush, desactivarPush, esIOS, instalada, pushSoportado, suscripcionActual } from "@/lib/push";
import { Alerta, Boton, Insignia, Modal, Panel, useAviso } from "@/components/ui";

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
  useEffect(() => {
    const listo = () => setEvento(window.__instalarApp);
    window.addEventListener("adzone:instalable", listo);
    return () => window.removeEventListener("adzone:instalable", listo);
  }, []);
  const iosSinInstalar = esIOS() && !instalada();
  const ofrecerInstalar = !instalada() && (evento || iosSinInstalar);   // celular y computadora
  // Los avisos del sistema los pide ahora «ActivarNotificaciones» al entrar: aquí solo se ofrece instalar la app
  if (cerrada || !ofrecerInstalar) return null;
  const cerrar = () => { guardar("adzone:sugerencia-app", "1"); setCerrada(true); };
  const instalar = async () => { evento.prompt(); await evento.userChoice.catch(() => {}); window.__instalarApp = null; setEvento(null); };
  return (
    <div className="mb-4 flex items-start gap-3 rounded-xl border border-azul/20 bg-azul/5 p-3 text-sm">
      <Download className="mt-0.5 size-5 shrink-0 text-azul" />
      <div className="min-w-0 flex-1 space-y-2">
        {ofrecerInstalar ? (
          iosSinInstalar && !evento
            ? <p>Instala Adzone Team en tu iPhone: toca <Share className="inline size-4" aria-label="Compartir" /> en Safari y luego <b>«Agregar a inicio»</b>.</p>
            : <><p>Instala Adzone Team en este dispositivo: se abre como una app, con su ícono, y te llegan los avisos.</p><Boton tam="sm" onClick={instalar}>Instalar la app</Boton></>
        ) : null}
      </div>
      <button type="button" className="rounded p-1 text-gris hover:bg-white" aria-label="Cerrar" onClick={cerrar}><X className="size-4" /></button>
    </div>
  );
}

/** Cómo instalar cuando el navegador no ofrece el botón directo (iPhone, Safari, Firefox…). */
function pasosManuales() {
  const ua = navigator.userAgent;
  if (esIOS()) return ["En Safari, toca el botón Compartir (el cuadrado con la flecha hacia arriba).", "Elige «Agregar a inicio» y confirma con «Agregar».", "Abre Adzone Team desde el nuevo ícono de tu pantalla de inicio."];
  if (/Android/i.test(ua)) return ["Abre esta página en Chrome.", "Toca el menú ⋮ (arriba a la derecha).", "Elige «Instalar app» o «Agregar a la pantalla principal»."];
  if (/Macintosh/.test(ua) && /Safari/.test(ua) && !/Chrome|Edg|Firefox/.test(ua)) return ["En Safari, abre el menú Archivo.", "Elige «Agregar al Dock».", "Abre Adzone Team desde el Dock como cualquier otra app."];
  if (/Firefox/.test(ua)) return ["Firefox no instala apps web en la computadora.", "Abre kpi.adzone.marketing en Chrome o Edge.", "Toca el ícono de instalar en la barra de direcciones (o menú ⋮ → «Instalar Adzone Team»)."];
  return ["En la barra de direcciones, toca el ícono de instalar (una pantalla con una flecha).", "O abre el menú ⋮ → «Transmitir, guardar y compartir» → «Instalar Adzone Team».", "Se abrirá en su propia ventana y quedará en tu escritorio y menú de inicio."];
}

/** Botón fijo en la cabecera, en celular y computadora, mientras la app no esté instalada. */
export function BotonInstalar() {
  const [evento, setEvento] = useState(() => window.__instalarApp || null);
  const [yaInstalada, setYaInstalada] = useState(instalada);
  const [ayuda, setAyuda] = useState(false);
  useEffect(() => {
    const listo = () => setEvento(window.__instalarApp);
    const hecha = () => { window.__instalarApp = null; setEvento(null); setYaInstalada(true); };
    window.addEventListener("adzone:instalable", listo);
    window.addEventListener("appinstalled", hecha);
    return () => { window.removeEventListener("adzone:instalable", listo); window.removeEventListener("appinstalled", hecha); };
  }, []);
  if (yaInstalada) return null;
  const instalar = async () => {
    if (!evento) { setAyuda(true); return; }
    evento.prompt();
    const r = await evento.userChoice.catch(() => null);
    window.__instalarApp = null; setEvento(null);
    if (r?.outcome === "accepted") setYaInstalada(true);
  };
  return (
    <>
      <button type="button" onClick={instalar} title="Instalar la app" aria-label="Instalar la app" data-guia="instalar"
        className="flex h-10 items-center gap-1.5 rounded-lg px-2.5 text-sm font-medium text-azul hover:bg-azul/5 max-lg:size-10 max-lg:justify-center max-lg:px-0">
        <Download className="size-5" /><span className="hidden xl:inline">Instalar app</span>
      </button>
      <Modal abierto={ayuda} onCerrar={() => setAyuda(false)} titulo="Instalar Adzone Team" descripcion="Se abre como una app, con su propio ícono, y te llegan los avisos." ancho="max-w-md">
        <ol className="list-decimal space-y-2 pl-5 text-sm">{pasosManuales().map((p) => <li key={p}>{p}</li>)}</ol>
      </Modal>
    </>
  );
}
