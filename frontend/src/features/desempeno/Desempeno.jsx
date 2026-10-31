import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Award, ChevronDown, CircleAlert, Download, Trophy, Undo2 } from "lucide-react";
import { anularEmpleado, declararEmpleado, empleadosDelMes, ranking as cargarRanking, urlExportarRanking } from "@/lib/api";
import { mesActual, nombreMes, plural } from "@/lib/formato";
import {
  Alerta, Avatar, Barra, Boton, Cabecera, Campo, Cargando, Insignia, Modal, Panel, Pestanas, Puntaje, SelectorMes, Vacio, cx,
  useAviso, useConfirmar,
} from "@/components/ui";

function Declarar({ abierto, candidato, departamento, mes, onCerrar, onListo }) {
  const [beneficio, setBeneficio] = useState("");
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  useEffect(() => { if (abierto) { setBeneficio(""); setMotivo(""); setError(""); } }, [abierto]);
  if (!candidato) return null;
  const enviar = async () => {
    setEnviando(true);
    setError("");
    try {
      await declararEmpleado({ periodo: `${mes}-01`, colaborador: candidato.colaborador_id, departamento: departamento?.id || null, beneficio: beneficio.trim(), motivo: motivo.trim() });
      onListo(candidato.nombre);
    } catch (e) { setError(e.message); }
    setEnviando(false);
  };
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={departamento ? `Empleado del Mes de ${departamento.nombre}` : "Empleado del Mes de ADZONE"}
      descripcion={`${candidato.nombre}, ${nombreMes(mes)}, puntaje ${Math.round(candidato.puntaje_total * 10) / 10}`}
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton variante="acento" icono={Award} onClick={enviar} cargando={enviando}>Declarar</Boton></>}>
      <div className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        <Campo etiqueta="Reconocimiento que recibe" ayuda="Ej.: bono, día libre, almuerzo con la dirección.">
          {(id) => <input id={id} className="campo" value={beneficio} onChange={(e) => setBeneficio(e.target.value)} maxLength={255} />}
        </Campo>
        <Campo etiqueta="Motivo" ayuda="Se publica en el Muro de Honor que ve todo el equipo.">
          {(id) => <textarea id={id} className="campo" rows={3} value={motivo} onChange={(e) => setMotivo(e.target.value)} />}
        </Campo>
        {!departamento && <p className="text-sm text-gris">Todo el equipo recibe un aviso con el nombre del ganador.</p>}
      </div>
    </Modal>
  );
}

const EVALUACION = {
  CUMPLE: { texto: "Cumple", tono: "verde" },
  BAJO_MINIMO: { texto: "Bajo el mínimo", tono: "rojo" },
  POCOS_DATOS: { texto: "Pocos datos", tono: "neutro" },
};

function Contador({ n, texto, tono }) {
  return (
    <div className={cx("rounded-xl border px-4 py-3", tono)}>
      <p className="font-display text-2xl font-semibold num">{n}</p>
      <p className="text-sm">{texto}</p>
    </div>
  );
}

/** Quién cumple el desempeño mínimo del mes, quién no y de quién no hay datos para juzgar. */
function RevisionMinimo({ datos, filas, sinEvaluar, mes }) {
  const de = (e) => filas.filter((f) => f.evaluacion === e);
  const bajo = de("BAJO_MINIMO").sort((a, b) => a.puntaje_total - b.puntaje_total);
  const pocos = de("POCOS_DATOS");
  return (
    <Panel titulo={`Desempeño mínimo · ${nombreMes(mes)}`}
      accion={<Link to="/configuracion" className="text-sm font-medium text-azul hover:underline">Mínimo: {datos.puntaje_minimo} pts</Link>}>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Contador n={de("CUMPLE").length} texto={`Cumplen (${datos.puntaje_minimo} o más)`} tono="border-verde/20 bg-verde-50 text-verde" />
        <Contador n={bajo.length} texto="Por debajo del mínimo" tono="border-rojo/20 bg-rojo-50 text-[#a3170f]" />
        <Contador n={pocos.length} texto="Pocos datos para juzgar" tono="border-linea bg-fondo text-gris" />
        <Contador n={sinEvaluar.length} texto="Sin evaluar" tono="border-amarillo/40 bg-amarillo-50 text-[#7a5000]" />
      </div>

      {datos.mes_en_curso && <Alerta tono="amarillo" className="mt-4">El mes no ha terminado: estos números todavía cambian. Para decidir, usa un mes cerrado y con todo validado.</Alerta>}
      {datos.pendientes_validar > 0 && <Alerta tono="amarillo" className="mt-4">{plural(datos.pendientes_validar, "entrega espera", "entregas esperan")} validación. Mientras no se validen, no suman: pide a los supervisores que validen antes de tomar decisiones.</Alerta>}

      {bajo.length > 0 && (
        <div className="mt-5">
          <p className="mb-2 font-medium text-[#a3170f]">Por debajo del mínimo</p>
          <ul className="divide-y divide-linea-suave rounded-xl border border-linea">
            {bajo.map((f) => (
              <li key={f.colaborador_id} className="flex flex-wrap items-start gap-x-4 gap-y-1 px-4 py-3">
                <div className="min-w-[min(100%,12rem)] flex-1">
                  <p className="font-medium">{f.nombre}</p>
                  <p className="text-sm text-gris">{f.puesto || "Sin puesto"}{f.departamento ? ` · ${f.departamento}` : ""}</p>
                  {f.motivos.length > 0 && <p className="mt-1 text-sm text-tinta">{f.motivos.join(" · ")}</p>}
                </div>
                <Puntaje valor={f.puntaje_total} className="text-lg" />
              </li>
            ))}
          </ul>
        </div>
      )}

      {pocos.length > 0 && (
        <div className="mt-5">
          <p className="mb-1 font-medium">Pocos datos para juzgar</p>
          <p className="mb-2 text-sm text-gris">Menos de {datos.minimo_tareas_evaluacion} tareas que ya cuentan y ningún KPI medido. Su puntaje no es base suficiente para decidir.</p>
          <ul className="flex flex-wrap gap-2">
            {pocos.map((f) => <li key={f.colaborador_id} className="rounded-full border border-linea bg-white px-3 py-1 text-sm">{f.nombre} <span className="text-gris">· {f.tareas.total} tarea(s) · {Math.round(f.puntaje_total)} pts</span></li>)}
          </ul>
        </div>
      )}

      {sinEvaluar.length > 0 && (
        <div className="mt-5">
          <p className="mb-1 font-medium">Sin evaluar</p>
          <p className="mb-2 text-sm text-gris">Tienen puesto, pero en el mes no tienen tareas vencidas ni validadas, ni KPIs anotados. Antes de decidir, revisa con su supervisor si se les asignó trabajo en la plataforma.</p>
          <div className="overflow-x-auto rounded-xl border border-linea">
            <table className="tabla">
              <thead><tr><th>Persona</th><th>Supervisor</th><th className="text-right">Tareas del mes</th></tr></thead>
              <tbody>
                {sinEvaluar.map((f) => (
                  <tr key={f.colaborador_id}>
                    <td><p className="font-medium">{f.nombre}</p><p className="text-sm text-gris">{f.puesto}{f.departamento ? ` · ${f.departamento}` : ""}</p></td>
                    <td className="text-sm">{f.supervisor || <span className="text-gris">—</span>}</td>
                    <td className="text-right text-sm num">{f.tareas_asignadas ? `${f.tareas_asignadas} (aún en plazo${f.por_validar ? ` o por validar` : ""})` : <span className="text-[#a3170f]">ninguna asignada</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <p className="mt-4 flex items-start gap-2 text-sm text-gris"><CircleAlert className="mt-0.5 size-4 shrink-0" />El puntaje sale solo de lo que se registra en la plataforma. Es una guía: la decisión sobre cada persona la toma la dirección, revisando su caso.</p>
    </Panel>
  );
}

function DetalleFila({ f }) {
  const t = f.tareas;
  return (
    <div className="grid gap-6 bg-fondo/70 px-6 py-5 md:grid-cols-2">
      <div>
        <p className="mb-2 font-medium">Tareas del mes</p>
        <ul className="space-y-1 text-sm text-gris">
          <li>{plural(t.completadas, "validada", "validadas")} de {t.total} que ya cuentan</li>
          <li>{t.a_tiempo} a tiempo y {t.a_la_primera} aprobadas a la primera</li>
          <li>{plural(t.vencidas, "vencida sin entregar", "vencidas sin entregar")}</li>
          <li>{t.por_validar} esperando validación y {t.en_plazo} todavía en plazo (no cuentan aún)</li>
          <li>Calidad promedio: {t.calidad_promedio ?? "sin calificar"}</li>
        </ul>
      </div>
      <div>
        <p className="mb-2 font-medium">KPIs del puesto</p>
        {f.kpis.length === 0 ? <p className="text-sm text-gris">Sin KPIs medidos este mes.</p> : (
          <ul className="space-y-3">
            {f.kpis.map((k) => (
              <li key={k.kpi_asignado_id}>
                <div className="flex justify-between gap-3 text-sm"><span className="min-w-0 truncate">{k.nombre}</span><span className="shrink-0 font-medium num">{Math.round(k.cumplimiento)}%</span></div>
                <Barra valor={k.cumplimiento} className="mt-1" />
                <p className="mt-0.5 text-xs text-gris">{k.valor} de {k.meta} {k.unidad_medida} · peso {k.ponderacion}% · {k.automatico ? "automático" : "manual"}</p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default function Desempeno() {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const [mes, setMes] = useState(mesActual());
  const [params, setParams] = useSearchParams();
  const grupo = params.get("grupo") === "agentes" ? "agentes" : "empleados"; // los agentes de call center se evalúan aparte
  const [datos, setDatos] = useState(null);
  const [ganadores, setGanadores] = useState([]);
  const [error, setError] = useState("");
  const [depto, setDepto] = useState("");
  const [abierta, setAbierta] = useState(null);
  const [declarando, setDeclarando] = useState(null);

  const cargar = useCallback(() => {
    setDatos(null);
    Promise.all([cargarRanking(mes, grupo), empleadosDelMes({ mes })])
      .then(([r, g]) => { setDatos(r); setGanadores(g); })
      .catch((e) => setError(e.message));
  }, [mes, grupo]);
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => { setDepto(""); setAbierta(null); }, [grupo]);

  const departamentos = useMemo(() => [...new Map((datos?.ranking || []).filter((f) => f.departamento_id).map((f) => [f.departamento_id, f.departamento])).entries()], [datos]);
  const filas = (datos?.ranking || []).filter((f) => !depto || String(f.departamento_id) === depto);
  const sinEvaluar = (datos?.sin_evaluar || []).filter((f) => !depto || String(f.departamento_id) === depto);
  const general = ganadores.find((g) => !g.departamento);
  const ganadorDe = (id) => ganadores.find((g) => g.departamento === id);

  const anular = async (g) => {
    if (!(await confirmar({ titulo: "¿Anular la declaración?", mensaje: `Se quita a ${g.colaborador_nombre} del Muro de Honor de ${nombreMes(mes)}. Después puedes declarar a otra persona.`, boton: "Anular", peligro: true }))) return;
    try { await anularEmpleado(g.id); avisar("Declaración anulada."); cargar(); } catch (e) { avisar(e.message, "rojo"); }
  };

  if (error) return <Alerta>{error}</Alerta>;
  return (
    <div>
      <Cabecera titulo="Desempeño y ranking" descripcion={datos ? `Puntaje = tareas validadas (puntualidad y calidad) y cumplimiento de KPIs. Mínimo ${datos.minimo_tareas} tareas validadas para ser candidato.` : ""}>
        <SelectorMes valor={mes} onCambio={setMes} />
        <a href={urlExportarRanking(mes, grupo)} className="inline-flex h-11 items-center gap-2 rounded-lg border border-linea bg-white px-4 text-[15px] font-medium hover:border-azul/40">
          <Download className="size-4" /> Descargar Excel
        </a>
      </Cabecera>

      <Pestanas className="mb-5 md:w-96" valor={grupo} onCambio={(v) => { if (v === "agentes") params.set("grupo", v); else params.delete("grupo"); setParams(params, { replace: true }); }} opciones={[
        { valor: "empleados", etiqueta: "Equipo" },
        { valor: "agentes", etiqueta: "Call Center" },
      ]} />

      {!datos ? <Cargando /> : (
        <div className="space-y-6">
          {datos.mes_en_curso && <Alerta tono="azul">El mes está en curso: el ranking es parcial. Declara al Empleado del Mes cuando termine y los supervisores hayan validado lo pendiente.</Alerta>}

          <RevisionMinimo datos={datos} filas={filas} sinEvaluar={sinEvaluar} mes={mes} />

          {grupo === "empleados" && <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
            <section className="rounded-2xl bg-noche p-6 text-white">
              <p className="flex items-center gap-2 text-white/70 first-letter:uppercase"><Trophy className="size-4 text-amarillo" />Empleado del Mes de la empresa · {nombreMes(mes)}</p>
              {general ? (
                <div className="mt-4">
                  <div className="flex items-center gap-4">
                    <Avatar nombre={general.colaborador_nombre} tam="lg" className="bg-amarillo text-tinta" />
                    <div><p className="font-display text-2xl font-semibold">{general.colaborador_nombre}</p><p className="text-white/70">{general.puesto} · {general.puntaje} pts</p></div>
                  </div>
                  {general.beneficio && <p className="mt-4 text-white/80">Reconocimiento: {general.beneficio}</p>}
                  <Boton variante="fantasma" tam="sm" icono={Undo2} className="mt-4 text-white/80 hover:bg-white/10" onClick={() => anular(general)}>Anular</Boton>
                </div>
              ) : datos.candidato_general ? (
                <div className="mt-4">
                  <p className="text-sm text-white/60">Candidato sugerido (el de mayor puntaje)</p>
                  <div className="mt-2 flex items-center gap-4">
                    <Avatar nombre={datos.candidato_general.nombre} tam="lg" className="bg-white/10 text-white" />
                    <div><p className="font-display text-2xl font-semibold">{datos.candidato_general.nombre}</p><p className="text-white/70">{datos.candidato_general.puesto} · {Math.round(datos.candidato_general.puntaje_total * 10) / 10} pts</p></div>
                  </div>
                  <Boton variante="acento" icono={Award} className="mt-5" onClick={() => setDeclarando({ candidato: datos.candidato_general })}>Declarar Empleado del Mes</Boton>
                  <p className="mt-3 text-sm text-white/60">Puedes elegir a otra persona desde el ranking.</p>
                </div>
              ) : (
                <p className="mt-4 text-white/70">Nadie llega todavía a {datos.minimo_tareas} tareas validadas este mes.</p>
              )}
            </section>

            <Panel titulo="Por departamento" cuerpo="p-0">
              {datos.candidatos_departamento.length === 0 ? <p className="px-5 py-6 text-sm text-gris">Sin candidatos todavía.</p> : (
                <ul>
                  {datos.candidatos_departamento.map((d) => {
                    const g = ganadorDe(d.departamento_id);
                    return (
                      <li key={d.departamento_id} className="flex items-center gap-3 border-b border-linea-suave px-5 py-3 last:border-0">
                        <div className="min-w-0 flex-1">
                          <p className="text-sm text-gris">{d.departamento}</p>
                          <p className="truncate font-medium">{g ? g.colaborador_nombre : d.candidato.nombre} <span className="font-normal text-gris">· {g ? g.puntaje : Math.round(d.candidato.puntaje_total * 10) / 10} pts</span></p>
                        </div>
                        {g ? (<><Insignia tono="amarillo"><Award className="size-3" />Declarado</Insignia><Boton variante="fantasma" tam="sm" onClick={() => anular(g)}>Anular</Boton></>)
                          : <Boton variante="secundario" tam="sm" onClick={() => setDeclarando({ candidato: d.candidato, departamento: { id: d.departamento_id, nombre: d.departamento } })}>Declarar</Boton>}
                      </li>
                    );
                  })}
                </ul>
              )}
            </Panel>
          </div>}

          <Panel titulo={`${grupo === "agentes" ? "Ranking del call center" : "Ranking"} de ${nombreMes(mes)}`} cuerpo="p-0"
            accion={departamentos.length > 1 && (
              <select className="campo h-9 w-auto py-0 text-sm" value={depto} onChange={(e) => setDepto(e.target.value)} aria-label="Departamento">
                <option value="">Todos los departamentos</option>
                {departamentos.map(([id, n]) => <option key={id} value={id}>{n}</option>)}
              </select>
            )}>
            {filas.length === 0 ? <div className="p-5"><Vacio icono={Trophy} titulo="Todavía no hay evaluaciones este mes">Una persona entra al ranking cuando vence alguna de sus tareas, le validan una entrega o se anota un KPI manual.</Vacio></div> : (
              <div className="overflow-x-auto">
                <table className="tabla">
                  <thead><tr>
                    <th className="w-12">#</th><th>Colaborador</th><th>Tareas validadas</th><th className="text-right">Calidad</th>
                    <th className="text-right">Tareas</th><th className="text-right">KPIs</th><th className="min-w-44">Puntaje</th><th className="text-right">Bono sugerido</th><th className="w-10"><span className="sr-only">Detalle</span></th>
                  </tr></thead>
                  <tbody>
                    {filas.map((f) => (
                      <Fragment key={f.colaborador_id}>
                        <tr className={cx(abierta === f.colaborador_id && "bg-fondo/70")}>
                          <td><span className={cx("flex size-7 items-center justify-center rounded-full text-sm font-semibold num", f.posicion === 1 ? "bg-amarillo text-tinta" : "bg-linea-suave text-gris")}>{f.posicion}</span></td>
                          <td><p className="font-medium">{f.nombre}</p><p className="text-sm text-gris">{f.puesto || "Sin puesto"}{f.departamento ? ` · ${f.departamento}` : ""}</p>
                            {!f.elegible && <p className="text-xs text-gris">Menos de {datos.minimo_tareas} validadas: no es candidato</p>}</td>
                          <td className="whitespace-nowrap text-sm"><span className="font-medium num">{f.tareas.completadas}/{f.tareas.total}</span>
                            <span className="text-gris"> · {f.tareas.a_tiempo} a tiempo</span>{f.tareas.vencidas > 0 && <span className="text-rojo"> · {plural(f.tareas.vencidas, "vencida", "vencidas")}</span>}</td>
                          <td className="text-right num">{f.tareas.calidad_promedio ?? "—"}</td>
                          <td className="text-right"><Puntaje valor={f.puntaje_tareas} /></td>
                          <td className="text-right"><Puntaje valor={f.puntaje_kpis} /></td>
                          <td><div className="flex items-center gap-3"><Puntaje valor={f.puntaje_total} className="w-12 text-lg" /><Barra valor={f.puntaje_total} /></div>
                            <Insignia tono={EVALUACION[f.evaluacion].tono} className="mt-1">{EVALUACION[f.evaluacion].texto}</Insignia></td>
                          <td className="text-right">{f.bono_sugerido ? <Insignia tono="verde">{f.bono_sugerido}%</Insignia> : <span className="text-gris">—</span>}</td>
                          <td>
                            <button type="button" onClick={() => setAbierta(abierta === f.colaborador_id ? null : f.colaborador_id)} className="rounded-lg p-1.5 text-gris hover:bg-fondo hover:text-azul"
                              aria-expanded={abierta === f.colaborador_id} aria-label={`Detalle de ${f.nombre}`}>
                              <ChevronDown className={cx("size-4 transition-transform", abierta === f.colaborador_id && "rotate-180")} />
                            </button>
                          </td>
                        </tr>
                        {abierta === f.colaborador_id && (
                          <tr><td colSpan={9} className="p-0">
                            <DetalleFila f={f} />
                            {grupo === "empleados" && !general && f.elegible && (
                              <div className="flex justify-end gap-2 bg-fondo/70 px-6 pb-5">
                                <Boton variante="secundario" tam="sm" icono={Award} onClick={() => setDeclarando({ candidato: f })}>Declarar Empleado del Mes de la empresa</Boton>
                              </div>
                            )}
                          </td></tr>
                        )}
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
          <p className="text-sm text-gris">El bono sugerido sale de los tramos en Reglas del puntaje. Es una guía: la decisión la toma la dirección.</p>
        </div>
      )}

      <Declarar abierto={!!declarando} candidato={declarando?.candidato} departamento={declarando?.departamento} mes={mes}
        onCerrar={() => setDeclarando(null)} onListo={(n) => { setDeclarando(null); avisar(`${n} es el Empleado del Mes. Ya aparece en el Muro de Honor.`); cargar(); }} />
    </div>
  );
}
