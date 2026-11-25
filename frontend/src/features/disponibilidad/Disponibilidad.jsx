// Quién está libre: tablero público para todos los departamentos, para pedir ayuda a quien no tiene tareas.
// Solo muestra CUÁNTAS tareas tiene cada persona y su próxima entrega; nunca de qué son.
import { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarClock, ChevronDown, ChevronsDownUp, ChevronsUpDown, Clock, HandHeart, Info, ListChecks, MessageCircle, Plus, RefreshCw, Search, UsersRound, X } from "lucide-react";
import { crearColaboracion, disponibilidad, equipo } from "@/lib/api";
import { fechaCorta } from "@/lib/formato";
import { useNovedades } from "@/lib/novedades";
import FormTarea from "@/features/tareas/FormTarea";
import { Alerta, Avatar, Boton, Cabecera, Campo, Cargando, Insignia, Modal, Vacio, cx, useAviso } from "@/components/ui";

const ESTADO = {
  LIBRE: { texto: "Libre", tono: "verde", orden: 0 },
  POCA: { texto: "Poca carga", tono: "amarillo", orden: 1 },
  OCUPADO: { texto: "Ocupado/a", tono: "rojo", orden: 2 },
  AUSENTE: { texto: "No disponible hoy", tono: "neutro", orden: 3 },
};
const horas = (h) => (!h ? "" : `~${h % 1 ? h.toFixed(1) : h} h`);

function PedirApoyo({ persona, onCerrar, onHecho }) {
  const avisar = useAviso();
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { setTexto(""); setError(""); }, [persona?.id]);
  if (!persona) return null;
  const enviar = async () => {
    if (texto.trim().length < 5) return setError("Cuéntale en qué necesitas apoyo (unas palabras).");
    setEnviando(true); setError("");
    try {
      await crearColaboracion({ ayudante: persona.id, descripcion: texto.trim() });
      avisar(`Le llegó tu pedido de apoyo a ${persona.nombre}.`);
      onHecho();
    } catch (e) { setError(e.message); }
    setEnviando(false);
  };
  return (
    <Modal abierto onCerrar={onCerrar} titulo={`Pedir apoyo a ${persona.nombre}`} descripcion={`${persona.puesto} · ${persona.departamento}`}
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton icono={HandHeart} cargando={enviando} onClick={enviar}>Pedir apoyo</Boton></>}>
      <div className="space-y-3">
        {error && <Alerta>{error}</Alerta>}
        <Campo etiqueta="¿En qué necesitas apoyo?" ayuda="Le llega un aviso. Si acepta y te ayuda, queda registrado como colaboración (y cuenta para su avance).">
          {(id) => <textarea id={id} className="campo" rows={4} value={texto} onChange={(e) => setTexto(e.target.value)} maxLength={500} placeholder="Ej.: Necesito ayuda editando un video de 1 minuto para mañana" autoFocus />}
        </Campo>
      </div>
    </Modal>
  );
}

const COLOR = {
  LIBRE: { punto: "bg-verde", barra: "bg-verde", borde: "border-l-verde", tile: "border-verde/40 bg-verde-50/50 text-verde", activo: "border-verde bg-verde text-white" },
  POCA: { punto: "bg-amarillo", barra: "bg-amarillo", borde: "border-l-amarillo", tile: "border-amarillo/50 bg-amarillo-50/60 text-[#a86a00]", activo: "border-amarillo bg-amarillo text-noche" },
  OCUPADO: { punto: "bg-rojo", barra: "bg-rojo", borde: "border-l-rojo", tile: "border-rojo/30 bg-rojo-50/60 text-rojo", activo: "border-rojo bg-rojo text-white" },
  AUSENTE: { punto: "bg-gris", barra: "bg-linea", borde: "border-l-linea", tile: "border-linea bg-fondo text-gris", activo: "border-gris bg-gris text-white" },
};

function Tarjeta({ p, onApoyo, onAsignar }) {
  const e = ESTADO[p.estado];
  return (
    <article className={cx("flex flex-col gap-3 rounded-2xl border border-l-4 bg-white p-4 transition-shadow hover:shadow-sm", COLOR[p.estado].borde, p.estado === "LIBRE" ? "border-verde/30" : "border-linea")}>
      <div className="flex items-start gap-3">
        <span className="relative shrink-0">
          <Avatar nombre={p.nombre} />
          <span className={cx("absolute -bottom-0.5 -right-0.5 size-3.5 rounded-full border-2 border-white", COLOR[p.estado].punto)} role="img" aria-label={e.texto} />
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="truncate !text-[15px] font-semibold !text-noche">{p.nombre}{p.es_yo && <span className="ml-1.5 text-xs font-normal text-gris">(tú)</span>}</h3>
          <p className="line-clamp-2 text-sm leading-snug text-gris">{p.puesto}</p>
        </div>
        <Insignia tono={e.tono} className="shrink-0">{e.texto}</Insignia>
      </div>
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg bg-fondo px-3 py-2 text-sm text-gris">
        {p.estado === "AUSENTE" ? <span className="flex items-center gap-1.5"><CalendarClock className="size-3.5" aria-hidden />De permiso o vacaciones hoy</span>
          : p.tareas_abiertas === 0
            ? <span className="flex items-center gap-1.5"><ListChecks className="size-3.5 text-verde" aria-hidden />Sin tareas abiertas{p.en_revision > 0 && <> · {p.en_revision} esperando validación</>}</span>
            : <>
              <span className="flex items-center gap-1.5"><ListChecks className="size-3.5" aria-hidden /><b className="text-tinta">{p.tareas_abiertas}</b> {p.tareas_abiertas === 1 ? "tarea abierta" : "tareas abiertas"}</span>
              {horas(p.horas_pendientes) && <span className="flex items-center gap-1.5"><Clock className="size-3.5" aria-hidden />{horas(p.horas_pendientes)}</span>}
              {p.proxima_entrega && <span className="flex items-center gap-1.5"><CalendarClock className="size-3.5" aria-hidden />Próxima entrega {fechaCorta(p.proxima_entrega)}</span>}
            </>}
      </p>
      {!p.es_yo && (
        <div className="mt-auto flex flex-wrap gap-2">
          {p.puedo_pedir_apoyo && <Boton tam="sm" variante={p.estado === "LIBRE" ? "primario" : "secundario"} icono={HandHeart} onClick={() => onApoyo(p)}>Pedir apoyo</Boton>}
          <Boton tam="sm" variante="secundario" icono={MessageCircle} onClick={() => window.dispatchEvent(new CustomEvent("adzone:abrir-chat", { detail: { id: p.id, nombre: p.nombre } }))}>Escribirle</Boton>
          {p.puedo_asignar && <Boton tam="sm" variante="secundario" icono={Plus} onClick={() => onAsignar(p)}>Asignar tarea</Boton>}
        </div>
      )}
      {!p.es_yo && !p.puedo_pedir_apoyo && p.departamento_id != null && (
        <p className="-mt-1 text-xs text-gris">De otro departamento: escríbele, o pide el apoyo formal por tu supervisor.</p>
      )}
    </article>
  );
}

/** Barra apilada con cómo está un departamento: cuántos libres, con poca carga, ocupados o ausentes. */
function BarraEstado({ lista }) {
  const n = lista.length || 1;
  return (
    <span className="flex h-2 w-24 overflow-hidden rounded-full bg-linea-suave" role="img"
      aria-label={["LIBRE", "POCA", "OCUPADO", "AUSENTE"].map((k) => `${lista.filter((x) => x.estado === k).length} ${ESTADO[k].texto.toLowerCase()}`).join(", ")}>
      {["LIBRE", "POCA", "OCUPADO", "AUSENTE"].map((k) => { const c = lista.filter((x) => x.estado === k).length; return c ? <span key={k} className={COLOR[k].barra} style={{ width: `${(100 * c) / n}%` }} /> : null; })}
    </span>
  );
}

function Resumen({ etiqueta, valor, clave, activa, onElegir }) {
  const c = COLOR[clave];
  return (
    <button type="button" onClick={onElegir} aria-pressed={activa}
      className={cx("flex flex-col items-start rounded-2xl border px-4 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-azul/25",
        activa ? c.activo : c.tile)}>
      <span className="font-display text-3xl font-bold leading-none">{valor}</span>
      <span className={cx("mt-1 text-sm font-medium", activa ? "" : "text-tinta")}>{etiqueta}</span>
    </button>
  );
}

export default function Disponibilidad() {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  const [vista, setVista] = useState("libres");
  const [buscar, setBuscar] = useState("");
  const [depto, setDepto] = useState("");
  const [cerrados, setCerrados] = useState(() => new Set());
  const [apoyo, setApoyo] = useState(null);
  const [asignando, setAsignando] = useState(null);
  const [gente, setGente] = useState([]);
  const avisar = useAviso();

  const cargar = useCallback(() => disponibilidad().then((d) => { setDatos(d); setError(""); }).catch((e) => setError(e.message)), []);
  useEffect(() => { cargar(); }, [cargar]);
  useNovedades(cargar, 30000);
  const asignar = async (p) => { if (!gente.length) { try { setGente(await equipo()); } catch { /* el formulario avisa */ } } setAsignando(p); };

  const deptos = useMemo(() => [...new Set((datos?.personas || []).map((p) => p.departamento).filter(Boolean))].sort(), [datos]);
  const filtradas = useMemo(() => (datos?.personas || []).filter((p) => {
    if (vista === "libres" && p.estado !== "LIBRE") return false;
    if (vista === "poca" && p.estado !== "POCA") return false;
    if (vista === "ocupados" && p.estado !== "OCUPADO") return false;
    if (vista === "ausentes" && p.estado !== "AUSENTE") return false;
    if (depto && p.departamento !== depto) return false;
    const t = buscar.toLowerCase();
    return !t || [p.nombre, p.puesto, p.departamento].some((x) => (x || "").toLowerCase().includes(t));
  }), [datos, vista, buscar, depto]);
  const grupos = useMemo(() => {
    const m = new Map();
    filtradas.forEach((p) => { const k = p.departamento || "Sin departamento"; (m.get(k) || m.set(k, []).get(k)).push(p); });
    return [...m.entries()].map(([k, l]) => [k, l.sort((a, b) => ESTADO[a.estado].orden - ESTADO[b.estado].orden || a.tareas_abiertas - b.tareas_abiertas || a.nombre.localeCompare(b.nombre))])
      .sort((a, b) => b[1].filter((x) => x.estado === "LIBRE").length - a[1].filter((x) => x.estado === "LIBRE").length || a[0].localeCompare(b[0]));
  }, [filtradas]);
  const alternar = (k) => setCerrados((c) => { const n = new Set(c); if (n.has(k)) n.delete(k); else n.add(k); return n; });
  const todoCerrado = grupos.length > 0 && grupos.every(([k]) => cerrados.has(k));

  if (error && !datos) return <Alerta>{error}</Alerta>;
  if (!datos) return <Cargando />;
  const r = datos.resumen;
  const ausentes = datos.personas.filter((p) => p.estado === "AUSENTE").length;

  return (
    <div>
      <Cabecera titulo="Quién está libre" descripcion="Personas de todos los departamentos que pueden apoyarte: pídeles ayuda o escríbeles. Solo se ve cuántas tareas tiene cada quien, nunca de qué son.">
        <Boton variante="secundario" icono={RefreshCw} onClick={cargar}>Actualizar</Boton>
      </Cabecera>

      <div className="mb-4 grid grid-cols-2 gap-2.5 md:grid-cols-5" role="group" aria-label="Filtrar por disponibilidad">
        <Resumen etiqueta="Libres" valor={r.libres} clave="LIBRE" activa={vista === "libres"} onElegir={() => setVista("libres")} />
        <Resumen etiqueta="Poca carga" valor={r.poca_carga} clave="POCA" activa={vista === "poca"} onElegir={() => setVista("poca")} />
        <Resumen etiqueta="Ocupados" valor={r.ocupados} clave="OCUPADO" activa={vista === "ocupados"} onElegir={() => setVista("ocupados")} />
        <Resumen etiqueta="No disponibles hoy" valor={ausentes} clave="AUSENTE" activa={vista === "ausentes"} onElegir={() => setVista("ausentes")} />
        <button type="button" onClick={() => setVista("todos")} aria-pressed={vista === "todos"}
          className={cx("col-span-2 flex items-center justify-between rounded-2xl border px-4 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-azul/25 md:col-span-1 md:flex-col md:items-start md:justify-start",
            vista === "todos" ? "border-noche bg-noche text-white" : "border-linea bg-white text-tinta hover:border-azul/50")}>
          <span className="font-display text-3xl font-bold leading-none">{datos.personas.length}</span>
          <span className="mt-1 text-sm font-medium">Todas las personas</span>
        </button>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="relative min-w-52 flex-1 md:max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" aria-hidden />
          <input className="campo h-11 !pl-9 !pr-9" placeholder="Buscar persona o puesto…" value={buscar} onChange={(e) => setBuscar(e.target.value)} aria-label="Buscar persona" />
          {buscar && <button type="button" onClick={() => setBuscar("")} aria-label="Borrar búsqueda" className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-gris hover:text-tinta"><X className="size-4" /></button>}
        </div>
        <select className="campo h-11 w-auto py-0" value={depto} onChange={(e) => setDepto(e.target.value)} aria-label="Departamento">
          <option value="">Todos los departamentos</option>
          {deptos.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
        {grupos.length > 1 && (
          <button type="button" onClick={() => setCerrados(todoCerrado ? new Set() : new Set(grupos.map(([k]) => k)))}
            className="ml-auto inline-flex h-11 items-center gap-2 rounded-lg border border-linea bg-white px-3 text-sm font-medium text-tinta hover:bg-fondo">
            {todoCerrado ? <ChevronsUpDown className="size-4" aria-hidden /> : <ChevronsDownUp className="size-4" aria-hidden />}{todoCerrado ? "Abrir todos" : "Contraer todos"}
          </button>
        )}
      </div>
      <details className="mb-5 rounded-xl bg-fondo px-4 py-2.5 text-sm text-gris">
        <summary className="flex cursor-pointer items-center gap-2 font-medium text-tinta"><Info className="size-4 text-azul" aria-hidden />¿Cómo se calcula quién está libre?</summary>
        <p className="mt-2">
          <b className="text-verde">Libre</b> = sin tareas abiertas · <b className="text-[#a86a00]">Poca carga</b> = 1 a {datos.poca_carga_max} · <b className="text-rojo">Ocupado/a</b> = más.
          Lo que ya entregó y espera validación no cuenta como carga. Quien está de permiso hoy aparece como no disponible.
        </p>
      </details>

      {grupos.length === 0 ? (
        <Vacio icono={UsersRound} titulo={vista === "libres" ? "Hoy nadie está libre" : "Nadie coincide"}>
          {vista === "libres" ? "Todas las personas tienen tareas abiertas. Mira «Poca carga» para quienes tienen menos." : "Prueba con otra búsqueda, departamento o filtro."}
        </Vacio>
      ) : (
        <div className="space-y-5">
          {grupos.map(([nombre, lista]) => {
            const cerrado = !buscar && cerrados.has(nombre);   // al buscar se muestran todos, para no esconder el resultado
            const libres = lista.filter((x) => x.estado === "LIBRE").length;
            return (
              <section key={nombre} aria-label={nombre} className="rounded-2xl border border-linea bg-white/60">
                <button type="button" onClick={() => alternar(nombre)} aria-expanded={!cerrado}
                  className="flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left hover:bg-white">
                  <ChevronDown className={cx("size-4 shrink-0 text-gris transition-transform", cerrado && "-rotate-90")} aria-hidden />
                  <h2 className="min-w-0 flex-1 truncate !text-base font-semibold !text-noche">{nombre}</h2>
                  <span className="hidden text-xs text-gris sm:inline">{libres} libre{libres === 1 ? "" : "s"} de {lista.length}</span>
                  <BarraEstado lista={lista} />
                  <Insignia tono={libres ? "verde" : "neutro"}>{libres}/{lista.length}</Insignia>
                </button>
                {!cerrado && <div className="grid gap-3 px-3 pb-3 sm:grid-cols-2 xl:grid-cols-3">{lista.map((p) => <Tarjeta key={p.id} p={p} onApoyo={setApoyo} onAsignar={asignar} />)}</div>}
              </section>
            );
          })}
        </div>
      )}
      <PedirApoyo persona={apoyo} onCerrar={() => setApoyo(null)} onHecho={() => setApoyo(null)} />
      <FormTarea abierto={!!asignando} onCerrar={() => setAsignando(null)} gente={gente} inicial={asignando ? { colaborador: String(asignando.id) } : null}
        onGuardada={(m) => { setAsignando(null); avisar(m || "Tarea asignada."); cargar(); }} />
    </div>
  );
}
