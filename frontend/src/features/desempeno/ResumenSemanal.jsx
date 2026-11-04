// Resultados → Resumen de la semana (Dirección): quién va bien, qué OT están en riesgo y dónde se pierde dinero.
import { useEffect, useState } from "react";
import { RefreshCw, Sparkles } from "lucide-react";
import { regenerarResumen, resumenSemanal } from "@/lib/api";
import { fechaCorta } from "@/lib/formato";
import { Alerta, Boton, Cabecera, Cargando, Insignia, Panel } from "@/components/ui";

/** Texto con títulos («Lo que va bien») y viñetas («- …» o «• …»), sin HTML. */
function Texto({ texto }) {
  return (
    <div className="space-y-2 text-[15px] leading-relaxed">
      {texto.split("\n").filter((l) => l.trim()).map((l, i) => {
        const t = l.trim().replace(/\*\*/g, "");
        if (/^[-•*]\s+/.test(t)) return <p key={i} className="flex gap-2 pl-1"><span className="text-azul">•</span><span>{t.replace(/^[-•*]\s+/, "")}</span></p>;
        if (/^(#+\s*|\d\)\s*)/.test(t) || (t.length < 40 && !t.endsWith("."))) return <p key={i} className="pt-2 font-display font-semibold text-noche">{t.replace(/^(#+\s*|\d\)\s*)/, "")}</p>;
        return <p key={i}>{t}</p>;
      })}
    </div>
  );
}

export default function ResumenSemanal() {
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);
  useEffect(() => { resumenSemanal().then(setD).catch((e) => setError(e.message)); }, []);
  const regenerar = async () => { setCargando(true); try { setD(await regenerarResumen()); } catch (e) { setError(e.message); } setCargando(false); };
  return (
    <div className="max-w-3xl space-y-5">
      <Cabecera titulo="Resumen de la semana" descripcion="Cada lunes: cómo fue la semana anterior, qué OT están en riesgo, quién necesita apoyo y dónde se pierde dinero." />
      {error && <Alerta>{error}</Alerta>}
      {!d ? !error && <Cargando texto="Preparando el resumen…" /> : <>
        <Panel titulo={`Semana del ${fechaCorta(d.actual.datos.semana.desde)} al ${fechaCorta(d.actual.datos.semana.hasta)}`}
          accion={<div className="flex items-center gap-2">{d.actual.con_ia ? <Insignia tono="azul"><Sparkles className="size-3" />Redactado con IA</Insignia> : <Insignia>Automático</Insignia>}
            <Boton tam="sm" variante="fantasma" icono={RefreshCw} cargando={cargando} onClick={regenerar} aria-label="Actualizar con los datos de ahora" /></div>}>
          <Texto texto={d.actual.texto} />
          {!d.ia_configurada && <p className="mt-4 text-xs text-gris">Sin la clave de la API de Claude, el resumen se arma con los números. Con la clave (ANTHROPIC_API_KEY en el servidor) lo redacta la IA con recomendaciones.</p>}
        </Panel>
        {d.anteriores.length > 0 && (
          <details className="rounded-2xl border border-linea bg-white p-5">
            <summary className="cursor-pointer font-display font-semibold">Semanas anteriores</summary>
            <div className="mt-4 space-y-6">{d.anteriores.map((a) => <div key={a.semana}><p className="mb-2 text-sm text-gris">Semana del {fechaCorta(a.semana)}</p><Texto texto={a.texto} /></div>)}</div>
          </details>
        )}
      </>}
    </div>
  );
}
