// Recordatorios: notas personales que te avisan a la hora que elijas (una reunión, ir a un lugar…).
// No son tareas: no suman al puntaje, ni a los KPI, ni cambian «quién está libre». Solo los ve su dueño.
import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AlarmClock, Check, ChevronDown, Pencil, Plus, Repeat, RotateCcw, Trash2 } from "lucide-react";
import { accionRecordatorio, borrarRecordatorio, guardarRecordatorio, listarRecordatorios } from "@/lib/api";
import { useNovedades } from "@/lib/novedades";
import { Alerta, Boton, Cabecera, Campo, Cargando, Insignia, Modal, Vacio, cx, useAviso, useConfirmar } from "@/components/ui";

const REPETIR = { NO: "No se repite", DIARIO: "Cada día", SEMANAL: "Cada semana", MENSUAL: "Cada mes" };
const pad = (n) => String(n).padStart(2, "0");
/** Valor para un <input type="datetime-local"> (hora local de quien lo usa). */
const paraInput = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
const enMinutos = (m) => { const d = new Date(Date.now() + m * 60000); d.setSeconds(0, 0); return d; };
const mananaA = (hora) => { const d = new Date(); d.setDate(d.getDate() + 1); d.setHours(hora, 0, 0, 0); return d; };
const hora12 = (d) => d.toLocaleTimeString("es-DO", { hour: "numeric", minute: "2-digit" });

/** «Hoy 3:00 p. m.», «Mañana 9:00 a. m.» o «vie, 27 nov · 2:00 p. m.». */
export function cuando(iso, ahora = new Date()) {
  const d = new Date(iso);
  const dia = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate());
  const dif = Math.round((dia(d) - dia(ahora)) / 86400000);
  const etiqueta = dif === 0 ? "Hoy" : dif === 1 ? "Mañana" : dif === -1 ? "Ayer" : d.toLocaleDateString("es-DO", { weekday: "short", day: "numeric", month: "short" });
  return `${etiqueta}${dif === 0 || dif === 1 || dif === -1 ? " " : " · "}${hora12(d)}`;
}

const ATAJOS = [
  ["En 30 min", () => enMinutos(30)],
  ["En 1 hora", () => enMinutos(60)],
  ["Mañana 9:00", () => mananaA(9)],
];

function Formulario({ inicial, onGuardado, onCancelar, referencia }) {
  const avisar = useAviso();
  const [f, setF] = useState(() => (inicial
    ? { titulo: inicial.titulo, nota: inicial.nota || "", cuando: paraInput(new Date(inicial.recordar_en)), repetir: inicial.repetir }
    : { titulo: "", nota: "", cuando: paraInput(enMinutos(60)), repetir: "NO" }));
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [conNota, setConNota] = useState(!!inicial?.nota);
  const guardar = async (e) => {
    e.preventDefault();
    if (!f.titulo.trim()) return setError("Escribe de qué te vamos a recordar.");
    const fecha = new Date(f.cuando);
    if (Number.isNaN(fecha.getTime())) return setError("Elige la fecha y la hora.");
    setGuardando(true); setError("");
    try {
      const guardado = await guardarRecordatorio({ id: inicial?.id, titulo: f.titulo.trim(), nota: f.nota.trim(), recordar_en: fecha.toISOString(), repetir: f.repetir });
      avisar(inicial ? "Cambios guardados." : `Listo: te avisaremos ${cuando(guardado.recordar_en).toLowerCase()}.`);
      if (!inicial) { setF({ titulo: "", nota: "", cuando: paraInput(enMinutos(60)), repetir: "NO" }); setConNota(false); }
      onGuardado(guardado);
    } catch (err) { setError(err.message); }
    setGuardando(false);
  };
  return (
    <form onSubmit={guardar} className="space-y-3">
      {error && <Alerta>{error}</Alerta>}
      <Campo etiqueta="¿De qué te recordamos?">
        {(id) => <input id={id} ref={referencia} className="campo" value={f.titulo} onChange={(e) => setF({ ...f, titulo: e.target.value })} maxLength={120} placeholder="Ej.: Reunión con el cliente en su oficina" />}
      </Campo>
      <div className="grid gap-3 sm:grid-cols-2">
        <Campo etiqueta="¿Cuándo?">
          {(id) => <input id={id} type="datetime-local" className="campo" value={f.cuando} onChange={(e) => setF({ ...f, cuando: e.target.value })} />}
        </Campo>
        <Campo etiqueta="Repetir">
          {(id) => <select id={id} className="campo" value={f.repetir} onChange={(e) => setF({ ...f, repetir: e.target.value })}>{Object.entries(REPETIR).map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select>}
        </Campo>
      </div>
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Atajos de hora">
        {ATAJOS.map(([texto, fn]) => (
          <button key={texto} type="button" onClick={() => setF({ ...f, cuando: paraInput(fn()) })}
            className="rounded-full border border-linea bg-white px-3 py-1 text-xs font-medium text-tinta hover:border-azul hover:text-azul">{texto}</button>
        ))}
      </div>
      {conNota
        ? <Campo etiqueta="Nota (opcional)">{(id) => <textarea id={id} rows={2} className="campo" value={f.nota} onChange={(e) => setF({ ...f, nota: e.target.value })} maxLength={1000} placeholder="Dirección, qué llevar, con quién…" />}</Campo>
        : <button type="button" onClick={() => setConNota(true)} className="text-sm font-medium text-azul hover:underline">+ Agregar una nota</button>}
      <div className="flex justify-end gap-2">
        {onCancelar && <Boton variante="secundario" onClick={onCancelar}>Cancelar</Boton>}
        <Boton type="submit" icono={inicial ? Check : Plus} cargando={guardando}>{inicial ? "Guardar cambios" : "Crear recordatorio"}</Boton>
      </div>
    </form>
  );
}

function Tarjeta({ r, onCambio, onEditar, onBorrar }) {
  const avisar = useAviso();
  const [ocupado, setOcupado] = useState(false);
  const correr = async (accion, cuerpo) => {
    setOcupado(true);
    try { onCambio(await accionRecordatorio(r.id, accion, cuerpo)); } catch (e) { avisar(e.message, "rojo"); }
    setOcupado(false);
  };
  const sono = r.estado === "AVISADO";
  const hecho = r.estado === "HECHO";
  return (
    <li className={cx("rounded-xl border bg-white p-4", sono ? "border-amarillo/60 bg-amarillo-50/40" : "border-linea", hecho && "opacity-70")}>
      <div className="flex items-start gap-3">
        <span className={cx("mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-xl", sono ? "bg-amarillo-50 text-[#a86a00]" : hecho ? "bg-verde-50 text-verde" : "bg-azul/10 text-azul")}>
          {hecho ? <Check className="size-4" aria-hidden /> : <AlarmClock className="size-4" aria-hidden />}
        </span>
        <div className="min-w-0 flex-1">
          <p className={cx("font-medium leading-snug", hecho && "line-through")}>{r.titulo}</p>
          {r.nota && <p className="mt-0.5 line-clamp-2 whitespace-pre-line text-sm text-gris">{r.nota}</p>}
          <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-gris">
            <span className={cx(sono && "font-medium text-[#a86a00]")}>{sono ? `Sonó ${cuando(r.recordar_en).toLowerCase()}` : cuando(r.recordar_en)}</span>
            {r.repetir !== "NO" && <Insignia tono="azul"><Repeat className="size-3" aria-hidden />{REPETIR[r.repetir]}</Insignia>}
          </p>
        </div>
        <div className="flex shrink-0 gap-0.5">
          {!hecho && <button type="button" onClick={() => onEditar(r)} aria-label={`Editar ${r.titulo}`} title="Editar" className="rounded-lg p-2 text-gris hover:bg-fondo hover:text-azul"><Pencil className="size-4" /></button>}
          <button type="button" onClick={() => onBorrar(r)} aria-label={`Borrar ${r.titulo}`} title="Borrar" className="rounded-lg p-2 text-gris hover:bg-fondo hover:text-rojo"><Trash2 className="size-4" /></button>
        </div>
      </div>
      {sono && r.repetir === "NO" && (
        <div className="mt-3 flex flex-wrap items-center gap-2 pl-12">
          <Boton tam="sm" icono={Check} cargando={ocupado} onClick={() => correr("hecho")}>Listo</Boton>
          <span className="text-xs text-gris">Posponer:</span>
          {[["10 min", 10], ["1 hora", 60], ["Mañana 9:00", Math.max(1, Math.round((mananaA(9) - new Date()) / 60000))]].map(([texto, min]) => (
            <button key={texto} type="button" disabled={ocupado} onClick={() => correr("posponer", { minutos: min })}
              className="rounded-full border border-linea bg-white px-3 py-1 text-xs font-medium text-tinta hover:border-azul hover:text-azul disabled:opacity-50">{texto}</button>
          ))}
        </div>
      )}
      {hecho && <div className="mt-2 pl-12"><button type="button" onClick={() => correr("reabrir")} disabled={ocupado} className="inline-flex items-center gap-1 text-xs font-medium text-azul hover:underline"><RotateCcw className="size-3" aria-hidden />Volver a pendientes</button></div>}
    </li>
  );
}

export default function Recordatorios() {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const [params, setParams] = useSearchParams();
  const [lista, setLista] = useState(null);
  const [error, setError] = useState("");
  const [editando, setEditando] = useState(null);
  const [verHechos, setVerHechos] = useState(false);
  const titulo = useRef(null);
  const cargar = useCallback(() => listarRecordatorios().then((l) => { setLista(l); setError(""); }).catch((e) => setError(e.message)), []);
  useEffect(() => { cargar(); }, [cargar]);
  useNovedades(cargar); // cuando suena uno, la lista se actualiza sola
  useEffect(() => {
    if (params.get("nuevo") === "1") { titulo.current?.focus(); params.delete("nuevo"); setParams(params, { replace: true }); }
  }, [params, setParams]);

  const poner = (r) => setLista((l) => (l || []).map((x) => (x.id === r.id ? r : x)));
  const agregar = (r) => setLista((l) => [...(l || []).filter((x) => x.id !== r.id), r]);
  const borrar = async (r) => {
    if (!(await confirmar({ titulo: `¿Borrar «${r.titulo}»?`, boton: "Borrar", peligro: true }))) return;
    try { await borrarRecordatorio(r.id); setLista((l) => l.filter((x) => x.id !== r.id)); } catch (e) { avisar(e.message, "rojo"); }
  };
  const por = (estado) => (lista || []).filter((r) => r.estado === estado).sort((a, b) => new Date(a.recordar_en) - new Date(b.recordar_en));
  const pendientes = por("PENDIENTE");
  const sonaron = por("AVISADO");
  const hechos = por("HECHO").reverse();
  const tarjeta = (r) => <Tarjeta key={r.id} r={r} onCambio={poner} onEditar={setEditando} onBorrar={borrar} />;
  return (
    <div className="mx-auto max-w-3xl">
      <Cabecera titulo="Recordatorios" descripcion="Notas que te avisan a la hora que elijas: una reunión, ir a un lugar… No son tareas: no suman a tu puntaje ni a tus KPI." />
      <section className="mb-6 rounded-xl border border-linea bg-white p-4 md:p-5" aria-label="Nuevo recordatorio">
        <Formulario onGuardado={agregar} referencia={titulo} />
      </section>
      {error && <Alerta>{error}</Alerta>}
      {!lista && !error ? <Cargando /> : lista && (
        <div className="space-y-6">
          {sonaron.length > 0 && (
            <section>
              <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-[#a86a00]">Ya sonaron ({sonaron.length})</h2>
              <ul className="space-y-2">{sonaron.map(tarjeta)}</ul>
            </section>
          )}
          <section>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gris">Pendientes ({pendientes.length})</h2>
            {pendientes.length === 0
              ? <Vacio icono={AlarmClock} titulo="Sin recordatorios pendientes">Crea uno arriba: te avisamos en la campanita y, si activaste los avisos, también en tu celular.</Vacio>
              : <ul className="space-y-2">{pendientes.map(tarjeta)}</ul>}
          </section>
          {hechos.length > 0 && (
            <section>
              <button type="button" onClick={() => setVerHechos((v) => !v)} aria-expanded={verHechos} className="mb-2 flex items-center gap-1 text-sm font-semibold uppercase tracking-wide text-gris hover:text-tinta">
                Hechos ({hechos.length})<ChevronDown className={cx("size-4 transition-transform", verHechos && "rotate-180")} aria-hidden />
              </button>
              {verHechos && <ul className="space-y-2">{hechos.map(tarjeta)}</ul>}
            </section>
          )}
          <p className="text-xs text-gris">Para que te lleguen con la aplicación cerrada, activa los avisos en <b>Mi cuenta → Avisos en el celular</b>.</p>
        </div>
      )}
      <Modal abierto={!!editando} onCerrar={() => setEditando(null)} titulo="Editar recordatorio">
        {editando && <Formulario inicial={editando} onGuardado={(r) => { poner(r); setEditando(null); }} onCancelar={() => setEditando(null)} />}
      </Modal>
    </div>
  );
}
