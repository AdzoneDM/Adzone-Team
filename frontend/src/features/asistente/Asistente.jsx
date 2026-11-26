// Asistente con IA: preguntas en lenguaje natural sobre los datos de la plataforma (con los permisos de cada quien)
// y el análisis del día con alertas para Dirección y quien gestiona un área.
import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AlertTriangle, ArrowUp, Check, ClipboardList, Clock, Copy, Database, Handshake, Lightbulb, ListTodo, MessageSquare, Plus, RefreshCw, ShieldCheck, Sparkles, Trash2, TrendingUp } from "lucide-react";
import {
  asistenteActualizarInforme, asistenteBorrar, asistenteConversacion, asistenteConversaciones, asistenteEstado, asistenteInforme, asistentePreguntar,
} from "@/lib/api";
import { fechaHora } from "@/lib/formato";
import { Alerta, Boton, Cargando, cx, useAviso, useConfirmar } from "@/components/ui";
import { copiarTexto } from "@/lib/portapapeles";
import Grafico, { leerGrafico } from "./Grafico";

const SUGERENCIAS = [
  { icono: ListTodo, tema: "Tareas", texto: "¿Quién tiene más tareas vencidas y cuáles son?" },
  { icono: Clock, tema: "Asistencia", texto: "¿Cómo va la puntualidad de mi equipo este mes?" },
  { icono: TrendingUp, tema: "Desempeño", texto: "Compara el desempeño de este mes con el anterior" },
  { icono: ClipboardList, tema: "Órdenes", texto: "¿Qué órdenes de trabajo están atrasadas?" },
  { icono: Handshake, tema: "Comercial", texto: "¿Cómo van las oportunidades comerciales?" },
  { icono: Lightbulb, tema: "Resumen", texto: "Dame un resumen de lo más urgente de hoy" },
];

const NOMBRES_CONSULTA = { personas: "personas", tareas_resumen: "tareas", tareas_lista: "tareas", desempeno_mes: "desempeño", asistencia: "asistencia",
  ordenes: "órdenes", comercial: "comercial", finanzas: "finanzas" };

/** Negritas **así** dentro de una línea. */
function enLinea(texto) {
  return texto.split(/(\*\*[^*]+\*\*)/g).map((p, i) => (p.startsWith("**") && p.endsWith("**") ? <strong key={i}>{p.slice(2, -2)}</strong> : <Fragment key={i}>{p}</Fragment>));
}

/** Texto de la respuesta: párrafos, listas con «-» y bloques ```grafico```. */
function Respuesta({ texto }) {
  const partes = texto.split(/```grafico\s*([\s\S]*?)```/g);
  return (
    <div className="space-y-2 text-[15px] leading-relaxed">
      {partes.map((p, i) => {
        if (i % 2 === 1) { const g = leerGrafico(p); return g ? <Grafico key={i} g={g} /> : null; }
        const bloques = p.trim().split(/\n{2,}/).filter(Boolean);
        return bloques.map((b, j) => {
          const lineas = b.split("\n");
          if (lineas.every((l) => /^\s*[-•]\s+/.test(l))) {
            return <ul key={`${i}-${j}`} className="list-disc space-y-1 pl-5">{lineas.map((l, k) => <li key={k}>{enLinea(l.replace(/^\s*[-•]\s+/, ""))}</li>)}</ul>;
          }
          return <p key={`${i}-${j}`} className="whitespace-pre-line">{enLinea(b.replace(/^#+\s*/gm, ""))}</p>;
        });
      })}
    </div>
  );
}

function Chat({ estado, onCambioLista }) {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const [lista, setLista] = useState([]);
  const [actual, setActual] = useState(null);   // { id, titulo, mensajes }
  const [texto, setTexto] = useState("");
  const [pensando, setPensando] = useState(false);
  const [error, setError] = useState("");
  const fin = useRef(null);
  const cargarLista = useCallback(() => asistenteConversaciones().then(setLista).catch(() => {}), []);
  useEffect(() => { cargarLista(); }, [cargarLista]);
  useEffect(() => { fin.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [actual, pensando]);

  const abrir = async (id) => { setError(""); try { setActual(await asistenteConversacion(id)); } catch (e) { avisar(e.message, "rojo"); } };
  const enviar = async (pregunta) => {
    const q = (pregunta ?? texto).trim();
    if (!q || pensando) return;
    setError(""); setTexto(""); setPensando(true);
    const previo = actual;
    setActual((a) => ({ id: a?.id, titulo: a?.titulo || q, mensajes: [...(a?.mensajes || []), { id: `p${Date.now()}`, rol: "user", texto: q }] }));
    try {
      const r = await asistentePreguntar(q, previo?.id);
      setActual((a) => ({ id: r.conversacion, titulo: r.titulo, mensajes: [...a.mensajes, r.respuesta] }));
      cargarLista(); onCambioLista?.();
    } catch (e) {
      setError(e.message); setTexto(q);
      setActual(previo);
    }
    setPensando(false);
  };
  const borrar = async (c) => {
    if (!(await confirmar({ titulo: "¿Borrar esta conversación?", mensaje: c.titulo, boton: "Borrar", peligro: true }))) return;
    try { await asistenteBorrar(c.id); if (actual?.id === c.id) setActual(null); cargarLista(); } catch (e) { avisar(e.message, "rojo"); }
  };

  const nuevo = () => { setActual(null); setError(""); };
  return (
    <div className="grid gap-4 lg:grid-cols-[15rem_minmax(0,1fr)]">
      <aside className="space-y-2 lg:sticky lg:top-20 lg:self-start">
        <button type="button" onClick={nuevo}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-white px-3 py-2.5 text-sm font-semibold text-azul shadow-sm ring-1 ring-linea transition hover:ring-azul/40">
          <Plus className="size-4" aria-hidden />Nueva conversación
        </button>
        {lista.length > 0 && (
          <div className="rounded-xl bg-white p-1.5 shadow-sm ring-1 ring-linea">
            <p className="px-2 pb-1 pt-1.5 text-[11px] font-semibold uppercase tracking-wide text-gris">Historial</p>
            <ul className="max-h-[12rem] space-y-0.5 overflow-y-auto lg:max-h-[58vh]">
              {lista.map((c) => (
                <li key={c.id} className="group flex items-center">
                  <button type="button" onClick={() => abrir(c.id)}
                    className={cx("flex min-w-0 flex-1 items-center gap-2 rounded-lg px-2 py-2 text-left text-[13px]", actual?.id === c.id ? "bg-azul/10 font-medium text-azul" : "text-tinta hover:bg-fondo")}>
                    <MessageSquare className="size-3.5 shrink-0 opacity-60" aria-hidden /><span className="truncate">{c.titulo}</span>
                  </button>
                  <button type="button" onClick={() => borrar(c)} aria-label={`Borrar «${c.titulo}»`} className="rounded p-1.5 text-gris hover:text-rojo sm:opacity-0 sm:group-hover:opacity-100 focus-visible:opacity-100"><Trash2 className="size-3.5" /></button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </aside>
      <section className="flex min-h-[calc(100dvh-20rem)] flex-col overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-linea">
        <div className="flex-1 space-y-6 overflow-y-auto px-4 py-6 sm:px-8">
          {!actual?.mensajes?.length && (
            <div className="mx-auto flex max-w-2xl flex-col items-center py-4 text-center sm:py-10">
              <span className="relative flex size-14 items-center justify-center rounded-2xl bg-gradient-to-br from-azul to-[#4a3aa8] text-white shadow-lg shadow-azul/25">
                <Sparkles className="size-7" aria-hidden />
                <span className="absolute -right-1 -top-1 size-3.5 rounded-full border-2 border-white bg-amarillo" aria-hidden />
              </span>
              <h2 className="mt-4 font-display text-2xl font-bold text-noche">¿Qué quieres saber hoy?</h2>
              <p className="mt-1.5 max-w-md text-sm text-gris">Respondo con los datos reales de la plataforma, con números y gráficos. Solo veo lo que tú puedes ver.</p>
              <div className="mt-7 grid w-full gap-2.5 sm:grid-cols-2">
                {SUGERENCIAS.filter((s) => s.tema !== "Comercial" || estado.puede_ver.includes("comerciales")).map((s) => (
                  <button key={s.texto} type="button" onClick={() => enviar(s.texto)} disabled={pensando || !estado.activo}
                    className="group flex items-start gap-3 rounded-xl border border-linea bg-white p-3.5 text-left transition hover:-translate-y-0.5 hover:border-azul/40 hover:shadow-md disabled:pointer-events-none disabled:opacity-50 motion-reduce:hover:translate-y-0">
                    <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-azul/10 text-azul transition-colors group-hover:bg-azul group-hover:text-white"><s.icono className="size-4" aria-hidden /></span>
                    <span className="min-w-0"><span className="block text-[11px] font-semibold uppercase tracking-wide text-gris">{s.tema}</span><span className="block text-sm text-tinta">{s.texto}</span></span>
                  </button>
                ))}
              </div>
            </div>
          )}
          {actual?.mensajes?.map((m) => (m.rol === "user" ? (
            <div key={m.id} className="flex justify-end"><p className="max-w-[85%] whitespace-pre-line rounded-2xl rounded-tr-md bg-azul px-4 py-2.5 text-[15px] text-white shadow-sm">{m.texto}</p></div>
          ) : <MensajeIA key={m.id} m={m} />))}
          {pensando && (
            <div className="flex items-center gap-3" aria-live="polite">
              <Avatar />
              <div className="flex items-center gap-2 rounded-2xl bg-fondo px-4 py-3 text-sm text-gris">
                <span className="flex gap-1" aria-hidden>{[0, 1, 2].map((i) => <span key={i} className="size-1.5 animate-bounce rounded-full bg-azul/60" style={{ animationDelay: `${i * 150}ms` }} />)}</span>
                Consultando los datos…
              </div>
            </div>
          )}
          <div ref={fin} />
        </div>
        {error && <Alerta className="mx-4 mb-2">{error}</Alerta>}
        <div className="border-t border-linea-suave bg-gradient-to-b from-white to-fondo/60 p-3 sm:px-6 sm:pb-4">
          <form onSubmit={(e) => { e.preventDefault(); enviar(); }}
            className="flex items-end gap-2 rounded-2xl border border-linea bg-white p-1.5 pl-4 shadow-sm transition focus-within:border-azul/50 focus-within:ring-4 focus-within:ring-azul/10">
            <textarea value={texto} onChange={(e) => setTexto(e.target.value)} rows={1} maxLength={2000} disabled={!estado.activo}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviar(); } }}
              placeholder={estado.activo ? "Pregunta sobre tareas, asistencia, desempeño, órdenes…" : "El asistente todavía no está configurado"}
              className="max-h-40 min-h-10 flex-1 resize-none border-0 bg-transparent py-2 text-[15px] outline-none placeholder:text-gris/80 focus:ring-0" aria-label="Pregunta" />
            <button type="submit" disabled={!estado.activo || !texto.trim() || pensando} aria-label="Preguntar"
              className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-azul text-white transition hover:bg-azul-700 disabled:bg-linea disabled:text-gris">
              {pensando ? <span className="size-4 animate-spin rounded-full border-2 border-white/40 border-t-white" /> : <ArrowUp className="size-5" aria-hidden />}
            </button>
          </form>
          <p className="mt-2 flex flex-wrap items-center justify-between gap-2 px-1 text-[11px] text-gris">
            <span className="inline-flex items-center gap-1"><ShieldCheck className="size-3.5" aria-hidden />Las respuestas salen de los datos; revisa lo importante antes de decidir.</span>
            {estado.activo && <Uso usadas={estado.preguntas_hoy} limite={estado.limite_diario} />}
          </p>
        </div>
      </section>
    </div>
  );
}

const Avatar = () => (
  <span className="flex size-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-azul to-[#4a3aa8] text-white shadow-sm"><Sparkles className="size-4" aria-hidden /></span>
);

function Uso({ usadas, limite }) {
  const pct = Math.min(100, Math.round((usadas / Math.max(1, limite)) * 100));
  return (
    <span className="inline-flex items-center gap-2" title={`${usadas} de ${limite} preguntas hoy`}>
      <span className="h-1.5 w-16 overflow-hidden rounded-full bg-linea"><span className={cx("block h-full rounded-full", pct >= 90 ? "bg-rojo" : "bg-azul")} style={{ width: `${pct}%` }} /></span>
      <span className="num">{usadas}/{limite} hoy</span>
    </span>
  );
}

function MensajeIA({ m }) {
  const avisar = useAviso();
  const [copiado, setCopiado] = useState(false);
  const copiar = async () => {
    const limpio = (m.texto || "").replace(/```grafico[\s\S]*?```/g, "").replace(/\*\*/g, "").trim();
    if (await copiarTexto(limpio)) { setCopiado(true); setTimeout(() => setCopiado(false), 1500); } else avisar("No se pudo copiar.", "rojo");
  };
  return (
    <div className="group flex gap-3">
      <Avatar />
      <div className="min-w-0 flex-1 pt-0.5">
        <Respuesta texto={m.texto} />
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-gris">
          {m.herramientas?.length > 0 && (
            <span className="inline-flex flex-wrap items-center gap-1"><Database className="size-3" aria-hidden />Consultó:
              {[...new Set(m.herramientas.map((h) => NOMBRES_CONSULTA[h] || h))].map((h) => <span key={h} className="rounded-full bg-fondo px-2 py-0.5 font-medium text-tinta ring-1 ring-linea-suave">{h}</span>)}
            </span>
          )}
          <button type="button" onClick={copiar} className="inline-flex items-center gap-1 rounded px-1 py-0.5 hover:bg-fondo hover:text-tinta sm:opacity-0 sm:group-hover:opacity-100 focus-visible:opacity-100">
            {copiado ? <Check className="size-3 text-verde" aria-hidden /> : <Copy className="size-3" aria-hidden />}{copiado ? "Copiado" : "Copiar"}
          </button>
        </div>
      </div>
    </div>
  );
}

const NIVEL = {
  alta: { etiqueta: "Urgente", borde: "border-l-rojo", chip: "bg-rojo-50 text-rojo", icono: "text-rojo" },
  media: { etiqueta: "Atender", borde: "border-l-amarillo-600", chip: "bg-amarillo-50 text-[#8a5a00]", icono: "text-[#a86a00]" },
  info: { etiqueta: "Info", borde: "border-l-linea", chip: "bg-fondo text-gris", icono: "text-gris" },
};

function Analisis() {
  const avisar = useAviso();
  const [d, setD] = useState(undefined);
  const [cargando, setCargando] = useState(false);
  useEffect(() => { asistenteInforme().then((r) => setD(r.informe)).catch((e) => avisar(e.message, "rojo")); }, [avisar]);
  const actualizar = async () => {
    setCargando(true);
    try { setD((await asistenteActualizarInforme()).informe); avisar("Análisis actualizado"); } catch (e) { avisar(e.message, "rojo"); }
    setCargando(false);
  };
  if (d === undefined) return <Cargando />;
  const alertas = d?.alertas || [];
  const urgentes = alertas.filter((a) => a.nivel === "alta").length;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        {[["Urgentes", urgentes, "text-rojo"], ["Para atender", alertas.length - urgentes, "text-[#a86a00]"], ["Temas", new Set(alertas.map((a) => a.tema)).size, "text-azul"]].map(([n, v, c]) => (
          <div key={n} className="rounded-xl bg-white px-4 py-3 shadow-sm ring-1 ring-linea">
            <p className="text-xs font-medium text-gris">{n}</p><p className={cx("num font-display text-2xl font-bold", v ? c : "text-gris")}>{v}</p>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-gris">{d ? `Generado ${fechaHora(d.creado)} · se actualiza solo cada mañana (lunes a sábado).` : "Todavía no hay análisis: se genera cada mañana, o ahora con el botón."}</p>
        <Boton variante="secundario" icono={RefreshCw} cargando={cargando} onClick={actualizar}>Actualizar ahora</Boton>
      </div>
      {d?.texto && (
        <div className="rounded-2xl bg-gradient-to-br from-azul/30 via-[#8a5cc7]/25 to-amarillo/40 p-px">
          <div className="rounded-[15px] bg-white p-5">
            <p className="mb-2 flex items-center gap-2 font-display font-semibold text-noche"><Avatar />Lectura del día</p>
            <Respuesta texto={d.texto} />
          </div>
        </div>
      )}
      {d && (alertas.length === 0 ? <Alerta tono="verde">Todo en orden: no hay alertas hoy.</Alerta> : (
        <ul className="grid gap-2.5">
          {alertas.map((a, i) => {
            const n = NIVEL[a.nivel] || NIVEL.info;
            return (
              <li key={i} className={cx("flex gap-3 rounded-xl border border-l-4 border-linea bg-white p-4 shadow-sm", n.borde)}>
                <AlertTriangle className={cx("mt-0.5 size-5 shrink-0", n.icono)} aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2">
                    <span className={cx("rounded-full px-2 py-0.5 text-[11px] font-semibold", n.chip)}>{n.etiqueta}</span>
                    <span className="text-[11px] font-semibold uppercase tracking-wide text-gris">{a.tema}</span>
                  </p>
                  <p className="mt-1 font-medium text-tinta">{a.titulo}</p>
                  {a.detalle && <p className="mt-0.5 text-sm text-gris">{a.detalle}</p>}
                </div>
                {a.enlace && <Link to={a.enlace} className="shrink-0 self-center rounded-lg px-3 py-1.5 text-sm font-semibold text-azul hover:bg-azul/5">Ver →</Link>}
              </li>
            );
          })}
        </ul>
      ))}
    </div>
  );
}

export default function Asistente() {
  const [estado, setEstado] = useState(null);
  const [error, setError] = useState("");
  const [params, setParams] = useSearchParams();
  useEffect(() => { asistenteEstado().then(setEstado).catch((e) => setError(e.message)); }, []);
  if (error) return <Alerta>{error}</Alerta>;
  if (!estado) return <Cargando />;
  const ver = params.get("ver") === "analisis" && estado.recibe_analisis ? "analisis" : "chat";
  const pestanas = [{ valor: "chat", etiqueta: "Preguntar", icono: MessageSquare }, { valor: "analisis", etiqueta: "Análisis del día", icono: TrendingUp }];
  return (
    <div className="space-y-5 pb-16">
      <header className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-[#16357a] via-azul to-[#4a3aa8] px-5 py-6 text-white shadow-sm md:px-8">
        <span className="pointer-events-none absolute -right-10 -top-16 size-56 rounded-full bg-white/10 blur-2xl" aria-hidden />
        <span className="pointer-events-none absolute -bottom-20 right-32 size-40 rounded-full bg-amarillo/25 blur-2xl" aria-hidden />
        <div className="relative flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0">
            <p className="inline-flex items-center gap-1.5 rounded-full bg-white/15 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide"><Sparkles className="size-3.5 text-amarillo" aria-hidden />Inteligencia artificial</p>
            <h1 className="mt-2 text-[26px] font-bold leading-tight !text-white md:text-3xl">Asistente IA</h1>
            <p className="mt-1 max-w-[62ch] text-sm text-white/80">Pregunta en tus palabras y te respondo con los datos de la plataforma. Puedes ver: {estado.puede_ver}.</p>
          </div>
          {estado.recibe_analisis && (
            <div className="inline-flex rounded-xl bg-white/10 p-1 ring-1 ring-white/20" role="tablist">
              {pestanas.map((p) => (
                <button key={p.valor} type="button" role="tab" aria-selected={ver === p.valor} onClick={() => setParams(p.valor === "chat" ? {} : { ver: p.valor })}
                  className={cx("inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-semibold transition", ver === p.valor ? "bg-white text-azul shadow" : "text-white/85 hover:bg-white/10")}>
                  <p.icono className="size-4" aria-hidden />{p.etiqueta}
                </button>
              ))}
            </div>
          )}
        </div>
      </header>
      {!estado.activo && <Alerta tono="amarillo">El asistente con IA todavía no está activado: falta configurar la clave de la API en el servidor. {estado.recibe_analisis ? "El análisis del día funciona igual, con alertas calculadas (sin la lectura de la IA)." : ""}</Alerta>}
      {ver === "analisis" ? <Analisis /> : <Chat estado={estado} onCambioLista={() => asistenteEstado().then(setEstado).catch(() => {})} />}
    </div>
  );
}
