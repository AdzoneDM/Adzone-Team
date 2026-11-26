// Control y seguimiento operativo: cualquier persona reporta; Operaciones registra, prioriza, deriva y da seguimiento.
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { AlarmClock, Ban, ChevronRight, Inbox, Plus, Repeat, Search } from "lucide-react";
import { casosOpciones, listarCasos } from "@/lib/api";
import { fechaCorta } from "@/lib/formato";
import { Alerta, Boton, Cabecera, Cargando, Pestanas, Vacio, cx, useAviso } from "@/components/ui";
import { EstadoCaso, ModalReportar, PrioridadCaso } from "./comun";

function Resumen({ r, onFiltro }) {
  const t = r.totales || {};
  const tarjetas = [
    ["Abiertos", (t.abiertos || 0) + (t.vencidos || 0), "abiertos", "text-azul"],
    ["Vencidos", t.vencidos || 0, "vencidos", "text-rojo"],
    ["Por validar", t.PENDIENTE_VALIDACION || 0, "PENDIENTE_VALIDACION", "text-[#6d4ac8]"],
    ["Cerrados", t.cerrados || 0, "CERRADO", "text-verde"],
  ];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {tarjetas.map(([n, v, f, c]) => (
          <button key={n} type="button" onClick={() => onFiltro(f)} className="rounded-xl bg-white px-4 py-3 text-left shadow-sm ring-1 ring-linea transition hover:ring-azul/40">
            <p className="text-xs font-medium text-gris">{n}</p><p className={cx("num font-display text-2xl font-bold", v ? c : "text-gris")}>{v}</p>
          </button>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div className="overflow-x-auto rounded-xl bg-white shadow-sm ring-1 ring-linea">
          <table className="w-full text-sm">
            <caption className="px-4 pt-3 text-left text-sm font-semibold text-noche">Por área asignada</caption>
            <thead><tr className="text-xs text-gris"><th className="px-4 py-2 text-left font-medium">Área</th><th className="px-3 py-2 text-right font-medium">Abiertos</th><th className="px-3 py-2 text-right font-medium">Vencidos</th><th className="px-4 py-2 text-right font-medium">Cerrados</th></tr></thead>
            <tbody>{(r.por_area || []).map((a) => (
              <tr key={a.area} className="border-t border-linea-suave"><td className="px-4 py-2">{a.area}</td><td className="num px-3 py-2 text-right">{a.abiertos}</td>
                <td className={cx("num px-3 py-2 text-right", a.vencidos && "font-semibold text-rojo")}>{a.vencidos}</td><td className="num px-4 py-2 text-right text-gris">{a.cerrados}</td></tr>
            ))}</tbody>
          </table>
          {!(r.por_area || []).length && <p className="px-4 pb-4 text-sm text-gris">Todavía no hay casos.</p>}
        </div>
        <div className="space-y-4">
          <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-linea">
            <p className="text-sm font-semibold text-noche">Por prioridad</p>
            <ul className="mt-2 space-y-1.5 text-sm">{(r.por_prioridad || []).map((p) => (
              <li key={p.prioridad} className="flex justify-between"><span>{p.prioridad}</span><span className="num text-gris">{p.abiertos + p.vencidos} abiertos{p.vencidos ? <b className="text-rojo"> · {p.vencidos} vencidos</b> : ""}</span></li>
            ))}</ul>
          </div>
          <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-linea">
            <p className="flex items-center gap-1.5 text-sm font-semibold text-noche"><Repeat className="size-4 text-[#a86a00]" aria-hidden />Situaciones recurrentes (90 días)</p>
            {(r.recurrentes || []).length ? (
              <ul className="mt-2 space-y-1.5 text-sm">{r.recurrentes.map((x) => <li key={`${x.categoria}-${x.area_origen}`} className="flex justify-between gap-2"><span>{x.categoria} · <span className="text-gris">{x.area_origen}</span></span><b className="num">{x.casos}</b></li>)}</ul>
            ) : <p className="mt-1 text-sm text-gris">Ninguna se repite 3 veces o más: nada que proponer todavía.</p>}
          </div>
        </div>
      </div>
    </div>
  );
}

function Fila({ c }) {
  return (
    <li>
      <Link to={`/casos/${c.id}`} className={cx("flex items-center gap-3 rounded-xl border bg-white px-4 py-3 transition hover:shadow-md", c.vencido ? "border-rojo/40" : "border-linea")}>
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-2 text-xs text-gris"><span className="font-mono font-semibold text-tinta">{c.codigo}</span>{c.tipo_texto} · {c.categoria_texto}
            {c.bloqueado && <span className="inline-flex items-center gap-1 font-semibold text-rojo"><Ban className="size-3" aria-hidden />Bloqueado</span>}</p>
          <p className="mt-0.5 truncate font-medium text-tinta">{c.titulo}</p>
          <p className="mt-0.5 text-xs text-gris">{c.area_asignada ? `${c.area_asignada}${c.responsable ? ` · ${c.responsable}` : " · sin responsable"}` : "Sin derivar"} · reportó {c.reportado_por} desde {c.area_origen || "—"}</p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1.5">
          <span className="flex flex-wrap justify-end gap-1.5"><PrioridadCaso p={c.prioridad} /><EstadoCaso c={c} /></span>
          {c.proxima_revision && c.estado !== "CERRADO" && (
            <span className={cx("inline-flex items-center gap-1 text-xs", c.vencido ? "font-semibold text-rojo" : "text-gris")}><AlarmClock className="size-3.5" aria-hidden />{c.vencido ? "Venció" : "Revisión"} {fechaCorta(c.proxima_revision)}</span>
          )}
        </div>
        <ChevronRight className="size-4 shrink-0 text-gris" aria-hidden />
      </Link>
    </li>
  );
}

export default function Casos() {
  const avisar = useAviso();
  const navegar = useNavigate();
  const [params, setParams] = useSearchParams();
  const [opciones, setOpciones] = useState(null);
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  const [reportar, setReportar] = useState(params.get("nuevo") === "1");
  const [buscar, setBuscar] = useState("");
  useEffect(() => { casosOpciones().then(setOpciones).catch((e) => setError(e.message)); }, []);
  const ops = opciones?.es_operaciones;
  const vista = params.get("vista") || (ops ? "todos" : "mios");
  const estado = params.get("estado") || "abiertos";
  const area = params.get("area") || "";
  const prioridad = params.get("prioridad") || "";
  const cargar = useCallback(() => {
    if (!opciones) return;
    listarCasos({ vista, estado: estado === "todos" ? "" : estado, area, prioridad, q: buscar.trim() }).then(setDatos).catch((e) => setError(e.message));
  }, [opciones, vista, estado, area, prioridad, buscar]);
  useEffect(() => { const t = setTimeout(cargar, buscar ? 300 : 0); return () => clearTimeout(t); }, [cargar, buscar]);
  const poner = (k, v) => setParams((p) => { const n = new URLSearchParams(p); if (v) n.set(k, v); else n.delete(k); return n; });

  if (error) return <Alerta>{error}</Alerta>;
  if (!opciones) return <Cargando />;
  const pestanas = ops ? [{ valor: "todos", etiqueta: "Todos los casos" }, { valor: "a_cargo", etiqueta: "A mi cargo" }, { valor: "mios", etiqueta: "Mis reportes" }]
    : [{ valor: "mios", etiqueta: "Mis reportes" }, { valor: "a_cargo", etiqueta: "De mi área" }];
  return (
    <div className="space-y-5">
      <Cabecera titulo="Casos operativos" descripcion={ops ? "Incidencias, solicitudes y mejoras de toda la empresa: registra, prioriza, deriva y verifica cada caso hasta su cierre."
        : "Reporta incidencias, solicitudes u oportunidades de mejora. Operaciones les da seguimiento hasta que queden resueltas."}>
        <Boton icono={Plus} onClick={() => setReportar(true)}>Reportar un caso</Boton>
      </Cabecera>
      <Pestanas opciones={pestanas} valor={vista} onCambio={(v) => poner("vista", v)} />
      {ops && vista === "todos" && datos?.resumen && <Resumen r={datos.resumen} onFiltro={(f) => poner("estado", f)} />}
      <div className="flex flex-wrap items-center gap-2 rounded-xl bg-white p-3 shadow-sm ring-1 ring-linea">
        <div className="relative min-w-48 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" aria-hidden />
          <input className="campo h-10 !pl-9" placeholder="Buscar por código, título o referencia" value={buscar} onChange={(e) => setBuscar(e.target.value)} aria-label="Buscar casos" />
        </div>
        <select className="campo h-10 w-auto" value={estado} onChange={(e) => poner("estado", e.target.value === "abiertos" ? "" : e.target.value)} aria-label="Estado">
          <option value="abiertos">Abiertos</option><option value="vencidos">Vencidos</option>
          {opciones.estados.map(([v, t]) => <option key={v} value={v}>{t}</option>)}<option value="todos">Todos</option>
        </select>
        <select className="campo h-10 w-auto" value={area} onChange={(e) => poner("area", e.target.value)} aria-label="Área asignada">
          <option value="">Todas las áreas</option><option value="sin">Sin derivar</option>
          {opciones.departamentos.map((d) => <option key={d.id} value={d.id}>{d.nombre}</option>)}
        </select>
        <select className="campo h-10 w-auto" value={prioridad} onChange={(e) => poner("prioridad", e.target.value)} aria-label="Prioridad">
          <option value="">Toda prioridad</option>{opciones.prioridades.map(([v, t]) => <option key={v} value={v}>{t}</option>)}<option value="sin">Sin prioridad</option>
        </select>
      </div>
      {!datos ? <Cargando /> : datos.casos.length === 0 ? (
        <Vacio icono={Inbox} titulo="No hay casos aquí" accion={<Boton variante="secundario" icono={Plus} onClick={() => setReportar(true)}>Reportar un caso</Boton>}>
          {estado === "abiertos" ? "No hay casos abiertos con estos filtros." : "Prueba con otros filtros."}
        </Vacio>
      ) : <ul className="space-y-2">{datos.casos.map((c) => <Fila key={c.id} c={c} />)}</ul>}
      <ModalReportar abierto={reportar} opciones={opciones} onCerrar={() => setReportar(false)}
        onCreado={(c) => { setReportar(false); avisar(`Caso ${c.codigo} enviado a Operaciones`); navegar(`/casos/${c.id}`); }} />
    </div>
  );
}
