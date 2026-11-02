// Ficha integral del mes: puntaje (4 partes), KPIs con su ficha técnica, horario, computadora (informativa), tareas,
// evaluación 360°, planes de mejora, expediente y tendencia de 6 o 12 meses.
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, Bot, Eye, Info } from "lucide-react";
import { fichaProductividad } from "@/lib/api";
import { mesActual, nombreMes, reloj } from "@/lib/formato";
import { Alerta, Barra, Cabecera, Cargando, Insignia, Panel, Pestanas, Puntaje, SelectorMes, cx } from "@/components/ui";
import { useSesion } from "@/lib/sesion";
import { ResumenAsistencia } from "@/features/asistencia/Asistencia";

const pct = (v) => (v == null ? "—" : `${Number(v).toLocaleString("es-DO", { maximumFractionDigits: 1 })} %`);
const FUENTE = {
  ENTREGAS_A_TIEMPO: "Tareas a tiempo", PRIMERA: "Tareas a la primera", RONDAS: "Rondas de las tareas", CALIDAD: "Calidad de las tareas",
  PUNTUALIDAD: "Control de horario", ASISTENCIA: "Control de horario", HORAS: "Control de horario", ADHERENCIA: "Control de horario",
  ACTIVIDAD_PC: "Computadora", PRODUCTIVIDAD_PC: "Computadora", TAREAS_COMPLETADAS: "Tareas validadas", RETRABAJO: "Correcciones",
  HORAS_POR_TAREA: "Cronómetro", DENTRO_ESTIMADO: "Cronómetro", UTILIZACION: "Cronómetro", HORAS_EXTRA: "Control de horario", "": "Tareas vinculadas",
};
const num = (v) => (v == null ? "—" : Number(v).toLocaleString("es-DO", { maximumFractionDigits: 2 }));
const TIPO_EVAL = { AUTO: "Autoevaluación", SUPERVISOR: "Supervisor", PAR: "Compañeros" };
const TONO_EVENTO = { RECONOCIMIENTO: "verde", CAPACITACION: "azul", BONO: "verde", OBSERVACION: "amarillo", INCIDENCIA: "amarillo",
  AMONESTACION_VERBAL: "rojo", AMONESTACION_ESCRITA: "rojo", OTRO: "neutro" };
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
  const { veSalarios } = useSesion();
  const [meses, setMeses] = useState("6");
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [verSeguimiento, setVerSeguimiento] = useState(false);
  useEffect(() => { setD(null); setError(""); fichaProductividad({ usuario, mes, meses }).then(setD).catch((e) => setError(e.message)); }, [usuario, mes, meses]);
  if (error) return <Alerta>{error}</Alerta>;
  if (!d) return <Cargando />;
  const p = d.puntaje;
  const pc = d.computadora;
  const ev = p ? EVALUACION[p.evaluacion] : null;
  const seguimiento = d.kpis.filter((k) => k.seguimiento);
  const kpis = verSeguimiento ? d.kpis : d.kpis.filter((k) => !k.seguimiento);
  const t = d.talento || {};
  return (
    <div className="space-y-5">
      {usuario && <button type="button" onClick={() => navigate(-1)} className="inline-flex items-center gap-1.5 text-sm font-medium text-azul hover:underline"><ArrowLeft className="size-4" />Volver</button>}
      <Cabecera titulo={`Ficha de ${d.persona.nombre}`} descripcion={`${d.persona.puesto || "Sin puesto"}${d.persona.departamento ? ` · ${d.persona.departamento}` : ""} · todo lo que la plataforma midió en ${nombreMes(mes)}.`}>
        <SelectorMes valor={mes} onCambio={(m) => setParams(usuario ? { usuario, mes: m } : { mes: m })} />
      </Cabecera>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <div className="rounded-xl border border-linea bg-noche p-4 text-white">
          <p className="text-sm text-white/70">Puntaje del mes{p?.posicion ? ` · puesto #${p.posicion}` : ""}</p>
          <p className="mt-1 font-display text-4xl font-semibold num">{p ? Number(p.puntaje_total).toLocaleString("es-DO", { maximumFractionDigits: 1 }) : "—"}</p>
          {ev && <Insignia tono={ev[1]} className="mt-2">{ev[0]}</Insignia>}
          {p?.bono_sugerido ? <p className="mt-2 text-sm text-white/80">Bono sugerido: {p.bono_sugerido} % del salario</p> : null}
        </div>
        <Componente titulo="Cumplimiento de tareas" valor={p?.puntaje_tareas} peso={d.pesos.tareas} />
        <Componente titulo="KPIs del puesto" valor={p?.puntaje_kpis} peso={d.pesos.kpis} />
        {d.pesos.calidad > 0 && <Componente titulo="Calidad y satisfacción" valor={p?.puntaje_calidad} peso={d.pesos.calidad} />}
        <Componente titulo="Asistencia y puntualidad" valor={p?.puntaje_jornada} peso={d.pesos.jornada} />
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

      <Panel titulo="KPIs del puesto" cuerpo="p-0" accion={seguimiento.length > 0 && (
        <button type="button" onClick={() => setVerSeguimiento(!verSeguimiento)} className="inline-flex items-center gap-1.5 text-sm font-medium text-azul hover:underline">
          <Eye className="size-4" />{verSeguimiento ? "Ocultar" : "Ver"} {seguimiento.length} de seguimiento</button>)}>
        {kpis.length === 0 ? <p className="p-5 text-sm text-gris">Sin KPIs medidos este mes. Los manuales se anotan en «KPIs del mes»; los automáticos salen solos cuando hay datos.</p> : (
          <div className="overflow-x-auto">
            <table className="tabla">
              <thead><tr><th>KPI</th><th>Origen</th><th className="text-right">Meta</th><th className="text-right">Logrado</th><th className="w-44">Cumplimiento</th><th className="text-right">Peso</th></tr></thead>
              <tbody>
                {kpis.map((k) => (
                  <tr key={k.kpi_asignado_id} className={k.seguimiento ? "bg-fondo/60" : ""}>
                    <td>
                      <span className="font-medium">{k.nombre}</span>
                      {(k.formula || k.responsable) && (
                        <span className="mt-0.5 flex items-start gap-1 text-xs text-gris" title={[k.formula && `Fórmula: ${k.formula}`, k.fuente_datos && `Fuente: ${k.fuente_datos}`, k.responsable && `Valida: ${k.responsable}`].filter(Boolean).join("\n")}>
                          <Info className="mt-0.5 size-3 shrink-0" /><span className="line-clamp-2">{k.formula || k.fuente_datos}{k.responsable ? ` · valida ${k.responsable}` : ""}</span>
                        </span>
                      )}
                    </td>
                    <td>{k.automatico ? <Insignia tono="azul"><Bot className="mr-1 inline size-3" />{FUENTE[k.fuente] || "Automático"}</Insignia> : <Insignia>Anotado</Insignia>}</td>
                    <td className="text-right num">{k.meta == null ? "—" : Number(k.meta).toLocaleString("es-DO")} <span className="text-xs text-gris">{k.unidad_medida}</span></td>
                    <td className="text-right num">{k.valor == null ? "—" : Number(k.valor).toLocaleString("es-DO")}</td>
                    <td>{k.oculto ? <span className="text-sm text-gris" title="Sale de la actividad en la computadora: solo la ven Dirección y Tecnología">Reservado</span> : k.cumplimiento == null ? <span className="text-sm text-gris">Sin medir</span> : (
                      <div className="flex items-center gap-2"><Barra valor={k.cumplimiento} /><span className="w-12 text-right text-sm num">{Math.round(k.cumplimiento)} %</span>
                        {k.bajo_umbral && <Insignia tono="rojo" className="ml-1">Bajo {num(k.umbral)} %</Insignia>}</div>)}</td>
                    <td className="text-right num">{k.seguimiento ? <Insignia>Seguimiento</Insignia> : `${k.ponderacion} %`}</td>
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
        <Panel titulo="Computadora · informativo, no da puntos">
          {!pc ? <p className="text-sm text-gris">La actividad en la computadora de otra persona solo la ven Dirección y Tecnología.</p> : pc.minutos_registrados ? <>
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
          {pc?.apps?.length ? <ul className="divide-y divide-linea-suave">{pc.apps.slice(0, 8).map((a) => (
            <li key={a.nombre} className="flex items-center gap-3 px-5 py-2"><span className="min-w-0 flex-1 truncate">{a.nombre}</span>
              <span className={cx("size-2 rounded-full", a.categoria === "P" ? "bg-verde" : a.categoria === "I" ? "bg-rojo" : "bg-[#9aa7bd]")} /><span className="w-14 text-right text-sm num">{reloj(a.minutos)}</span></li>
          ))}</ul> : <p className="p-5 text-sm text-gris">Sin datos.</p>}
        </Panel>
      </div>

      <Talento t={t} usuario={d.persona.id} esAdmin={veSalarios} />

      <Panel titulo={`Tendencia de ${meses} meses`} cuerpo="p-0" accion={<Pestanas className="!flex" opciones={[{ valor: "6", etiqueta: "6 meses" }, { valor: "12", etiqueta: "12 meses" }]} valor={meses} onCambio={setMeses} />}>
        <div className="overflow-x-auto">
          <table className="tabla">
            <thead><tr><th>Mes</th><th className="text-right">Puntaje</th><th className="text-right">Adherencia al horario</th><th className="text-right">Productividad en PC</th><th className="text-right">Tareas a tiempo</th><th className="text-right">Calidad</th></tr></thead>
            <tbody>
              {d.tendencia.map((x) => (
                <tr key={x.mes}><td className="first-letter:uppercase">{nombreMes(x.mes)}</td>
                  <td className="text-right"><Puntaje valor={x.puntaje} /></td>
                  <td className="text-right"><Puntaje valor={x.adherencia} /></td><td className="text-right"><Puntaje valor={x.productividad} /></td>
                  <td className="text-right"><Puntaje valor={x.a_tiempo} /></td><td className="text-right"><Puntaje valor={x.calidad} /></td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

function Talento({ t, usuario, esAdmin }) {
  const ev = t.evaluacion;
  const tipos = ev ? Object.entries(ev.por_tipo || {}) : [];
  const comp = ev?.competencias || [];
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel titulo={ev ? `Evaluación 360° · ${ev.ciclo.nombre}` : "Evaluación 360°"} cuerpo="p-0">
        {!ev || tipos.length === 0 ? <p className="p-5 text-sm text-gris">{ev?.pendientes ? `${ev.pendientes} evaluación(es) en curso o en revisión.` : "Sin evaluaciones cerradas todavía."}</p> : (
          <div className="overflow-x-auto">
            <table className="tabla">
              <thead><tr><th>Competencia</th>{tipos.map(([k]) => <th key={k} className="text-right">{TIPO_EVAL[k]}</th>)}</tr></thead>
              <tbody>
                {comp.map((c) => (
                  <tr key={c.clave}><td>{c.nombre}</td>{tipos.map(([k, v]) => {
                    const n = v.competencias[c.clave];
                    return <td key={k} className={cx("text-right num", n != null && n < 3 && "font-semibold text-rojo")}>{num(n)}</td>;
                  })}</tr>
                ))}
                <tr className="font-semibold"><td>Promedio (de 5)</td>{tipos.map(([k, v]) => <td key={k} className="text-right num">{num(v.promedio)}</td>)}</tr>
              </tbody>
            </table>
            {tipos.flatMap(([k, v]) => v.comentarios.filter((c) => c.fortalezas || c.a_mejorar || c.comentario).map((c, i) => (
              <div key={`${k}${i}`} className="border-t border-linea-suave px-5 py-3 text-sm">
                <p className="text-xs font-medium text-gris">{TIPO_EVAL[k]}{c.de ? ` · ${c.de}` : ""}</p>
                {c.fortalezas && <p><strong>Fortalezas:</strong> {c.fortalezas}</p>}
                {c.a_mejorar && <p><strong>A mejorar:</strong> {c.a_mejorar}</p>}
                {c.comentario && <p className="text-gris">{c.comentario}</p>}
              </div>
            )))}
          </div>
        )}
      </Panel>
      <div className="space-y-4">
        <Panel titulo="Planes de mejora" accion={<Link to={`/talento?ver=planes&usuario=${usuario}`} className="text-sm font-medium text-azul hover:underline">Abrir</Link>}>
          {!t.planes?.length ? <p className="text-sm text-gris">Sin planes de mejora.</p> : (
            <ul className="space-y-2">{t.planes.map((p) => (
              <li key={p.id} className="flex items-start justify-between gap-3 text-[15px]">
                <span><span className="font-medium">{p.motivo}</span><span className="block text-xs text-gris">Revisión {p.revision} · {p.cumplidos} de {p.objetivos.length} objetivos cumplidos</span></span>
                <Insignia tono={p.estado_codigo === "ABIERTO" ? "amarillo" : p.estado_codigo === "CUMPLIDO" ? "verde" : "neutro"}>{p.estado}</Insignia>
              </li>))}</ul>
          )}
        </Panel>
        <Panel titulo="Expediente" accion={<Link to={`/talento?ver=expediente&usuario=${usuario}`} className="text-sm font-medium text-azul hover:underline">Abrir</Link>}>
          {!t.expediente?.length ? <p className="text-sm text-gris">Sin registros.</p> : (
            <ul className="max-h-72 space-y-2 overflow-y-auto">{t.expediente.slice(0, 10).map((e) => (
              <li key={e.id} className="text-[15px]">
                <div className="flex items-center gap-2"><Insignia tono={TONO_EVENTO[e.tipo]}>{e.tipo_nombre}</Insignia><span className="text-xs text-gris">{e.fecha}</span>
                  {!e.visible && <Insignia>Interno</Insignia>}{e.monto != null && <span className="text-xs num">RD$ {num(e.monto)}</span>}</div>
                <p className="mt-0.5 font-medium">{e.titulo}</p>
                {e.justificacion && <p className="text-sm text-gris">Descargo: {e.justificacion}</p>}
              </li>))}</ul>
          )}
          {t.horas_capacitacion > 0 && <p className="mt-3 text-sm text-gris">{num(t.horas_capacitacion)} h de capacitación registradas.</p>}
        </Panel>
        {t.equipos?.length > 0 && (
          <Panel titulo="Equipos asignados">
            <ul className="space-y-1 text-[15px]">{t.equipos.map((e) => <li key={e.id}><span className="font-medium">{e.codigo}</span> · {e.nombre} <span className="text-xs text-gris">{e.categoria}{e.serie ? ` · ${e.serie}` : ""}</span></li>)}</ul>
          </Panel>
        )}
        {esAdmin && t.salarios?.length > 0 && (
          <Panel titulo="Historial salarial">
            <ul className="space-y-1 text-[15px]">{t.salarios.map((c, i) => (
              <li key={i} className="flex justify-between gap-3"><span>{c.fecha}{c.motivo ? ` · ${c.motivo}` : ""}</span><span className="num">RD$ {num(c.anterior)} → <strong>{num(c.nuevo)}</strong></span></li>))}</ul>
          </Panel>
        )}
      </div>
    </div>
  );
}
