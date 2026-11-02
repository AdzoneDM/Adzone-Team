// Talento: evaluaciones 360° (evaluar, resultados, revisión de la dirección, ciclos), planes de mejora, expediente y auditoría.
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CheckCircle2, ClipboardCheck, Plus, RotateCcw, Save, Trash2 } from "lucide-react";
import {
  auditoria, avanceEvaluacion, borrarEvento, ciclosEvaluacion, confirmarEvaluacion, crearCiclo, editarCiclo, enviarEvaluacion,
  equipo, evaluacionesPorRevisar, expediente, guardarEvento, guardarPlan, misEvaluaciones, planesMejora, resultadosEvaluacion,
} from "@/lib/api";
import { useSesion } from "@/lib/sesion";
import { Alerta, Boton, Cabecera, Campo, Cargando, Insignia, Modal, Panel, Pestanas, Vacio, cx, useAviso, useConfirmar } from "@/components/ui";
import { SelectorPersona } from "@/components/Selectores";

const TIPO_EVAL = { AUTO: "Autoevaluación", SUPERVISOR: "Como supervisor", PAR: "Como compañero" };
const TIPOS_EVENTO = [["RECONOCIMIENTO", "Reconocimiento"], ["OBSERVACION", "Observación"], ["AMONESTACION_VERBAL", "Amonestación verbal"],
  ["AMONESTACION_ESCRITA", "Amonestación escrita"], ["INCIDENCIA", "Incidencia"], ["CAPACITACION", "Capacitación"], ["BONO", "Bono"], ["OTRO", "Otro"]];
const TONO_EVENTO = { RECONOCIMIENTO: "verde", CAPACITACION: "azul", BONO: "verde", OBSERVACION: "amarillo", INCIDENCIA: "amarillo",
  AMONESTACION_VERBAL: "rojo", AMONESTACION_ESCRITA: "rojo", OTRO: "neutro" };
const local = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const hoy = () => local(new Date());
const enDias = (n) => { const d = new Date(); d.setDate(d.getDate() + n); return local(d); };
const num = (v) => (v == null ? "—" : Number(v).toLocaleString("es-DO", { maximumFractionDigits: 2 }));

export default function Talento() {
  const { esAdmin, puedeValidar, gestiona } = useSesion();
  const [params, setParams] = useSearchParams();
  const supervisa = esAdmin || puedeValidar || gestiona;
  const opciones = [
    { valor: "evaluar", etiqueta: "Evaluar" },
    { valor: "resultados", etiqueta: "Mis resultados" },
    { valor: "planes", etiqueta: "Planes de mejora" },
    { valor: "expediente", etiqueta: "Expediente" },
    ...(supervisa ? [{ valor: "avance", etiqueta: "Avance" }] : []),
    ...(esAdmin ? [{ valor: "revisar", etiqueta: "Por validar" }, { valor: "ciclos", etiqueta: "Ciclos" }, { valor: "auditoria", etiqueta: "Auditoría" }] : []),
  ];
  const ver = opciones.some((o) => o.valor === params.get("ver")) ? params.get("ver") : "evaluar";
  const usuario = params.get("usuario") || "";
  return (
    <div className="space-y-5">
      <Cabecera titulo="Talento" descripcion="Evaluaciones 360° (tú, tu supervisor y compañeros), planes de mejora y el expediente de cada persona." />
      <Pestanas opciones={opciones} valor={ver} onCambio={(v) => setParams({ ver: v })} />
      {ver === "evaluar" && <Evaluar />}
      {ver === "resultados" && <Resultados />}
      {ver === "planes" && <Planes usuarioInicial={usuario} supervisa={supervisa} />}
      {ver === "expediente" && <Expediente usuarioInicial={usuario} supervisa={supervisa} esAdmin={esAdmin} />}
      {ver === "avance" && <Avance />}
      {ver === "revisar" && <Revisar />}
      {ver === "ciclos" && <Ciclos />}
      {ver === "auditoria" && <Auditoria />}
    </div>
  );
}

// ---------------------------------------------------------------- Evaluar
function Evaluar() {
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [abierta, setAbierta] = useState(null);
  const cargar = () => misEvaluaciones().then(setD).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);
  if (error) return <Alerta>{error}</Alerta>;
  if (!d) return <Cargando />;
  const pendientes = d.evaluaciones.filter((e) => e.estado === "PENDIENTE");
  const hechas = d.evaluaciones.filter((e) => e.estado !== "PENDIENTE");
  if (!d.evaluaciones.length) return <Vacio icono={ClipboardCheck} titulo="No tienes evaluaciones abiertas">Cuando la dirección abra un ciclo, aquí verás a quién te toca evaluar.</Vacio>;
  return (
    <div className="space-y-4">
      <Panel titulo={`Por hacer (${pendientes.length})`} cuerpo="p-0">
        {pendientes.length === 0 ? <p className="p-5 text-sm text-gris">¡Listo! Enviaste todas.</p> : (
          <ul className="divide-y divide-linea-suave">{pendientes.map((e) => (
            <li key={e.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
              <span className="min-w-0 flex-1"><span className="font-medium">{e.tipo === "AUTO" ? "Tú mismo" : e.evaluado_nombre}</span>
                <span className="block text-xs text-gris">{TIPO_EVAL[e.tipo]} · {e.puesto || "Sin puesto"} · {e.ciclo_nombre}</span>
                {e.nota_revision && <span className="block text-xs text-[#a86a00]">La dirección pidió revisarla: {e.nota_revision}</span>}</span>
              <Boton tam="sm" onClick={() => setAbierta(e)}>Evaluar</Boton>
            </li>))}</ul>
        )}
      </Panel>
      {hechas.length > 0 && (
        <Panel titulo="Enviadas" cuerpo="p-0">
          <ul className="divide-y divide-linea-suave">{hechas.map((e) => (
            <li key={e.id} className="flex items-center gap-3 px-5 py-2.5 text-[15px]">
              <span className="flex-1">{e.tipo === "AUTO" ? "Autoevaluación" : e.evaluado_nombre} <span className="text-xs text-gris">· {TIPO_EVAL[e.tipo]}</span></span>
              <span className="num text-sm">{num(e.promedio)} / 5</span>
              {e.estado === "EN_REVISION" ? <Insignia tono="amarillo">La valida la dirección</Insignia> : <Insignia tono="verde">Enviada</Insignia>}
            </li>))}</ul>
        </Panel>
      )}
      {abierta && <FormEvaluacion e={abierta} competencias={d.competencias} escala={d.escala} onCerrar={() => setAbierta(null)} onListo={() => { setAbierta(null); cargar(); }} />}
    </div>
  );
}

function FormEvaluacion({ e, competencias, escala, onCerrar, onListo }) {
  const avisar = useAviso();
  const [p, setP] = useState(e.puntajes || {});
  const [txt, setTxt] = useState({ fortalezas: e.fortalezas || "", a_mejorar: e.a_mejorar || "", comentario: e.comentario || "" });
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const valores = competencias.map((c) => p[c.clave]).filter(Boolean);
  const promedio = valores.length ? valores.reduce((a, b) => a + b, 0) / valores.length : null;
  const etiquetas = Array.isArray(escala) ? Object.fromEntries(escala.map((x) => (Array.isArray(x) ? x : [x.valor, x.nombre]))) : escala || {};
  const enviar = async () => {
    setError(""); setEnviando(true);
    try {
      const r = await enviarEvaluacion(e.id, { puntajes: p, ...txt });
      avisar(r.estado === "EN_REVISION" ? "Enviada. Como está por debajo de «Cumple», la valida la dirección antes de que la vea la persona." : "Evaluación enviada.");
      onListo();
    } catch (err) { setError(err.message); }
    setEnviando(false);
  };
  return (
    <Modal abierto onCerrar={onCerrar} ancho="max-w-2xl" titulo={e.tipo === "AUTO" ? "Tu autoevaluación" : `Evaluar a ${e.evaluado_nombre}`}
      descripcion={`${TIPO_EVAL[e.tipo]} · 1 = muy por debajo, 3 = cumple, 5 = excelente.${e.tipo === "PAR" ? " Tus respuestas son anónimas." : ""}`}
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton icono={Save} cargando={enviando} onClick={enviar} disabled={valores.length < competencias.length}>Enviar</Boton></>}>
      {error && <Alerta className="mb-3">{error}</Alerta>}
      <div className="space-y-3">
        {competencias.map((c) => (
          <fieldset key={c.clave} className="flex flex-wrap items-center justify-between gap-2 border-b border-linea-suave pb-3">
            <legend className="sr-only">{c.nombre}</legend>
            <span className="text-[15px] font-medium">{c.nombre}</span>
            <div className="flex gap-1">{[1, 2, 3, 4, 5].map((n) => (
              <button key={n} type="button" aria-pressed={p[c.clave] === n} title={etiquetas[n] || ""} onClick={() => setP({ ...p, [c.clave]: n })}
                className={cx("size-10 rounded-lg border text-sm font-semibold num", p[c.clave] === n ? (n < 3 ? "border-rojo bg-rojo text-white" : "border-azul bg-azul text-white") : "border-linea bg-white hover:border-azul")}>{n}</button>
            ))}</div>
          </fieldset>
        ))}
      </div>
      {promedio != null && <p className="mt-3 text-sm text-gris">Promedio: <strong className="num">{promedio.toFixed(1)}</strong> de 5</p>}
      <div className="mt-4 grid gap-3">
        <Campo etiqueta="Fortalezas">{(id) => <textarea id={id} rows={2} className="campo" value={txt.fortalezas} onChange={(ev) => setTxt({ ...txt, fortalezas: ev.target.value })} />}</Campo>
        <Campo etiqueta="Qué mejorar" ayuda={e.tipo === "SUPERVISOR" && promedio != null && promedio < 3 ? "Obligatorio: la evaluación está por debajo de «Cumple»." : null}>
          {(id) => <textarea id={id} rows={2} className="campo" value={txt.a_mejorar} onChange={(ev) => setTxt({ ...txt, a_mejorar: ev.target.value })} />}</Campo>
        <Campo etiqueta="Comentario">{(id) => <textarea id={id} rows={2} className="campo" value={txt.comentario} onChange={(ev) => setTxt({ ...txt, comentario: ev.target.value })} />}</Campo>
      </div>
    </Modal>
  );
}

// ---------------------------------------------------------------- Resultados
export function TablaResultados({ ciclo }) {
  const tipos = Object.entries(ciclo.por_tipo || {});
  const NOMBRE = { AUTO: "Yo", SUPERVISOR: "Supervisor", PAR: "Compañeros" };
  if (!tipos.length) return <p className="p-5 text-sm text-gris">{ciclo.pendientes ? `${ciclo.pendientes} evaluación(es) en curso o en revisión.` : "Sin evaluaciones cerradas."}</p>;
  return (
    <div className="overflow-x-auto">
      <table className="tabla">
        <thead><tr><th>Competencia</th>{tipos.map(([k, v]) => <th key={k} className="text-right">{NOMBRE[k]}{v.cantidad > 1 ? ` (${v.cantidad})` : ""}</th>)}</tr></thead>
        <tbody>
          {ciclo.competencias.map((c) => (
            <tr key={c.clave}><td>{c.nombre}</td>{tipos.map(([k, v]) => {
              const n = v.competencias[c.clave];
              return <td key={k} className={cx("text-right num", n != null && n < 3 && "font-semibold text-rojo")}>{num(n)}</td>;
            })}</tr>
          ))}
          <tr className="font-semibold"><td>Promedio</td>{tipos.map(([k, v]) => <td key={k} className="text-right num">{num(v.promedio)}</td>)}</tr>
        </tbody>
      </table>
      {tipos.flatMap(([k, v]) => v.comentarios.filter((c) => c.fortalezas || c.a_mejorar || c.comentario).map((c, i) => (
        <div key={`${k}${i}`} className="border-t border-linea-suave px-5 py-3 text-sm">
          <p className="text-xs font-medium text-gris">{NOMBRE[k]}{c.de ? ` · ${c.de}` : ""}</p>
          {c.fortalezas && <p><strong>Fortalezas:</strong> {c.fortalezas}</p>}
          {c.a_mejorar && <p><strong>A mejorar:</strong> {c.a_mejorar}</p>}
          {c.comentario && <p className="text-gris">{c.comentario}</p>}
        </div>
      )))}
    </div>
  );
}

function Resultados() {
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { resultadosEvaluacion().then(setD).catch((e) => setError(e.message)); }, []);
  if (error) return <Alerta>{error}</Alerta>;
  if (!d) return <Cargando />;
  if (!d.ciclos.length) return <Vacio icono={ClipboardCheck} titulo="Aún no tienes evaluaciones">Aparecen aquí cuando se cierran.</Vacio>;
  return d.ciclos.map((c) => <Panel key={c.ciclo.id} titulo={c.ciclo.nombre} cuerpo="p-0" className="mb-4"><TablaResultados ciclo={c} /></Panel>);
}

// ---------------------------------------------------------------- Avance del ciclo (supervisores y dirección)
function Avance() {
  const [ciclos, setCiclos] = useState(null);
  const [ciclo, setCiclo] = useState("");
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [ver, setVer] = useState(null);
  useEffect(() => { ciclosEvaluacion().then((c) => { setCiclos(c); if (c[0]) setCiclo(String(c[0].id)); }).catch((e) => setError(e.message)); }, []);
  useEffect(() => { if (ciclo) { setD(null); avanceEvaluacion(ciclo).then(setD).catch((e) => setError(e.message)); } }, [ciclo]);
  if (error) return <Alerta>{error}</Alerta>;
  if (!ciclos) return <Cargando />;
  if (!ciclos.length) return <Vacio icono={ClipboardCheck} titulo="No hay ciclos de evaluación">La dirección los abre en «Ciclos».</Vacio>;
  return (
    <Panel titulo="Avance de tu equipo" cuerpo="p-0" accion={
      <select className="campo !h-9 !w-auto" value={ciclo} onChange={(e) => setCiclo(e.target.value)} aria-label="Ciclo">
        {ciclos.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}</select>}>
      {!d ? <Cargando /> : (
        <div className="overflow-x-auto"><table className="tabla">
          <thead><tr><th>Persona</th><th className="text-right">Evaluaciones</th><th className="text-right">Supervisor (de 5)</th><th /></tr></thead>
          <tbody>{d.personas.map((p) => (
            <tr key={p.id}><td className="font-medium">{p.nombre}</td>
              <td className="text-right num">{p.hechas}/{p.total}{p.en_revision ? <Insignia tono="amarillo" className="ml-2">{p.en_revision} por validar</Insignia> : null}</td>
              <td className="text-right num">{num(p.supervisor)}</td>
              <td className="text-right"><button type="button" className="text-sm font-medium text-azul hover:underline" onClick={() => setVer(p)}>Resultados</button></td></tr>))}</tbody>
        </table></div>
      )}
      {ver && <ResultadosDe persona={ver} ciclo={ciclo} onCerrar={() => setVer(null)} />}
    </Panel>
  );
}

function ResultadosDe({ persona, ciclo, onCerrar }) {
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { resultadosEvaluacion(persona.id, ciclo).then(setD).catch((e) => setError(e.message)); }, [persona.id, ciclo]);
  const c = d?.ciclos.find((x) => String(x.ciclo.id) === String(ciclo));
  return (
    <Modal abierto onCerrar={onCerrar} ancho="max-w-2xl" titulo={`Resultados de ${persona.nombre}`}>
      {error ? <Alerta>{error}</Alerta> : !d ? <Cargando /> : c ? <TablaResultados ciclo={c} /> : <p className="text-sm text-gris">Sin resultados en este ciclo.</p>}
    </Modal>
  );
}

// ---------------------------------------------------------------- Validación de la dirección
function Revisar() {
  const avisar = useAviso();
  const [lista, setLista] = useState(null);
  const [error, setError] = useState("");
  const [notas, setNotas] = useState({});
  const cargar = () => evaluacionesPorRevisar().then(setLista).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);
  const decidir = async (e, devolver) => {
    try { await confirmarEvaluacion(e.id, { devolver, nota: notas[e.id] || "" }); avisar(devolver ? "Devuelta al evaluador." : "Confirmada: ya la puede ver la persona."); cargar(); }
    catch (err) { setError(err.message); }
  };
  if (!lista) return error ? <Alerta>{error}</Alerta> : <Cargando />;
  if (!lista.length) return <Vacio icono={CheckCircle2} titulo="Nada por validar">Las evaluaciones del supervisor por debajo de «Cumple» llegan aquí antes de que las vea la persona.</Vacio>;
  return (
    <div className="space-y-3">
      {error && <Alerta>{error}</Alerta>}
      {lista.map((e) => (
        <Panel key={e.id} titulo={`${e.evaluado_nombre} · ${num(e.promedio)} de 5`}>
          <p className="text-sm text-gris">{e.puesto || "Sin puesto"} · evaluó {e.evaluador_nombre} · {e.ciclo_nombre}</p>
          {e.a_mejorar && <p className="mt-2 text-[15px]"><strong>A mejorar:</strong> {e.a_mejorar}</p>}
          {e.fortalezas && <p className="text-[15px]"><strong>Fortalezas:</strong> {e.fortalezas}</p>}
          {e.comentario && <p className="text-[15px] text-gris">{e.comentario}</p>}
          <div className="mt-3 flex flex-wrap items-end gap-2">
            <Campo etiqueta="Nota (opcional)" className="min-w-60 flex-1">{(id) => <input id={id} className="campo" value={notas[e.id] || ""} onChange={(ev) => setNotas({ ...notas, [e.id]: ev.target.value })} />}</Campo>
            <Boton variante="secundario" icono={RotateCcw} onClick={() => decidir(e, true)}>Devolver al evaluador</Boton>
            <Boton icono={CheckCircle2} onClick={() => decidir(e, false)}>Confirmar</Boton>
          </div>
        </Panel>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- Ciclos
function Ciclos() {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const [lista, setLista] = useState(null);
  const [nuevo, setNuevo] = useState(null);
  const [error, setError] = useState("");
  const cargar = () => ciclosEvaluacion().then(setLista).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);
  const crear = async () => {
    setError("");
    try { await crearCiclo(nuevo); setNuevo(null); avisar("Ciclo abierto: a cada persona le llegó su lista de evaluaciones."); cargar(); }
    catch (e) { setError(e.message); }
  };
  const cerrar = async (c) => {
    if (!(await confirmar({ titulo: `¿Cerrar «${c.nombre}»?`, mensaje: "Ya no se podrán enviar evaluaciones de este ciclo.", boton: "Cerrar ciclo" }))) return;
    await editarCiclo(c.id, { abierto: false }); cargar();
  };
  if (!lista) return error ? <Alerta>{error}</Alerta> : <Cargando />;
  return (
    <Panel titulo="Ciclos de evaluación" cuerpo="p-0" accion={<Boton tam="sm" icono={Plus} onClick={() => setNuevo({ nombre: "", tipo: "TRIMESTRAL", desde: enDias(-90), hasta: hoy(), cierre: enDias(14), con_pares: true })}>Abrir ciclo</Boton>}>
      {error && <Alerta className="m-4">{error}</Alerta>}
      {!lista.length ? <p className="p-5 text-sm text-gris">Abre el primero: se crea la autoevaluación de cada persona, la de su supervisor y dos compañeros de su departamento.</p> : (
        <ul className="divide-y divide-linea-suave">{lista.map((c) => (
          <li key={c.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
            <span className="min-w-0 flex-1"><span className="font-medium">{c.nombre}</span><span className="block text-xs text-gris">{c.desde} a {c.hasta} · cierra {c.cierre}{c.con_pares ? " · con compañeros" : ""}</span></span>
            <span className="text-sm num">{c.avance.hechas}/{c.avance.total}</span>
            {c.abierto ? <Boton tam="sm" variante="secundario" onClick={() => cerrar(c)}>Cerrar</Boton> : <Insignia>Cerrado</Insignia>}
          </li>))}</ul>
      )}
      {nuevo && (
        <Modal abierto onCerrar={() => setNuevo(null)} titulo="Abrir ciclo de evaluación" pie={<><Boton variante="secundario" onClick={() => setNuevo(null)}>Cancelar</Boton><Boton onClick={crear}>Abrir</Boton></>}>
          {error && <Alerta className="mb-3">{error}</Alerta>}
          <div className="grid gap-3 sm:grid-cols-2">
            <Campo etiqueta="Nombre" className="sm:col-span-2">{(id) => <input id={id} className="campo" placeholder="4.º trimestre 2026" value={nuevo.nombre} onChange={(e) => setNuevo({ ...nuevo, nombre: e.target.value })} />}</Campo>
            <Campo etiqueta="Tipo">{(id) => <select id={id} className="campo" value={nuevo.tipo} onChange={(e) => setNuevo({ ...nuevo, tipo: e.target.value })}><option value="MENSUAL">Mensual</option><option value="TRIMESTRAL">Trimestral</option><option value="ANUAL">Anual</option></select>}</Campo>
            <Campo etiqueta="Fecha límite">{(id) => <input id={id} type="date" className="campo" value={nuevo.cierre} onChange={(e) => setNuevo({ ...nuevo, cierre: e.target.value })} />}</Campo>
            <Campo etiqueta="Período evaluado desde">{(id) => <input id={id} type="date" className="campo" value={nuevo.desde} onChange={(e) => setNuevo({ ...nuevo, desde: e.target.value })} />}</Campo>
            <Campo etiqueta="Hasta">{(id) => <input id={id} type="date" className="campo" value={nuevo.hasta} onChange={(e) => setNuevo({ ...nuevo, hasta: e.target.value })} />}</Campo>
            <label className="flex min-h-11 items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" className="accent-azul" checked={nuevo.con_pares} onChange={(e) => setNuevo({ ...nuevo, con_pares: e.target.checked })} />Incluir evaluación de compañeros (360°, anónima)</label>
          </div>
        </Modal>
      )}
    </Panel>
  );
}

// ---------------------------------------------------------------- Selección de persona para planes y expediente
function usePersona(usuarioInicial, supervisa) {
  const { usuario: yo, esAdmin } = useSesion();
  const [persona, setPersona] = useState(usuarioInicial || "");
  const [ids, setIds] = useState(null);
  useEffect(() => { if (supervisa && !esAdmin) equipo().then((l) => setIds(new Set((l || []).map((x) => String(x.id))))).catch(() => setIds(new Set())); }, [supervisa, esAdmin]);
  const filtro = useMemo(() => (esAdmin ? null : (g) => String(g.id) === String(yo?.id) || ids?.has(String(g.id))), [esAdmin, ids, yo]);
  return { persona, setPersona, filtro, propio: !persona || String(persona) === String(yo?.id) };
}

// ---------------------------------------------------------------- Planes de mejora
function Planes({ usuarioInicial, supervisa }) {
  const avisar = useAviso();
  const { usuario: yo } = useSesion();
  const { persona, setPersona, filtro, propio } = usePersona(usuarioInicial, supervisa);
  const [lista, setLista] = useState(null);
  const [error, setError] = useState("");
  const [editando, setEditando] = useState(null);
  const cargar = () => planesMejora(persona).then(setLista).catch((e) => setError(e.message));
  useEffect(() => { setLista(null); setError(""); cargar(); }, [persona]); // eslint-disable-line react-hooks/exhaustive-deps
  const guardar = async (p) => {
    setError("");
    try { await guardarPlan(p); setEditando(null); avisar("Plan guardado."); cargar(); } catch (e) { setError(e.message); }
  };
  const marcar = (p, i) => guardar({ id: p.id, objetivos: p.objetivos.map((o, j) => (j === i ? { ...o, cumplido: !o.cumplido } : o)) });
  return (
    <div className="space-y-4">
      {supervisa && (
        <div className="flex flex-wrap items-end gap-3">
          <SelectorPersona etiqueta="Persona" valor={persona} onCambio={setPersona} filtro={filtro} vacio="Yo y mi equipo" />
          {persona && !propio && <Boton icono={Plus} onClick={() => setEditando({ colaborador: Number(persona), motivo: "", objetivos: [{ texto: "", meta: "", fecha: enDias(30) }], capacitacion: "", inicio: hoy(), revision: enDias(30) })}>Nuevo plan</Boton>}
        </div>
      )}
      {error && <Alerta>{error}</Alerta>}
      {!lista ? <Cargando /> : !lista.length ? <Vacio icono={ClipboardCheck} titulo="Sin planes de mejora">{supervisa ? "Elige a una persona de tu equipo para abrirle uno (por ejemplo, cuando un KPI queda bajo su umbral)." : "Si tu supervisor te abre uno, lo verás aquí con sus objetivos y fecha de revisión."}</Vacio> : (
        lista.map((p) => (
          <Panel key={p.id} titulo={`${p.colaborador_nombre} · ${p.motivo}`} accion={<Insignia tono={p.estado === "ABIERTO" ? "amarillo" : p.estado === "CUMPLIDO" ? "verde" : "neutro"}>{{ ABIERTO: "Abierto", CUMPLIDO: "Cumplido", NO_CUMPLIDO: "No cumplido", CANCELADO: "Cancelado" }[p.estado]}</Insignia>}>
            <p className="text-sm text-gris">Desde {p.inicio} · revisión {p.revision} · abrió {p.creado_por_nombre}{p.kpi_nombre ? ` · KPI: ${p.kpi_nombre}` : ""}</p>
            <ul className="mt-3 space-y-2">{p.objetivos.map((o, i) => (
              <li key={i} className="flex items-start gap-2 text-[15px]">
                <input type="checkbox" className="mt-1 accent-azul" checked={!!o.cumplido} disabled={!supervisa || p.estado !== "ABIERTO" || String(p.colaborador) === String(yo?.id)} onChange={() => marcar(p, i)} aria-label={o.texto} />
                <span className={cx(o.cumplido && "text-gris line-through")}>{o.texto}{o.meta ? ` — meta: ${o.meta}` : ""}{o.fecha ? <span className="text-xs text-gris"> · {o.fecha}</span> : null}</span>
              </li>))}</ul>
            {p.capacitacion && <p className="mt-3 text-sm"><strong>Capacitación:</strong> {p.capacitacion}</p>}
            {p.resultado && <p className="mt-2 text-sm"><strong>Resultado:</strong> {p.resultado}</p>}
            {supervisa && p.estado === "ABIERTO" && String(p.colaborador) !== String(yo?.id) && (
              <div className="mt-3 flex flex-wrap gap-2">
                <Boton tam="sm" variante="secundario" onClick={() => setEditando(p)}>Editar</Boton>
                <Boton tam="sm" variante="secundario" onClick={() => guardar({ id: p.id, estado: "CUMPLIDO" })}>Marcar cumplido</Boton>
                <Boton tam="sm" variante="fantasma" onClick={() => guardar({ id: p.id, estado: "NO_CUMPLIDO" })}>No cumplido</Boton>
              </div>
            )}
          </Panel>
        ))
      )}
      {editando && <FormPlan plan={editando} onCerrar={() => setEditando(null)} onGuardar={guardar} />}
    </div>
  );
}

function FormPlan({ plan, onCerrar, onGuardar }) {
  const [p, setP] = useState(plan);
  const obj = p.objetivos || [];
  const ponerObj = (i, campo, v) => setP({ ...p, objetivos: obj.map((o, j) => (j === i ? { ...o, [campo]: v } : o)) });
  return (
    <Modal abierto onCerrar={onCerrar} ancho="max-w-2xl" titulo={p.id ? "Editar plan de mejora" : "Nuevo plan de mejora"}
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton icono={Save} onClick={() => onGuardar(p)}>Guardar</Boton></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Campo etiqueta="Motivo" className="sm:col-span-2">{(id) => <input id={id} className="campo" value={p.motivo} onChange={(e) => setP({ ...p, motivo: e.target.value })} placeholder="Ej.: entregas fuera de plazo" />}</Campo>
        <Campo etiqueta="Inicio">{(id) => <input id={id} type="date" className="campo" value={p.inicio} onChange={(e) => setP({ ...p, inicio: e.target.value })} />}</Campo>
        <Campo etiqueta="Revisión">{(id) => <input id={id} type="date" className="campo" value={p.revision} onChange={(e) => setP({ ...p, revision: e.target.value })} />}</Campo>
      </div>
      <p className="etiqueta mt-4">Objetivos</p>
      <ul className="space-y-2">{obj.map((o, i) => (
        <li key={i} className="grid gap-2 sm:grid-cols-[1fr_8rem_9rem_auto]">
          <input className="campo" placeholder="Qué debe lograr" value={o.texto} onChange={(e) => ponerObj(i, "texto", e.target.value)} aria-label="Objetivo" />
          <input className="campo" placeholder="Meta" value={o.meta || ""} onChange={(e) => ponerObj(i, "meta", e.target.value)} aria-label="Meta" />
          <input type="date" className="campo" value={o.fecha || ""} onChange={(e) => ponerObj(i, "fecha", e.target.value)} aria-label="Fecha" />
          <Boton variante="fantasma" icono={Trash2} aria-label="Quitar objetivo" onClick={() => setP({ ...p, objetivos: obj.filter((_, j) => j !== i) })} />
        </li>))}</ul>
      <Boton variante="secundario" tam="sm" icono={Plus} className="mt-2" onClick={() => setP({ ...p, objetivos: [...obj, { texto: "", meta: "", fecha: "" }] })}>Objetivo</Boton>
      <Campo etiqueta="Capacitación o apoyo" className="mt-4">{(id) => <textarea id={id} rows={2} className="campo" value={p.capacitacion || ""} onChange={(e) => setP({ ...p, capacitacion: e.target.value })} />}</Campo>
      {p.id && <Campo etiqueta="Resultado" className="mt-3">{(id) => <textarea id={id} rows={2} className="campo" value={p.resultado || ""} onChange={(e) => setP({ ...p, resultado: e.target.value })} />}</Campo>}
    </Modal>
  );
}

// ---------------------------------------------------------------- Expediente
function Expediente({ usuarioInicial, supervisa, esAdmin }) {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const { persona, setPersona, filtro, propio } = usePersona(usuarioInicial, supervisa);
  const [lista, setLista] = useState(null);
  const [error, setError] = useState("");
  const [nuevo, setNuevo] = useState(null);
  const [descargo, setDescargo] = useState({});
  const cargar = () => expediente(persona).then(setLista).catch((e) => setError(e.message));
  useEffect(() => { setLista(null); setError(""); cargar(); }, [persona]); // eslint-disable-line react-hooks/exhaustive-deps
  const guardar = async (e) => {
    setError("");
    try { await guardarEvento(e); setNuevo(null); avisar("Guardado en el expediente."); cargar(); } catch (err) { setError(err.message); }
  };
  const borrar = async (e) => {
    if (!(await confirmar({ titulo: "¿Borrar este registro?", mensaje: e.titulo, boton: "Borrar", peligro: true }))) return;
    await borrarEvento(e.id); cargar();
  };
  const tipos = TIPOS_EVENTO.filter(([k]) => k !== "BONO" || esAdmin);
  return (
    <div className="space-y-4">
      {supervisa && (
        <div className="flex flex-wrap items-end gap-3">
          <SelectorPersona etiqueta="Persona" valor={persona} onCambio={setPersona} filtro={filtro} vacio="Mi expediente" />
          {persona && !propio && <Boton icono={Plus} onClick={() => setNuevo({ colaborador: Number(persona), tipo: "RECONOCIMIENTO", fecha: hoy(), titulo: "", descripcion: "", visible_al_colaborador: true })}>Registrar</Boton>}
        </div>
      )}
      {error && <Alerta>{error}</Alerta>}
      {!lista ? <Cargando /> : !lista.length ? <Vacio icono={ClipboardCheck} titulo="Expediente vacío">Reconocimientos, observaciones, incidencias, capacitaciones y bonos quedan aquí.</Vacio> : (
        <Panel titulo="Registros" cuerpo="p-0">
          <ul className="divide-y divide-linea-suave">{lista.map((e) => (
            <li key={e.id} className="px-5 py-3">
              <div className="flex flex-wrap items-center gap-2">
                <Insignia tono={TONO_EVENTO[e.tipo]}>{e.tipo_nombre}</Insignia><span className="text-xs text-gris">{e.fecha} · {e.registrado_por_nombre}</span>
                {!e.visible_al_colaborador && <Insignia>Interno</Insignia>}
                {e.monto != null && <span className="text-xs num">RD$ {num(e.monto)}</span>}{e.horas != null && <span className="text-xs num">{num(e.horas)} h</span>}
                {esAdmin && <Boton tam="sm" variante="fantasma" icono={Trash2} className="ml-auto text-rojo" aria-label="Borrar" onClick={() => borrar(e)} />}
              </div>
              <p className="mt-1 font-medium">{e.titulo}</p>
              {e.descripcion && <p className="text-sm text-gris">{e.descripcion}</p>}
              {e.justificacion && <p className="mt-1 text-sm"><strong>Descargo:</strong> {e.justificacion}</p>}
              {propio && !e.justificacion && ["OBSERVACION", "AMONESTACION_VERBAL", "AMONESTACION_ESCRITA", "INCIDENCIA"].includes(e.tipo) && (
                <div className="mt-2 flex flex-wrap gap-2">
                  <input className="campo min-w-60 flex-1" placeholder="Escribe tu descargo o justificación" value={descargo[e.id] || ""} onChange={(ev) => setDescargo({ ...descargo, [e.id]: ev.target.value })} aria-label="Descargo" />
                  <Boton tam="sm" disabled={!descargo[e.id]} onClick={() => guardar({ id: e.id, justificacion: descargo[e.id] })}>Enviar</Boton>
                </div>
              )}
            </li>))}</ul>
        </Panel>
      )}
      {nuevo && (
        <Modal abierto onCerrar={() => setNuevo(null)} titulo="Registrar en el expediente" pie={<><Boton variante="secundario" onClick={() => setNuevo(null)}>Cancelar</Boton><Boton icono={Save} onClick={() => guardar(nuevo)}>Guardar</Boton></>}>
          {error && <Alerta className="mb-3">{error}</Alerta>}
          <div className="grid gap-3 sm:grid-cols-2">
            <Campo etiqueta="Tipo">{(id) => <select id={id} className="campo" value={nuevo.tipo} onChange={(e) => setNuevo({ ...nuevo, tipo: e.target.value })}>{tipos.map(([k, n]) => <option key={k} value={k}>{n}</option>)}</select>}</Campo>
            <Campo etiqueta="Fecha">{(id) => <input id={id} type="date" className="campo" value={nuevo.fecha} onChange={(e) => setNuevo({ ...nuevo, fecha: e.target.value })} />}</Campo>
            <Campo etiqueta="Título" className="sm:col-span-2">{(id) => <input id={id} className="campo" value={nuevo.titulo} onChange={(e) => setNuevo({ ...nuevo, titulo: e.target.value })} />}</Campo>
            <Campo etiqueta="Detalle" className="sm:col-span-2">{(id) => <textarea id={id} rows={3} className="campo" value={nuevo.descripcion} onChange={(e) => setNuevo({ ...nuevo, descripcion: e.target.value })} />}</Campo>
            {nuevo.tipo === "BONO" && <Campo etiqueta="Monto (RD$)" ayuda="Escríbelo solo aquí: el título y el detalle los puede ver la persona y su supervisor.">{(id) => <input id={id} type="number" min={0} className="campo" value={nuevo.monto || ""} onChange={(e) => setNuevo({ ...nuevo, monto: e.target.value })} />}</Campo>}
            {nuevo.tipo === "CAPACITACION" && <Campo etiqueta="Horas">{(id) => <input id={id} type="number" min={0} step="0.5" className="campo" value={nuevo.horas || ""} onChange={(e) => setNuevo({ ...nuevo, horas: e.target.value })} />}</Campo>}
            <label className="flex min-h-11 items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" className="accent-azul" checked={nuevo.visible_al_colaborador} onChange={(e) => setNuevo({ ...nuevo, visible_al_colaborador: e.target.checked })} />La persona lo ve (y puede escribir su descargo)</label>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- Auditoría
function Auditoria() {
  const [texto, setTexto] = useState("");
  const [lista, setLista] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { const t = setTimeout(() => auditoria({ q: texto }).then(setLista).catch((e) => setError(e.message)), 300); return () => clearTimeout(t); }, [texto]);
  const fmt = (o) => (o ? Object.entries(o).map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`).join(" · ") : "");
  return (
    <Panel titulo="Auditoría de cambios" cuerpo="p-0" accion={<input className="campo !h-9 w-56" placeholder="Buscar…" value={texto} onChange={(e) => setTexto(e.target.value)} aria-label="Buscar en la auditoría" />}>
      <p className="px-5 pt-4 text-sm text-gris">Quién cambió KPIs, pesos, metas, reglas del puntaje, marcajes, horarios, puestos y salarios, con el valor de antes y el de después.</p>
      {error && <Alerta className="m-4">{error}</Alerta>}
      {!lista ? <Cargando /> : !lista.length ? <p className="p-5 text-sm text-gris">Sin cambios registrados.</p> : (
        <div className="overflow-x-auto"><table className="tabla">
          <thead><tr><th>Fecha</th><th>Quién</th><th>Qué</th><th>Antes</th><th>Después</th></tr></thead>
          <tbody>{lista.map((a) => (
            <tr key={a.id}><td className="whitespace-nowrap text-sm">{new Date(a.fecha).toLocaleString("es-DO", { dateStyle: "short", timeStyle: "short" })}</td>
              <td className="text-sm">{a.usuario || "Sistema"}</td><td className="text-sm"><span className="font-medium">{a.accion}</span><span className="block text-xs text-gris">{a.objeto}</span></td>
              <td className="max-w-xs text-xs text-gris">{fmt(a.antes)}</td><td className="max-w-xs text-xs">{fmt(a.despues)}</td></tr>))}</tbody>
        </table></div>
      )}
    </Panel>
  );
}
