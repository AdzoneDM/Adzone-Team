// OT Maestra completa: E1–E7, compuerta G0, Órdenes de Área, traspasos, acta de entrega, facturas, costos y cierre (G6).
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft, ArrowRight, Ban, BadgeCheck, CircleCheckBig, FilePlus2, FileSignature, FileText, Lock, Pause, Pencil, Play, PlusCircle, Printer,
  Receipt, Send, ShieldAlert, Trash2, Undo2, Upload, Wallet,
} from "lucide-react";
import {
  cancelarOrden, cerrarOrden, comentarOrden, confirmarAnticipo, costosOrden, eliminarOrden, facturarOrden, ordenCompleta, pausarOrden, quitarArchivo,
  reanudarOrden, reenviarOrden, subirArchivosOrden,
} from "@/lib/api";
import { dinero, fechaCorta, fechaHora, hace } from "@/lib/formato";
import { useRecurso } from "@/lib/recursos";
import { useSesion } from "@/lib/sesion";
import Comentarios from "@/components/Comentarios";
import { Alerta, Boton, Cargando, Panel, Pestanas, cx, useAviso, useConfirmar } from "@/components/ui";
import FormOrden from "./FormOrden";
import {
  ActaModal, AgregarAreaModal, AutorizarCambioModal, CambioModal, ExcepcionModal, FirmarActaModal, LiberarG5Modal, LiberarModal, MotivoModal,
  RechazarG0Modal,
} from "./acciones";
import { AreaChip, Checklist, Dato, EstadoOA, EstadoOrden, EtapasE, Plazo, PrioridadOrden } from "./piezas";

function Historial({ eventos }) {
  return (
    <ol className="relative space-y-3 border-l border-linea pl-5">
      {eventos.map((h) => (
        <li key={h.id} className="relative">
          <span className="absolute -left-[25px] top-1.5 size-2.5 rounded-full bg-azul/40 ring-4 ring-white" />
          <p className="text-sm"><span className="font-medium">{h.texto}</span> <span className="text-gris">· {h.usuario_nombre} · {fechaHora(h.fecha)}</span></p>
          {h.detalle && <p className="text-sm text-gris">{h.detalle}</p>}
        </li>
      ))}
    </ol>
  );
}

function Archivos({ orden, archivos, onCambio }) {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const ref = useRef(null);
  const [categoria, setCategoria] = useState("ARTE");
  const [subiendo, setSubiendo] = useState(false);
  const subir = async (lista) => {
    if (!lista?.length) return;
    setSubiendo(true);
    try { await subirArchivosOrden(orden.id, Array.from(lista), { categoria }); avisar("Archivo(s) agregado(s)."); onCambio(); } catch (e) { avisar(e.message, "rojo"); }
    setSubiendo(false);
  };
  return (
    <Panel titulo="Archivos y evidencias" accion={orden.estado !== "CANCELADA" && (
      <div className="flex items-center gap-2">
        <select aria-label="Tipo de archivo" className="h-9 rounded-lg border border-linea bg-white px-2 text-sm" value={categoria} onChange={(e) => setCategoria(e.target.value)}>
          <option value="ARTE">Arte</option><option value="APROBACION">Aprobación del cliente</option><option value="FOTO">Foto</option><option value="COMPROBANTE">Comprobante</option><option value="OTRO">Otro</option>
        </select>
        <Boton variante="fantasma" tam="sm" icono={Upload} cargando={subiendo} onClick={() => ref.current?.click()}>Subir</Boton>
      </div>
    )}>
      <input ref={ref} type="file" multiple className="sr-only" tabIndex={-1} onChange={(e) => { subir(e.target.files); e.target.value = ""; }} />
      {archivos.length === 0 ? <p className="text-sm text-gris">Cotización firmada, brief, logo, artes, aprobaciones del cliente (WhatsApp/correo), fotos de la instalación… hasta 25 MB cada uno.</p> : (
        <ul className="grid grid-cols-[repeat(auto-fill,minmax(130px,1fr))] gap-3">
          {archivos.map((a) => (
            <li key={a.id} className="group relative overflow-hidden rounded-lg border border-linea">
              <a href={a.url} target="_blank" rel="noopener noreferrer" className="block">
                {a.es_imagen ? <img src={a.url} alt={a.nombre_original} loading="lazy" className="aspect-[4/3] w-full bg-fondo object-cover" />
                  : <span className="flex aspect-[4/3] items-center justify-center bg-fondo text-gris"><FileText className="size-8" /></span>}
                <span className="block truncate px-2 pt-1.5 text-xs">{a.nombre_original}</span>
                <span className="block truncate px-2 pb-1.5 text-[11px] text-gris">{{ ARTE: "Arte", APROBACION: "Aprobación", FOTO: "Foto", COMPROBANTE: "Comprobante" }[a.categoria] || "Otro"}</span>
              </a>
              <button type="button" aria-label={`Quitar ${a.nombre_original}`} onClick={async () => {
                if (!(await confirmar({ titulo: "¿Quitar este archivo?", mensaje: a.nombre_original, boton: "Quitar", peligro: true }))) return;
                try { await quitarArchivo(a.id); onCambio(); } catch (e) { avisar(e.message, "rojo"); }
              }} className="absolute right-1 top-1 rounded-md bg-white/90 p-1.5 text-rojo opacity-0 shadow group-hover:opacity-100 focus:opacity-100"><Trash2 className="size-4" /></button>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function Costos({ orden }) {
  const [c, setC] = useState(null);
  useEffect(() => { costosOrden(orden.id).then(setC).catch(() => setC(false)); }, [orden.id, orden.estado]);
  if (c === false) return null;
  if (!c) return <Panel titulo="Costo real y margen"><Cargando /></Panel>;
  const margenTono = c.margen_pct == null ? "" : c.margen_pct >= 35 ? "text-verde" : c.margen_pct >= 15 ? "text-noche" : "text-rojo";
  return (
    <Panel titulo="Costo real y margen" cuerpo="p-0">
      <div className="overflow-x-auto">
        <table className="tabla">
          <thead><tr><th>Orden de Área</th><th className="text-right">Horas</th><th className="text-right">Mano de obra</th><th className="text-right">Materiales</th><th className="text-right">Externos</th><th className="text-right">Retrabajo</th><th className="text-right">Total</th></tr></thead>
          <tbody>
            {Object.entries(c.areas).map(([n, x]) => (
              <tr key={n}><td className="num">{n}</td><td className="text-right num">{x.horas}</td><td className="text-right num">{dinero(x.mano_obra)}</td><td className="text-right num">{dinero(x.materiales)}</td>
                <td className="text-right num">{dinero(x.servicios_externos)}</td><td className="text-right num">{dinero(x.retrabajo)}</td><td className="text-right font-medium num">{dinero(x.total)}</td></tr>
            ))}
            {Number(c.gastos) > 0 && <tr><td>Gastos de la OT</td><td colSpan={5} /><td className="text-right num">{dinero(c.gastos)}</td></tr>}
          </tbody>
        </table>
      </div>
      <dl className="grid grid-cols-2 gap-3 border-t border-linea p-5 sm:grid-cols-5">
        <Dato etiqueta="Cotizado">{dinero(c.cotizado)}</Dato>
        <Dato etiqueta="Costo real">{dinero(c.costo_real)}</Dato>
        <Dato etiqueta="Margen"><span className={margenTono}>{dinero(c.margen)}{c.margen_pct != null && ` · ${c.margen_pct}%`}</span></Dato>
        <Dato etiqueta="Cobrado">{dinero(c.pagado)}</Dato>
        <Dato etiqueta="Saldo del cliente"><span className={Number(c.saldo) > 0 ? "text-[#a86a00]" : "text-verde"}>{dinero(c.saldo)}</span></Dato>
      </dl>
    </Panel>
  );
}

export default function OrdenDetalle() {
  const { id } = useParams();
  const { usuario, esAdmin, esCoordinacion, esFinanzas, misAreas } = useSesion();
  const [catalogo] = useRecurso("catalogo");
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const navigate = useNavigate();
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [modal, setModal] = useState(null);
  const [sel, setSel] = useState(null);
  const [pestana, setPestana] = useState("resumen");

  const cargar = useCallback(() => ordenCompleta(id).then(setD).catch((e) => setError(e.message)), [id]);
  useEffect(() => { cargar(); }, [cargar]);

  if (error) return <Alerta>{error}</Alerta>;
  if (!d) return <Cargando />;
  const o = d.orden;
  const hecho = (_, msg) => { setModal(null); setSel(null); if (msg) avisar(msg); cargar(); };
  const accion = async (fn, msg) => { try { await fn(); avisar(msg); cargar(); } catch (e) { avisar(e.message, "rojo"); } };
  const facturar = async (anticipo) => {
    try { const f = await facturarOrden(o.id, anticipo ? { anticipo: true } : {}); avisar(`Factura ${f.numero} creada en borrador. Emítela en Cashflow para el NCF.`); navigate(`/finanzas?ver=facturas&id=${f.id}`); }
    catch (e) { avisar(e.message, "rojo"); }
  };

  const soyComercial = [o.solicitada_por, o.asesor_comercial].includes(usuario.id);
  const enG0 = ["SOLICITADA", "DEVUELTA"].includes(o.estado);
  const enProduccion = ["LIBERADA", "EN_PRODUCCION", "LISTA"].includes(o.estado);
  const anticipoPendiente = !o.anticipo_confirmado && !o.excepcion_g0_por_nombre && Number(o.anticipo_requerido) > 0;
  const actaAbierta = d.actas.find((a) => !a.firmada);
  const supervisaIns = misAreas.includes("INS");

  const acciones = [];
  if (esCoordinacion && o.estado === "SOLICITADA") {
    acciones.push(<Boton key="li" icono={CircleCheckBig} onClick={() => setModal("liberar")}>Liberar (G0)</Boton>);
    acciones.push(<Boton key="rg" variante="secundario" icono={Undo2} onClick={() => setModal("rechazar")}>Rechazar</Boton>);
  }
  if (esFinanzas && enG0 && !o.anticipo_confirmado) acciones.push(<Boton key="ca" variante="secundario" icono={BadgeCheck} onClick={() => accion(() => confirmarAnticipo(o.id), "Anticipo confirmado (G0).")}>Confirmar anticipo</Boton>);
  if (esFinanzas && enG0 && Number(o.anticipo_requerido) > 0 && !d.facturas?.some((f) => f.es_anticipo)) acciones.push(<Boton key="fa" variante="secundario" icono={Receipt} onClick={() => facturar(true)}>Factura de anticipo</Boton>);
  if (esAdmin && o.estado === "SOLICITADA" && anticipoPendiente) acciones.push(<Boton key="ex" variante="secundario" icono={ShieldAlert} onClick={() => setModal("excepcion")}>Excepción sin anticipo</Boton>);
  if (o.estado === "DEVUELTA" && (soyComercial || esCoordinacion)) acciones.push(<Boton key="re" icono={Send} onClick={() => accion(() => reenviarOrden(o.id), "Reenviada a Coordinación.")}>Reenviar a Coordinación</Boton>);
  if (o.estado === "LISTA" && !actaAbierta && (esCoordinacion || esFinanzas || supervisaIns)) acciones.push(<Boton key="ac" variante="acento" icono={FileSignature} onClick={() => setModal("acta")}>Preparar acta de entrega</Boton>);
  if (esFinanzas && o.estado === "ENTREGADA" && !d.facturas?.some((f) => !f.es_anticipo)) acciones.push(<Boton key="ff" icono={Receipt} onClick={() => facturar(false)}>Facturar</Boton>);
  if (esFinanzas && o.estado === "ENTREGADA") acciones.push(<Boton key="ce" variante="secundario" icono={Lock} onClick={async () => {
    if (await confirmar({ titulo: `¿Cerrar ${o.numero} (G6)?`, mensaje: "Se calcula el costo real y el margen. Ya no se puede modificar.", boton: "Cerrar OT" })) accion(() => cerrarOrden(o.id), "OT cerrada (E7).");
  }}>Cerrar OT (G6)</Boton>);
  if (esCoordinacion && enProduccion) acciones.push(<Boton key="aa" variante="secundario" icono={PlusCircle} onClick={() => setModal("area")}>Agregar área</Boton>);
  if (!enG0 && !["CERRADA", "CANCELADA"].includes(o.estado)) acciones.push(<Boton key="cb" variante="secundario" icono={FilePlus2} onClick={() => setModal("cambio")}>Cambio / retrabajo</Boton>);
  if (esCoordinacion && enProduccion) acciones.push(<Boton key="pa" variante="secundario" icono={Pause} onClick={() => setModal("pausar")}>Pausar</Boton>);
  if (esCoordinacion && o.estado === "EN_PAUSA") acciones.push(<Boton key="rn" icono={Play} onClick={() => accion(() => reanudarOrden(o.id), "OT reanudada.")}>Reanudar</Boton>);
  if (o.puedo_editar) acciones.push(<Boton key="ed" variante="secundario" icono={Pencil} onClick={() => setModal("editar")}>Editar</Boton>);
  const puedeCancelar = !["ENTREGADA", "CERRADA", "CANCELADA"].includes(o.estado) && (esCoordinacion || (enG0 && soyComercial));
  const pendientesCambio = d.cambios.filter((c) => c.estado === "SOLICITADA").length;

  return (
    <div className="pb-24 md:pb-0">
      <Link to="/ordenes" className="mb-3 inline-flex items-center gap-1.5 text-sm font-medium text-azul hover:underline"><ArrowLeft className="size-4" />Órdenes</Link>
      <header className="mb-5 rounded-2xl border border-linea bg-white p-5">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-gris num">{o.numero || o.solicitud}</span>
          {o.numero && <span className="text-xs text-gris num">({o.solicitud})</span>}
          <EstadoOrden estado={o.estado} />
          <PrioridadOrden prioridad={o.prioridad} />
          {o.numero_cotizacion && <span className="text-xs text-gris">Cot. {o.numero_cotizacion}</span>}
          <a href={`/imprimir/ot/${o.id}`} target="_blank" rel="noopener" className="ml-auto inline-flex items-center gap-1 text-sm font-medium text-azul hover:underline"><Printer className="size-4" />F-01</a>
        </div>
        <h1 className="text-2xl font-semibold leading-tight md:text-[28px]">{o.titulo}</h1>
        <p className="mt-1 text-gris">
          <Link to={`/clientes/${o.cliente}`} className="font-medium text-tinta hover:text-azul">{o.cliente_nombre}</Link>
          {o.proyecto && <> · <Link to={`/proyectos/${o.proyecto}`} className="hover:text-azul">{o.proyecto_nombre}</Link></>}
          {" · "}<Plazo orden={o} />
        </p>
        {!enG0 && !["CANCELADA", "EN_PAUSA"].includes(o.estado) && <div className="mt-4"><EtapasE orden={o} areas={d.areas} /></div>}
        {o.estado === "CANCELADA" && <Alerta className="mt-4"><span className="font-medium">Cancelada:</span> {o.motivo_cancelacion}</Alerta>}
        {o.estado === "DEVUELTA" && <Alerta className="mt-4"><span className="font-medium">Devuelta en G0:</span> {o.g0_rechazo}</Alerta>}
        {o.estado === "SOLICITADA" && !esCoordinacion && <Alerta tono="azul" className="mt-4">Coordinación de Producción la revisa (G0) y le asigna el número OT. Te llega el aviso.
          {o.g0_faltan?.length > 0 && <> Falta: {o.g0_faltan.join("; ")}.</>}</Alerta>}
        {o.excepcion_g0_por_nombre && !o.anticipo_confirmado && <Alerta tono="amarillo" className="mt-4">Liberada sin anticipo por excepción de {o.excepcion_g0_por_nombre}: «{o.excepcion_g0_motivo}». Regularizar antes de {fechaHora(o.excepcion_g0_regularizar)}.</Alerta>}
        {pendientesCambio > 0 && esCoordinacion && <Alerta tono="amarillo" className="mt-4">{pendientesCambio} solicitud(es) de cambio por autorizar (pestaña «Cambios»).</Alerta>}
        {acciones.length > 0 && <div className="mt-4 hidden flex-wrap gap-2 md:flex">{acciones}</div>}
      </header>

      <Pestanas className="mb-5 md:w-fit" valor={pestana} onCambio={setPestana} opciones={[
        { valor: "resumen", etiqueta: "F-01" },
        { valor: "areas", etiqueta: `Áreas${d.areas.length ? ` (${d.areas.length})` : ""}` },
        { valor: "entrega", etiqueta: "Entrega y cierre" },
        { valor: "cambios", etiqueta: `Cambios${d.cambios.length ? ` (${d.cambios.length})` : ""}` },
        { valor: "conversacion", etiqueta: `Conversación${d.comentarios.length ? ` (${d.comentarios.length})` : ""}` },
      ]} />

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-5">
          {pestana === "resumen" && (
            <>
              <Panel titulo="1 · Datos del cliente">
                <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
                  <Dato etiqueta="Empresa">{o.cliente_nombre}{o.cliente_rnc && <span className="text-gris"> · RNC {o.cliente_rnc}</span>}</Dato>
                  <Dato etiqueta="Tipo de cliente">{o.tipo_cliente_nombre}</Dato>
                  <Dato etiqueta="Contacto">{[o.contacto, o.telefono, o.correo].filter(Boolean).join(" · ")}</Dato>
                  <Dato etiqueta="Dirección de entrega / instalación">{o.direccion_entrega}</Dato>
                  <Dato etiqueta="Asesor comercial">{o.asesor_comercial_nombre}</Dato>
                  <Dato etiqueta="Pedida por">{o.solicitada_por_nombre} · {hace(o.fecha_creacion)}</Dato>
                </dl>
              </Panel>
              <Panel titulo="2 · Alcance">
                <p className="whitespace-pre-line text-[15px]">{o.descripcion || <span className="text-gris">Sin descripción.</span>}</p>
                {o.exclusiones && <p className="mt-3 border-t border-linea-suave pt-3 text-sm"><span className="font-medium">No incluye:</span> {o.exclusiones}</p>}
              </Panel>
              <Panel titulo="3 · Áreas y secuencia" cuerpo="p-0">
                <ul className="divide-y divide-linea-suave">
                  {(d.areas.length ? d.areas : o.plan_areas.map((p, i) => ({ ...p, id: `p${i}` }))).map((a) => (
                    <li key={a.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-5 py-3">
                      <span className="w-6 text-center text-sm font-semibold text-gris num">{a.secuencia}</span>
                      <AreaChip area={a.area} />
                      <span className="min-w-0 flex-1 font-medium">{a.que_produce}</span>
                      {a.tiempo_estandar_dias != null && <span className="text-sm text-gris">{Number(a.tiempo_estandar_dias)} d</span>}
                      {a.numero && <Link to={`/ordenes/${o.id}/areas/${a.id}`} className="inline-flex items-center gap-1 text-sm font-medium text-azul hover:underline">{a.numero}<ArrowRight className="size-3.5" /></Link>}
                      {a.estado && <EstadoOA estado={a.estado} />}
                    </li>
                  ))}
                </ul>
              </Panel>
              <Panel titulo="4 · Fecha comprometida">
                <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-3">
                  <Dato etiqueta="La pide el cliente">{o.fecha_requerida && fechaCorta(o.fecha_requerida)}</Dato>
                  <Dato etiqueta="Comprometida">{o.fecha_compromiso ? fechaCorta(o.fecha_compromiso) : "Al liberar"}</Dato>
                  <Dato etiqueta="Rondas de cambios incluidas">{o.rondas_incluidas}</Dato>
                  {o.tiempo_estandar_dias != null && <Dato etiqueta="Cálculo" className="sm:col-span-3">Estándar {Number(o.tiempo_estandar_dias)} d · cola {Number(o.cola_dias)} d · aprobación {Number(o.aprobacion_dias)} d · colchón {o.colchon_pct} %</Dato>}
                </dl>
              </Panel>
              <Panel titulo="G0 · Compuerta de apertura">
                <Checklist items={(catalogo?.g0 || []).map((x) => x.texto)} valor={o.g0} soloLectura />
                <dl className="mt-3 grid gap-3 border-t border-linea-suave pt-3 sm:grid-cols-3">
                  <Dato etiqueta="Anticipo">{o.anticipo_confirmado ? `Confirmado · ${o.anticipo_confirmado_por_nombre || ""} ${o.anticipo_fecha ? fechaCorta(o.anticipo_fecha) : ""}` : o.excepcion_g0_por_nombre ? "Excepción de Gerencia" : "Pendiente"}</Dato>
                  <Dato etiqueta="Liberada por">{o.aprobada_por_nombre && `${o.aprobada_por_nombre} · ${fechaHora(o.fecha_aprobacion)}`}</Dato>
                  <Dato etiqueta="Coordinador a cargo">{o.responsable_nombre}</Dato>
                </dl>
              </Panel>
            </>
          )}

          {pestana === "areas" && (
            <>
              {d.areas.length === 0 ? <Panel><p className="text-sm text-gris">Al liberar la OT, Coordinación emite una Orden de Área por cada área de la sección 3.</p></Panel> : (
                <ul className="grid gap-3 md:grid-cols-2">
                  {d.areas.map((a) => (
                    <li key={a.id}>
                      <Link to={`/ordenes/${o.id}/areas/${a.id}`} className={cx("block rounded-xl border bg-white p-4 hover:border-azul/40 hover:shadow-md", a.vencida ? "border-rojo/40" : "border-linea")}>
                        <div className="mb-1 flex items-center justify-between gap-2"><span className="text-sm font-semibold text-gris num">{a.numero}</span><AreaChip area={a.area} /></div>
                        <p className="font-medium">{a.que_produce}</p>
                        <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-gris">
                          <EstadoOA estado={a.estado} />
                          {a.responsable_nombre && <span>{a.responsable_nombre}</span>}
                          {a.fecha_entrega_interna && <span className={cx(a.vencida && "font-medium text-rojo")}>· {fechaCorta(a.fecha_entrega_interna)}</span>}
                          {a.tarea && <span className="num">· {a.tarea.pasos_hechos}/{a.tarea.pasos} etapas</span>}
                          {a.g4_ronda > 0 && <span>· G4 ronda {a.g4_ronda}</span>}
                          {a.pase_retrabajo > 0 && <span className="text-[#a86a00]">· retrabajo {a.pase_retrabajo}</span>}
                        </div>
                        {a.traspaso_pendiente && <p className="mt-2 text-sm font-medium text-[#a86a00]">Traspaso a {a.traspaso_pendiente.recibe_area} esperando firma</p>}
                        {a.bloqueada_por?.length > 0 && <p className="mt-2 text-sm text-gris">Espera: {a.bloqueada_por.join(", ")}</p>}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
              {d.traspasos.length > 0 && (
                <Panel titulo="Vales de traspaso (F-13)" cuerpo="p-0">
                  <ul className="divide-y divide-linea-suave">
                    {d.traspasos.map((t) => (
                      <li key={t.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-5 py-3 text-sm">
                        <span className="font-semibold num">{t.numero}</span><span className="rounded bg-fondo px-1.5 text-xs font-medium">{t.compuerta}</span>
                        <span className="min-w-0 flex-1">{t.entrega_area} → {t.recibe_area}<span className="block text-gris">{t.que_entrega}</span></span>
                        <span className="text-gris">{t.entrega_por_nombre}{t.recibe_por_nombre && ` / ${t.recibe_por_nombre}`}</span>
                        <span className={cx("rounded-full px-2 py-0.5 text-xs font-medium", t.resultado === "ACEPTADO" ? "bg-verde-50 text-verde" : t.resultado === "RECHAZADO" ? "bg-rojo-50 text-[#a3170f]" : "bg-amarillo-50 text-[#7a5000]")}>{t.resultado_nombre}</span>
                        {t.causa_rechazo && <span className="w-full text-[#a3170f]">{t.causa_rechazo}</span>}
                      </li>
                    ))}
                  </ul>
                </Panel>
              )}
            </>
          )}

          {pestana === "entrega" && (
            <>
              <Panel titulo="Acta de entrega / instalación (F-12)">
                {d.actas.length === 0 ? <p className="text-sm text-gris">{o.estado === "LISTA" ? "Todas las áreas terminaron: prepara el acta." : "Se prepara cuando todas las áreas terminan (OT lista para entregar)."} Sin acta firmada no se cierra la OT ni se factura.</p> : (
                  <ul className="space-y-3">
                    {d.actas.map((a) => (
                      <li key={a.id} className="rounded-xl border border-linea p-4">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold num">{a.numero}</span><span className="text-sm text-gris">{a.modalidad_nombre} · {fechaCorta(a.fecha)} · {a.direccion}</span>
                          <a href={`/imprimir/acta/${a.id}`} target="_blank" rel="noopener" className="ml-auto inline-flex items-center gap-1 text-sm font-medium text-azul hover:underline"><Printer className="size-4" />Imprimir</a>
                        </div>
                        <ol className="mt-3 grid gap-2 text-sm sm:grid-cols-3">
                          <li className={cx("rounded-lg p-2", a.liberada_por_nombre ? "bg-verde-50 text-verde" : "bg-fondo text-gris")}>G5 · {a.liberada_por_nombre ? `liberada por ${a.liberada_por_nombre}` : "falta liberar la salida"}</li>
                          <li className={cx("rounded-lg p-2", a.firmada ? "bg-verde-50 text-verde" : "bg-fondo text-gris")}>{a.firmada ? `${a.conformidad_nombre} · ${a.supervisor_nombre}` : "Falta la firma del cliente"}</li>
                          <li className="rounded-lg bg-fondo p-2 text-gris">{a.saldo_al_liberar != null ? `Saldo al salir: ${dinero(a.saldo_al_liberar)}` : a.garantia || "—"}</li>
                        </ol>
                        {!a.firmada && (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {!a.liberada_por_nombre && esFinanzas && <Boton tam="sm" icono={Wallet} onClick={() => { setSel(a); setModal("g5"); }}>Liberar salida (G5)</Boton>}
                            {a.liberada_por_nombre && <Boton tam="sm" variante="acento" icono={FileSignature} onClick={() => { setSel(a); setModal("firmar"); }}>Firma del cliente</Boton>}
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
                {d.firmas.filter((f) => f.contexto === "ACTA").length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-4 border-t border-linea-suave pt-4">
                    {d.firmas.filter((f) => f.contexto === "ACTA").map((f) => (
                      <figure key={f.id} className="text-sm">
                        {f.imagen ? <img src={f.imagen} alt={`Firma de ${f.nombre}`} className="h-16 rounded border border-linea bg-white" /> : <div className="flex h-16 w-40 items-center justify-center rounded border border-dashed border-linea text-xs text-gris">Firma registrada</div>}
                        <figcaption className="mt-1"><span className="font-medium">{f.nombre}</span><span className="block text-gris">{f.rol}{f.documento && ` · ${f.documento}`}</span></figcaption>
                      </figure>
                    ))}
                  </div>
                )}
              </Panel>
              {d.facturas && (
                <Panel titulo="Facturas" accion={esFinanzas && ["ENTREGADA", "LISTA", "EN_PRODUCCION", "LIBERADA"].includes(o.estado) && Number(d.saldo) > 0 && (
                  <Boton variante="fantasma" tam="sm" icono={Receipt} onClick={() => facturar(true)}>Anticipo / abono</Boton>)}>
                  {d.facturas.length === 0 ? <p className="text-sm text-gris">Sin facturas. El anticipo se factura antes de liberar; el resto, con el acta firmada.</p> : (
                    <ul className="space-y-2">{d.facturas.map((f) => (
                      <li key={f.id}><Link to={`/finanzas?ver=facturas&id=${f.id}`} className="flex flex-wrap justify-between gap-2 text-sm hover:text-azul">
                        <span className="font-medium">{f.numero}{f.es_anticipo && " · anticipo"}{f.ncf && <span className="font-normal text-gris"> · NCF {f.ncf}</span>}</span>
                        <span>{dinero(f.total)} · saldo {dinero(f.saldo)} · {f.estado.toLowerCase()}</span></Link></li>
                    ))}</ul>
                  )}
                </Panel>
              )}
              {o.monto != null && <Costos orden={o} />}
              {o.estado === "CERRADA" && <Alerta tono="verde">Cerrada (E7) el {fechaHora(o.fecha_cierre)}. Costo real {dinero(o.costo_real)}.</Alerta>}
            </>
          )}

          {pestana === "cambios" && (
            <Panel titulo="Solicitudes de cambio y retrabajos (F-14)" accion={!enG0 && !["CERRADA", "CANCELADA"].includes(o.estado) && <Boton variante="fantasma" tam="sm" icono={FilePlus2} onClick={() => setModal("cambio")}>Nueva</Boton>} cuerpo="p-0">
              {d.cambios.length === 0 ? <p className="p-5 text-sm text-gris">Cuando el cliente pide algo fuera de lo aprobado, o hay que rehacer algo, se registra aquí: deja el costo, el impacto en la fecha y la acción preventiva.</p> : (
                <ul className="divide-y divide-linea-suave">{d.cambios.map((c) => (
                  <li key={c.id} className="px-5 py-3.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold num">{c.numero}</span>
                      <span className={cx("rounded-full px-2 py-0.5 text-xs font-medium", c.tipo === "CAMBIO" ? "bg-azul/10 text-azul" : "bg-amarillo-50 text-[#7a5000]")}>{c.tipo === "CAMBIO" ? "Cambio de alcance" : "Retrabajo"}</span>
                      {c.oa_numero && <span className="text-sm text-gris">{c.oa_numero}</span>}
                      <span className={cx("ml-auto rounded-full px-2 py-0.5 text-xs font-medium", c.estado === "AUTORIZADA" ? "bg-verde-50 text-verde" : c.estado === "RECHAZADA" ? "bg-rojo-50 text-[#a3170f]" : "bg-linea-suave")}>{c.estado_nombre}</span>
                    </div>
                    <p className="mt-1 text-[15px]">{c.descripcion}</p>
                    <p className="text-sm text-gris">{c.clasificacion.join(", ")}{Number(c.monto_cliente) > 0 && ` · al cliente ${dinero(c.monto_cliente)}`}{Number(c.costo_retrabajo) > 0 && ` · costo ${dinero(c.costo_retrabajo)}`} · {c.solicitado_por_nombre} · {hace(c.fecha)}</p>
                    {c.accion_preventiva && <p className="text-sm"><span className="font-medium">Acción preventiva:</span> {c.accion_preventiva}</p>}
                    {c.estado === "SOLICITADA" && esCoordinacion && <Boton tam="sm" className="mt-2" onClick={() => { setSel(c); setModal("autorizar"); }}>Revisar y autorizar</Boton>}
                  </li>
                ))}</ul>
              )}
            </Panel>
          )}

          {pestana === "conversacion" && (
            <>
              <Panel titulo="Conversación"><Comentarios lista={d.comentarios} onEnviar={async (texto) => { await comentarOrden(o.id, texto); cargar(); }} /></Panel>
              <Archivos orden={o} archivos={d.archivos} onCambio={cargar} />
            </>
          )}
        </div>

        <aside className="space-y-5">
          <Panel titulo="Resumen">
            <dl className="space-y-3">
              <Dato etiqueta="Coordinador">{o.responsable_nombre || "Al liberar"}</Dato>
              <Dato etiqueta="Áreas">{o.progreso ? `${o.progreso.terminadas} de ${o.progreso.areas} terminadas` : `${o.plan_areas.length} planificada(s)`}</Dato>
              <Dato etiqueta="Fecha comprometida">{o.fecha_compromiso && fechaCorta(o.fecha_compromiso)}</Dato>
              <Dato etiqueta="Entregada">{o.fecha_entrega && `${fechaCorta(o.fecha_entrega)} · recibió ${o.recibido_por}`}</Dato>
              <Dato etiqueta="Monto (sin ITBIS)">{o.monto != null && dinero(o.monto)}</Dato>
              <Dato etiqueta="Anticipo requerido">{o.anticipo_requerido != null && `${dinero(o.anticipo_requerido)}${o.anticipo_confirmado ? " · confirmado" : ""}`}</Dato>
              {d.saldo != null && <Dato etiqueta="Saldo del cliente">{dinero(d.saldo)}</Dato>}
            </dl>
          </Panel>
          {pestana !== "conversacion" && <Archivos orden={o} archivos={d.archivos} onCambio={cargar} />}
          <Panel titulo="Historial"><Historial eventos={d.historial} /></Panel>
          {(puedeCancelar || (enG0 && (esCoordinacion || soyComercial))) && (
            <div className="flex flex-wrap gap-2">
              {puedeCancelar && <Boton variante="peligro" icono={Ban} onClick={() => setModal("cancelar")}>Cancelar OT</Boton>}
              {enG0 && (
                <Boton variante="fantasma" icono={Trash2} className="text-rojo" onClick={async () => {
                  if (!(await confirmar({ titulo: "¿Borrar esta solicitud?", mensaje: "Solo se puede mientras no se ha liberado.", boton: "Borrar", peligro: true }))) return;
                  try { await eliminarOrden(o.id); avisar("Solicitud borrada."); navigate("/ordenes"); } catch (e) { avisar(e.message, "rojo"); }
                }}>Borrar</Boton>
              )}
            </div>
          )}
        </aside>
      </div>

      {acciones.length > 0 && (
        <div className="fixed inset-x-0 bottom-[calc(3.5rem+env(safe-area-inset-bottom))] z-30 flex gap-2 overflow-x-auto border-t border-linea bg-white/95 px-4 py-2.5 backdrop-blur md:hidden">
          {acciones.map((a) => <div key={a.key} className="shrink-0">{a}</div>)}
        </div>
      )}

      <LiberarModal orden={o} abierto={modal === "liberar"} onCerrar={() => setModal(null)} onHecho={hecho} />
      <RechazarG0Modal orden={o} abierto={modal === "rechazar"} onCerrar={() => setModal(null)} onHecho={hecho} />
      <ExcepcionModal orden={o} abierto={modal === "excepcion"} onCerrar={() => setModal(null)} onHecho={hecho} />
      <AgregarAreaModal orden={o} abierto={modal === "area"} onCerrar={() => setModal(null)} onHecho={hecho} />
      <CambioModal orden={o} areas={d.areas} abierto={modal === "cambio"} onCerrar={() => setModal(null)} onHecho={hecho} />
      <AutorizarCambioModal cambio={sel} abierto={modal === "autorizar"} onCerrar={() => setModal(null)} onHecho={hecho} />
      <ActaModal orden={o} abierto={modal === "acta"} onCerrar={() => setModal(null)} onHecho={(r, m) => { hecho(r, m); setPestana("entrega"); }} />
      <LiberarG5Modal acta={sel} saldo={d.saldo} abierto={modal === "g5"} onCerrar={() => setModal(null)} onHecho={hecho} />
      <FirmarActaModal acta={sel} abierto={modal === "firmar"} onCerrar={() => setModal(null)} onHecho={hecho} />
      <MotivoModal titulo={`Pausar ${o.codigo}`} boton="Pausar" abierto={modal === "pausar"} onCerrar={() => setModal(null)}
        onConfirmar={async (m) => { await pausarOrden(o.id, m); hecho(null, "OT en pausa."); }} />
      <MotivoModal titulo={`Cancelar ${o.codigo}`} descripcion="Sus Órdenes de Área y tareas abiertas también se cancelan." boton="Cancelar OT" peligro abierto={modal === "cancelar"} onCerrar={() => setModal(null)}
        onConfirmar={async (m) => { await cancelarOrden(o.id, m); hecho(null, "OT cancelada."); }} />
      <FormOrden abierto={modal === "editar"} inicial={o} onCerrar={() => setModal(null)} onGuardada={() => hecho(null, "Cambios guardados.")} />
    </div>
  );
}
