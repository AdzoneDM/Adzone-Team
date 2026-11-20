// Pide activar las notificaciones del sistema (Windows, Linux, Mac o celular) al entrar, para que los avisos salgan
// aunque la app esté minimizada o cerrada. Si ya dio permiso, activa este dispositivo sin molestar.
import { useEffect, useState } from "react";
import { BellRing, ShieldAlert } from "lucide-react";
import { activarPush, esIOS, instalada, pushSoportado, suscripcionActual } from "@/lib/push";
import { permisoNotificaciones } from "@/lib/notificaciones";
import { Boton, useAviso } from "@/components/ui";

const LLAVE = "adzone:notificaciones-despues";
const DIA = 24 * 3600 * 1000;

const pospuesto = () => { try { return Number(localStorage.getItem(LLAVE) || 0) > Date.now(); } catch { return false; } };
const posponer = (ms) => { try { localStorage.setItem(LLAVE, String(Date.now() + ms)); } catch { /* sin almacenamiento */ } };

export default function ActivarNotificaciones() {
  const avisar = useAviso();
  const [fase, setFase] = useState(null); // "pedir" | "bloqueadas" | null
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (!pushSoportado() || (esIOS() && !instalada())) return undefined; // en iPhone primero se instala la app
    const permiso = permisoNotificaciones();
    let vivo = true;
    (async () => {
      if (permiso === "granted") {
        // Ya dio permiso: si este dispositivo aún no está registrado en el servidor, se registra solo
        const sus = await suscripcionActual().catch(() => null);
        if (!sus) await activarPush().catch(() => {});
        return;
      }
      if (pospuesto()) return;
      // Unos segundos después de entrar, para no encimarse con la pantalla de entrada
      await new Promise((r) => setTimeout(r, 4000));
      if (vivo) setFase(permiso === "denied" ? "bloqueadas" : "pedir");
    })();
    return () => { vivo = false; };
  }, []);

  if (!fase) return null;
  const luego = (dias) => { posponer(dias * DIA); setFase(null); };
  const activar = async () => {
    setEnviando(true); setError("");
    try { await activarPush(); avisar("Notificaciones activadas: te llegó una de prueba."); setFase(null); }
    catch (e) { setError(e.message); if (permisoNotificaciones() === "denied") setFase("bloqueadas"); }
    setEnviando(false);
  };

  return (
    <div className="fixed inset-0 z-[72] flex items-end justify-center bg-noche-900/60 p-4 backdrop-blur-sm sm:items-center" role="dialog" aria-modal="true" aria-labelledby="notif-titulo">
      <div className="w-full max-w-md overflow-hidden rounded-3xl bg-white text-center shadow-2xl">
        <div className={fase === "pedir" ? "h-2 bg-azul" : "h-2 bg-amarillo"} />
        <div className="px-6 pb-6 pt-7 sm:px-8">
          <span className={`mx-auto flex size-16 items-center justify-center rounded-full ${fase === "pedir" ? "bg-azul/10 text-azul" : "bg-amarillo-50 text-[#a86a00]"}`}>
            {fase === "pedir" ? <BellRing className="size-8" aria-hidden /> : <ShieldAlert className="size-8" aria-hidden />}
          </span>
          {fase === "pedir" ? (
            <>
              <h2 id="notif-titulo" className="mt-4 text-2xl font-semibold text-tinta">Activa las notificaciones</h2>
              <p className="mt-2 text-[15px] text-gris">Te avisamos de tus tareas, recordatorios y entregas con una notificación y sonido en tu computadora o celular, <b>aunque tengas la app minimizada</b>.</p>
              {error && <p className="mt-3 text-sm text-rojo" role="alert">{error}</p>}
              <Boton icono={BellRing} onClick={activar} cargando={enviando} className="mt-6 !h-12 w-full !text-base" autoFocus>Activar notificaciones</Boton>
              <button type="button" onClick={() => luego(1)} className="mt-3 rounded-lg px-3 py-2 text-sm font-medium text-gris hover:bg-fondo hover:text-tinta">Ahora no</button>
            </>
          ) : (
            <>
              <h2 id="notif-titulo" className="mt-4 text-2xl font-semibold text-tinta">Las notificaciones están bloqueadas</h2>
              <p className="mt-2 text-[15px] text-gris">Para recibir los avisos fuera de la app, permítelos en el navegador: toca el <b>candado</b> junto a la dirección, entra en <b>Notificaciones</b> y elige <b>Permitir</b>. Luego recarga la página.</p>
              <Boton variante="secundario" onClick={() => luego(3)} className="mt-6 !h-12 w-full" autoFocus>Entendido</Boton>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
