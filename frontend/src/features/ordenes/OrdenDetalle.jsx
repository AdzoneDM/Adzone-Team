// Una orden de trabajo completa: etapa, datos del área, tareas, archivos, conversación e historial.
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft, Ban, CircleCheckBig, FileText, Paperclip, Pause, Pencil, Play, Receipt, Trash2, Truck, Upload,
} from "lucide-react";
import { comentarOrden, eliminarOrden, facturarOrden, moverOrden, ordenCompleta, quitarArchivo, reanudarOrden, subirArchivosOrden } from "@/lib/api";
import { ESTADOS_ORDEN, dinero, fechaCorta, fechaHora, hace } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import Comentarios from "@/components/Comentarios";
import { Alerta, Boton, Cargando, EstadoTarea, Panel, cx, useAviso, useConfirmar } from "@/components/ui";
import { DetalleTarea, Progreso } from "@/features/tareas/componentes";
import BotonCronometro from "@/features/tiempo/BotonCronometro";
import FormOrden from "./FormOrden";
import { AprobarModal, CancelarOrdenModal, EntregarOrdenModal } from "./acciones";
import { EstadoOrden, Plazo, PrioridadOrden, TipoOrden } from "./piezas";

const ETAPAS = ["SOLICITADA", "APROBADA", "EN_PRODUCCION", "CONTROL_CALIDAD", "LISTA", "ENTREGADA"];

function Etapas({ estado }) {
  const actual = ETAPAS.indexOf(estado);
  return (
    <ol className="flex gap-1" aria-label="Etapas de la orden">
      {ETAPAS.map((e, i) => {
        const hecha = actual >= 0 && i < actual;
        const ahora = i === actual;
        return (
          <li key={e} className="min-w-0 flex-1">
            <span className={cx("block h-1.5 rounded-full", hecha ? "bg-azul" : ahora ? "bg-amarillo" : "bg-linea")} />
            <span className={cx("mt-1.5 hidden truncate text-xs md:block", ahora ? "font-semibold text-tinta" : "text-gris")}>{ESTADOS_ORDEN[e]}</span>
          </li>
        );
      })}
    </ol>
  );
}

function valorCampo(campo, v) {
  if (v === undefined || v === null || v === "" || (Array.isArray(v) && !v.length)) return null;
  if (campo.tipo === "multiple") return v.join(", ");
  if (campo.tipo === "sino") return v ? "Sí" : "No";
  if (campo.tipo === "fecha") return fechaCorta(v);
  if (campo.tipo === "fechahora") return fechaHora(v);
  if (campo.tipo === "dinero") return dinero(v);
  if (campo.tipo === "numero") return Number(v).toLocaleString("es-DO");
  return v;
}

function Dato({ etiqueta, children }) {
  if (children === null || children === undefined || children === "" || children === false) return null;
  return <div><dt className="text-sm text-gris">{etiqueta}</dt><dd className="font-medium">{children}</dd></div>;
}

export default function OrdenDetalle() {
  const { id } = useParams();
  const { usuario } = useSesion();
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const navigate = useNavigate();
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [modal, setModal] = useState(null);
  const [tarea, setTarea] = useState(null);
  const [subiendo, setSubiendo] = useState(false);
  const archivoRef = useRef(null);

  const cargar = useCallback(() => ordenCompleta(id).then(setD).catch((e) => setError(e.message)), [id]);
  useEffect(() => { cargar(); }, [cargar]);

  if (error) return <Alerta>{error}</Alerta>;
  if (!d) return <Cargando />;
  const o = d.orden;
  const hecho = (_, msg) => { setModal(null); if (msg) avisar(msg); cargar(); };
  const mover = async (estado, msg) => {
    try { await moverOrden(o.id, estado); avisar(msg || `Ahora: ${ESTADOS_ORDEN[estado]}.`); cargar(); } catch (e) { avisar(e.message, "rojo"); }
  };
  const subir = async (lista) => {
    if (!lista?.length) return;
    setSubiendo(true);
    try { await subirArchivosOrden(o.id, Array.from(lista)); avisar("Archivo(s) agregado(s)."); cargar(); } catch (e) { avisar(e.message, "rojo"); }
    setSubiendo(false);
  };

  const acciones = [];
  if (o.puedo_gestionar && o.estado === "SOLICITADA") acciones.push(<Boton key="ap" icono={CircleCheckBig} onClick={() => setModal("aprobar")}>Aprobar</Boton>);
  if ((o.puedo_gestionar || o.soy_responsable) && o.estado === "LISTA") acciones.push(<Boton key="en" variante="acento" icono={Truck} onClick={() => setModal("entregar")}>Entregar</Boton>);
  if (o.puedo_gestionar && o.estado === "CONTROL_CALIDAD" && !o.progreso) acciones.push(<Boton key="li" icono={CircleCheckBig} onClick={() => mover("LISTA")}>Marcar lista</Boton>);
  if ((o.puedo_gestionar || o.soy_responsable) && o.estado === "APROBADA" && !o.progreso) acciones.push(<Boton key="pr" icono={Play} onClick={() => mover("EN_PRODUCCION")}>Empezar producción</Boton>);
  if (o.puedo_gestionar && o.siguientes.includes("EN_PAUSA")) acciones.push(<Boton key="pa" variante="secundario" icono={Pause} onClick={() => mover("EN_PAUSA", "Orden en pausa.")}>Pausar</Boton>);
  if (o.puedo_gestionar && o.estado === "EN_PAUSA") acciones.push(<Boton key="re" icono={Play} onClick={async () => { try { await reanudarOrden(o.id); avisar("Orden reanudada."); cargar(); } catch (e) { avisar(e.message, "rojo"); } }}>Reanudar</Boton>);
  if (usuario.es_finanzas && ["LISTA", "ENTREGADA"].includes(o.estado) && o.facturada === false) {
    acciones.push(<Boton key="fa" variante="secundario" icono={Receipt} onClick={async () => {
      try { const f = await facturarOrden(o.id); avisar(`Factura ${f.numero} creada en borrador.`); navigate(`/finanzas?ver=facturas&id=${f.id}`); } catch (e) { avisar(e.message, "rojo"); }
    }}>Facturar</Boton>);
  }
  if (o.soy_responsable && !["ENTREGADA", "CANCELADA", "SOLICITADA"].includes(o.estado)) acciones.push(<BotonCronometro key="cr" orden={o.id} />);
  if (o.puedo_editar) acciones.push(<Boton key="ed" variante="secundario" icono={Pencil} onClick={() => setModal("editar")}>Editar</Boton>);
  const puedeCancelar = !["ENTREGADA", "CANCELADA"].includes(o.estado) && (o.puedo_gestionar || (o.estado === "SOLICITADA" && o.solicitada_por === usuario.id));

  const campos = d.formulario?.campos || [];
  const datosArea = campos.map((c) => ({ c, v: valorCampo(c, o.detalles?.[c.clave]) })).filter((x) => x.v !== null);

  return (
    <div className="pb-24 md:pb-0">
      <Link to="/ordenes" className="mb-3 inline-flex items-center gap-1.5 text-sm font-medium text-azul hover:underline"><ArrowLeft className="size-4" />Órdenes</Link>
      <header className="mb-5 rounded-2xl border border-linea bg-white p-5">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-gris num">{o.numero}</span>
          <TipoOrden orden={o} />
          <EstadoOrden estado={o.estado} />
          <PrioridadOrden prioridad={o.prioridad} />
        </div>
        <h1 className="text-2xl font-semibold leading-tight md:text-[28px]">{o.titulo}</h1>
        <p className="mt-1 text-gris">
          <Link to={`/clientes/${o.cliente}`} className="font-medium text-tinta hover:text-azul">{o.cliente_nombre}</Link>
          {o.proyecto && <> · <Link to={`/proyectos/${o.proyecto}`} className="hover:text-azul">{o.proyecto_nombre}</Link></>}
          {" · "}<Plazo orden={o} />
        </p>
        {!["CANCELADA", "EN_PAUSA"].includes(o.estado) && <div className="mt-4"><Etapas estado={o.estado} /></div>}
        {o.estado === "CANCELADA" && <Alerta className="mt-4"><span className="font-medium">Cancelada:</span> {o.motivo_cancelacion}</Alerta>}
        {o.estado === "SOLICITADA" && !o.puedo_gestionar && <Alerta tono="azul" className="mt-4">{o.departamento_nombre} la revisará para aprobarla y asignarla. Te llega el aviso.</Alerta>}
        {acciones.length > 0 && <div className="mt-4 hidden flex-wrap gap-2 md:flex">{acciones}</div>}
      </header>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-5">
          {(datosArea.length > 0 || o.descripcion) && (
            <Panel titulo={`Datos de ${o.tipo_nombre.toLowerCase()}`}>
              {datosArea.length > 0 && (
                <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
                  {datosArea.map(({ c, v }) => <div key={c.clave} className={c.tipo === "largo" ? "sm:col-span-2" : ""}><dt className="text-sm text-gris">{c.etiqueta}</dt><dd className="whitespace-pre-line font-medium">{v}</dd></div>)}
                </dl>
              )}
              {o.descripcion && <p className={cx("whitespace-pre-line text-[15px]", datosArea.length && "mt-4 border-t border-linea-suave pt-4")}>{o.descripcion}</p>}
            </Panel>
          )}

          <Panel titulo="Producción" cuerpo="p-0">
            {d.tareas.length === 0 ? (
              <p className="p-5 text-sm text-gris">{o.estado === "SOLICITADA" ? "Al aprobarla se crea la tarea de producción con sus pasos." : "Sin tareas: el avance se mueve a mano."}</p>
            ) : (
              <ul className="divide-y divide-linea-suave">
                {d.tareas.map((t) => (
                  <li key={t.id}>
                    <button type="button" onClick={() => setTarea(t)} className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-5 py-3.5 text-left hover:bg-fondo">
                      <span className="min-w-0 flex-1"><span className="block font-medium">{t.titulo}</span>
                        <span className="text-sm text-gris">{[t.colaborador_nombre, ...(t.companeros_nombres || [])].join(", ")} · vence {fechaCorta(t.fecha_limite)}</span></span>
                      <Progreso progreso={t.progreso} />
                      <EstadoTarea estado={t.estado} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel titulo="Archivos" accion={o.estado !== "CANCELADA" && (
            <Boton variante="fantasma" tam="sm" icono={Upload} cargando={subiendo} onClick={() => archivoRef.current?.click()}>Subir</Boton>
          )}>
            <input ref={archivoRef} type="file" multiple className="sr-only" tabIndex={-1} onChange={(e) => { subir(e.target.files); e.target.value = ""; }} />
            {d.archivos.length === 0 ? <p className="text-sm text-gris">Artes, referencias, fotos de la instalación, comprobantes… (hasta 25 MB cada uno).</p> : (
              <ul className="grid grid-cols-[repeat(auto-fill,minmax(130px,1fr))] gap-3">
                {d.archivos.map((a) => (
                  <li key={a.id} className="group relative overflow-hidden rounded-lg border border-linea">
                    <a href={a.url} target="_blank" rel="noopener noreferrer" className="block">
                      {a.es_imagen ? <img src={a.url} alt={a.nombre_original} loading="lazy" className="aspect-[4/3] w-full bg-fondo object-cover" />
                        : <span className="flex aspect-[4/3] items-center justify-center bg-fondo text-gris"><FileText className="size-8" /></span>}
                      <span className="block truncate px-2 py-1.5 text-xs">{a.nombre_original}</span>
                    </a>
                    <button type="button" aria-label={`Quitar ${a.nombre_original}`} onClick={async () => {
                      if (!(await confirmar({ titulo: "¿Quitar este archivo?", mensaje: a.nombre_original, boton: "Quitar", peligro: true }))) return;
                      try { await quitarArchivo(a.id); cargar(); } catch (e) { avisar(e.message, "rojo"); }
                    }} className="absolute right-1 top-1 rounded-md bg-white/90 p-1.5 text-rojo opacity-0 shadow group-hover:opacity-100 focus:opacity-100"><Trash2 className="size-4" /></button>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel titulo="Conversación">
            <Comentarios lista={d.comentarios} onEnviar={async (texto) => { await comentarOrden(o.id, texto); cargar(); }} />
          </Panel>
        </div>

        <aside className="space-y-5">
          <Panel titulo="Resumen">
            <dl className="space-y-3">
              <Dato etiqueta="Responsable">{o.responsable_nombre || "Por asignar"}</Dato>
              <Dato etiqueta="Equipo">{o.equipo_nombres?.join(", ")}</Dato>
              <Dato etiqueta="Departamento">{o.departamento_nombre}</Dato>
              <Dato etiqueta="Pedida por">{o.solicitada_por_nombre} · {hace(o.fecha_creacion)}</Dato>
              <Dato etiqueta="La pide el cliente para">{o.fecha_requerida && fechaCorta(o.fecha_requerida)}</Dato>
              <Dato etiqueta="Fecha comprometida">{o.fecha_compromiso && fechaCorta(o.fecha_compromiso)}</Dato>
              <Dato etiqueta="Aprobada por">{o.aprobada_por_nombre}</Dato>
              <Dato etiqueta="Entregada">{o.fecha_entrega && `${fechaCorta(o.fecha_entrega)} · recibió ${o.recibido_por}`}</Dato>
              <Dato etiqueta="Monto acordado">{o.monto != null && dinero(o.monto)}</Dato>
            </dl>
          </Panel>
          {d.facturas && d.facturas.length > 0 && (
            <Panel titulo="Facturas">
              <ul className="space-y-2">{d.facturas.map((f) => (
                <li key={f.id}><Link to={`/finanzas?ver=facturas&id=${f.id}`} className="flex justify-between text-sm hover:text-azul"><span className="font-medium">{f.numero}</span><span>{dinero(f.total)} · saldo {dinero(f.saldo)}</span></Link></li>
              ))}</ul>
            </Panel>
          )}
          <Panel titulo="Historial">
            <ol className="relative space-y-3 border-l border-linea pl-5">
              {d.historial.map((h) => (
                <li key={h.id} className="relative">
                  <span className="absolute -left-[25px] top-1.5 size-2.5 rounded-full bg-azul/40 ring-4 ring-white" />
                  <p className="text-sm"><span className="font-medium">{h.texto}</span> <span className="text-gris">· {h.usuario_nombre} · {fechaHora(h.fecha)}</span></p>
                  {h.detalle && <p className="text-sm text-gris">{h.detalle}</p>}
                </li>
              ))}
            </ol>
          </Panel>
          {(puedeCancelar || (o.estado === "SOLICITADA" && (o.puedo_gestionar || o.solicitada_por === usuario.id))) && (
            <div className="flex flex-wrap gap-2">
              {puedeCancelar && <Boton variante="peligro" icono={Ban} onClick={() => setModal("cancelar")}>Cancelar orden</Boton>}
              {o.estado === "SOLICITADA" && (
                <Boton variante="fantasma" icono={Trash2} className="text-rojo" onClick={async () => {
                  if (!(await confirmar({ titulo: "¿Borrar esta orden?", mensaje: "Solo se puede mientras nadie la ha aprobado.", boton: "Borrar", peligro: true }))) return;
                  try { await eliminarOrden(o.id); avisar("Orden borrada."); navigate("/ordenes"); } catch (e) { avisar(e.message, "rojo"); }
                }}>Borrar</Boton>
              )}
            </div>
          )}
        </aside>
      </div>

      {/* Celular: acciones fijas abajo, al alcance del pulgar */}
      {acciones.length > 0 && (
        <div className="fixed inset-x-0 bottom-[calc(3.5rem+env(safe-area-inset-bottom))] z-30 flex gap-2 overflow-x-auto border-t border-linea bg-white/95 px-4 py-2.5 backdrop-blur md:hidden">
          {acciones.map((a) => <div key={a.key} className="shrink-0">{a}</div>)}
        </div>
      )}

      <AprobarModal orden={o} abierto={modal === "aprobar"} onCerrar={() => setModal(null)} onHecho={hecho} />
      <EntregarOrdenModal orden={o} abierto={modal === "entregar"} onCerrar={() => setModal(null)} onHecho={hecho} />
      <CancelarOrdenModal orden={o} abierto={modal === "cancelar"} onCerrar={() => setModal(null)} onHecho={hecho} />
      <FormOrden abierto={modal === "editar"} inicial={o} onCerrar={() => setModal(null)} onGuardada={() => hecho(null, "Cambios guardados.")} />
      <DetalleTarea tarea={tarea} abierto={!!tarea} onCerrar={() => setTarea(null)}
        onCambio={(t) => { setTarea(t); cargar(); }}
        pie={tarea && tarea.soy_participante && ["PENDIENTE", "EN_PROGRESO"].includes(tarea.estado) && (
          <div className="flex w-full flex-wrap justify-end gap-2">
            <BotonCronometro tarea={tarea.id} />
            <Link to={`/mis-tareas?tarea=${tarea.id}`} className="inline-flex h-11 items-center gap-2 rounded-lg bg-amarillo px-4 text-[15px] font-medium text-tinta"><Paperclip className="size-4" />Entregar desde Mis tareas</Link>
          </div>
        )} />
    </div>
  );
}
