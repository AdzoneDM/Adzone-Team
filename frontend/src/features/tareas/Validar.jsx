// Por validar: las entregas de tu equipo esperando revisión, en tarjetas con lo importante a la vista, filtros, orden y buscador;
// al elegir una se abre el panel de revisión (a la derecha en computadora, en una ventana en celular y tableta).
// La lista se actualiza sola cuando alguien entrega, valida o devuelve, sin parpadeo y sin perder lo que estás escribiendo.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CalendarClock, CircleCheckBig, Clock, FileText, Film, ImageIcon, Link2, MessageSquareText, RotateCcw, Search, X } from "lucide-react";
import { listarTareas } from "@/lib/api";
import { fechaCorta, fechaHora } from "@/lib/formato";
import { useNovedades } from "@/lib/novedades";
import { useSinRecargaSuave } from "@/lib/recargaSuave";
import { refrescarAvisos } from "@/app/Estructura";
import { Alerta, Avatar, Cabecera, Cargando, Insignia, Modal, PrioridadTarea, Vacio, cx, useAviso } from "@/components/ui";
import RevisionTarea from "./RevisionTarea";
import { PESO_PRIORIDAD, diasTarde, entregaDe, resumenEvidencia, textoEspera, urgencia } from "./validarUtil";

const ICONO_EVIDENCIA = { imagen: ImageIcon, video: Film, pdf: FileText, documento: FileText, enlace: Link2, nota: MessageSquareText };
const BARRA = { nueva: "bg-azul", normal: "bg-linea", larga: "bg-rojo" };
const ESTADOS = [
  ["", "Todas"], ["nuevas", "Recién entregadas"], ["largas", "Esperando mucho"], ["atrasadas", "Atrasadas"], ["a_tiempo", "A tiempo"], ["corregidas", "Corregidas"],
];
const FECHAS = [["", "Cualquier fecha"], ["hoy", "Entregadas hoy"], ["7", "Últimos 7 días"], ["30", "Últimos 30 días"]];
const ORDENES = [["antiguas", "Más antiguas primero"], ["recientes", "Más recientes primero"], ["limite", "Fecha límite más próxima"], ["prioridad", "Prioridad más alta"]];

const coincideEstado = (t, estado) => (
  !estado || (estado === "nuevas" && urgencia(t) === "nueva") || (estado === "largas" && urgencia(t) === "larga") || (estado === "atrasadas" && diasTarde(t) > 0)
  || (estado === "a_tiempo" && diasTarde(t) === 0) || (estado === "corregidas" && t.rondas_revision > 0)
);
const coincideFecha = (t, fecha) => {
  if (!fecha) return true;
  const e = new Date(entregaDe(t));
  if (fecha === "hoy") return e.toDateString() === new Date().toDateString();
  return Date.now() - e.getTime() <= Number(fecha) * 86400000;
};
const ordenar = (lista, orden) => [...lista].sort((a, b) => {
  if (orden === "recientes") return new Date(entregaDe(b)) - new Date(entregaDe(a));
  if (orden === "limite") return String(a.fecha_limite).localeCompare(String(b.fecha_limite)) || new Date(entregaDe(a)) - new Date(entregaDe(b));
  if (orden === "prioridad") return (PESO_PRIORIDAD[b.prioridad] || 0) - (PESO_PRIORIDAD[a.prioridad] || 0) || new Date(entregaDe(a)) - new Date(entregaDe(b));
  return new Date(entregaDe(a)) - new Date(entregaDe(b));
});

function Tarjeta({ t, activa, onElegir }) {
  const urg = urgencia(t);
  const tarde = diasTarde(t);
  const evidencia = resumenEvidencia(t);
  return (
    <li>
      <button type="button" onClick={() => onElegir(t.id)} aria-current={activa}
        className={cx("relative flex w-full flex-col gap-2.5 overflow-hidden rounded-2xl border bg-white p-4 pl-5 text-left transition-all",
          activa ? "border-azul shadow-[0_0_0_3px_rgba(37,99,235,0.14)]" : "border-linea hover:border-azul/40 hover:shadow-sm")}>
        <span className={cx("absolute inset-y-0 left-0 w-1.5", BARRA[urg])} aria-hidden />
        <span className="flex items-start gap-3">
          <Avatar nombre={t.colaborador_nombre} />
          <span className="min-w-0 flex-1">
            <span className="block truncate font-semibold leading-tight">{t.colaborador_nombre}</span>
            <span className="block truncate text-xs text-gris">{[t.colaborador_puesto, t.colaborador_departamento].filter(Boolean).join(" · ")}</span>
          </span>
          <Insignia tono={tarde === 0 ? "verde" : "amarillo"} className="shrink-0">{tarde === 0 ? "A tiempo" : "Atrasada"}</Insignia>
        </span>
        <span className="block text-[15px] font-medium leading-snug">{t.titulo}</span>
        <span className="flex flex-wrap items-center gap-1.5">
          {urg === "nueva" && <Insignia tono="azul">Recién entregada</Insignia>}
          {urg === "larga" && <Insignia tono="rojo"><Clock className="size-3" aria-hidden />Lleva {textoEspera(t).replace("hace ", "")} esperando</Insignia>}
          {t.rondas_revision > 0 && <Insignia tono="rojo"><RotateCcw className="size-3" aria-hidden />Entrega n.º {t.rondas_revision + 1}</Insignia>}
          <PrioridadTarea prioridad={t.prioridad} />
        </span>
        <span className="grid gap-x-3 gap-y-0.5 text-xs text-gris sm:grid-cols-2">
          <span className="flex items-center gap-1.5"><Clock className="size-3.5 shrink-0" aria-hidden />Entregó {fechaHora(entregaDe(t))} · {textoEspera(t)}</span>
          <span className="flex items-center gap-1.5"><CalendarClock className="size-3.5 shrink-0" aria-hidden />Límite {fechaCorta(t.fecha_limite)}{tarde > 0 ? ` · ${tarde} ${tarde === 1 ? "día" : "días"} tarde` : ""}</span>
        </span>
        <span className="flex flex-wrap items-center gap-1.5">
          {evidencia.length === 0
            ? <span className="rounded-full bg-fondo px-2.5 py-0.5 text-xs text-gris">Sin evidencia</span>
            : evidencia.map((e) => {
              const Icono = ICONO_EVIDENCIA[e.clave];
              return <span key={e.clave} className="inline-flex items-center gap-1 rounded-full bg-fondo px-2.5 py-0.5 text-xs font-medium text-tinta"><Icono className="size-3.5 text-azul" aria-hidden />{e.texto}</span>;
            })}
        </span>
      </button>
    </li>
  );
}

const Selector = ({ valor, onCambio, opciones, etiqueta }) => (
  <select aria-label={etiqueta} value={valor} onChange={(e) => onCambio(e.target.value)} className="campo h-10 min-w-0 py-0 text-sm">
    {opciones.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
  </select>
);

export default function Validar() {
  const avisar = useAviso();
  const [lista, setLista] = useState(null);
  const [error, setError] = useState("");
  const [params] = useSearchParams();
  const [elegida, setElegida] = useState(() => Number(params.get("tarea")) || null);   // viene del aviso «Por validar»
  const [esPC, setEsPC] = useState(() => window.matchMedia("(min-width: 1024px)").matches);
  const [q, setQ] = useState("");
  const [estado, setEstado] = useState("");
  const [persona, setPersona] = useState("");
  const [depto, setDepto] = useState("");
  const [fecha, setFecha] = useState("");
  const [orden, setOrden] = useState("antiguas");
  const accionPropia = useRef(false);
  const lista0 = useRef(null);
  const elegidaRef = useRef(elegida);
  useEffect(() => { elegidaRef.current = elegida; }, [elegida]);

  useEffect(() => {
    const m = window.matchMedia("(min-width: 1024px)");
    const f = () => setEsPC(m.matches);
    m.addEventListener("change", f);
    return () => m.removeEventListener("change", f);
  }, []);

  const cargar = useCallback(() => {
    listarTareas({ ambito: "por_validar" })
      .then((t) => {
        // Si la que estabas revisando desapareció sin que tú la resolvieras, alguien más la revisó: se avisa en vez de cambiar la pantalla en silencio
        const previa = lista0.current;
        const viendo = elegidaRef.current;
        if (viendo && previa && !accionPropia.current && previa.some((x) => x.id === viendo) && !t.some((x) => x.id === viendo)) {
          avisar(`«${previa.find((x) => x.id === viendo).titulo}» ya la revisó otra persona.`);
        }
        accionPropia.current = false;
        lista0.current = t;
        setLista(t);
        setError("");
      })
      .catch((e) => setError(e.message));
  }, [avisar]);
  useEffect(() => { cargar(); }, [cargar]);
  useNovedades(cargar);
  useSinRecargaSuave();   // aquí no se vuelve a montar: perderías la tarea que estás revisando (ya se refresca sola)

  const personas = useMemo(() => [...new Map((lista || []).map((t) => [t.colaborador, t.colaborador_nombre])).entries()].sort((a, b) => a[1].localeCompare(b[1])), [lista]);
  const deptos = useMemo(() => [...new Set((lista || []).map((t) => t.colaborador_departamento).filter(Boolean))].sort(), [lista]);
  const visibles = useMemo(() => {
    const buscar = q.trim().toLowerCase();
    return ordenar((lista || []).filter((t) => coincideEstado(t, estado) && coincideFecha(t, fecha)
      && (!persona || String(t.colaborador) === persona) && (!depto || t.colaborador_departamento === depto)
      && (!buscar || `${t.titulo} ${t.colaborador_nombre} ${t.cliente || ""} ${t.colaborador_puesto || ""}`.toLowerCase().includes(buscar))), orden);
  }, [lista, q, estado, fecha, persona, depto, orden]);

  // En computadora siempre hay una elegida (la primera de la lista visible); en celular, solo si tocas una
  useEffect(() => {
    if (!lista) return;
    setElegida((e) => (e && visibles.some((x) => x.id === e) ? e : esPC ? visibles[0]?.id ?? null : null));
  }, [lista, visibles, esPC]);

  const listo = (id) => {
    accionPropia.current = true;
    lista0.current = (lista0.current || []).filter((t) => t.id !== id);
    setLista((l) => l.filter((t) => t.id !== id));
    refrescarAvisos();
  };

  const hayFiltros = q || estado || persona || depto || fecha || orden !== "antiguas";
  const limpiar = () => { setQ(""); setEstado(""); setPersona(""); setDepto(""); setFecha(""); setOrden("antiguas"); };
  const nuevas = (lista || []).filter((t) => urgencia(t) === "nueva").length;
  const atrasadas = (lista || []).filter((t) => diasTarde(t) > 0).length;
  const largas = (lista || []).filter((t) => urgencia(t) === "larga").length;

  if (error && !lista) return <Alerta>{error}</Alerta>;
  if (!lista) return <Cargando />;
  const tarea = lista.find((t) => t.id === elegida);

  return (
    <div>
      <Cabecera titulo="Por validar" descripcion="Una tarea solo suma al avance, al puntaje y al KPI de la persona cuando la validas. Nadie valida su propio trabajo.">
        <div className="flex flex-wrap items-center gap-2" aria-live="polite">
          <Insignia tono={lista.length ? "azul" : "verde"} className="!px-3 !py-1 !text-sm">{lista.length} {lista.length === 1 ? "pendiente" : "pendientes"}</Insignia>
          {nuevas > 0 && <Insignia tono="azul">{nuevas} {nuevas === 1 ? "recién entregada" : "recién entregadas"}</Insignia>}
          {largas > 0 && <Insignia tono="rojo">{largas} esperando mucho</Insignia>}
          {atrasadas > 0 && <Insignia tono="amarillo">{atrasadas} {atrasadas === 1 ? "atrasada" : "atrasadas"}</Insignia>}
        </div>
      </Cabecera>

      {lista.length === 0 ? (
        <Vacio icono={CircleCheckBig} titulo="Estás al día">No hay entregas de tu equipo esperando validación. Cuando alguien entregue, aparecerá aquí sola.</Vacio>
      ) : (
        <>
          <div className="mb-4 space-y-2.5 rounded-2xl border border-linea bg-white p-3" role="search">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" aria-hidden />
              <input className="campo h-11 !pl-9 !pr-9" placeholder="Buscar por persona, tarea o cliente…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Buscar entregas" />
              {q && <button type="button" onClick={() => setQ("")} aria-label="Borrar búsqueda" className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-gris hover:text-tinta"><X className="size-4" /></button>}
            </div>
            <div className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-0.5" role="group" aria-label="Estado">
              {ESTADOS.map(([v, t]) => (
                <button key={v} type="button" aria-pressed={estado === v} onClick={() => setEstado(v)}
                  className={cx("shrink-0 rounded-full border px-3 py-1 text-sm font-medium transition-colors", estado === v ? "border-noche bg-noche text-white" : "border-linea bg-white text-tinta hover:border-azul/50")}>{t}</button>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
              <Selector etiqueta="Colaborador" valor={persona} onCambio={setPersona} opciones={[["", "Todo el equipo"], ...personas.map(([id, n]) => [String(id), n])]} />
              <Selector etiqueta="Departamento" valor={depto} onCambio={setDepto} opciones={[["", "Todos los departamentos"], ...deptos.map((d) => [d, d])]} />
              <Selector etiqueta="Fecha de entrega" valor={fecha} onCambio={setFecha} opciones={FECHAS} />
              <Selector etiqueta="Ordenar por" valor={orden} onCambio={setOrden} opciones={ORDENES} />
            </div>
            {hayFiltros && (
              <p className="flex items-center justify-between text-xs text-gris">
                <span>Mostrando {visibles.length} de {lista.length}</span>
                <button type="button" onClick={limpiar} className="font-medium text-azul hover:underline">Quitar filtros</button>
              </p>
            )}
          </div>

          <div className="grid gap-6 lg:grid-cols-[minmax(300px,420px)_minmax(0,1fr)]">
            {visibles.length === 0 ? (
              <div className="lg:col-span-2"><Vacio icono={Search} titulo="Ninguna entrega coincide">Prueba con otra búsqueda o quita los filtros.</Vacio></div>
            ) : (
              <ul className="space-y-3 lg:max-h-[calc(100vh-14rem)] lg:overflow-y-auto lg:pr-1" aria-label="Entregas pendientes">
                {visibles.map((t) => <Tarjeta key={t.id} t={t} activa={t.id === elegida && esPC} onElegir={setElegida} />)}
              </ul>
            )}
            {esPC && tarea && visibles.length > 0 && (
              <section className="sticky top-24 max-h-[calc(100vh-7rem)] self-start overflow-y-auto rounded-2xl border border-linea bg-white p-6" aria-label="Revisión">
                <RevisionTarea tarea={tarea} onListo={listo} onFallo={cargar} />
              </section>
            )}
          </div>
        </>
      )}
      {!esPC && (
        <Modal abierto={!!tarea} onCerrar={() => setElegida(null)} titulo="Revisar entrega" ancho="md:max-w-3xl">
          {tarea && <RevisionTarea tarea={tarea} onListo={listo} onFallo={cargar} />}
        </Modal>
      )}
    </div>
  );
}
