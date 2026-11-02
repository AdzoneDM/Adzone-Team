// Ficha de productividad del mes: puntaje, KPIs (manuales y automáticos), horario, computadora, tiempo y tendencia.
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, Bot } from "lucide-react";
import { fichaProductividad } from "@/lib/api";
import { mesActual, nombreMes, reloj } from "@/lib/formato";
import { Alerta, Barra, Cabecera, Cargando, Insignia, Panel, Puntaje, SelectorMes, cx } from "@/components/ui";
import { ResumenAsistencia } from "@/features/asistencia/Asistencia";

const pct = (v) => (v == null ? "—" : `${Number(v).toLocaleString("es-DO", { maximumFractionDigits: 1 })} %`);
const FUENTE = {
  ENTREGAS_A_TIEMPO: "Tareas a tiempo", PRIMERA: "Tareas a la primera", RONDAS: "Rondas de las tareas", CALIDAD: "Calidad de las tareas",
  PUNTUALIDAD: "Control de horario", ASISTENCIA: "Control de horario", HORAS: "Control de horario", ADHERENCIA: "Control de horario",
  ACTIVIDAD_PC: "Computadora", PRODUCTIVIDAD_PC: "Computadora", "": "Tareas vinculadas",
};
const EVALUACION = { CUMPLE: ["Cumple", "verde"], BAJO_MINIMO: ["Bajo el mínimo", "rojo"], POCOS_DATOS: ["Pocos datos", "neutro"] };

function Componente({ titulo, valor, peso }) {
  return (
    <div className="rounded-xl border border-linea bg-white p-4">
      <p className="text-sm text-gris">{titulo} <span className="text-xs">· {peso} %</span></p>
      <p className="mt-1 text-3xl"><Puntaje valor={valor} /></p>
      <Barra valor={valor} className="mt-2" />
    </div>
  );
}

function Fila({ etiqueta, valor, nota }) {
  return <div className="flex items-baseline justify-between gap-3 border-b border-linea-suave py-2 last:border-0"><span className="text-[15px]">{etiqueta}</span><span className="text-right"><span className="font-semibold num">{valor}</span>{nota && <span className="block text-xs text-gris">{nota}</span>}</span></div>;
}

export default function Ficha() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const usuario = params.get("usuario") || "";
  const mes = params.get("mes") || mesActual();
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { setD(null); setError(""); fichaProductividad({ usuario, mes }).then(setD).catch((e) => setError(e.message)); }, [usuario, mes]);
  if (error) return <Alerta>{error}</Alerta>;
  if (!d) return <Cargando />;
  const p = d.puntaje;
  const pc = d.computadora;
  const ev = p ? EVALUACION[p.evaluacion] : null;
  return (
    <div className="space-y-5">
      {usuario && <button type="button" onClick={() => navigate(-1)} className="inline-flex items-center gap-1.5 text-sm font-medium text-azul hover:underline"><ArrowLeft className="size-4" />Volver</button>}
      <Cabecera titulo={`Ficha de ${d.persona.nombre}`} descripcion={`${d.persona.puesto || "Sin puesto"}${d.persona.departamento ? ` · ${d.persona.departamento}` : ""} · todo lo que la plataforma midió en ${nombreMes(mes)}.`}>
        <SelectorMes valor={mes} onCambio={(m) => setParams(usuario ? { usuario, mes: m } : { mes: m })} />
      </Cabecera>

      <div className="grid gap-3 md:grid-cols-4">
        <div className="rounded-xl border border-linea bg-noche p-4 text-white">
          <p className="text-sm text-white/70">Puntaje del mes{p?.posicion ? ` · puesto #${p.posicion}` : ""}</p>
          <p className="mt-1 font-display text-4xl font-semibold num">{p ? Number(p.puntaje_total).toLocaleString("es-DO", { maximumFractionDigits: 1 }) : "—"}</p>
          {ev && <Insignia tono={ev[1]} className="mt-2">{ev[0]}</Insignia>}
          {p?.bono_sugerido ? <p className="mt-2 text-sm text-white/80">Bono sugerido: {p.bono_sugerido} % del salario</p> : null}
        </div>
        <Componente titulo="Tareas" valor={p?.puntaje_tareas} peso={d.pesos.tareas} />
        <Componente titulo="KPIs del puesto" valor={p?.puntaje_kpis} peso={d.pesos.kpis} />
        <Componente titulo="Jornada (horario y computadora)" valor={p?.puntaje_jornada} peso={d.pesos.jornada} />
      </div>

      {(d.alertas.length > 0 || p?.motivos?.length > 0) && (
        <Panel titulo="Para atender">
          <ul className="space-y-2">
            {[...d.alertas.map((a) => a.texto), ...(p?.motivos || []).map((m) => `Le baja el puntaje: ${m}.`)].map((t) => (
              <li key={t} className="flex items-start gap-2 text-[15px]"><AlertTriangle className="mt-0.5 size-4 shrink-0 text-[#a86a00]" />{t}</li>
            ))}
          </ul>
        </Panel>
      )}

      <Panel titulo="KPIs del puesto" cuerpo="p-0">
        {d.kpis.length === 0 ? <p className="p-5 text-sm text-gris">Sin KPIs medidos este mes. Los manuales se anotan en «KPIs del mes»; los automáticos salen solos cuando hay datos.</p> : (
          <div className="overflow-x-auto">
            <table className="tabla">
              <thead><tr><th>KPI</th><th>Origen</th><th className="text-right">Meta</th><th className="text-right">Logrado</th><th className="w-40">Cumplimiento</th><th className="text-right">Peso</th></tr></thead>
              <tbody>
                {d.kpis.map((k) => (
                  <tr key={k.kpi_asignado_id}>
                    <td className="font-medium">{k.nombre}</td>
                    <td>{k.automatico ? <Insignia tono="azul"><Bot className="mr-1 inline size-3" />{FUENTE[k.fuente] || "Automático"}</Insignia> : <Insignia>Anotado</Insignia>}</td>
                    <td className="text-right num">{Number(k.meta).toLocaleString("es-DO")} <span className="text-xs text-gris">{k.unidad_medida}</span></td>
                    <td className="text-right num">{Number(k.valor).toLocaleString("es-DO")}</td>
                    <td><div className="flex items-center gap-2"><Barra valor={k.cumplimiento} /><span className="w-12 text-right text-sm num">{Math.round(k.cumplimiento)} %</span></div></td>
                    <td className="text-right num">{k.ponderacion} %</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Control de horario</h2>
        <ResumenAsistencia r={d.horario} adherencia={d.horario.adherencia} />
      </section>

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel titulo="Computadora">
          {pc.minutos_registrados ? <>
            <Fila etiqueta="Tiempo activo" valor={pct(pc.actividad)} nota={`${reloj(pc.minutos_activos)} de ${reloj(pc.minutos_registrados)} registrados`} />
            <Fila etiqueta="Productivo" valor={pct(pc.productividad)} nota={`${reloj(pc.minutos_productivos)} productivo · ${reloj(pc.minutos_improductivos)} improductivo`} />
            <Fila etiqueta="Tiempo de foco" valor={reloj(pc.minutos_foco)} nota={`${pc.sesiones_foco} bloque(s) de 25+ minutos`} />
            <Fila etiqueta="Nivel de actividad" valor={pct(pc.intensidad)} />
            <Fila etiqueta="Cambios de ventana" valor={pc.cambios_por_hora ?? "—"} nota="por hora" />
            <Fila etiqueta="Cobertura de la jornada" valor={pct(pc.cobertura)} nota="Jornada con la computadora reportando" />
            <Fila etiqueta="Días con actividad" valor={pc.dias_con_actividad} />
          </> : <p className="text-sm text-gris">Sin actividad de computadora este mes (sin agente vinculado o sin aceptar la política).</p>}
        </Panel>
        <Panel titulo="Tareas">
          <Fila etiqueta="Validadas en el mes" valor={d.tareas.validadas} />
          <Fila etiqueta="Entregadas a tiempo" valor={pct(d.tareas.a_tiempo_pct)} />
          <Fila etiqueta="Aprobadas a la primera" valor={pct(d.tareas.a_la_primera_pct)} />
          <Fila etiqueta="Rondas de revisión" valor={d.tareas.rondas_promedio ?? "—"} nota="1 = a la primera" />
          <Fila etiqueta="Calidad" valor={pct(d.tareas.calidad_pct)} />
          <Fila etiqueta="Tiempo registrado en tareas" valor={reloj(d.tiempo.minutos_en_tareas)} nota={d.tiempo.utilizacion != null ? `${pct(d.tiempo.utilizacion)} de la jornada` : null} />
        </Panel>
        <Panel titulo="Aplicaciones más usadas" cuerpo="p-0">
          {pc.apps?.length ? <ul className="divide-y divide-linea-suave">{pc.apps.slice(0, 8).map((a) => (
            <li key={a.nombre} className="flex items-center gap-3 px-5 py-2"><span className="min-w-0 flex-1 truncate">{a.nombre}</span>
              <span className={cx("size-2 rounded-full", a.categoria === "P" ? "bg-verde" : a.categoria === "I" ? "bg-rojo" : "bg-[#9aa7bd]")} /><span className="w-14 text-right text-sm num">{reloj(a.minutos)}</span></li>
          ))}</ul> : <p className="p-5 text-sm text-gris">Sin datos.</p>}
        </Panel>
      </div>

      <Panel titulo="Tendencia de 6 meses" cuerpo="p-0">
        <div className="overflow-x-auto">
          <table className="tabla">
            <thead><tr><th>Mes</th><th className="text-right">Adherencia al horario</th><th className="text-right">Productividad en PC</th><th className="text-right">Tareas a tiempo</th><th className="text-right">Calidad</th></tr></thead>
            <tbody>
              {d.tendencia.map((t) => (
                <tr key={t.mes}><td className="first-letter:uppercase">{nombreMes(t.mes)}</td>
                  <td className="text-right"><Puntaje valor={t.adherencia} /></td><td className="text-right"><Puntaje valor={t.productividad} /></td>
                  <td className="text-right"><Puntaje valor={t.a_tiempo} /></td><td className="text-right"><Puntaje valor={t.calidad} /></td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
