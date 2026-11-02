// Monitoreo v10 (nivel Teramind): resumen con rango de fechas, incidencias, pantallas en vivo, computadoras,
// reglas de comportamiento y perfiles de monitoreo.
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Bot, Check, CircleAlert, Lightbulb, Monitor, Pencil, Plus, ShieldAlert, Trash2, TrendingDown, TrendingUp, X } from "lucide-react";
import {
  borrarPerfilMonitoreo, borrarReglaComportamiento, computadoras, guardarPerfilMonitoreo, guardarReglaComportamiento, incidencias,
  pantallasEnVivo, perfilesMonitoreo, reaplicarReglas, reglasComportamiento, resumenMonitoreo, revisarIncidencia, urlCaptura,
} from "@/lib/api";
import { hace, hoyISO, reloj } from "@/lib/formato";
import { useRecurso } from "@/lib/recursos";
import { Alerta, Boton, Campo, Cargando, Insignia, Modal, Panel, Puntaje, Vacio, cx, useAviso, useConfirmar } from "@/components/ui";
import { SelectorPersonas } from "@/components/Selectores";

const pct = (v) => (v == null ? "—" : `${Number(v).toLocaleString("es-DO", { maximumFractionDigits: 1 })} %`);
const hora = (iso) => (iso ? new Date(iso).toLocaleTimeString("es-DO", { hour: "numeric", minute: "2-digit" }) : "—");
const menos = (dias) => { const d = new Date(); d.setDate(d.getDate() - dias); return d.toISOString().slice(0, 10); };
const RIESGO = { BAJO: ["Bajo", "azul"], MEDIO: ["Medio", "amarillo"], ALTO: ["Alto", "rojo"], CRITICO: ["Crítico", "rojo"], SIN_RIESGO: ["Sin riesgo", "verde"] };
const CATEGORIA = { PRODUCTIVIDAD: "Productividad", SEGURIDAD: "Seguridad", IA: "Uso de IA", CUMPLIMIENTO: "Cumplimiento" };
const COLOR_CAT = { P: "bg-verde", I: "bg-rojo", N: "bg-[#9aa7bd]" };

function Rango({ desde, hasta, onCambio }) {
  const presets = [[7, "7 días"], [30, "30 días"], [90, "90 días"]];
  return (
    <div className="flex flex-wrap items-center gap-2">
      {presets.map(([n, t]) => (
        <button key={n} type="button" onClick={() => onCambio(menos(n - 1), hoyISO())}
          className={cx("h-9 rounded-lg border px-3 text-sm font-medium", desde === menos(n - 1) && hasta === hoyISO() ? "border-azul bg-azul text-white" : "border-linea bg-white hover:border-azul")}>{t}</button>
      ))}
      <input type="date" aria-label="Desde" className="campo !h-9 w-40" value={desde} max={hasta} onChange={(e) => onCambio(e.target.value, hasta)} />
      <input type="date" aria-label="Hasta" className="campo !h-9 w-40" value={hasta} max={hoyISO()} onChange={(e) => onCambio(desde, e.target.value)} />
    </div>
  );
}

function Cifra({ titulo, valor, detalle, tono }) {
  return (
    <div className="rounded-xl border border-linea bg-white p-4">
      <p className="text-sm text-gris">{titulo}</p>
      <p className={cx("mt-1 font-display text-2xl font-semibold num", tono)}>{valor}</p>
      {detalle && <p className="mt-0.5 text-xs text-gris">{detalle}</p>}
    </div>
  );
}

/** Lista con barras horizontales (como los widgets del Overview de Teramind). */
function Barras({ titulo, filas, valor, etiqueta, color, enlace, vacio = "Sin datos en el período." }) {
  const max = Math.max(1, ...filas.map(valor));
  return (
    <Panel titulo={titulo} cuerpo="p-0">
      {!filas.length ? <p className="p-5 text-sm text-gris">{vacio}</p> : (
        <ul className="divide-y divide-linea-suave">{filas.map((f, i) => (
          <li key={i} className="px-5 py-2">
            <div className="flex items-center gap-3 text-[15px]">
              <span className="min-w-0 flex-1 truncate" title={f.nombre}>{enlace ? <Link to={enlace(f)} className="hover:text-azul">{f.nombre}</Link> : f.nombre}</span>
              <span className="shrink-0 text-sm num">{etiqueta(f)}</span>
            </div>
            <div className="mt-1 h-1.5 rounded-full bg-linea-suave"><div className={cx("h-full rounded-full", color ? color(f) : "bg-azul")} style={{ width: `${(valor(f) / max) * 100}%` }} /></div>
          </li>))}</ul>
      )}
    </Panel>
  );
}

// ---------------------------------------------------------------- Resumen
export function Resumen() {
  const [r, setR] = useState({ desde: menos(6), hasta: hoyISO() });
  const [departamento, setDepartamento] = useState("");
  const [deptos] = useRecurso("departamentos");
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { setD(null); setError(""); resumenMonitoreo({ ...r, departamento }).then(setD).catch((e) => setError(e.message)); }, [r, departamento]);
  const t = d?.totales;
  const cambio = t && t.productividad != null && t.productividad_anterior != null ? Math.round((t.productividad - t.productividad_anterior) * 10) / 10 : null;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Rango desde={r.desde} hasta={r.hasta} onCambio={(desde, hasta) => setR({ desde, hasta })} />
        <select className="campo !h-9 !w-auto" aria-label="Departamento" value={departamento} onChange={(e) => setDepartamento(e.target.value)}>
          <option value="">Todos los departamentos</option>
          {(deptos || []).map((x) => <option key={x.id} value={x.id}>{x.nombre}</option>)}
        </select>
      </div>
      {error ? <Alerta>{error}</Alerta> : !d ? <Cargando texto="Calculando el período…" /> : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <Cifra titulo="Personas con datos" valor={t.personas} detalle={`${reloj(t.minutos)} registradas`} />
            <Cifra titulo="Tiempo activo" valor={pct(t.actividad)} detalle={`${reloj(t.minutos_activos)} activo`} tono={t.actividad != null && t.actividad < 60 ? "text-rojo" : ""} />
            <Cifra titulo="Productivo" valor={<Puntaje valor={t.productividad} />} detalle={cambio == null ? "Del tiempo activo" : <span className="inline-flex items-center gap-1">{cambio >= 0 ? <TrendingUp className="size-3 text-verde" /> : <TrendingDown className="size-3 text-rojo" />}{cambio > 0 ? "+" : ""}{cambio} frente al período anterior</span>} />
            <Cifra titulo="Uso de IA" valor={reloj(t.ia_minutos)} detalle={`${d.ia.personas} persona(s)`} />
            <Cifra titulo="Incidencias" valor={t.incidencias} detalle="Reglas de comportamiento" tono={t.incidencias ? "text-[#a86a00]" : ""} />
            <Cifra titulo="En riesgo alto" valor={t.en_riesgo} detalle="Riesgo alto o crítico" tono={t.en_riesgo ? "text-rojo" : ""} />
          </div>
          {d.insights.length > 0 && (
            <Panel titulo="Lo que hay que mirar">
              <ul className="space-y-2">{d.insights.map((x, i) => (
                <li key={i} className="flex items-start gap-2 text-[15px]">
                  {x.tono === "mal" ? <CircleAlert className="mt-0.5 size-4 shrink-0 text-rojo" /> : x.tono === "bien" ? <TrendingUp className="mt-0.5 size-4 shrink-0 text-verde" /> : <Lightbulb className="mt-0.5 size-4 shrink-0 text-[#a86a00]" />}{x.texto}
                </li>))}</ul>
            </Panel>
          )}
          <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-4">
            <Barras titulo="Actividad por persona" filas={d.personas.slice(0, 12)} valor={(f) => f.actividad || 0} etiqueta={(f) => pct(f.actividad)}
              color={(f) => (f.actividad < 60 ? "bg-rojo" : "bg-azul")} enlace={(f) => `/monitoreo?ver=persona&persona=${f.id}`} />
            <Barras titulo="Sitios web" filas={d.sitios} valor={(f) => f.minutos} etiqueta={(f) => reloj(f.minutos)} color={(f) => COLOR_CAT[f.categoria]} />
            <Barras titulo="Aplicaciones" filas={d.apps} valor={(f) => f.minutos} etiqueta={(f) => reloj(f.minutos)} color={(f) => COLOR_CAT[f.categoria]} />
            <Barras titulo="Reglas que se activaron" filas={d.incidencias} valor={(f) => f.veces} etiqueta={(f) => `${f.veces} · ${f.personas} pers.`}
              color={(f) => (f.riesgo === "CRITICO" || f.riesgo === "ALTO" ? "bg-rojo" : f.riesgo === "MEDIO" ? "bg-amarillo-600" : "bg-azul")} vacio="Ninguna regla se activó." />
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Panel titulo="Uso de inteligencia artificial" cuerpo="p-0">
              {!d.ia.herramientas.length ? <p className="p-5 text-sm text-gris">Nadie usó herramientas de IA en el período.</p> : (
                <div className="grid gap-0 sm:grid-cols-2">
                  <ul className="divide-y divide-linea-suave border-linea-suave sm:border-r">{d.ia.herramientas.map((h) => (
                    <li key={h.nombre} className="flex items-center gap-3 px-5 py-2"><Bot className="size-4 text-azul" /><span className="flex-1">{h.nombre}</span><span className="text-sm num">{reloj(h.minutos)} · {h.personas} pers.</span></li>))}</ul>
                  <ul className="divide-y divide-linea-suave">{d.ia.por_persona.map((p) => (
                    <li key={p.id} className="px-5 py-2"><div className="flex justify-between gap-2"><span className="truncate">{p.nombre}</span><span className="text-sm num">{reloj(p.minutos)}</span></div>
                      <span className="text-xs text-gris">{p.herramientas.join(", ")}</span></li>))}</ul>
                </div>
              )}
            </Panel>
            <Panel titulo="Riesgo interno" cuerpo="p-0">
              {!d.riesgo.length ? <p className="p-5 text-sm text-gris">Nadie suma puntos de riesgo en el período.</p> : (
                <ul className="divide-y divide-linea-suave">{d.riesgo.map((p) => (
                  <li key={p.id} className="flex flex-wrap items-center gap-3 px-5 py-2.5">
                    <span className="min-w-0 flex-1"><Link to={`/monitoreo?ver=incidencias&persona=${p.id}`} className="font-medium hover:text-azul">{p.nombre}</Link>
                      <span className="block text-xs text-gris">{p.reglas.map(([n, v]) => `${n} (${v})`).join(" · ")}</span></span>
                    <span className="text-sm num">{p.puntos} pts</span><Insignia tono={RIESGO[p.nivel][1]}>{RIESGO[p.nivel][0]}</Insignia>
                  </li>))}</ul>
              )}
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- Incidencias
export function Incidencias({ persona, gestiona }) {
  const avisar = useAviso();
  const [r, setR] = useState({ desde: menos(29), hasta: hoyISO() });
  const [estado, setEstado] = useState("");
  const [lista, setLista] = useState(null);
  const [error, setError] = useState("");
  const [notas, setNotas] = useState({});
  const cargar = useCallback(() => incidencias({ ...r, estado, persona }).then(setLista).catch((e) => setError(e.message)), [r, estado, persona]);
  useEffect(() => { setLista(null); cargar(); }, [cargar]);
  const decidir = async (i, nuevo) => {
    try { await revisarIncidencia(i.id, { estado: nuevo, nota: notas[i.id] || "" }); avisar(nuevo === "DESCARTADA" ? "Descartada: no suma riesgo." : "Marcada como revisada."); cargar(); }
    catch (e) { setError(e.message); }
  };
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Rango desde={r.desde} hasta={r.hasta} onCambio={(desde, hasta) => setR({ desde, hasta })} />
        <select className="campo !h-9 !w-auto" aria-label="Estado" value={estado} onChange={(e) => setEstado(e.target.value)}>
          <option value="">Todas</option><option value="NUEVA">Nuevas</option><option value="REVISADA">Revisadas</option><option value="DESCARTADA">Descartadas</option>
        </select>
      </div>
      {error && <Alerta>{error}</Alerta>}
      {!lista ? <Cargando /> : !lista.length ? <Vacio icono={ShieldAlert} titulo="Sin incidencias">Aparecen cuando alguien activa una regla de comportamiento (apuestas, acceso remoto, juegos, IA no aprobada…).</Vacio> : (
        <Panel cuerpo="p-0">
          <ul className="divide-y divide-linea-suave">{lista.map((i) => (
            <li key={i.id} className="px-5 py-3">
              <div className="flex flex-wrap items-center gap-2">
                <Insignia tono={RIESGO[i.riesgo][1]}>{RIESGO[i.riesgo][0]}</Insignia>
                <span className="font-medium">{i.regla_nombre}</span><span className="text-sm text-gris">· {i.persona} · {i.dia} · {hora(i.primera)}–{hora(i.ultima)} · {reloj(i.minutos)}</span>
                {i.estado !== "NUEVA" && <Insignia tono={i.estado === "DESCARTADA" ? "neutro" : "verde"} className="ml-auto">{i.estado === "DESCARTADA" ? "Descartada" : "Revisada"}{i.revisada_por_nombre ? ` · ${i.revisada_por_nombre}` : ""}</Insignia>}
              </div>
              <p className="mt-1 truncate text-sm text-gris" title={i.ejemplo}>{i.ejemplo}</p>
              {i.nota && <p className="text-sm">Nota: {i.nota}</p>}
              {gestiona && i.estado === "NUEVA" && (
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <input className="campo !h-9 min-w-48 flex-1" placeholder="Nota (opcional)" aria-label="Nota" value={notas[i.id] || ""} onChange={(e) => setNotas({ ...notas, [i.id]: e.target.value })} />
                  <Boton tam="sm" variante="secundario" icono={X} onClick={() => decidir(i, "DESCARTADA")}>Descartar</Boton>
                  <Boton tam="sm" icono={Check} onClick={() => decidir(i, "REVISADA")}>Revisada</Boton>
                </div>
              )}
            </li>))}</ul>
        </Panel>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- Pantallas en vivo
export function Pantallas() {
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [foto, setFoto] = useState(null);
  const [vuelta, setVuelta] = useState(0);
  useEffect(() => {
    const cargar = () => pantallasEnVivo().then((x) => { setD(x); setVuelta((v) => v + 1); }).catch((e) => setError(e.message));
    cargar();
    const t = setInterval(() => document.visibilityState === "visible" && cargar(), 60000);
    return () => clearInterval(t);
  }, []);
  if (error) return <Alerta>{error}</Alerta>;
  if (!d) return <Cargando />;
  return (
    <div className="space-y-3">
      <p className="text-sm text-gris">La última captura de hoy de cada persona. Se actualiza cada minuto. Solo hay capturas para los perfiles que las tienen activas (Monitoreo → Reglas → Perfiles).</p>
      {!d.capturas_activas && <Alerta tono="amarillo">Ningún perfil de monitoreo toma capturas. Actívalas en un perfil para ver las pantallas.</Alerta>}
      {!d.personas.length ? <Vacio icono={Monitor} titulo="Sin capturas hoy">Aparecen aquí en cuanto el agente envía la primera.</Vacio> : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {d.personas.map((p) => (
            <button key={p.id} type="button" onClick={() => setFoto(p)} className="overflow-hidden rounded-xl border border-linea bg-white text-left hover:border-azul">
              <img src={`${urlCaptura(p.captura)}?v=${vuelta}`} alt={`Pantalla de ${p.nombre}`} loading="lazy" className="aspect-video w-full bg-noche object-cover" />
              <span className="block px-3 py-2"><span className="flex items-center gap-2 font-medium">
                <span className={cx("size-2 rounded-full", p.ahora?.en_vivo ? "bg-verde" : "bg-[#9aa7bd]")} />{p.nombre}</span>
                <span className="block truncate text-xs text-gris">{p.hora} · {p.ahora?.app || p.app || "—"}</span></span>
            </button>
          ))}
        </div>
      )}
      <Modal abierto={!!foto} onCerrar={() => setFoto(null)} titulo={foto ? `${foto.nombre} · ${foto.hora}` : ""} ancho="md:max-w-5xl">
        {foto && <img src={urlCaptura(foto.captura)} alt="" className="w-full rounded-lg" />}
      </Modal>
    </div>
  );
}

// ---------------------------------------------------------------- Computadoras y personas
const ESTADO_PC = { EN_LINEA: ["En línea", "verde"], DESCONECTADO: ["Desconectado", "neutro"], SIN_EQUIPO: ["Sin computadora", "amarillo"],
  SIN_POLITICA: ["Sin aceptar política", "rojo"], NO_MONITOREADO: ["No monitoreado", "azul"] };
export function Computadoras() {
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [filtro, setFiltro] = useState("");
  useEffect(() => { computadoras().then(setD).catch((e) => setError(e.message)); }, []);
  const personas = useMemo(() => (d?.personas || []).filter((p) => !filtro || p.estado === filtro), [d, filtro]);
  if (error) return <Alerta>{error}</Alerta>;
  if (!d) return <Cargando />;
  const cuenta = (e) => d.personas.filter((p) => p.estado === e).length;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => setFiltro("")} className={cx("h-9 rounded-full border px-3 text-sm", !filtro ? "border-azul bg-azul text-white" : "border-linea bg-white")}>Todas ({d.personas.length})</button>
        {Object.entries(ESTADO_PC).map(([k, [t]]) => (
          <button key={k} type="button" onClick={() => setFiltro(k)} className={cx("h-9 rounded-full border px-3 text-sm", filtro === k ? "border-azul bg-azul text-white" : "border-linea bg-white")}>{t} ({cuenta(k)})</button>
        ))}
      </div>
      <Panel titulo="Personas" cuerpo="p-0">
        <div className="overflow-x-auto"><table className="tabla">
          <thead><tr><th>Persona</th><th>Departamento</th><th>Perfil de monitoreo</th><th className="text-right">Computadoras</th><th>Último contacto</th><th>Estado</th></tr></thead>
          <tbody>{personas.map((p) => (
            <tr key={p.id}><td className="min-w-44"><Link to={`/monitoreo?ver=persona&persona=${p.id}`} className="font-medium hover:text-azul">{p.nombre}</Link><span className="block text-xs text-gris">{p.puesto}</span></td>
              <td className="text-sm">{p.departamento || "—"}</td><td className="text-sm">{p.perfil || "General"}{p.capturas ? <Insignia className="ml-1">Capturas</Insignia> : null}</td>
              <td className="text-right num">{p.equipos}</td><td className="whitespace-nowrap text-sm">{p.ultimo_contacto ? hace(p.ultimo_contacto) : "—"}</td>
              <td><Insignia tono={ESTADO_PC[p.estado][1]}>{ESTADO_PC[p.estado][0]}</Insignia></td></tr>))}</tbody>
        </table></div>
      </Panel>
      <Panel titulo={`Computadoras (${d.computadoras.length})`} cuerpo="p-0">
        {!d.computadoras.length ? <p className="p-5 text-sm text-gris">Sin computadoras vinculadas.</p> : (
          <div className="overflow-x-auto"><table className="tabla">
            <thead><tr><th>Computadora</th><th>Persona</th><th>Sistema</th><th>Agente</th><th>Último contacto</th><th>Estado</th></tr></thead>
            <tbody>{d.computadoras.map((c) => (
              <tr key={c.id} className={c.activo ? "" : "opacity-55"}><td className="font-medium">{c.nombre}<span className="block text-xs text-gris">adz_{c.prefijo}…</span></td><td className="text-sm">{c.persona}</td>
                <td className="text-sm">{c.sistema || "—"}</td><td className="text-sm num">{c.version_agente || "—"}</td><td className="whitespace-nowrap text-sm">{c.ultimo_contacto ? hace(c.ultimo_contacto) : "Nunca"}</td>
                <td>{!c.activo ? <Insignia>Desvinculada</Insignia> : c.en_linea ? <Insignia tono="verde">En línea</Insignia> : <Insignia>Desconectada</Insignia>}</td></tr>))}</tbody>
          </table></div>
        )}
      </Panel>
    </div>
  );
}

// ---------------------------------------------------------------- Reglas de comportamiento
const NUEVA_REGLA = { nombre: "", descripcion: "", categoria: "PRODUCTIVIDAD", campo: "DOMINIO", patrones: "", minutos_minimos: 1, riesgo: "MEDIO", accion: "REGISTRAR", departamentos: [], excluir_departamentos: [], activa: true };
export function ReglasComportamiento() {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const [deptos] = useRecurso("departamentos");
  const [lista, setLista] = useState(null);
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const cargar = () => reglasComportamiento().then(setLista).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);
  const guardar = async () => {
    setError("");
    try { await guardarReglaComportamiento({ ...form, minutos_minimos: Number(form.minutos_minimos) || 1 }); setForm(null); avisar("Regla guardada. Se aplica a la actividad que llegue desde ahora."); cargar(); }
    catch (e) { setError(e.message); }
  };
  const borrar = async (r) => {
    if (!(await confirmar({ titulo: `¿Borrar «${r.nombre}»?`, mensaje: "Se borran también sus incidencias. Si solo quieres pausarla, desactívala.", boton: "Borrar", peligro: true }))) return;
    await borrarReglaComportamiento(r.id); cargar();
  };
  const nombreDepto = (id) => (deptos || []).find((x) => x.id === id)?.nombre || id;
  const Chips = ({ campo }) => (
    <div className="flex flex-wrap gap-1.5">{(deptos || []).map((x) => {
      const on = form[campo].includes(x.id);
      return <button key={x.id} type="button" aria-pressed={on} onClick={() => setForm({ ...form, [campo]: on ? form[campo].filter((v) => v !== x.id) : [...form[campo], x.id] })}
        className={cx("min-h-9 rounded-full border px-3 text-sm", on ? "border-azul bg-azul text-white" : "border-linea bg-white")}>{x.nombre}</button>;
    })}</div>
  );
  if (!lista) return error ? <Alerta>{error}</Alerta> : <Cargando />;
  return (
    <Panel titulo={`Reglas de comportamiento (${lista.length})`} cuerpo="p-0" accion={<div className="flex gap-2">
      <Boton tam="sm" variante="secundario" onClick={async () => { const r = await reaplicarReglas(); avisar(`Aplicadas a los últimos 30 días: ${r.incidencias} incidencia(s).`); cargar(); }}>Aplicar a 30 días</Boton>
      <Boton tam="sm" icono={Plus} onClick={() => setForm(NUEVA_REGLA)}>Regla</Boton></div>}>
      <p className="px-5 pt-4 text-sm text-gris">Si alguien usa un sitio, una aplicación o una ventana con cierto texto durante los minutos indicados en un día, se registra una incidencia y, si la regla lo pide, se avisa a su supervisor (y a Tecnología en seguridad o riesgo alto). Trabajan con lo que el agente ya mide: nunca contenido, teclas ni archivos.</p>
      <ul className="mt-2 divide-y divide-linea-suave">{lista.map((r) => (
        <li key={r.id} className={cx("flex flex-wrap items-center gap-3 px-5 py-3", !r.activa && "opacity-55")}>
          <span className="min-w-0 flex-1">
            <span className="flex flex-wrap items-center gap-2"><span className="font-medium">{r.nombre}</span><Insignia tono={RIESGO[r.riesgo][1]}>{RIESGO[r.riesgo][0]}</Insignia>
              <Insignia>{CATEGORIA[r.categoria]}</Insignia>{r.accion === "ALERTAR" && <Insignia tono="azul">Avisa</Insignia>}{!r.activa && <Insignia>Pausada</Insignia>}</span>
            <span className="block truncate text-xs text-gris">{r.patrones.split("\n").join(", ")} · desde {r.minutos_minimos} min/día
              {r.excluir_departamentos.length ? ` · no aplica a ${r.excluir_departamentos.map(nombreDepto).join(", ")}` : ""}</span>
          </span>
          <span className="text-sm num">{r.incidencias_30d} en 30 días</span>
          <Boton tam="sm" variante="fantasma" icono={Pencil} aria-label={`Editar ${r.nombre}`} onClick={() => setForm(r)} />
          <Boton tam="sm" variante="fantasma" icono={Trash2} className="text-rojo" aria-label={`Borrar ${r.nombre}`} onClick={() => borrar(r)} />
        </li>))}</ul>
      {form && (
        <Modal abierto onCerrar={() => setForm(null)} ancho="max-w-2xl" titulo={form.id ? "Editar regla" : "Nueva regla de comportamiento"}
          pie={<><Boton variante="secundario" onClick={() => setForm(null)}>Cancelar</Boton><Boton onClick={guardar}>Guardar</Boton></>}>
          {error && <Alerta className="mb-3">{error}</Alerta>}
          <div className="grid gap-3 sm:grid-cols-2">
            <Campo etiqueta="Nombre" className="sm:col-span-2">{(id) => <input id={id} className="campo" value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} />}</Campo>
            <Campo etiqueta="Qué revisa">{(id) => <select id={id} className="campo" value={form.campo} onChange={(e) => setForm({ ...form, campo: e.target.value })}><option value="DOMINIO">Sitio web</option><option value="APP">Aplicación</option><option value="TITULO">Texto en el título de la ventana</option></select>}</Campo>
            <Campo etiqueta="Categoría">{(id) => <select id={id} className="campo" value={form.categoria} onChange={(e) => setForm({ ...form, categoria: e.target.value })}>{Object.entries(CATEGORIA).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>}</Campo>
            <Campo etiqueta="Sitios, aplicaciones o textos" ayuda="Uno por línea. Ej.: bet365.com, anydesk, «Facturas personales»." className="sm:col-span-2">{(id) => <textarea id={id} rows={4} className="campo font-mono text-sm" value={form.patrones} onChange={(e) => setForm({ ...form, patrones: e.target.value })} />}</Campo>
            <Campo etiqueta="Minutos en el día para contar" ayuda="1 = cualquier uso.">{(id) => <input id={id} type="number" min={1} max={480} className="campo" value={form.minutos_minimos} onChange={(e) => setForm({ ...form, minutos_minimos: e.target.value })} />}</Campo>
            <Campo etiqueta="Riesgo">{(id) => <select id={id} className="campo" value={form.riesgo} onChange={(e) => setForm({ ...form, riesgo: e.target.value })}>{["BAJO", "MEDIO", "ALTO", "CRITICO"].map((k) => <option key={k} value={k}>{RIESGO[k][0]}</option>)}</select>}</Campo>
            <Campo etiqueta="Acción">{(id) => <select id={id} className="campo" value={form.accion} onChange={(e) => setForm({ ...form, accion: e.target.value })}><option value="REGISTRAR">Solo registrar</option><option value="ALERTAR">Registrar y avisar</option></select>}</Campo>
            <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" className="accent-azul" checked={form.activa} onChange={(e) => setForm({ ...form, activa: e.target.checked })} />Activa</label>
            <Campo etiqueta="Solo para estos departamentos (vacío = todos)" className="sm:col-span-2">{() => <Chips campo="departamentos" />}</Campo>
            <Campo etiqueta="No aplica en (es parte de su trabajo)" className="sm:col-span-2">{() => <Chips campo="excluir_departamentos" />}</Campo>
          </div>
        </Modal>
      )}
    </Panel>
  );
}

// ---------------------------------------------------------------- Perfiles de monitoreo
const NUEVO_PERFIL = { nombre: "", descripcion: "", monitorear: true, capturas: false, capturas_cada_min: 10, desenfocar_capturas: true, umbral_inactivo_seg: 180, departamentos: [], personas: [] };
export function Perfiles() {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const [deptos] = useRecurso("departamentos");
  const [lista, setLista] = useState(null);
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const cargar = () => perfilesMonitoreo().then(setLista).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);
  const guardar = async () => {
    setError("");
    try {
      await guardarPerfilMonitoreo({ ...form, capturas_cada_min: Number(form.capturas_cada_min), umbral_inactivo_seg: Number(form.umbral_inactivo_seg) });
      setForm(null); avisar("Perfil guardado. Los agentes lo toman en su próxima consulta (1 minuto)."); cargar();
    } catch (e) { setError(e.message); }
  };
  const borrar = async (p) => {
    if (!(await confirmar({ titulo: `¿Borrar el perfil «${p.nombre}»?`, mensaje: "Sus personas vuelven a la configuración general.", boton: "Borrar", peligro: true }))) return;
    await borrarPerfilMonitoreo(p.id); cargar();
  };
  if (!lista) return error ? <Alerta>{error}</Alerta> : <Cargando />;
  return (
    <Panel titulo="Perfiles de monitoreo" cuerpo="p-0" accion={<Boton tam="sm" icono={Plus} onClick={() => setForm(NUEVO_PERFIL)}>Perfil</Boton>}>
      <p className="px-5 pt-4 text-sm text-gris">Qué se mide a cada quien: con o sin capturas, cada cuánto y desde cuándo cuenta como inactivo. El perfil de una persona gana sobre el de su departamento; sin perfil se usa la configuración general.</p>
      {!lista.length ? <p className="p-5 text-sm text-gris">Sin perfiles: todos usan la configuración general.</p> : (
        <ul className="mt-2 divide-y divide-linea-suave">{lista.map((p) => (
          <li key={p.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
            <span className="min-w-0 flex-1"><span className="font-medium">{p.nombre}</span>
              <span className="block text-xs text-gris">{p.monitorear ? `${p.capturas ? `Capturas cada ${p.capturas_cada_min} min${p.desenfocar_capturas ? " (desenfocadas)" : ""}` : "Sin capturas"} · inactivo a los ${p.umbral_inactivo_seg} s` : "No registra actividad"}
                {" · "}{p.departamentos.map((id) => (deptos || []).find((x) => x.id === id)?.nombre).filter(Boolean).join(", ") || "sin departamentos"}{p.personas.length ? ` · ${p.personas.length} persona(s)` : ""}</span></span>
            <Boton tam="sm" variante="fantasma" icono={Pencil} aria-label={`Editar ${p.nombre}`} onClick={() => setForm(p)} />
            <Boton tam="sm" variante="fantasma" icono={Trash2} className="text-rojo" aria-label={`Borrar ${p.nombre}`} onClick={() => borrar(p)} />
          </li>))}</ul>
      )}
      {form && (
        <Modal abierto onCerrar={() => setForm(null)} ancho="max-w-2xl" titulo={form.id ? "Editar perfil" : "Nuevo perfil de monitoreo"}
          pie={<><Boton variante="secundario" onClick={() => setForm(null)}>Cancelar</Boton><Boton onClick={guardar}>Guardar</Boton></>}>
          {error && <Alerta className="mb-3">{error}</Alerta>}
          <div className="grid gap-3 sm:grid-cols-2">
            <Campo etiqueta="Nombre" className="sm:col-span-2">{(id) => <input id={id} className="campo" value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} placeholder="Ej.: Call Center con capturas" />}</Campo>
            <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" className="accent-azul" checked={form.monitorear} onChange={(e) => setForm({ ...form, monitorear: e.target.checked })} />Registrar actividad</label>
            <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" className="accent-azul" checked={form.capturas} onChange={(e) => setForm({ ...form, capturas: e.target.checked })} />Tomar capturas de pantalla</label>
            <Campo etiqueta="Capturas cada (minutos)">{(id) => <input id={id} type="number" min={1} max={120} className="campo" value={form.capturas_cada_min} onChange={(e) => setForm({ ...form, capturas_cada_min: e.target.value })} />}</Campo>
            <Campo etiqueta="Inactivo después de (segundos)">{(id) => <input id={id} type="number" min={30} max={3600} className="campo" value={form.umbral_inactivo_seg} onChange={(e) => setForm({ ...form, umbral_inactivo_seg: e.target.value })} />}</Campo>
            <label className="flex min-h-11 items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" className="accent-azul" checked={form.desenfocar_capturas} onChange={(e) => setForm({ ...form, desenfocar_capturas: e.target.checked })} />Desenfocar las capturas (recomendado)</label>
            <Campo etiqueta="Departamentos" className="sm:col-span-2">{() => (
              <div className="flex flex-wrap gap-1.5">{(deptos || []).map((x) => {
                const on = form.departamentos.includes(x.id);
                return <button key={x.id} type="button" aria-pressed={on} onClick={() => setForm({ ...form, departamentos: on ? form.departamentos.filter((v) => v !== x.id) : [...form.departamentos, x.id] })}
                  className={cx("min-h-9 rounded-full border px-3 text-sm", on ? "border-azul bg-azul text-white" : "border-linea bg-white")}>{x.nombre}</button>;
              })}</div>)}</Campo>
            <div className="sm:col-span-2"><SelectorPersonas leyenda="Personas con este perfil (gana sobre el departamento)" valor={form.personas} onCambio={(v) => setForm({ ...form, personas: v.map(Number) })} /></div>
          </div>
        </Modal>
      )}
    </Panel>
  );
}
