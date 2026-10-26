// OT Maestras y Órdenes de Área: tablero por etapa, tablero por área (la cola de cada área), tabla y calendario.
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { BarChart3, CalendarDays, ClipboardList, Download, Kanban, Layers, Plus, Search, Table2 } from "lucide-react";
import { listarAreas, listarOrdenes, resumenOrdenes, urlBitacora } from "@/lib/api";
import { ESTADOS_OA, ESTADOS_ORDEN, hoyISO, mesActual, sumarDias } from "@/lib/formato";
import { useRecurso } from "@/lib/recursos";
import { useSesion } from "@/lib/sesion";
import Calendario, { rangoMes } from "@/components/Calendario";
import { Alerta, Boton, Cabecera, Cargando, Pestanas, Vacio, cx, useAviso } from "@/components/ui";
import FormOrden from "./FormOrden";
import {
  COLOR_AREA, COLUMNAS_OA, COLUMNAS_OT, CaminoAreas, EstadoOrden, Plazo, PrioridadOrden, TarjetaOA, TarjetaOrden, puntoEstado,
} from "./piezas";

function Indicador({ etiqueta, valor, tono, onClick, activo }) {
  return (
    <button type="button" onClick={onClick} disabled={!onClick} aria-pressed={activo}
      className={cx("rounded-xl border bg-white px-4 py-3 text-left transition", activo ? "border-azul ring-2 ring-azul/20" : "border-linea", onClick && "hover:border-azul/40")}>
      <p className="text-sm text-gris">{etiqueta}</p>
      <p className={cx("font-display text-2xl font-semibold num", tono)}>{valor ?? "—"}</p>
    </button>
  );
}

function Columnas({ columnas, nombres, render, vacio }) {
  return (
    <div className="-mx-4 overflow-x-auto px-4 pb-2 md:mx-0 md:px-0">
      <div className="flex min-w-max snap-x gap-3">
        {columnas.map(({ clave, lista }) => (
          <section key={clave} aria-label={nombres[clave]} className="flex w-[78vw] max-w-[300px] shrink-0 snap-start flex-col rounded-xl bg-linea-suave/70 p-2 md:w-72">
            <header className="flex items-center gap-2 px-1.5 pb-2 pt-1">
              <span className={cx("size-2.5 rounded-full", puntoEstado(clave))} aria-hidden />
              <h2 className="text-sm font-semibold">{nombres[clave]}</h2>
              <span className="ml-auto rounded-full bg-white px-2 text-xs font-medium text-gris num">{lista.length}</span>
            </header>
            <ul className="flex min-h-24 flex-col gap-2">
              {lista.map(render)}
              {!lista.length && <li className="rounded-lg border border-dashed border-linea px-3 py-5 text-center text-xs text-gris">{vacio?.(clave) || "Nada aquí"}</li>}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}

function Tabla({ ordenes, onAbrir }) {
  return (
    <>
      <div className="hidden overflow-x-auto rounded-xl border border-linea bg-white md:block">
        <table className="tabla">
          <thead><tr><th>OT</th><th>Cliente</th><th>Áreas</th><th>Asesor</th><th>Estado</th><th>Plazo</th></tr></thead>
          <tbody>
            {ordenes.map((o) => (
              <tr key={o.id} className="cursor-pointer" onClick={() => onAbrir(o)}>
                <td className="max-w-sm"><p className="text-xs font-semibold text-gris num">{o.codigo}</p><p className="font-medium">{o.titulo}</p></td>
                <td className="text-sm">{o.cliente_nombre}{o.proyecto_nombre && <span className="block text-xs text-gris">{o.proyecto_nombre}</span>}</td>
                <td><CaminoAreas areas={o.areas_resumen?.length ? o.areas_resumen : o.plan_areas} /></td>
                <td className="whitespace-nowrap text-sm">{o.asesor_comercial_nombre}</td>
                <td><div className="flex flex-wrap gap-1"><EstadoOrden estado={o.estado} /><PrioridadOrden prioridad={o.prioridad} /></div></td>
                <td className="whitespace-nowrap"><Plazo orden={o} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="space-y-2 md:hidden">{ordenes.map((o) => <li key={o.id}><TarjetaOrden orden={o} onAbrir={onAbrir} /></li>)}</ul>
    </>
  );
}

export default function Ordenes() {
  const avisar = useAviso();
  const navigate = useNavigate();
  const { misAreas, esCoordinacion, esFinanzas, esAdmin } = useSesion();
  const [params, setParams] = useSearchParams();
  const [catalogo] = useRecurso("catalogo");
  const [ordenes, setOrdenes] = useState(null);
  const [oas, setOas] = useState(null);
  const [resumen, setResumen] = useState(null);
  const [error, setError] = useState("");
  const [buscar, setBuscar] = useState("");
  const [nueva, setNueva] = useState(null);
  const supervisaAlgo = misAreas.length > 0 && !esAdmin && !esCoordinacion;
  const vista = params.get("ver") || (supervisaAlgo ? "areas" : "tablero");
  // En «Por área», quien supervisa empieza viendo sus áreas; puede quitar el filtro.
  const area = params.has("area") ? params.get("area") : vista === "areas" && supervisaAlgo ? misAreas.join(",") : "";
  const mias = params.get("mias") === "1";
  const vencidas = params.get("vencidas") === "1";
  const estadoFiltro = params.get("estado") || "";
  const [mes, setMes] = useState(mesActual());
  useEffect(() => { if (params.get("nueva") === "1") setNueva({}); }, [params]);

  const poner = (clave, valor) => { if (valor) params.set(clave, valor); else params.delete(clave); setParams(params, { replace: true }); };

  const cargar = useCallback(() => {
    setError("");
    if (vista === "areas") {
      listarAreas({ abiertas: 1, area, mias: mias ? 1 : "" }).then(setOas).catch((e) => setError(e.message));
    } else {
      const base = { area, mias: mias ? 1 : "", vencidas: vencidas ? 1 : "", estado: estadoFiltro };
      let pedido;
      if (vista === "calendario") { const { desde, hasta } = rangoMes(mes); pedido = listarOrdenes({ ...base, desde, hasta }); }
      else if (vista === "tablero") pedido = listarOrdenes({ ...base, estado: estadoFiltro || COLUMNAS_OT.join(",") });
      else pedido = listarOrdenes(base);
      pedido.then(setOrdenes).catch((e) => setError(e.message));
    }
    resumenOrdenes({ mias: mias ? 1 : "" }).then(setResumen).catch(() => {});
  }, [vista, area, mias, vencidas, estadoFiltro, mes]);
  useEffect(() => { cargar(); }, [cargar]);

  const texto = buscar.toLowerCase();
  const lista = useMemo(() => (ordenes || []).filter((o) => !texto || `${o.codigo} ${o.titulo} ${o.cliente_nombre} ${o.numero_cotizacion}`.toLowerCase().includes(texto)), [ordenes, texto]);
  const listaOA = useMemo(() => (oas || []).filter((o) => !texto || `${o.numero} ${o.que_produce} ${o.cliente_nombre} ${o.orden_titulo}`.toLowerCase().includes(texto)), [oas, texto]);
  const abrir = (o) => navigate(`/ordenes/${o.id}`);
  const abrirOA = (oa) => navigate(`/ordenes/${oa.orden}/areas/${oa.id}`);
  const hace30 = sumarDias(hoyISO(), -30);
  const areasSel = area ? area.split(",") : [];
  const ponerAreas = (lista_) => { params.set("area", lista_.join(",")); setParams(params, { replace: true }); };
  const filtroEstado = (e) => {
    if (estadoFiltro === e) { params.delete("estado"); } else { params.set("estado", e); params.set("ver", "tabla"); }
    setParams(params, { replace: true });
  };
  const cargando = vista === "areas" ? !oas : !ordenes;

  if (error) return <Alerta>{error}</Alerta>;
  return (
    <div>
      <Cabecera titulo="Órdenes de trabajo" descripcion="OT Maestra (F-01) → Órdenes de Área (F-02 a F-10) → traspasos con doble firma → acta de entrega → cierre. Cada área ve su cola.">
        <a href={urlBitacora()} className="inline-flex h-11 items-center gap-2 rounded-lg border border-linea bg-white px-4 text-[15px] font-medium hover:bg-fondo"><Download className="size-4" />Bitácora F-15</a>
        <Link to="/ordenes/indicadores" className="inline-flex h-11 items-center gap-2 rounded-lg border border-linea bg-white px-4 text-[15px] font-medium hover:bg-fondo"><BarChart3 className="size-4" />Indicadores</Link>
        <Boton icono={Plus} onClick={() => setNueva({})}>Nueva OT</Boton>
      </Cabecera>

      <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
        <Indicador etiqueta="Por revisar (G0)" valor={resumen?.por_aprobar} tono={resumen?.por_aprobar ? "text-[#a86a00]" : ""} onClick={() => filtroEstado("SOLICITADA")} activo={estadoFiltro === "SOLICITADA"} />
        <Indicador etiqueta="Devueltas" valor={resumen?.devueltas} tono={resumen?.devueltas ? "text-rojo" : ""} onClick={() => filtroEstado("DEVUELTA")} activo={estadoFiltro === "DEVUELTA"} />
        <Indicador etiqueta="Abiertas" valor={resumen?.abiertas} />
        <Indicador etiqueta="Vencidas" valor={resumen?.vencidas} tono={resumen?.vencidas ? "text-rojo" : ""}
          onClick={() => { if (vencidas) params.delete("vencidas"); else { params.set("vencidas", "1"); params.set("ver", "tabla"); } setParams(params, { replace: true }); }} activo={vencidas} />
        <Indicador etiqueta="Listas para entregar" valor={resumen?.listas} tono={resumen?.listas ? "text-verde" : ""} onClick={() => filtroEstado("LISTA")} activo={estadoFiltro === "LISTA"} />
        {esFinanzas && <Indicador etiqueta="Entregadas por cerrar" valor={resumen?.por_cerrar} onClick={() => filtroEstado("ENTREGADA")} activo={estadoFiltro === "ENTREGADA"} />}
        <Indicador etiqueta="A tiempo este mes" valor={resumen?.a_tiempo_pct != null ? `${resumen.a_tiempo_pct}%` : "—"}
          tono={resumen?.a_tiempo_pct >= 90 ? "text-verde" : resumen?.a_tiempo_pct >= 70 ? "text-noche" : resumen?.a_tiempo_pct != null ? "text-rojo" : ""} />
      </div>

      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center">
        <Pestanas className="lg:w-[30rem]" valor={vista} onCambio={(v) => { params.set("ver", v); params.delete("estado"); params.delete("area"); setParams(params, { replace: true }); }} opciones={[
          { valor: "tablero", etiqueta: <><Kanban className="size-4" />OT</> },
          { valor: "areas", etiqueta: <><Layers className="size-4" />Por área</> },
          { valor: "tabla", etiqueta: <><Table2 className="size-4" />Tabla</> },
          { valor: "calendario", etiqueta: <><CalendarDays className="size-4" />Calendario</> },
        ]} />
        <div className="flex flex-1 flex-wrap items-center gap-2">
          <div className="relative min-w-44 flex-1 lg:max-w-xs">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" />
            <input className="campo h-11 pl-9" placeholder="Buscar OT, cliente o cotización" value={buscar} onChange={(e) => setBuscar(e.target.value)} aria-label="Buscar" />
          </div>
          <label className="flex h-11 items-center gap-2 rounded-lg border border-linea bg-white px-3 text-sm">
            <input type="checkbox" checked={mias} onChange={(e) => poner("mias", e.target.checked ? "1" : "")} className="accent-azul" /> Solo las mías
          </label>
          {estadoFiltro && <button type="button" onClick={() => poner("estado", "")} className="h-9 rounded-full bg-noche px-3 text-sm text-white">{ESTADOS_ORDEN[estadoFiltro]} ×</button>}
        </div>
      </div>

      <div className="mb-5 flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none]" role="group" aria-label="Filtrar por área">
        <button type="button" onClick={() => ponerAreas([])} aria-pressed={!areasSel.length}
          className={cx("h-9 shrink-0 rounded-full border px-3.5 text-sm font-medium", !areasSel.length ? "border-noche bg-noche text-white" : "border-linea bg-white")}>Todas</button>
        {(catalogo?.areas || []).map((a) => {
          const on = areasSel.includes(a.codigo);
          return (
            <button key={a.codigo} type="button" onClick={() => ponerAreas(on ? areasSel.filter((x) => x !== a.codigo) : [...areasSel, a.codigo])} aria-pressed={on}
              className={cx("inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full border px-3 text-sm font-medium", on ? "border-noche bg-noche text-white" : "border-linea bg-white")}>
              <span className="size-2 rounded-full" style={{ backgroundColor: COLOR_AREA[a.codigo]?.[0] }} aria-hidden />{a.nombre}
              {resumen?.por_area?.[a.codigo] ? <span className="num opacity-70">{resumen.por_area[a.codigo]}</span> : null}
            </button>
          );
        })}
      </div>

      {cargando ? <Cargando /> : vista === "areas" ? (
        listaOA.length === 0 ? <Vacio icono={Layers} titulo="No hay Órdenes de Área abiertas con esos filtros">Cuando Coordinación libera una OT, cada área recibe aquí su Orden de Área para revisarla (G1).</Vacio> : (
          <Columnas nombres={ESTADOS_OA} columnas={COLUMNAS_OA.map((e) => ({ clave: e, lista: listaOA.filter((o) => (e === "EMITIDA" ? ["EMITIDA", "RECHAZADA"].includes(o.estado) : o.estado === e)) }))}
            render={(oa) => <li key={oa.id}><TarjetaOA oa={oa} onAbrir={abrirOA} /></li>}
            vacio={(e) => (e === "TERMINADA" ? "Las terminadas salen del tablero" : null)} />
        )
      ) : vista === "calendario" ? (
        <Calendario mes={mes} onMes={setMes} items={lista.filter((o) => o.fecha_compromiso || o.fecha_requerida).map((o) => {
          const [color, fondo] = COLOR_AREA[o.areas_resumen?.[0]?.area || o.plan_areas?.[0]?.area] || ["#16336b", "#e8edf6"];
          return { id: o.id, fecha: o.fecha_compromiso || o.fecha_requerida, titulo: `${(o.codigo || "").slice(-4)} · ${o.titulo}`, color, fondo,
            tachado: ["ENTREGADA", "CERRADA", "CANCELADA"].includes(o.estado), onClick: () => abrir(o) };
        })} />
      ) : lista.length === 0 ? (
        <Vacio icono={ClipboardList} titulo={buscar || area || mias || vencidas || estadoFiltro ? "No hay OT con esos filtros" : "Todavía no hay órdenes"}
          accion={<Boton icono={Plus} onClick={() => setNueva({})}>Nueva OT</Boton>}>
          Cada trabajo para un cliente empieza con la OT Maestra: datos del cliente, alcance, áreas que intervienen y la compuerta G0.
        </Vacio>
      ) : vista === "tablero" ? (
        <Columnas nombres={ESTADOS_ORDEN} columnas={COLUMNAS_OT.map((e) => ({ clave: e, lista: lista.filter((o) => o.estado === e && (e !== "ENTREGADA" || (o.fecha_entrega || "") >= hace30)) }))
          .filter((c) => !["EN_PAUSA", "DEVUELTA"].includes(c.clave) || c.lista.length)}
          render={(o) => <li key={o.id}><TarjetaOrden orden={o} onAbrir={abrir} /></li>}
          vacio={(e) => (e === "ENTREGADA" ? "Entregadas en los últimos 30 días" : null)} />
      ) : <Tabla ordenes={lista} onAbrir={abrir} />}

      <FormOrden abierto={!!nueva} inicial={nueva} onCerrar={() => { setNueva(null); poner("nueva", ""); }}
        onGuardada={(o) => { setNueva(null); poner("nueva", ""); avisar(`Solicitud ${o.solicitud} entregada a Coordinación para la compuerta G0.`); navigate(`/ordenes/${o.id}`); }} />
    </div>
  );
}
