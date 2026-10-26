// Proyectos: tabla, tablero por estado y cronograma (Gantt) de todos los proyectos.
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ChartGantt, FolderKanban, Kanban, Plus, Search, Table2 } from "lucide-react";
import { guardarProyecto, listarProyectos } from "@/lib/api";
import { ESTADOS_PROYECTO, fechaCorta, hoyISO } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import Cronograma from "@/components/Cronograma";
import { Alerta, Boton, Cabecera, Cargando, Pestanas, Vacio, cx, useAviso } from "@/components/ui";
import { AvanceProyecto, EstadoProyecto, FormProyecto } from "./piezas";

const COLS = ["PLANIFICADO", "EN_CURSO", "EN_PAUSA", "TERMINADO"];

function Tarjeta({ p, onAbrir }) {
  const vencido = p.fecha_fin && p.fecha_fin < hoyISO() && !["TERMINADO", "CANCELADO"].includes(p.estado);
  return (
    <button type="button" onClick={() => onAbrir(p)} draggable onDragStart={(e) => e.dataTransfer.setData("text/plain", String(p.id))}
      className={cx("block w-full rounded-xl border bg-white p-3 text-left hover:border-azul/40 hover:shadow-md", vencido ? "border-rojo/40" : "border-linea")}>
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="text-xs text-gris num">{p.codigo}</span>
        {p.departamento_nombre && <span className="rounded-full px-2 py-0.5 text-xs font-medium" style={{ color: p.color, backgroundColor: p.color_fondo }}>{p.departamento_nombre}</span>}
      </div>
      <p className="font-medium leading-snug">{p.nombre}</p>
      <p className="truncate text-sm text-gris">{p.cliente_nombre}</p>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
        <AvanceProyecto progreso={p.progreso} ancho="w-16" />
        {p.fecha_fin && <span className={cx("text-xs", vencido ? "font-medium text-rojo" : "text-gris")}>Entrega {fechaCorta(p.fecha_fin)}</span>}
      </div>
      {p.responsable_nombre && <p className="mt-2 truncate border-t border-linea-suave pt-2 text-xs text-gris">{p.responsable_nombre}{p.miembros_nombres.length ? ` +${p.miembros_nombres.length}` : ""}</p>}
    </button>
  );
}

export default function Proyectos() {
  const { usuario } = useSesion();
  const avisar = useAviso();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [lista, setLista] = useState(null);
  const [error, setError] = useState("");
  const [buscar, setBuscar] = useState("");
  const [form, setForm] = useState(null);
  const vista = params.get("ver") || "tabla";
  const todos = params.get("todos") === "1";
  useEffect(() => { if (params.get("nuevo") === "1" && (usuario.gestiona || usuario.es_finanzas)) setForm({}); }, [params, usuario]);
  const poner = (k, v) => { if (v) params.set(k, v); else params.delete(k); setParams(params, { replace: true }); };

  const cargar = useCallback(() => listarProyectos(todos ? {} : { activos: 1 }).then(setLista).catch((e) => setError(e.message)), [todos]);
  useEffect(() => { cargar(); }, [cargar]);
  const filtrada = useMemo(() => (lista || []).filter((p) => !buscar || `${p.codigo} ${p.nombre} ${p.cliente_nombre}`.toLowerCase().includes(buscar.toLowerCase())), [lista, buscar]);
  const abrir = (p) => navigate(`/proyectos/${p.id}`);
  const puedeCrear = usuario.gestiona || usuario.es_finanzas;

  const soltar = async (id, estado) => {
    const p = lista.find((x) => x.id === id);
    if (!p || p.estado === estado) return;
    if (!p.puedo_gestionar) return avisar("Solo el responsable o quien gestiona su departamento lo mueve.", "rojo");
    try { const n = await guardarProyecto({ id, estado }); setLista((l) => l.map((x) => (x.id === id ? n : x))); } catch (e) { avisar(e.message, "rojo"); }
  };

  if (error) return <Alerta>{error}</Alerta>;
  return (
    <div>
      <Cabecera titulo="Proyectos" descripcion="Los trabajos grandes de cada cliente: sus tareas, órdenes, tiempos y, para quien gestiona, su rentabilidad.">
        {puedeCrear && <Boton icono={Plus} onClick={() => setForm({})}>Nuevo proyecto</Boton>}
      </Cabecera>
      <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-center">
        <Pestanas className="md:w-96" valor={vista} onCambio={(v) => poner("ver", v === "tabla" ? "" : v)} opciones={[
          { valor: "tabla", etiqueta: <><Table2 className="size-4" />Tabla</> },
          { valor: "tablero", etiqueta: <><Kanban className="size-4" />Tablero</> },
          { valor: "cronograma", etiqueta: <><ChartGantt className="size-4" />Cronograma</> },
        ]} />
        <div className="relative flex-1 md:max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" />
          <input className="campo h-11 pl-9" placeholder="Buscar proyecto o cliente" value={buscar} onChange={(e) => setBuscar(e.target.value)} aria-label="Buscar proyecto" />
        </div>
        <label className="flex h-11 items-center gap-2 rounded-lg border border-linea bg-white px-3 text-sm">
          <input type="checkbox" checked={todos} onChange={(e) => poner("todos", e.target.checked ? "1" : "")} className="accent-azul" /> Incluir terminados
        </label>
      </div>

      {!lista ? <Cargando /> : filtrada.length === 0 ? (
        <Vacio icono={FolderKanban} titulo="No hay proyectos" accion={puedeCrear && <Boton icono={Plus} onClick={() => setForm({})}>Nuevo proyecto</Boton>}>
          Un proyecto agrupa las tareas y órdenes de un mismo trabajo: una campaña completa, un sitio web, la cobertura de un torneo.
        </Vacio>
      ) : vista === "cronograma" ? (
        <Cronograma filas={filtrada.map((p) => ({
          id: p.id, etiqueta: p.nombre, sub: `${p.codigo} · ${p.cliente_nombre}`, inicio: p.fecha_inicio, fin: p.fecha_fin,
          color: p.color || "#224b9a", fondo: p.color_fondo || "#e6edfa", onClick: () => abrir(p),
          progreso: p.progreso.tareas ? (100 * p.progreso.validadas) / p.progreso.tareas : 0,
          alerta: p.fecha_fin < hoyISO() && !["TERMINADO", "CANCELADO"].includes(p.estado),
        }))} vacio="Ponles fecha de inicio y de entrega a los proyectos para verlos en el cronograma." />
      ) : vista === "tablero" ? (
        <div className="-mx-4 overflow-x-auto px-4 md:mx-0 md:px-0">
          <div className="flex min-w-max gap-3">
            {COLS.filter((c) => c !== "TERMINADO" || todos).map((c) => (
              <section key={c} onDragOver={(e) => e.preventDefault()} onDrop={(e) => soltar(Number(e.dataTransfer.getData("text/plain")), c)}
                className="w-[78vw] max-w-[300px] shrink-0 rounded-xl bg-linea-suave/70 p-2 md:w-72" aria-label={ESTADOS_PROYECTO[c]}>
                <h2 className="flex items-center justify-between px-1.5 pb-2 text-sm font-semibold">{ESTADOS_PROYECTO[c]}<span className="rounded-full bg-white px-2 text-xs text-gris num">{filtrada.filter((p) => p.estado === c).length}</span></h2>
                <ul className="flex min-h-24 flex-col gap-2">{filtrada.filter((p) => p.estado === c).map((p) => <li key={p.id}><Tarjeta p={p} onAbrir={abrir} /></li>)}</ul>
              </section>
            ))}
          </div>
        </div>
      ) : (
        <>
          <div className="hidden overflow-x-auto rounded-xl border border-linea bg-white md:block">
            <table className="tabla">
              <thead><tr><th>Proyecto</th><th>Cliente</th><th>Responsable</th><th>Estado</th><th>Avance</th><th>Entrega</th></tr></thead>
              <tbody>
                {filtrada.map((p) => (
                  <tr key={p.id} className="cursor-pointer" onClick={() => abrir(p)}>
                    <td><p className="text-xs text-gris num">{p.codigo}</p><p className="font-medium">{p.nombre}</p>
                      {p.progreso.vencidas > 0 && <p className="text-xs font-medium text-rojo">{p.progreso.vencidas} tarea(s) vencida(s)</p>}</td>
                    <td className="text-sm">{p.cliente_nombre}</td>
                    <td className="text-sm">{p.responsable_nombre || "—"}</td>
                    <td><EstadoProyecto estado={p.estado} /></td>
                    <td><AvanceProyecto progreso={p.progreso} /></td>
                    <td className={cx("whitespace-nowrap text-sm", p.fecha_fin && p.fecha_fin < hoyISO() && !["TERMINADO", "CANCELADO"].includes(p.estado) && "font-medium text-rojo")}>{p.fecha_fin ? fechaCorta(p.fecha_fin) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="space-y-2 md:hidden">{filtrada.map((p) => <li key={p.id}><Tarjeta p={p} onAbrir={abrir} /></li>)}</ul>
        </>
      )}
      <FormProyecto abierto={!!form} inicial={form} onCerrar={() => { setForm(null); poner("nuevo", ""); }}
        onGuardado={(p) => { setForm(null); avisar(`Proyecto ${p.codigo} creado.`); navigate(`/proyectos/${p.id}`); }} />
    </div>
  );
}
