// Alertas de tareas: tarjetas que se apilan abajo a la izquierda, con sonido, y se quedan hasta que se atienden.
// No tapan la pantalla: se puede seguir trabajando mientras llegan.
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Clock, X } from "lucide-react";
import { leerAvisos } from "@/lib/api";
import { ALERTAS_TAREA, esAlertaTarea } from "@/lib/alertas";
import { hace } from "@/lib/formato";
import { cx } from "@/components/ui";

const MAX_VISIBLES = 3;

const TONOS = {
  amarillo: { barra: "bg-amarillo", icono: "bg-amarillo-50 text-[#a86a00]", etiqueta: "text-[#a86a00]" },
  azul: { barra: "bg-azul", icono: "bg-azul/10 text-azul", etiqueta: "text-azul" },
  rojo: { barra: "bg-rojo", icono: "bg-rojo-50 text-rojo", etiqueta: "text-rojo" },
};

function Tarjeta({ aviso, onAtender, className }) {
  const info = ALERTAS_TAREA[aviso.tipo];
  const tono = TONOS[info.tono];
  const Icono = info.icono;
  const destino = aviso.enlace ? (aviso.tarea && !aviso.enlace.includes("tarea=") ? `${aviso.enlace}?tarea=${aviso.tarea}` : aviso.enlace) : null;
  return (
    <article role="alert" aria-labelledby={`alerta-${aviso.id}`}
      className={cx("pointer-events-auto relative animate-[entrar-izquierda_0.4s_cubic-bezier(0.2,0.9,0.3,1.1)] overflow-hidden rounded-2xl bg-white shadow-[0_18px_50px_-12px_rgba(15,37,80,0.35)] ring-1 ring-noche/10 motion-reduce:animate-none", className)}>
      <span className={cx("absolute inset-y-0 left-0 w-1.5", tono.barra)} aria-hidden />
      <div className="py-4 pl-6 pr-4">
        <div className="flex items-start gap-3">
          <span className={cx("flex size-11 shrink-0 items-center justify-center rounded-xl", tono.icono)}><Icono className="size-5" aria-hidden /></span>
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2">
              <p className={cx("truncate text-[11px] font-bold uppercase tracking-[0.14em]", tono.etiqueta)}>{info.etiqueta}</p>
              <button type="button" onClick={() => onAtender(aviso, false)} aria-label="Cerrar la alerta" className="-mr-1 -mt-1 shrink-0 rounded-lg p-1.5 text-gris hover:bg-fondo hover:text-tinta"><X className="size-4" aria-hidden /></button>
            </div>
            <h2 id={`alerta-${aviso.id}`} className="mt-0.5 text-base font-semibold leading-snug !text-tinta">{aviso.titulo}</h2>
            {aviso.mensaje && <p className="mt-1 line-clamp-3 whitespace-pre-line text-sm leading-relaxed text-gris">{aviso.mensaje}</p>}
            <p className="mt-2 flex flex-wrap items-center gap-x-2.5 gap-y-0.5 text-xs text-gris">
              {aviso.remitente_nombre && <span>De <b className="font-semibold text-tinta">{aviso.remitente_nombre}</b></span>}
              <span className="inline-flex items-center gap-1"><Clock className="size-3" aria-hidden />{hace(aviso.fecha)}</span>
            </p>
          </div>
        </div>
        <div className="mt-3 flex items-center gap-2 pl-14">
          {destino && (
            <button type="button" onClick={() => onAtender(aviso, true, destino)}
              className="h-9 rounded-lg bg-noche px-4 text-sm font-semibold text-white transition hover:bg-noche-900 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-azul/30 active:scale-[0.98]">{info.boton}</button>
          )}
          <button type="button" onClick={() => onAtender(aviso, false)}
            className="h-9 rounded-lg px-3 text-sm font-medium text-gris transition hover:bg-fondo hover:text-tinta focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-azul/20">Entendido</button>
        </div>
      </div>
    </article>
  );
}

export default function AlertaTarea({ avisos, refrescar, sonar }) {
  const navigate = useNavigate();
  const pendientes = avisos.filter(esAlertaTarea);
  const visibles = pendientes.slice(0, MAX_VISIBLES);
  const ocultas = pendientes.length - visibles.length;

  // Recordatorios, devoluciones y vencimientos insisten: vuelve a sonar cada 30 s y la pestaña parpadea hasta atenderlos
  const insiste = visibles.some((a) => ALERTAS_TAREA[a.tipo]?.insiste);
  useEffect(() => {
    if (!insiste) return undefined;
    const original = document.title;
    let alterno = false;
    const titulo = setInterval(() => { alterno = !alterno; document.title = alterno ? "🔔 Tienes una alerta" : original; }, 1200);
    const sonido = setInterval(sonar, 30000);
    return () => { clearInterval(titulo); clearInterval(sonido); document.title = original; };
  }, [insiste, sonar]);

  if (!pendientes.length) return null;

  // «Entendido» atiende solo esa alerta; «Ver…» la atiende y lleva a la tarea
  const atender = async (aviso, ir, destino) => {
    try { await leerAvisos([aviso.id]); } catch { /* se reintenta en el próximo refresco */ }
    refrescar();
    if (ir && destino) navigate(destino);
  };

  return (
    <div className="pointer-events-none fixed inset-x-3 bottom-[calc(4.75rem+env(safe-area-inset-bottom))] z-[80] flex flex-col-reverse gap-3 sm:inset-x-auto sm:left-4 sm:w-[420px] lg:bottom-6 lg:left-[17rem]" aria-live="assertive">
      {/* En el celular solo la más reciente (las demás esperan); en pantallas grandes, hasta tres apiladas */}
      {visibles.map((a, i) => <Tarjeta key={a.id} aviso={a} onAtender={atender} className={i > 0 ? "max-sm:hidden" : ""} />)}
      {(pendientes.length > 1) && (
        <p className={cx("pointer-events-auto order-last self-start rounded-full bg-noche px-3 py-1 text-xs font-medium text-white shadow-lg", ocultas === 0 && "sm:hidden")}>
          <span className="sm:hidden">+{pendientes.length - 1} alerta{pendientes.length > 2 ? "s" : ""} más</span>
          {ocultas > 0 && <span className="hidden sm:inline">+{ocultas} alerta{ocultas > 1 ? "s" : ""} más</span>}
        </p>
      )}
    </div>
  );
}
