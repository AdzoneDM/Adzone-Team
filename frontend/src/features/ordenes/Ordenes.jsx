// Órdenes de trabajo: tablero por estado (arrastrable), tabla y calendario. Como un tablero de Monday, pero con el flujo de ADZONE.
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { CalendarDays, ClipboardList, Kanban, Plus, Search, Table2 } from "lucide-react";
import { listarOrdenes, moverOrden, resumenOrdenes } from "@/lib/api";
import { ESTADOS_ORDEN, hoyISO, mesActual, sumarDias } from "@/lib/formato";
import { useRecurso } from "@/lib/recursos";
import Calendario, { rangoMes } from "@/components/Calendario";
import { Alerta, Boton, Cabecera, Cargando, Pestanas, Vacio, cx, useAviso } from "@/components/ui";
import FormOrden from "./FormOrden";
import { AprobarModal, EntregarOrdenModal } from "./acciones";
import { AvanceOrden, COLUMNAS, ESTILO_ESTADO, EstadoOrden, ICONO_TIPO, Plazo, PrioridadOrden, TarjetaOrden, TipoOrden } from "./piezas";

function Indicador({ etiqueta, valor, tono, onClick, activo }) {
  return (
    <button type="button" onClick={onClick} disabled={!onClick} aria-pressed={activo}
      className={cx("rounded-xl border bg-white px-4 py-3 text-left transition", activo ? "border-azul ring-2 ring-azul/20" : "border-linea", onClick && "hover:border-azul/40")}>
      <p className="text-sm text-gris">{etiqueta}</p>
      <p className={cx("font-display text-2xl font-semibold num", tono)}>{valor ?? "—"}</p>
    </button>
  );
}

function Tablero({ ordenes, onAbrir, onSoltar }) {
  const [sobre, setSobre] = useState(null);
  const hace30 = sumarDias(hoyISO(), -30);
  const columnas = COLUMNAS.map((estado) => ({
    estado,
    lista: ordenes.filter((o) => o.estado === estado && (estado !== "ENTREGADA" || (o.fecha_entrega || "") >= hace30)),
  })).filter((c) => c.estado !== "EN_PAUSA" || c.lista.length);
  return (
    <div className="-mx-4 overflow-x-auto px-4 pb-2 md:mx-0 md:px-0">
      <div className="flex min-w-max snap-x gap-3">
        {columnas.map(({ estado, lista }) => (
          <section key={estado} aria-label={ESTADOS_ORDEN[estado]}
            onDragOver={(e) => { e.preventDefault(); setSobre(estado); }} onDragLeave={() => setSobre(null)}
            onDrop={(e) => { e.preventDefault(); setSobre(null); onSoltar(Number(e.dataTransfer.getData("text/plain")), estado); }}
            className={cx("flex w-[78vw] max-w-[300px] shrink-0 snap-start flex-col rounded-xl bg-linea-suave/70 p-2 transition md:w-72", sobre === estado && "bg-azul/10 ring-2 ring-azul/30")}>
            <header className="flex items-center gap-2 px-1.5 pb-2 pt-1">
              <span className={cx("size-2.5 rounded-full", ESTILO_ESTADO[estado].punto)} aria-hidden />
              <h2 className="text-sm font-semibold">{ESTADOS_ORDEN[estado]}</h2>
              <span className="ml-auto rounded-full bg-white px-2 text-xs font-medium text-gris num">{lista.length}</span>
            </header>
            <ul className="flex min-h-24 flex-col gap-2">
              {lista.map((o) => <li key={o.id}><TarjetaOrden orden={o} onAbrir={onAbrir} arrastrable={o.puedo_gestionar || o.soy_responsable} /></li>)}
              {!lista.length && <li className="rounded-lg border border-dashed border-linea px-3 py-5 text-center text-xs text-gris">{estado === "ENTREGADA" ? "Entregadas en los últimos 30 días" : "Nada aquí"}</li>}
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
          <thead><tr><th>Orden</th><th>Cliente</th><th>Área</th><th>Responsable</th><th>Estado</th><th>Plazo</th><th>Avance</th></tr></thead>
          <tbody>
            {ordenes.map((o) => (
              <tr key={o.id} className="cursor-pointer" onClick={() => onAbrir(o)}>
                <td className="max-w-sm"><p className="text-xs text-gris num">{o.numero}</p><p className="font-medium">{o.titulo}</p></td>
                <td className="text-sm">{o.cliente_nombre}{o.proyecto_nombre && <span className="block text-xs text-gris">{o.proyecto_nombre}</span>}</td>
                <td><TipoOrden orden={o} /></td>
                <td className="whitespace-nowrap text-sm">{o.responsable_nombre || <span className="text-gris">Por asignar</span>}</td>
                <td><div className="flex flex-wrap gap-1"><EstadoOrden estado={o.estado} /><PrioridadOrden prioridad={o.prioridad} /></div></td>
                <td className="whitespace-nowrap"><Plazo orden={o} /></td>
                <td><AvanceOrden progreso={o.progreso} /></td>
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
  const [params, setParams] = useSearchParams();
  const [catalogo] = useRecurso("catalogo");
  const [ordenes, setOrdenes] = useState(null);
  const [resumen, setResumen] = useState(null);
  const [error, setError] = useState("");
  const [buscar, setBuscar] = useState("");
  const [nueva, setNueva] = useState(null);
  useEffect(() => { if (params.get("nueva") === "1") setNueva({}); }, [params]);
  const [aprobando, setAprobando] = useState(null);
  const [entregando, setEntregando] = useState(null);
  const [version, setVersion] = useState(0);
  const vista = params.get("ver") || "tablero";
  const tipo = params.get("tipo") || "";
  const mias = params.get("mias") === "1";
  const vencidas = params.get("vencidas") === "1";
  const [mes, setMes] = useState(mesActual());

  const poner = (clave, valor) => { if (valor) params.set(clave, valor); else params.delete(clave); setParams(params, { replace: true }); };

  const cargar = useCallback(() => {
    const base = { tipo, mias: mias ? 1 : "", vencidas: vencidas ? 1 : "" };
    let pedido;
    if (vista === "calendario") {
      const { desde, hasta } = rangoMes(mes);
      pedido = listarOrdenes({ ...base, desde, hasta });
    } else if (vista === "tablero") {
      pedido = listarOrdenes({ ...base, estado: COLUMNAS.join(",") });
    } else {
      pedido = listarOrdenes(base);
    }
    pedido.then(setOrdenes).catch((e) => setError(e.message));
    resumenOrdenes({ tipo, mias: mias ? 1 : "" }).then(setResumen).catch(() => {});
  }, [vista, tipo, mias, vencidas, mes]);
  useEffect(() => { cargar(); }, [cargar, version]);

  const lista = useMemo(() => (ordenes || []).filter((o) => !buscar ||
    `${o.numero} ${o.titulo} ${o.cliente_nombre}`.toLowerCase().includes(buscar.toLowerCase())), [ordenes, buscar]);

  const abrir = (o) => navigate(`/ordenes/${o.id}`);
  const recargar = () => setVersion((v) => v + 1);

  const soltar = async (id, estado) => {
    const o = ordenes.find((x) => x.id === id);
    if (!o || o.estado === estado) return;
    if (estado === "APROBADA" && o.estado === "SOLICITADA") return setAprobando(o);
    if (estado === "ENTREGADA") return setEntregando(o);
    const antes = ordenes;
    setOrdenes((l) => l.map((x) => (x.id === id ? { ...x, estado } : x)));  // se mueve al instante
    try {
      const nueva = await moverOrden(id, estado);
      setOrdenes((l) => l.map((x) => (x.id === id ? nueva : x)));
      avisar(`${nueva.numero}: ${ESTADOS_ORDEN[estado]}.`);
    } catch (e) {
      setOrdenes(antes);
      avisar(e.message, "rojo");
    }
  };

  const hecho = (o, msg) => { setAprobando(null); setEntregando(null); avisar(msg); recargar(); };

  if (error) return <Alerta>{error}</Alerta>;
  return (
    <div>
      <Cabecera titulo="Órdenes de trabajo" descripcion="Todo lo que se produce para los clientes, de la solicitud a la entrega. Arrastra una tarjeta para moverla de etapa.">
        <Boton icono={Plus} onClick={() => setNueva({})}>Nueva orden</Boton>
      </Cabecera>

      <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-5">
        <Indicador etiqueta="Abiertas" valor={resumen?.abiertas} />
        <Indicador etiqueta="Por aprobar" valor={resumen?.por_aprobar} tono={resumen?.por_aprobar ? "text-[#a86a00]" : ""} />
        <Indicador etiqueta="Vencidas" valor={resumen?.vencidas} tono={resumen?.vencidas ? "text-rojo" : ""}
          onClick={() => { poner("vencidas", vencidas ? "" : "1"); if (!vencidas) poner("ver", "tabla"); }} activo={vencidas} />
        <Indicador etiqueta="Entregadas este mes" valor={resumen?.entregadas_mes} />
        <Indicador etiqueta="A tiempo este mes" valor={resumen?.a_tiempo_pct != null ? `${resumen.a_tiempo_pct}%` : "—"}
          tono={resumen?.a_tiempo_pct >= 90 ? "text-verde" : resumen?.a_tiempo_pct >= 70 ? "text-noche" : resumen?.a_tiempo_pct != null ? "text-rojo" : ""} />
      </div>

      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center">
        <Pestanas className="lg:w-96" valor={vista} onCambio={(v) => poner("ver", v === "tablero" ? "" : v)} opciones={[
          { valor: "tablero", etiqueta: <><Kanban className="size-4" />Tablero</> },
          { valor: "tabla", etiqueta: <><Table2 className="size-4" />Tabla</> },
          { valor: "calendario", etiqueta: <><CalendarDays className="size-4" />Calendario</> },
        ]} />
        <div className="flex flex-1 flex-wrap items-center gap-2">
          <div className="relative min-w-44 flex-1 lg:max-w-xs">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" />
            <input className="campo h-11 pl-9" placeholder="Buscar orden o cliente" value={buscar} onChange={(e) => setBuscar(e.target.value)} aria-label="Buscar orden" />
          </div>
          <label className="flex h-11 items-center gap-2 rounded-lg border border-linea bg-white px-3 text-sm">
            <input type="checkbox" checked={mias} onChange={(e) => poner("mias", e.target.checked ? "1" : "")} className="accent-azul" /> Solo las mías
          </label>
        </div>
      </div>

      <div className="mb-5 flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none]" role="group" aria-label="Filtrar por área">
        <button type="button" onClick={() => poner("tipo", "")} aria-pressed={!tipo}
          className={cx("h-9 shrink-0 rounded-full border px-3.5 text-sm font-medium", !tipo ? "border-noche bg-noche text-white" : "border-linea bg-white")}>Todas las áreas</button>
        {(catalogo || []).map((t) => {
          const Icono = ICONO_TIPO[t.tipo];
          const on = tipo === t.tipo;
          return (
            <button key={t.tipo} type="button" onClick={() => poner("tipo", on ? "" : t.tipo)} aria-pressed={on}
              className={cx("inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full border px-3.5 text-sm font-medium", on ? "border-noche bg-noche text-white" : "border-linea bg-white")}>
              <Icono className="size-4" />{t.nombre}{resumen?.por_tipo?.[t.tipo] ? <span className="num opacity-70">{resumen.por_tipo[t.tipo]}</span> : null}
            </button>
          );
        })}
      </div>

      {!ordenes ? <Cargando /> : vista === "calendario" ? (
        <Calendario mes={mes} onMes={setMes} items={lista.filter((o) => o.fecha_compromiso || o.fecha_requerida).map((o) => ({
          id: o.id, fecha: o.fecha_compromiso || o.fecha_requerida, titulo: `${o.numero.slice(-4)} · ${o.titulo}`, color: o.color, fondo: o.color_fondo,
          tachado: ["ENTREGADA", "CANCELADA"].includes(o.estado), onClick: () => abrir(o),
        }))} />
      ) : lista.length === 0 ? (
        <Vacio icono={ClipboardList} titulo={buscar || tipo || mias || vencidas ? "No hay órdenes con esos filtros" : "Todavía no hay órdenes"}
          accion={<Boton icono={Plus} onClick={() => setNueva({})}>Nueva orden</Boton>}>
          Cada trabajo para un cliente empieza aquí: impresión, una grabación en Adzone TV, una campaña, un video, un sitio web o una gestión administrativa.
        </Vacio>
      ) : vista === "tablero" ? <Tablero ordenes={lista} onAbrir={abrir} onSoltar={soltar} /> : <Tabla ordenes={lista} onAbrir={abrir} />}

      {vista === "tablero" && ordenes?.length > 0 && <p className="mt-3 hidden text-xs text-gris md:block">Las entregadas se ven 30 días; las anteriores están en «Tabla».</p>}

      <FormOrden abierto={!!nueva} inicial={nueva} onCerrar={() => { setNueva(null); poner("nueva", ""); }}
        onGuardada={(o) => { setNueva(null); poner("nueva", ""); avisar(`${o.numero} pedida. ${o.departamento_nombre} recibió el aviso para aprobarla.`); navigate(`/ordenes/${o.id}`); }} />
      <AprobarModal orden={aprobando} abierto={!!aprobando} onCerrar={() => setAprobando(null)} onHecho={hecho} />
      <EntregarOrdenModal orden={entregando} abierto={!!entregando} onCerrar={() => setEntregando(null)} onHecho={hecho} />
    </div>
  );
}
