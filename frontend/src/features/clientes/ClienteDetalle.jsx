// Expediente del cliente: todo lo que se le ha trabajado en un solo lugar (proyectos, órdenes, tareas con su historial,
// archivos y evidencias, entregas y reportes del período en PDF o Excel), sin saltar de un módulo a otro.
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  ArrowLeft, Briefcase, Camera, ChevronDown, ClipboardList, Download, FileSpreadsheet, FileText, FolderKanban, History, ImageIcon, ListChecks,
  Mail, MapPin, Pencil, Phone, Plus, Search, Trash2, Truck, X,
} from "lucide-react";
import { equipo as cargarEquipo, expedienteCliente, obtenerCliente, quitarLogoCliente, resumenCliente, subirLogoCliente, urlReporteCliente } from "@/lib/api";
import { eliminarClienteConfirmando } from "./eliminar";
import { dinero, fechaCorta, fechaHora, hoyISO } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import { useVisor } from "@/components/VisorImagen";
import { Alerta, Boton, Cargando, EstadoTarea, Panel, Pestanas, Vacio, cx, useAviso, useConfirmar } from "@/components/ui";
import FormOrden from "@/features/ordenes/FormOrden";
import { TarjetaOrden } from "@/features/ordenes/piezas";
import { EstadoProyecto, FormProyecto } from "@/features/proyectos/piezas";
import FormTarea from "@/features/tareas/FormTarea";
import { FormCliente } from "./Clientes";
import { EstadoOp, EstadoSol, FormOportunidad } from "@/features/comercial/piezas";

const iniciales = (n = "") => n.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]).join("").toUpperCase();

function Logo({ c, puede, onCambio }) {
  const entrada = useRef(null);
  const avisar = useAviso();
  const [subiendo, setSubiendo] = useState(false);
  const subir = async (archivo) => {
    if (!archivo) return;
    setSubiendo(true);
    try { onCambio(await subirLogoCliente(c.id, archivo)); avisar("Logo actualizado"); } catch (e) { avisar(e.message, "rojo"); }
    setSubiendo(false);
  };
  return (
    <div className="group relative size-20 shrink-0 md:size-24">
      {c.logo_url
        ? <img src={c.logo_url} alt={`Logo de ${c.nombre}`} className="size-full rounded-2xl bg-white object-contain p-1.5 ring-1 ring-linea" />
        : <span className="flex size-full items-center justify-center rounded-2xl bg-azul/10 font-display text-2xl font-bold text-azul md:text-3xl" aria-hidden>{iniciales(c.nombre)}</span>}
      {puede && (
        <>
          <input ref={entrada} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={(e) => { subir(e.target.files?.[0]); e.target.value = ""; }} />
          <button type="button" onClick={() => entrada.current?.click()} disabled={subiendo} aria-label={c.logo_url ? "Cambiar el logo" : "Subir logo o foto"} title={c.logo_url ? "Cambiar el logo" : "Subir logo o foto"}
            className="absolute -bottom-1.5 -right-1.5 flex size-8 items-center justify-center rounded-full bg-azul text-white shadow-md ring-2 ring-white hover:bg-azul-700">
            {subiendo ? <span className="size-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" /> : <Camera className="size-4" />}
          </button>
          {c.logo_url && (
            <button type="button" onClick={async () => { try { onCambio(await quitarLogoCliente(c.id)); } catch (e) { avisar(e.message, "rojo"); } }} aria-label="Quitar el logo" title="Quitar el logo"
              className="absolute -right-1.5 -top-1.5 hidden size-6 items-center justify-center rounded-full bg-white text-gris shadow ring-1 ring-linea hover:text-rojo group-hover:flex"><X className="size-3.5" /></button>
          )}
        </>
      )}
    </div>
  );
}

const Cifra = ({ etiqueta, valor, tono = "text-noche" }) => (
  <div className="rounded-xl bg-fondo px-3 py-2"><p className="text-[11px] font-medium text-gris">{etiqueta}</p><p className={cx("num font-display text-xl font-bold", tono)}>{valor}</p></div>
);

// ── Tareas: historial completo con filtros y trazabilidad ─────────────────────────────────────────────────────────
const MODOS_FECHA = [["todo", "Todo"], ["dia", "Un día"], ["mes", "Un mes"], ["rango", "Rango"]];

function FiltrosTareas({ f, setF, e }) {
  const poner = (k) => (ev) => setF((x) => ({ ...x, [k]: ev.target.value }));
  return (
    <div className="space-y-3 rounded-xl bg-white p-3 shadow-sm ring-1 ring-linea">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-48 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" aria-hidden />
          <input className="campo h-10 !pl-9" placeholder="Buscar en las tareas" value={f.q} onChange={poner("q")} aria-label="Buscar en las tareas" />
        </div>
        <select className="campo h-10 w-auto" value={f.empleado} onChange={poner("empleado")} aria-label="Empleado">
          <option value="">Todos los empleados</option>{e.empleados.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
        </select>
        <select className="campo h-10 w-auto" value={f.proyecto} onChange={poner("proyecto")} aria-label="Proyecto">
          <option value="">Todos los proyectos</option><option value="sin">Sin proyecto</option>{e.proyectos.map((p) => <option key={p.id} value={p.id}>{p.codigo} · {p.nombre}</option>)}
        </select>
        <select className="campo h-10 w-auto" value={f.estado} onChange={poner("estado")} aria-label="Estado">
          <option value="">Todos los estados</option>{e.estados.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
        </select>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-gris">Trabajadas:</span>
        <div className="inline-flex rounded-lg border border-linea bg-fondo p-0.5" role="group" aria-label="Período">
          {MODOS_FECHA.map(([v, t]) => (
            <button key={v} type="button" aria-pressed={f.modo === v} onClick={() => setF((x) => ({ ...x, modo: v }))}
              className={cx("rounded-md px-3 py-1 text-sm font-medium", f.modo === v ? "bg-white text-noche shadow-sm" : "text-gris hover:text-tinta")}>{t}</button>
          ))}
        </div>
        {f.modo === "dia" && <input type="date" className="campo h-9 w-auto" value={f.dia} onChange={poner("dia")} aria-label="Día" />}
        {f.modo === "mes" && <input type="month" className="campo h-9 w-auto" value={f.mes} onChange={poner("mes")} aria-label="Mes" />}
        {f.modo === "rango" && <>
          <input type="date" className="campo h-9 w-auto" value={f.desde} onChange={poner("desde")} aria-label="Desde" />
          <span className="text-sm text-gris">al</span>
          <input type="date" className="campo h-9 w-auto" value={f.hasta} onChange={poner("hasta")} aria-label="Hasta" />
        </>}
      </div>
    </div>
  );
}

function Linea({ etiqueta, valor, quien }) {
  if (!valor && !quien) return null;
  return <p className="text-xs"><span className="text-gris">{etiqueta}:</span> <span className="text-tinta">{valor ? fechaHora(valor) : ""}{quien ? `${valor ? " · " : ""}${quien}` : ""}</span></p>;
}

function FilaTarea({ t, onVerImagen }) {
  const [abierta, setAbierta] = useState(false);
  return (
    <li className="rounded-xl border border-linea bg-white">
      <button type="button" onClick={() => setAbierta((a) => !a)} aria-expanded={abierta} className="flex w-full items-start gap-3 p-4 text-left">
        <div className="min-w-0 flex-1">
          <p className="font-medium text-tinta">{t.titulo}</p>
          <p className="mt-0.5 text-xs text-gris">{[t.proyecto, t.orden].filter(Boolean).join(" · ") || "Sin proyecto"} · {t.responsable}{t.companeros.length ? ` y ${t.companeros.join(", ")}` : ""}</p>
          <p className="mt-0.5 text-xs text-gris">Asignó {t.asignada_por || "—"} · creada {fechaCorta(t.creada)}{t.finalizada ? ` · finalizada ${fechaCorta(t.finalizada)}` : ""}{t.entrega_cliente ? ` · entregada al cliente ${fechaCorta(t.entrega_cliente)}` : ""}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2"><EstadoTarea estado={t.estado} /><ChevronDown className={cx("size-4 text-gris transition-transform", abierta && "rotate-180")} /></div>
      </button>
      {abierta && (
        <div className="grid gap-4 border-t border-linea-suave p-4 md:grid-cols-2">
          <div className="space-y-1.5">
            {t.descripcion && <p className="whitespace-pre-line text-sm text-tinta">{t.descripcion}</p>}
            <Linea etiqueta="Creada / asignada" valor={t.creada} quien={t.asignada_por} />
            <Linea etiqueta="Empezó a trabajarla" valor={t.inicio_trabajo} quien={t.responsable} />
            <Linea etiqueta="Entregada" valor={t.entregada} />
            <Linea etiqueta="Finalizada / resuelta" valor={t.finalizada} quien={t.resuelta_por} />
            {t.entrega_cliente && <p className="text-xs"><span className="text-gris">Entrega al cliente:</span> {fechaCorta(t.entrega_cliente)}</p>}
            {t.dias_trabajados?.length > 0 && (
              <div className="text-xs"><span className="text-gris">Días trabajados:</span>
                <ul className="mt-0.5 space-y-0.5">{t.dias_trabajados.map((d, i) => (
                  <li key={i}>{fechaCorta(d.fecha)} · {d.persona} · {d.minutos >= 60 ? `${Math.floor(d.minutos / 60)} h ${d.minutos % 60} min` : `${d.minutos} min`}</li>
                ))}</ul>
              </div>
            )}
            {t.evidencia_nota && <p className="rounded-lg bg-fondo p-2 text-sm"><b className="font-medium">Nota de entrega:</b> {t.evidencia_nota}</p>}
            {t.evidencia_enlace && <a href={t.evidencia_enlace} target="_blank" rel="noopener noreferrer" className="block break-all text-sm text-azul underline">{t.evidencia_enlace}</a>}
            {t.evidencias.length > 0 && (
              <ul className="flex flex-wrap gap-2 pt-1">{t.evidencias.map((e) => (
                <li key={e.id}>{e.purgado ? <span className="text-xs italic text-gris">{e.nombre} (se borró por espacio)</span> : e.es_imagen ? (
                  <button type="button" onClick={() => onVerImagen(e)} className="block size-16 overflow-hidden rounded-lg ring-1 ring-linea" aria-label={`Ver ${e.nombre}`}>
                    <img src={e.url} alt={e.nombre} loading="lazy" className="size-full object-cover" /></button>
                ) : <a href={`${e.url}?descargar=1`} download={e.nombre} className="flex h-16 max-w-40 items-center gap-1.5 rounded-lg bg-fondo px-2 text-xs ring-1 ring-linea hover:bg-linea-suave"><FileText className="size-4 shrink-0 text-azul" /><span className="truncate">{e.nombre}</span></a>}</li>
              ))}</ul>
            )}
          </div>
          <div>
            <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-gris"><History className="size-3.5" />Quién hizo qué y cuándo</p>
            <ol className="space-y-2 border-l border-linea pl-3">
              {t.modificaciones.map((m, i) => (
                <li key={i} className="text-xs"><b className="font-semibold text-tinta">{m.accion}</b> <span className="text-gris">· {m.usuario || "Plataforma"} · {fechaHora(m.fecha)}</span>
                  {m.detalle && <span className="mt-0.5 block whitespace-pre-line text-gris">{m.detalle}</span>}</li>
              ))}
              {!t.modificaciones.length && <li className="text-xs text-gris">Sin movimientos registrados.</li>}
            </ol>
          </div>
        </div>
      )}
    </li>
  );
}

const FILTRO_INICIAL = { q: "", empleado: "", proyecto: "", estado: "", modo: "todo", dia: hoyISO(), mes: hoyISO().slice(0, 7), desde: "", hasta: "" };
const aParams = (f) => ({
  q: f.q.trim(), empleado: f.empleado, proyecto: f.proyecto, estado: f.estado,
  ...(f.modo === "dia" ? { dia: f.dia } : f.modo === "mes" ? { mes: f.mes } : f.modo === "rango" ? { desde: f.desde, hasta: f.hasta } : {}),
});

function Reporte({ c, e }) {
  const hoy = hoyISO();
  const [desde, setDesde] = useState(`${hoy.slice(0, 7)}-01`);
  const [hasta, setHasta] = useState(hoy);
  const [proyecto, setProyecto] = useState("");
  const params = { desde, hasta, proyecto };
  return (
    <div className="max-w-2xl space-y-4 rounded-2xl bg-white p-5 shadow-sm ring-1 ring-linea">
      <div>
        <h2 className="text-lg font-semibold">Reporte de trabajos realizados</h2>
        <p className="text-sm text-gris">Para cuando {c.nombre} pide evidencia de lo trabajado en un período: datos del cliente, proyectos, órdenes, cada tarea con su responsable, fechas de ejecución, finalización y entrega, estado y evidencias.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-sm"><span className="etiqueta">Desde</span><input type="date" className="campo" value={desde} onChange={(ev) => setDesde(ev.target.value)} /></label>
        <label className="text-sm"><span className="etiqueta">Hasta</span><input type="date" className="campo" value={hasta} min={desde} onChange={(ev) => setHasta(ev.target.value)} /></label>
        <label className="text-sm"><span className="etiqueta">Proyecto</span>
          <select className="campo" value={proyecto} onChange={(ev) => setProyecto(ev.target.value)}><option value="">Todos</option>{e.proyectos.map((p) => <option key={p.id} value={p.id}>{p.codigo} · {p.nombre}</option>)}</select></label>
      </div>
      <div className="flex flex-wrap gap-2">
        <a href={urlReporteCliente(c.id, { ...params, formato: "pdf" })} target="_blank" rel="noopener" className="inline-flex h-10 items-center gap-2 rounded-lg bg-azul px-4 text-sm font-semibold text-white hover:bg-azul-700"><FileText className="size-4" />Ver PDF</a>
        <a href={urlReporteCliente(c.id, { ...params, formato: "xlsx" })} className="inline-flex h-10 items-center gap-2 rounded-lg border border-linea bg-white px-4 text-sm font-semibold text-azul hover:bg-fondo"><FileSpreadsheet className="size-4" />Descargar Excel</a>
      </div>
      {!e.ve_todas_las_tareas && <p className="text-xs text-gris">El reporte incluye las tareas que tú puedes ver (las tuyas, las de tu equipo y las que asignaste). Dirección lo genera con todas.</p>}
    </div>
  );
}

export default function ClienteDetalle() {
  const { id } = useParams();
  const { usuario, puedeValidar, puedeAsignar } = useSesion();
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const ver = useVisor();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const pestana = params.get("ver") || "resumen";
  const [c, setC] = useState(null);
  const [r, setR] = useState(null);
  const [e, setE] = useState(null);
  const [filtros, setFiltros] = useState(FILTRO_INICIAL);
  const [error, setError] = useState("");
  const [modal, setModal] = useState(null);
  const [gente, setGente] = useState([]);
  const cargar = useCallback(() => Promise.all([obtenerCliente(id), resumenCliente(id)]).then(([a, b]) => { setC(a); setR(b); }).catch((er) => setError(er.message)), [id]);
  useEffect(() => { cargar(); }, [cargar]);
  const filtrosJSON = JSON.stringify(aParams(filtros));
  const cargarExpediente = useCallback(() => expedienteCliente(id, JSON.parse(filtrosJSON)).then(setE).catch((er) => setError(er.message)), [id, filtrosJSON]);
  useEffect(() => { const t = setTimeout(cargarExpediente, 250); return () => clearTimeout(t); }, [cargarExpediente]);
  useEffect(() => { if (puedeValidar || puedeAsignar) cargarEquipo().then(setGente).catch(() => {}); }, [puedeValidar, puedeAsignar]);
  const eliminar = async () => {
    const res = await eliminarClienteConfirmando({ cliente: c, confirmar, avisar });
    if (res === "eliminado") navigate("/clientes", { replace: true });
    else if (res === "inactivo") cargar();
  };
  if (error) return <Alerta>{error}</Alerta>;
  if (!c || !r || !e) return <Cargando />;
  const abiertas = r.ordenes.filter((o) => !["ENTREGADA", "CERRADA", "CANCELADA"].includes(o.estado));
  const puedeEditar = usuario.gestiona || usuario.es_finanzas || usuario.clientes_completo;
  const editaCliente = puedeEditar || usuario.edita_clientes;
  const porEstado = e.resumen_tareas.por_estado;
  const verImagen = (ev) => {
    const imgs = e.archivos.filter((a) => a.es_imagen && !a.purgado).map((a) => ({ src: a.url, nombre: a.nombre, detalle: `${a.subido_por || ""} · ${fechaHora(a.fecha)}`, descargar: `${a.url}${a.url.includes("?") ? "&" : "?"}descargar=1` }));
    ver(imgs.length ? imgs : [{ src: ev.url, nombre: ev.nombre }], Math.max(0, imgs.findIndex((x) => x.src === ev.url)));
  };
  const pestanas = [
    { valor: "resumen", etiqueta: "Resumen" },
    { valor: "proyectos", etiqueta: `Proyectos (${e.proyectos.length})` },
    { valor: "ordenes", etiqueta: `Órdenes (${e.ordenes.length})` },
    { valor: "tareas", etiqueta: `Tareas (${e.resumen_tareas.total})` },
    { valor: "archivos", etiqueta: `Archivos (${e.archivos.length})` },
    { valor: "entregas", etiqueta: "Entregas" },
    { valor: "reporte", etiqueta: "Reportes" },
  ];
  return (
    <div className="space-y-5">
      <Link to="/clientes" className="inline-flex items-center gap-1.5 text-sm font-medium text-azul hover:underline"><ArrowLeft className="size-4" />Clientes</Link>

      <header className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-linea">
        <div className="flex flex-wrap items-start gap-5">
          <Logo c={c} puede={editaCliente} onCambio={setC} />
          <div className="min-w-0 flex-1">
            <p className="text-sm text-gris">{c.tipo_nombre}{c.rnc ? ` · RNC ${c.rnc}` : ""}{!c.activo && <b className="ml-2 font-medium text-rojo">Inactivo</b>}</p>
            <h1 className="mt-0.5 text-2xl font-bold leading-tight md:text-3xl">{c.nombre}</h1>
            <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-sm">
              {c.contacto && <li className="font-medium">{c.contacto}</li>}
              {c.telefono && <li><a href={`tel:${c.telefono}`} className="flex items-center gap-1.5 hover:text-azul"><Phone className="size-4 text-gris" />{c.telefono}</a></li>}
              {c.correo && <li><a href={`mailto:${c.correo}`} className="flex items-center gap-1.5 break-all hover:text-azul"><Mail className="size-4 shrink-0 text-gris" />{c.correo}</a></li>}
              {c.direccion && <li className="flex items-start gap-1.5"><MapPin className="mt-0.5 size-4 shrink-0 text-gris" />{c.direccion}</li>}
            </ul>
            {c.notas && <p className="mt-2 max-w-3xl whitespace-pre-line text-sm text-gris">{c.notas}</p>}
          </div>
          <div className="flex flex-wrap gap-2">
            <Boton tam="sm" variante="acento" icono={Download} onClick={() => { const n = new URLSearchParams(params); n.set("ver", "reporte"); setParams(n, { replace: true }); }}>Exportar trabajos</Boton>
            <Boton tam="sm" icono={Plus} onClick={() => setModal("orden")}>Orden</Boton>
            {(puedeValidar || puedeAsignar) && <Boton tam="sm" variante="secundario" icono={ListChecks} onClick={() => setModal("tarea")}>Tarea</Boton>}
            {puedeEditar && <Boton tam="sm" variante="secundario" icono={FolderKanban} onClick={() => setModal("proyecto")}>Proyecto</Boton>}
            {usuario.es_comercial && <Boton tam="sm" variante="secundario" icono={Briefcase} onClick={() => setModal("oportunidad")}>Oportunidad</Boton>}
            {editaCliente && <Boton tam="sm" variante="secundario" icono={Pencil} onClick={() => setModal("editar")}>Editar</Boton>}
            {puedeEditar && !c.es_interno && <Boton tam="sm" variante="peligro" icono={Trash2} onClick={eliminar} aria-label="Eliminar cliente" />}
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-5">
          <Cifra etiqueta="Proyectos activos" valor={e.proyectos.filter((p) => ["PLANIFICADO", "EN_CURSO", "EN_PAUSA"].includes(p.estado)).length} />
          <Cifra etiqueta="Órdenes abiertas" valor={abiertas.length} tono="text-azul" />
          <Cifra etiqueta="Tareas en curso" valor={(porEstado.PENDIENTE || 0) + (porEstado.EN_PROGRESO || 0) + (porEstado.EN_REVISION || 0)} />
          <Cifra etiqueta="Tareas finalizadas" valor={porEstado.COMPLETADA || 0} tono="text-verde" />
          <Cifra etiqueta="Entregas" valor={e.entregas.length} />
        </div>
      </header>

      <Pestanas opciones={pestanas} valor={pestana} onCambio={(v) => { const n = new URLSearchParams(params); if (v === "resumen") n.delete("ver"); else n.set("ver", v); setParams(n, { replace: true }); }} />

      {pestana === "resumen" && (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
          <div className="space-y-5">
            <section>
              <h2 className="mb-3 text-[17px] font-semibold">Órdenes abiertas ({abiertas.length})</h2>
              {abiertas.length === 0 ? <Vacio icono={ClipboardList} titulo="Nada en producción para este cliente" accion={<Boton icono={Plus} onClick={() => setModal("orden")}>Nueva orden</Boton>} />
                : <ul className="grid gap-3 md:grid-cols-2">{abiertas.map((o) => <li key={o.id}><TarjetaOrden orden={o} onAbrir={() => navigate(`/ordenes/${o.id}`)} /></li>)}</ul>}
            </section>
            <Panel titulo="Últimas tareas" cuerpo="p-0" accion={<button type="button" onClick={() => setParams({ ver: "tareas" })} className="text-sm font-medium text-azul hover:underline">Ver todas</button>}>
              {e.tareas.length === 0 ? <p className="p-5 text-sm text-gris">Todavía no hay tareas para este cliente.</p> : (
                <ul className="divide-y divide-linea-suave">{e.tareas.slice(0, 6).map((t) => (
                  <li key={t.id} className="flex items-center gap-3 px-5 py-2.5 text-sm"><span className="min-w-0 flex-1 truncate">{t.titulo}<span className="block text-xs text-gris">{t.responsable} · {fechaCorta(t.creada)}</span></span><EstadoTarea estado={t.estado} /></li>
                ))}</ul>
              )}
            </Panel>
          </div>
          <aside className="space-y-5">
            {r.finanzas && (
              <Panel titulo="Cuenta">
                <dl className="grid grid-cols-2 gap-3 text-sm">
                  <div><dt className="text-gris">Facturado</dt><dd className="font-semibold num">{dinero(r.finanzas.facturado)}</dd></div>
                  <div><dt className="text-gris">Cobrado</dt><dd className="font-semibold num">{dinero(r.finanzas.cobrado)}</dd></div>
                  <div className="col-span-2"><dt className="text-gris">Saldo por cobrar</dt><dd className={cx("font-display text-xl font-semibold num", r.finanzas.saldo > 0 && "text-[#a86a00]")}>{dinero(r.finanzas.saldo)}</dd></div>
                </dl>
                {r.finanzas.facturas.length > 0 && (
                  <ul className="mt-3 divide-y divide-linea-suave border-t border-linea-suave text-sm">
                    {r.finanzas.facturas.map((f) => (
                      <li key={f.id}><Link to={`/finanzas?ver=facturas&id=${f.id}`} className="flex justify-between py-2 hover:text-azul">
                        <span>{f.numero} · {fechaCorta(f.fecha)}</span><span className={cx("num", f.vencida && "font-medium text-rojo")}>{Number(f.saldo) > 0 ? `debe ${dinero(f.saldo)}` : "pagada"}</span></Link></li>
                    ))}
                  </ul>
                )}
              </Panel>
            )}
            {r.oportunidades && (
              <Panel titulo={`Oportunidades (${r.oportunidades.length})`} cuerpo="p-0" accion={<Boton tam="sm" variante="secundario" icono={Plus} onClick={() => setModal("oportunidad")}>Nueva</Boton>}>
                {r.oportunidades.length === 0 ? <p className="p-5 text-sm text-gris">Sin oportunidades registradas.</p> : (
                  <ul className="divide-y divide-linea-suave">{r.oportunidades.map((o) => (
                    <li key={o.id}><Link to={`/oportunidades?oportunidad=${o.id}`} className="flex items-center gap-3 px-5 py-3 hover:bg-fondo">
                      <span className="min-w-0 flex-1"><span className="block truncate font-medium">{o.titulo}</span><span className="text-xs text-gris">{o.codigo} · {fechaCorta(o.fecha_creacion)}</span></span><EstadoOp estado={o.estado} /></Link></li>))}</ul>
                )}
              </Panel>
            )}
            {r.solicitudes?.length > 0 && (
              <Panel titulo={`Servicios solicitados (${r.solicitudes.length})`} cuerpo="p-0">
                <ul className="divide-y divide-linea-suave">{r.solicitudes.map((s) => (
                  <li key={s.id}><Link to={`/oportunidades?solicitud=${s.id}`} className="flex items-center gap-3 px-5 py-3 hover:bg-fondo">
                    <span className="min-w-0 flex-1"><span className="block truncate font-medium">{s.servicio_nombre}</span><span className="text-xs text-gris">{s.codigo} · {s.departamento_nombre}</span></span><EstadoSol estado={s.estado} /></Link></li>))}</ul>
              </Panel>
            )}
          </aside>
        </div>
      )}

      {pestana === "proyectos" && (e.proyectos.length === 0 ? <Vacio icono={FolderKanban} titulo="Sin proyectos" accion={puedeEditar && <Boton icono={Plus} onClick={() => setModal("proyecto")}>Nuevo proyecto</Boton>} /> : (
        <ul className="grid gap-3 md:grid-cols-2">{e.proyectos.map((p) => {
          const pct = p.tareas ? Math.round((p.tareas_hechas / p.tareas) * 100) : 0;
          return (
            <li key={p.id}><Link to={`/proyectos/${p.id}`} className="block rounded-xl border border-linea bg-white p-4 transition hover:shadow-md">
              <div className="flex items-start justify-between gap-2"><span className="min-w-0"><span className="block font-semibold">{p.nombre}</span><span className="text-xs text-gris">{p.codigo}{p.responsable ? ` · ${p.responsable}` : ""}{p.departamento ? ` · ${p.departamento}` : ""}</span></span><EstadoProyecto estado={p.estado} /></div>
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-linea"><div className="h-full rounded-full bg-verde" style={{ width: `${pct}%` }} /></div>
              <p className="mt-1.5 text-xs text-gris">{p.tareas_hechas} de {p.tareas} tareas finalizadas · {p.ordenes} orden(es){p.fecha_fin ? ` · entrega ${fechaCorta(p.fecha_fin)}` : ""}</p>
            </Link></li>
          );
        })}</ul>
      ))}

      {pestana === "ordenes" && (e.ordenes.length === 0 ? <Vacio icono={ClipboardList} titulo="Sin órdenes de trabajo" accion={<Boton icono={Plus} onClick={() => setModal("orden")}>Nueva orden</Boton>} /> : (
        <div className="overflow-x-auto rounded-xl bg-white shadow-sm ring-1 ring-linea">
          <table className="w-full min-w-[42rem] text-sm">
            <thead className="text-left text-xs text-gris"><tr>{["Orden", "Trabajo", "Proyecto", "Área", "Estado", "Compromiso", "Entregada"].map((h) => <th key={h} className="px-4 py-2.5 font-medium">{h}</th>)}</tr></thead>
            <tbody>{e.ordenes.map((o) => (
              <tr key={o.id} className="border-t border-linea-suave hover:bg-fondo">
                <td className="px-4 py-2.5"><Link to={`/ordenes/${o.id}`} className="font-medium text-azul hover:underline num">{o.codigo}</Link></td>
                <td className="px-4 py-2.5">{o.titulo}</td><td className="px-4 py-2.5 text-gris">{o.proyecto || "—"}</td><td className="px-4 py-2.5 text-gris">{o.departamento || "—"}</td>
                <td className="px-4 py-2.5">{o.estado_texto}</td><td className="px-4 py-2.5 text-gris">{o.fecha_compromiso ? fechaCorta(o.fecha_compromiso) : "—"}</td>
                <td className="px-4 py-2.5">{o.fecha_entrega ? fechaCorta(o.fecha_entrega) : "—"}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      ))}

      {pestana === "tareas" && (
        <div className="space-y-3">
          <FiltrosTareas f={filtros} setF={setFiltros} e={e} />
          {!e.ve_todas_las_tareas && <p className="text-xs text-gris">Ves las tareas de este cliente que te corresponden: las tuyas, las de tu equipo y las que asignaste.</p>}
          {e.tareas.length === 0 ? <Vacio icono={ListChecks} titulo="No hay tareas con estos filtros" /> : (
            <ul className="space-y-2">{e.tareas.map((t) => <FilaTarea key={t.id} t={t} onVerImagen={verImagen} />)}</ul>
          )}
        </div>
      )}

      {pestana === "archivos" && (e.archivos.length === 0 ? <Vacio icono={ImageIcon} titulo="Todavía no hay archivos ni evidencias" /> : (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">{e.archivos.map((a, i) => (
          <li key={i} className="overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-linea">
            {a.es_imagen && !a.purgado
              ? <button type="button" onClick={() => verImagen(a)} className="block aspect-[4/3] w-full bg-fondo" aria-label={`Ver ${a.nombre}`}><img src={a.url} alt={a.nombre} loading="lazy" className="size-full object-cover" /></button>
              : <a href={a.purgado ? undefined : `${a.url}${a.url.includes("?") ? "&" : "?"}descargar=1`} download={a.nombre} className="flex aspect-[4/3] w-full items-center justify-center bg-fondo text-azul"><FileText className="size-8" /></a>}
            <div className="p-2.5">
              <p className="truncate text-sm font-medium" title={a.nombre}>{a.nombre}</p>
              <p className="truncate text-[11px] text-gris">{a.tipo} · {a.de}</p>
              <p className="flex items-center justify-between text-[11px] text-gris"><span>{fechaCorta(a.fecha)}</span>
                {!a.purgado && <a href={`${a.url}${a.url.includes("?") ? "&" : "?"}descargar=1`} download={a.nombre} className="text-azul hover:underline" aria-label={`Descargar ${a.nombre}`}><Download className="size-3.5" /></a>}</p>
            </div>
          </li>
        ))}</ul>
      ))}

      {pestana === "entregas" && (e.entregas.length === 0 ? <Vacio icono={Truck} titulo="Todavía no hay entregas" /> : (
        <ol className="relative space-y-3 border-l-2 border-linea pl-5">{e.entregas.map((x, i) => (
          <li key={i} className="relative rounded-xl bg-white p-3 shadow-sm ring-1 ring-linea">
            <span className={cx("absolute -left-[27px] top-4 size-3 rounded-full ring-4 ring-fondo", x.tipo === "Tarea" ? "bg-azul" : "bg-verde")} aria-hidden />
            <p className="text-xs text-gris">{fechaCorta(x.fecha)} · {x.tipo}</p>
            <p className="font-medium">{x.que}</p>
            <p className="text-xs text-gris">{x.recibido_por ? (x.tipo === "Tarea" ? x.recibido_por : `Recibió: ${x.recibido_por}`) : ""}{x.estado ? ` · ${x.estado}` : ""}</p>
          </li>
        ))}</ol>
      ))}

      {pestana === "reporte" && <Reporte c={c} e={e} />}

      <FormCliente abierto={modal === "editar"} inicial={c} onCerrar={() => setModal(null)} onGuardado={() => { setModal(null); avisar("Cliente actualizado."); cargar(); }} />
      <FormOrden abierto={modal === "orden"} inicial={{ cliente: c.id }} onCerrar={() => setModal(null)} onGuardada={(o) => { setModal(null); avisar(`${o.numero} pedida.`); navigate(`/ordenes/${o.id}`); }} />
      {usuario.es_comercial && <FormOportunidad abierto={modal === "oportunidad"} inicial={{ cliente: c.id }} onCerrar={() => setModal(null)} onGuardado={(o) => { setModal(null); navigate(`/oportunidades?oportunidad=${o.id}`); }} />}
      <FormProyecto abierto={modal === "proyecto"} inicial={{ cliente: c.id }} onCerrar={() => setModal(null)} onGuardado={(p) => { setModal(null); navigate(`/proyectos/${p.id}`); }} />
      {(puedeValidar || puedeAsignar) && <FormTarea abierto={modal === "tarea"} inicial={{ cliente_ref: c.id, cliente: c.nombre }} gente={gente} onCerrar={() => setModal(null)}
        onGuardada={(msg) => { setModal(null); avisar(msg); cargarExpediente(); }} />}
    </div>
  );
}
