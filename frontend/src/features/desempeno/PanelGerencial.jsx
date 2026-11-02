// Panel gerencial de la Dirección: la empresa del mes en una pantalla, por área, con alertas para decidir.
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AlertTriangle, Download, GraduationCap, ScrollText, TrendingDown } from "lucide-react";
import { panelGerencial, urlExportarPanel } from "@/lib/api";
import { mesActual, nombreMes } from "@/lib/formato";
import { Alerta, Barra, Cabecera, Cargando, Insignia, Panel, Puntaje, SelectorMes, cx } from "@/components/ui";

const pct = (v) => (v == null ? "—" : `${Number(v).toLocaleString("es-DO", { maximumFractionDigits: 1 })} %`);
const NIVEL = { alta: ["Alta", "rojo"], media: ["Media", "amarillo"], baja: ["Baja", "azul"] };

function Cifra({ titulo, valor, detalle, enlace }) {
  const cuerpo = (
    <div className="h-full rounded-xl border border-linea bg-white p-4">
      <p className="text-sm text-gris">{titulo}</p>
      <p className="mt-1 font-display text-3xl font-semibold num">{valor}</p>
      {detalle && <p className="mt-1 text-xs text-gris">{detalle}</p>}
    </div>
  );
  return enlace ? <Link to={enlace} className="block hover:[&>div]:border-azul">{cuerpo}</Link> : cuerpo;
}

function Serie({ valores }) {
  const v = valores.filter((x) => x != null);
  if (!v.length) return <span className="text-gris">—</span>;
  const max = Math.max(...v, 1);
  return (
    <span className="inline-flex h-6 items-end gap-0.5" aria-label={`Últimos meses: ${valores.map((x) => x ?? "sin datos").join(", ")}`}>
      {valores.map((x, i) => <span key={i} className={cx("w-1.5 rounded-sm", x == null ? "bg-linea-suave" : i === valores.length - 1 ? "bg-azul" : "bg-[#9aa7bd]")} style={{ height: `${x == null ? 15 : Math.max(10, (x / max) * 100)}%` }} />)}
    </span>
  );
}

export default function PanelGerencial() {
  const [params, setParams] = useSearchParams();
  const mes = params.get("mes") || mesActual();
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { setD(null); setError(""); panelGerencial(mes).then(setD).catch((e) => setError(e.message)); }, [mes]);
  return (
    <div className="space-y-5">
      <Cabecera titulo="Panel gerencial" descripcion={`La empresa en ${nombreMes(mes)}: personal, productividad, entregas, áreas y alertas.`}>
        <SelectorMes valor={mes} onCambio={(m) => setParams({ mes: m })} />
        <a href={urlExportarPanel(mes)} className="inline-flex h-11 items-center gap-2 rounded-lg border border-linea bg-white px-4 text-sm font-medium hover:border-azul"><Download className="size-4" />Excel</a>
      </Cabecera>
      {error ? <Alerta>{error}</Alerta> : !d ? <Cargando texto="Calculando el mes…" /> : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <Cifra titulo="Personal activo" valor={d.personal_activo} detalle={`${d.evaluados} evaluados en el mes`} enlace="/organizacion" />
            <Cifra titulo="Productividad general" valor={<Puntaje valor={d.puntaje_promedio} />} detalle="Puntaje promedio" enlace={`/desempeno?mes=${mes}`} />
            <Cifra titulo="OT completadas" valor={d.ot_completadas} detalle={`${d.ot_abiertas} abiertas`} enlace="/ordenes" />
            <Cifra titulo="Entregas a tiempo" valor={pct(d.ot_a_tiempo)} detalle="OT entregadas en su fecha" />
            <Cifra titulo="Tareas validadas" valor={d.tareas_validadas} detalle={`${pct(d.tareas_a_tiempo)} a tiempo`} />
            <Cifra titulo="Asistencia · calidad" valor={<><Puntaje valor={d.asistencia_promedio} /> · <Puntaje valor={d.calidad_promedio} /></>}
              detalle={`${d.planes_abiertos} plan(es) de mejora abiertos`} enlace="/talento?ver=planes" />
          </div>

          <Panel titulo={`Alertas gerenciales (${d.alertas.length})`} cuerpo="p-0">
            {!d.alertas.length ? <p className="p-5 text-sm text-gris">Sin alertas este mes.</p> : (
              <ul className="divide-y divide-linea-suave">{d.alertas.map((a, i) => (
                <li key={i} className="flex items-start gap-3 px-5 py-3">
                  {a.tipo === "POLITICAS" || a.tipo === "DOCUMENTOS" ? <ScrollText className="mt-0.5 size-4 shrink-0 text-[#a86a00]" /> : a.tipo === "TENDENCIA" ? <TrendingDown className="mt-0.5 size-4 shrink-0 text-[#a86a00]" /> : a.tipo === "CAPACITACION" ? <GraduationCap className="mt-0.5 size-4 shrink-0 text-azul" /> : <AlertTriangle className="mt-0.5 size-4 shrink-0 text-rojo" />}
                  <span className="min-w-0 flex-1"><Link to={a.enlace} className="font-medium hover:text-azul">{a.titulo}</Link><span className="block text-sm text-gris">{a.detalle}</span></span>
                  <Insignia tono={NIVEL[a.nivel][1]}>{NIVEL[a.nivel][0]}</Insignia>
                </li>))}</ul>
            )}
          </Panel>

          <Panel titulo="Indicadores por área" cuerpo="p-0">
            <div className="overflow-x-auto"><table className="tabla">
              <thead><tr><th>Área</th><th className="text-right">Personas</th><th className="text-right">Puntaje</th><th>Tendencia 6 meses</th><th className="text-right">KPIs</th><th className="text-right">Calidad</th>
                <th className="text-right">Asistencia</th><th className="text-right">Productivo PC</th><th className="text-right">Tareas validadas</th><th className="text-right">Vencidas</th><th className="text-right">Horas</th></tr></thead>
              <tbody>{d.departamentos.map((x) => (
                <tr key={x.nombre}>
                  <td className="font-medium">{x.nombre}{x.bajo_minimo ? <Insignia tono="rojo" className="ml-2">{x.bajo_minimo} bajo el mínimo</Insignia> : null}</td>
                  <td className="text-right num">{x.personas}<span className="block text-xs text-gris">{x.evaluados} evaluados</span></td>
                  <td className="text-right"><Puntaje valor={x.puntaje} /></td>
                  <td><Serie valores={x.tendencia} /></td>
                  <td className="text-right"><Puntaje valor={x.kpis} /></td>
                  <td className="text-right"><Puntaje valor={x.calidad} /></td>
                  <td className="text-right"><Puntaje valor={x.asistencia} /></td>
                  <td className="text-right"><Puntaje valor={x.productividad_pc} /></td>
                  <td className="text-right num">{x.tareas_validadas}</td>
                  <td className={cx("text-right num", x.tareas_vencidas >= x.personas * 2 && x.tareas_vencidas >= 3 && "font-semibold text-rojo")}>{x.tareas_vencidas}</td>
                  <td className="text-right num">{x.horas}</td>
                </tr>))}</tbody>
            </table></div>
          </Panel>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel titulo="Tendencia de la empresa" cuerpo="p-0">
              <div className="overflow-x-auto"><table className="tabla">
                <thead><tr><th>Mes</th><th className="w-40">Puntaje promedio</th><th className="text-right">OT completadas</th><th className="text-right">OT a tiempo</th><th className="text-right">Tareas a tiempo</th></tr></thead>
                <tbody>{d.tendencia.map((m) => (
                  <tr key={m.mes}><td className="first-letter:uppercase">{nombreMes(m.mes)}</td>
                    <td><div className="flex items-center gap-2"><Barra valor={m.puntaje} /><span className="w-10 text-right text-sm num">{m.puntaje ?? "—"}</span></div></td>
                    <td className="text-right num">{m.ot_completadas}</td><td className="text-right num">{pct(m.ot_a_tiempo)}</td><td className="text-right num">{pct(m.tareas_a_tiempo)}</td></tr>))}</tbody>
              </table></div>
            </Panel>
            <div className="space-y-4">
              <Panel titulo="Destacados del mes" cuerpo="p-0">
                {!d.destacados.length ? <p className="p-5 text-sm text-gris">Sin evaluados todavía.</p> : (
                  <ul className="divide-y divide-linea-suave">{d.destacados.map((p, i) => (
                    <li key={p.id} className="flex items-center gap-3 px-5 py-2"><span className="w-5 text-sm text-gris num">{i + 1}</span>
                      <Link to={`/ficha?usuario=${p.id}&mes=${mes}`} className="min-w-0 flex-1 truncate hover:text-azul">{p.nombre}<span className="text-xs text-gris"> · {p.puesto}</span></Link><Puntaje valor={p.puntaje} /></li>))}</ul>
                )}
              </Panel>
              {d.atencion.length > 0 && (
                <Panel titulo="Necesitan atención" cuerpo="p-0">
                  <ul className="divide-y divide-linea-suave">{d.atencion.map((p) => (
                    <li key={p.id} className="px-5 py-2"><div className="flex items-center gap-3"><Link to={`/ficha?usuario=${p.id}&mes=${mes}`} className="min-w-0 flex-1 truncate hover:text-azul">{p.nombre}</Link><Puntaje valor={p.puntaje} /></div>
                      {p.motivos.length > 0 && <p className="text-xs text-gris">{p.motivos.join(" · ")}</p>}</li>))}</ul>
                </Panel>
              )}
            </div>
          </div>

          <Panel titulo="Necesidades de capacitación" className="scroll-mt-20" cuerpo="p-0">
            <div id="capacitacion" />
            {!d.capacitacion.length ? <p className="p-5 text-sm text-gris">Salen de las competencias con promedio menor a 3 en la última evaluación y de los KPIs bajo su umbral en dos o más personas del área.</p> : (
              <ul className="divide-y divide-linea-suave">{d.capacitacion.map((c, i) => (
                <li key={i} className="flex flex-wrap items-center gap-3 px-5 py-2.5"><span className="flex-1"><span className="font-medium">{c.tema}</span><span className="block text-xs text-gris">{c.departamento} · {c.origen}</span></span>
                  {c.promedio != null && <span className="text-sm num">{c.promedio} de 5</span>}{c.personas != null && <span className="text-sm num">{c.personas} personas</span>}</li>))}</ul>
            )}
          </Panel>
          {d.evaluaciones_por_revisar > 0 && <Alerta tono="amarillo"><Link to="/talento?ver=revisar" className="font-medium underline">{d.evaluaciones_por_revisar} evaluación(es) baja(s) esperan tu validación.</Link></Alerta>}
        </>
      )}
    </div>
  );
}
