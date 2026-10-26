// Indicadores semanales de producción: lo que se revisa en la reunión de los lunes.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { indicadoresProduccion } from "@/lib/api";
import { dinero, fechaCorta, hoyISO, lunesDe, sumarDias } from "@/lib/formato";
import { Alerta, Cabecera, Campo, Cargando, Panel, cx } from "@/components/ui";
import { AreaChip } from "./piezas";

function Numero({ etiqueta, valor, tono, ayuda }) {
  return (
    <div className="rounded-xl border border-linea bg-white px-4 py-3">
      <p className="text-sm text-gris">{etiqueta}</p>
      <p className={cx("font-display text-2xl font-semibold num", tono)}>{valor ?? "—"}</p>
      {ayuda && <p className="text-xs text-gris">{ayuda}</p>}
    </div>
  );
}

const pct = (v) => (v == null ? "—" : `${v}%`);
const tonoPct = (v) => (v == null ? "" : v >= 90 ? "text-verde" : v >= 70 ? "" : "text-rojo");

export default function Indicadores() {
  const lunes = lunesDe(hoyISO());
  const [desde, setDesde] = useState(sumarDias(lunes, -7));
  const [hasta, setHasta] = useState(sumarDias(lunes, -1));
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { setD(null); indicadoresProduccion({ desde, hasta }).then(setD).catch((e) => setError(e.message)); }, [desde, hasta]);
  const atajos = [["Semana pasada", sumarDias(lunes, -7), sumarDias(lunes, -1)], ["Esta semana", lunes, hoyISO()], ["Últimos 30 días", sumarDias(hoyISO(), -29), hoyISO()]];

  return (
    <div>
      <Link to="/ordenes" className="mb-3 inline-flex items-center gap-1.5 text-sm font-medium text-azul hover:underline"><ArrowLeft className="size-4" />Órdenes</Link>
      <Cabecera titulo="Indicadores de producción" descripcion="A tiempo, colas, rechazos en compuertas, retrabajos, tiempos muertos y desperdicio por área. Todo sale de lo que ya se registra en las OT.">
        <div className="flex flex-wrap items-end gap-2">
          {atajos.map(([t, a, b]) => <button key={t} type="button" onClick={() => { setDesde(a); setHasta(b); }}
            className={cx("h-11 rounded-lg border px-3 text-sm font-medium", desde === a && hasta === b ? "border-noche bg-noche text-white" : "border-linea bg-white")}>{t}</button>)}
          <Campo etiqueta="Desde">{(id) => <input id={id} type="date" className="campo h-11" value={desde} onChange={(e) => setDesde(e.target.value)} />}</Campo>
          <Campo etiqueta="Hasta">{(id) => <input id={id} type="date" className="campo h-11" value={hasta} onChange={(e) => setHasta(e.target.value)} />}</Campo>
        </div>
      </Cabecera>
      {error && <Alerta>{error}</Alerta>}
      {!d ? <Cargando /> : (
        <div className="space-y-5">
          <p className="text-sm text-gris">Del {fechaCorta(d.desde)} al {fechaCorta(d.hasta)}</p>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
            <Numero etiqueta="Solicitadas" valor={d.ot.solicitadas} />
            <Numero etiqueta="Liberadas" valor={d.ot.liberadas} />
            <Numero etiqueta="Devueltas en G0" valor={d.ot.devueltas_g0} tono={d.ot.devueltas_g0 ? "text-[#a86a00]" : ""} />
            <Numero etiqueta="Entregadas" valor={d.ot.entregadas} />
            <Numero etiqueta="A tiempo" valor={pct(d.ot.a_tiempo_pct)} tono={tonoPct(d.ot.a_tiempo_pct)} />
            <Numero etiqueta="En producción" valor={d.ot.en_produccion} />
            <Numero etiqueta="Vencidas hoy" valor={d.ot.vencidas} tono={d.ot.vencidas ? "text-rojo" : ""} />
            <Numero etiqueta="Sin anticipo (excepción)" valor={d.ot.excepciones_sin_anticipo} />
          </div>
          {d.ot.margen_pct !== undefined && (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Numero etiqueta="OT cerradas" valor={d.ot.cerradas} />
              <Numero etiqueta="Vendido" valor={dinero(d.ot.vendido)} />
              <Numero etiqueta="Costo real" valor={dinero(d.ot.costo)} />
              <Numero etiqueta="Margen" valor={pct(d.ot.margen_pct)} tono={d.ot.margen_pct >= 30 ? "text-verde" : d.ot.margen_pct != null && d.ot.margen_pct < 15 ? "text-rojo" : ""} />
            </div>
          )}
          <Panel titulo="Por área" cuerpo="p-0">
            {d.areas.length === 0 ? <p className="p-5 text-sm text-gris">No supervisas ningún área.</p> : (
              <div className="overflow-x-auto">
                <table className="tabla">
                  <thead><tr><th>Área</th><th className="text-right">Terminadas</th><th className="text-right">A tiempo</th><th className="text-right">En cola</th><th className="text-right">En curso</th>
                    <th className="text-right">Vencidas</th><th className="text-right">Rechazos G1</th><th className="text-right">Traspasos rechazados</th><th className="text-right">Retrabajos</th>
                    <th className="text-right">Min. perdidos</th><th className="text-right">Rondas G4</th><th className="text-right">Desperdicio</th></tr></thead>
                  <tbody>
                    {d.areas.map((a) => (
                      <tr key={a.area}>
                        <td><AreaChip area={a.area} nombre={a.nombre} /></td>
                        <td className="text-right num">{a.terminadas}</td>
                        <td className={cx("text-right num", tonoPct(a.a_tiempo_pct))}>{pct(a.a_tiempo_pct)}</td>
                        <td className="text-right num">{a.en_cola}</td>
                        <td className="text-right num">{a.en_curso}</td>
                        <td className={cx("text-right num", a.vencidas && "font-semibold text-rojo")}>{a.vencidas}</td>
                        <td className="text-right num">{a.rechazos_g1}</td>
                        <td className={cx("text-right num", a.traspasos_rechazados && "text-[#a86a00]")}>{a.traspasos_rechazados}</td>
                        <td className="text-right num" title={Object.entries(a.causas_retrabajo).map(([k, v]) => `${k}: ${v}`).join("\n")}>{a.retrabajos}</td>
                        <td className="text-right num">{a.minutos_perdidos}</td>
                        <td className="text-right num">{a.rondas_g4_promedio ?? "—"}</td>
                        <td className="text-right num">{a.desperdicio != null ? dinero(a.desperdicio) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
          <Panel titulo="Velocidad, calidad y control (uso estratégico de herramientas)" cuerpo="p-0">
            <div className="overflow-x-auto">
              <table className="tabla">
                <thead><tr><th>Área</th><th className="text-right">Brief → propuesta</th><th className="text-right">Aprobadas a la primera</th>
                  <th className="text-right">Ajustes en revisión interna</th><th className="text-right">Horas reales / estándar</th><th className="text-right">Rendimiento</th></tr></thead>
                <tbody>
                  {d.areas.filter((a) => a.brief_a_propuesta_h != null || a.primera_aprobacion_pct != null || a.horas_estandar != null || a.devoluciones_internas).map((a) => {
                    const rend = a.horas_estandar && a.horas_reales ? Math.round((a.horas_estandar / a.horas_reales) * 100) : null;
                    return (
                      <tr key={a.area}>
                        <td><AreaChip area={a.area} nombre={a.nombre} /></td>
                        <td className="text-right num">{a.brief_a_propuesta_h != null ? `${a.brief_a_propuesta_h} h` : "—"}</td>
                        <td className={cx("text-right num", tonoPct(a.primera_aprobacion_pct))}>{pct(a.primera_aprobacion_pct)}</td>
                        <td className="text-right num">{a.devoluciones_internas}</td>
                        <td className="text-right num">{a.horas_estandar != null ? `${a.horas_reales} / ${a.horas_estandar} h` : "—"}</td>
                        <td className={cx("text-right num", rend == null ? "" : rend >= 90 ? "text-verde" : rend >= 70 ? "" : "text-rojo")}>{rend != null ? `${rend}%` : "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="px-5 pb-4 pt-2 text-xs text-gris">Rendimiento = horas del cronograma de producción ÷ horas reales del cronómetro (100 % = en el estándar). Meta: más contenido aprobado con menos retrabajo.</p>
          </Panel>
          {d.areas.some((a) => a.retrabajos) && (
            <Panel titulo="Causas de retrabajo">
              <ul className="grid gap-2 sm:grid-cols-2">{d.areas.filter((a) => a.retrabajos).map((a) => (
                <li key={a.area} className="text-sm"><AreaChip area={a.area} /> {Object.entries(a.causas_retrabajo).map(([k, v]) => `${k} (${v})`).join(", ")}</li>
              ))}</ul>
            </Panel>
          )}
        </div>
      )}
    </div>
  );
}
