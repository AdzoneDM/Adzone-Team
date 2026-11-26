// Asistente con IA: preguntas en lenguaje natural sobre los datos de la plataforma (con los permisos de cada quien)
// y el análisis del día con alertas para Dirección y quien gestiona un área.
import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AlertTriangle, Database, Plus, RefreshCw, SendHorizontal, Sparkles, Trash2 } from "lucide-react";
import {
  asistenteActualizarInforme, asistenteBorrar, asistenteConversacion, asistenteConversaciones, asistenteEstado, asistenteInforme, asistentePreguntar,
} from "@/lib/api";
import { fechaHora } from "@/lib/formato";
import { Alerta, Boton, Cabecera, Cargando, Insignia, Panel, Pestanas, cx, useAviso, useConfirmar } from "@/components/ui";
import Grafico, { leerGrafico } from "./Grafico";

const SUGERENCIAS = [
  "¿Quién tiene más tareas vencidas y cuáles son?",
  "¿Cómo va la puntualidad de mi equipo este mes?",
  "Compara el desempeño de este mes con el anterior",
  "¿Qué órdenes de trabajo están atrasadas?",
  "¿Cómo van las oportunidades comerciales?",
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

  return (
    <div className="grid gap-4 lg:grid-cols-[16rem_minmax(0,1fr)]">
      <aside className="space-y-2">
        <Boton icono={Plus} variante="secundario" className="w-full" onClick={() => { setActual(null); setError(""); }}>Nueva conversación</Boton>
        {lista.length > 0 && (
          <ul className="max-h-[14rem] space-y-0.5 overflow-y-auto rounded-xl border border-linea bg-white p-1 lg:max-h-[60vh]">
            {lista.map((c) => (
              <li key={c.id} className="group flex items-center">
                <button type="button" onClick={() => abrir(c.id)} className={cx("min-w-0 flex-1 truncate rounded-lg px-2.5 py-2 text-left text-sm", actual?.id === c.id ? "bg-azul/10 font-medium text-azul" : "hover:bg-fondo")}>{c.titulo}</button>
                <button type="button" onClick={() => borrar(c)} aria-label={`Borrar «${c.titulo}»`} className="rounded p-1.5 text-gris hover:text-rojo sm:opacity-0 sm:group-hover:opacity-100"><Trash2 className="size-3.5" /></button>
              </li>
            ))}
          </ul>
        )}
      </aside>
      <section className="flex min-h-[60vh] flex-col overflow-hidden rounded-xl border border-linea bg-white">
        <div className="flex-1 space-y-4 overflow-y-auto p-4 sm:p-5">
          {!actual?.mensajes?.length && (
            <div className="space-y-4 py-6 text-center">
              <span className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-azul/10 text-azul"><Sparkles className="size-6" /></span>
              <div><p className="font-display text-lg font-semibold">Pregúntale a Adzone</p>
                <p className="mx-auto max-w-md text-sm text-gris">Respondo con los datos reales de la plataforma: tareas, asistencia, desempeño, órdenes, comercial{estado.puede_ver.includes("finanzas") ? " y finanzas" : ""}. Solo veo lo que tú puedes ver.</p></div>
              <div className="flex flex-wrap justify-center gap-2">
                {SUGERENCIAS.map((s) => <button key={s} type="button" onClick={() => enviar(s)} disabled={pensando || !estado.activo} className="rounded-full border border-linea px-3 py-1.5 text-sm hover:border-azul hover:text-azul disabled:opacity-50">{s}</button>)}
              </div>
            </div>
          )}
          {actual?.mensajes?.map((m) => (m.rol === "user" ? (
            <div key={m.id} className="flex justify-end"><p className="max-w-[85%] whitespace-pre-line rounded-2xl rounded-br-md bg-azul px-4 py-2.5 text-[15px] text-white">{m.texto}</p></div>
          ) : (
            <div key={m.id} className="flex gap-3">
              <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full bg-azul/10 text-azul"><Sparkles className="size-4" /></span>
              <div className="min-w-0 flex-1">
                <Respuesta texto={m.texto} />
                {m.herramientas?.length > 0 && (
                  <p className="mt-1.5 flex flex-wrap items-center gap-1 text-[11px] text-gris"><Database className="size-3" aria-hidden />Consultó: {[...new Set(m.herramientas.map((h) => NOMBRES_CONSULTA[h] || h))].join(", ")}</p>
                )}
              </div>
            </div>
          )))}
          {pensando && (
            <div className="flex items-center gap-3 text-sm text-gris" aria-live="polite">
              <span className="flex size-8 items-center justify-center rounded-full bg-azul/10 text-azul"><Sparkles className="size-4 animate-pulse" /></span>
              Consultando los datos… puede tardar unos segundos.
            </div>
          )}
          <div ref={fin} />
        </div>
        {error && <Alerta className="mx-4 mb-2">{error}</Alerta>}
        <form onSubmit={(e) => { e.preventDefault(); enviar(); }} className="flex items-end gap-2 border-t border-linea p-3">
          <textarea value={texto} onChange={(e) => setTexto(e.target.value)} rows={1} maxLength={2000} disabled={!estado.activo}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviar(); } }}
            placeholder={estado.activo ? "Escribe tu pregunta sobre los datos…" : "El asistente todavía no está configurado"}
            className="campo max-h-40 min-h-11 flex-1 resize-none" aria-label="Pregunta" />
          <Boton type="submit" icono={SendHorizontal} cargando={pensando} disabled={!estado.activo || !texto.trim()} aria-label="Preguntar">Preguntar</Boton>
        </form>
        {estado.activo && <p className="px-3 pb-2 text-[11px] text-gris">{estado.preguntas_hoy} de {estado.limite_diario} preguntas hoy · Las respuestas salen de los datos, pero revisa lo importante antes de decidir.</p>}
      </section>
    </div>
  );
}

const TONO = { alta: "rojo", media: "amarillo", info: "neutro" };

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
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-gris">{d ? `Generado ${fechaHora(d.creado)} · se actualiza solo cada mañana (lunes a sábado).` : "Todavía no hay análisis: se genera cada mañana, o ahora con el botón."}</p>
        <Boton variante="secundario" icono={RefreshCw} cargando={cargando} onClick={actualizar}>Actualizar ahora</Boton>
      </div>
      {d?.texto && (
        <Panel titulo={<span className="flex items-center gap-2"><Sparkles className="size-4 text-azul" />Lectura del día</span>}>
          <Respuesta texto={d.texto} />
        </Panel>
      )}
      {d && (d.alertas.length === 0 ? <Alerta tono="verde">Todo en orden: no hay alertas hoy.</Alerta> : (
        <ul className="grid gap-2">
          {d.alertas.map((a, i) => (
            <li key={i} className="flex gap-3 rounded-xl border border-linea bg-white p-4">
              <AlertTriangle className={cx("mt-0.5 size-5 shrink-0", a.nivel === "alta" ? "text-rojo" : "text-[#a86a00]")} aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-2 font-medium"><Insignia tono={TONO[a.nivel]}>{a.nivel === "alta" ? "Urgente" : a.nivel === "media" ? "Atender" : "Info"}</Insignia>{a.titulo}</p>
                {a.detalle && <p className="mt-0.5 text-sm text-gris">{a.detalle}</p>}
              </div>
              {a.enlace && <Link to={a.enlace} className="shrink-0 self-center text-sm font-medium text-azul hover:underline">Ver</Link>}
            </li>
          ))}
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
  return (
    <div className="space-y-5">
      <Cabecera titulo="Asistente IA" descripcion={`Pregunta en tus palabras y responde con los datos de la plataforma. Ves: ${estado.puede_ver}.`} />
      {!estado.activo && <Alerta tono="amarillo">El asistente con IA todavía no está activado: falta configurar la clave de la API en el servidor. {estado.recibe_analisis ? "El análisis del día funciona igual, con alertas calculadas (sin la lectura de la IA)." : ""}</Alerta>}
      {estado.recibe_analisis && <Pestanas opciones={[{ valor: "chat", etiqueta: "Preguntar" }, { valor: "analisis", etiqueta: "Análisis del día" }]} valor={ver} onCambio={(v) => setParams(v === "chat" ? {} : { ver: v })} />}
      {ver === "analisis" ? <Analisis /> : <Chat estado={estado} onCambioLista={() => asistenteEstado().then(setEstado).catch(() => {})} />}
    </div>
  );
}
