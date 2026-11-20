// Alerta emergente de tareas: ocupa la pantalla, suena y no se pierde entre los demás avisos hasta que se atiende.
import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Clock } from "lucide-react";
import { leerAvisos } from "@/lib/api";
import { ALERTAS_TAREA, esAlertaTarea } from "@/lib/alertas";
import { hace } from "@/lib/formato";
import { cx } from "@/components/ui";

const TONOS = {
  amarillo: { banda: "bg-amarillo", halo: "bg-amarillo/40", aro: "ring-amarillo bg-amarillo-50 text-[#a86a00]", etiqueta: "text-[#a86a00]" },
  azul: { banda: "bg-azul", halo: "bg-azul/30", aro: "ring-azul/70 bg-azul/10 text-azul", etiqueta: "text-azul" },
  rojo: { banda: "bg-rojo", halo: "bg-rojo/30", aro: "ring-rojo bg-rojo-50 text-rojo", etiqueta: "text-rojo" },
};

export default function AlertaTarea({ avisos, refrescar, sonar }) {
  const navigate = useNavigate();
  const pendientes = avisos.filter(esAlertaTarea);
  const a = pendientes[0];
  const info = a && ALERTAS_TAREA[a.tipo];
  const principal = useRef(null);

  // Los que insisten (recordatorios, devoluciones, vencimientos) vuelven a sonar cada 30 s y parpadean en la pestaña
  const insiste = !!info?.insiste;
  useEffect(() => {
    if (!insiste) return undefined;
    const original = document.title;
    let alterno = false;
    const titulo = setInterval(() => { alterno = !alterno; document.title = alterno ? "🔔 Tienes una alerta" : original; }, 1200);
    const sonido = setInterval(sonar, 30000);
    return () => { clearInterval(titulo); clearInterval(sonido); document.title = original; };
  }, [insiste, sonar]);

  useEffect(() => { if (a) principal.current?.focus(); }, [a?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!a) return null;
  const tono = TONOS[info.tono];
  const Icono = info.icono;
  const destino = a.enlace ? (a.tarea && !a.enlace.includes("tarea=") ? `${a.enlace}?tarea=${a.tarea}` : a.enlace) : null;

  // «Entendido» atiende solo esta alerta: si hay más, pasa a la siguiente
  const atender = async (ir) => {
    try { await leerAvisos([a.id]); } catch { /* se reintenta en el próximo refresco */ }
    refrescar();
    if (ir && destino) navigate(destino);
  };

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-noche-900/75 p-4 backdrop-blur-md" role="alertdialog" aria-modal="true" aria-labelledby="alerta-titulo" aria-describedby="alerta-mensaje">
      <div key={a.id} className="w-full max-w-xl animate-[entrar-alerta_0.35s_cubic-bezier(0.2,0.9,0.3,1.15)] overflow-hidden rounded-3xl bg-white shadow-[0_30px_90px_-20px_rgba(0,0,0,0.6)] motion-reduce:animate-none">
        <div className={cx("h-2", tono.banda)} />
        <div className="flex flex-col items-center px-6 pb-7 pt-9 text-center sm:px-10">
          <span className="relative flex size-24 items-center justify-center">
            <span className={cx("absolute inline-flex size-full animate-ping rounded-full motion-reduce:animate-none", tono.halo)} />
            <span className={cx("relative flex size-24 items-center justify-center rounded-full ring-4", tono.aro)}>
              <Icono className="size-11" aria-hidden />
            </span>
          </span>
          <p className={cx("mt-8 text-xs font-bold uppercase tracking-[0.18em]", tono.etiqueta)}>{info.etiqueta}</p>
          <h2 id="alerta-titulo" className="mt-2 text-[26px] font-semibold leading-tight text-tinta sm:text-[32px]">{a.titulo}</h2>
          {a.mensaje && <p id="alerta-mensaje" className="mt-4 max-w-md whitespace-pre-line text-lg leading-relaxed text-gris">{a.mensaje}</p>}
          <p className="mt-5 flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-sm text-gris">
            {a.remitente_nombre && <span>De <b className="font-semibold text-tinta">{a.remitente_nombre}</b></span>}
            <span className="inline-flex items-center gap-1"><Clock className="size-3.5" aria-hidden />{hace(a.fecha)}</span>
          </p>
          {pendientes.length > 1 && (
            <p className="mt-4 inline-flex items-center gap-2 rounded-full bg-fondo px-3 py-1 text-xs font-medium text-gris" aria-live="polite">
              <span className="flex gap-1" aria-hidden>{pendientes.slice(0, 6).map((p, i) => <span key={p.id} className={cx("size-1.5 rounded-full", i === 0 ? tono.banda : "bg-linea")} />)}</span>
              Te quedan {pendientes.length - 1} alerta{pendientes.length > 2 ? "s" : ""} más
            </p>
          )}
        </div>
        <div className="grid gap-3 border-t border-linea-suave bg-fondo/70 p-5 sm:grid-cols-2 sm:p-6">
          {destino && (
            <button ref={principal} type="button" onClick={() => atender(true)}
              className="h-14 rounded-2xl bg-noche px-5 text-base font-semibold text-white shadow-lg shadow-noche/30 transition hover:bg-noche-900 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-azul/30 active:scale-[0.99] sm:order-2">
              {info.boton}
            </button>
          )}
          <button ref={destino ? undefined : principal} type="button" onClick={() => atender(false)}
            className={cx("h-14 rounded-2xl border border-linea bg-white px-5 text-base font-semibold text-tinta transition hover:bg-linea-suave focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-azul/20 sm:order-1", !destino && "sm:col-span-2")}>
            Entendido
          </button>
        </div>
      </div>
    </div>
  );
}
