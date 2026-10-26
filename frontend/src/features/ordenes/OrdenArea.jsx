// Orden de Área (F-02 a F-10): G1 de entrada, especificación, ejecución (tarea), aprobación del cliente (G4),
// control de calidad (G3 al validar la tarea), salida con doble firma (G2/G5), materiales, incidencias y costos.
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft, CircleCheckBig, ClipboardCheck, FileText, Package, Pencil, Printer, Send, ShieldCheck, Undo2, Upload, Wrench, X,
} from "lucide-react";
import {
  accionArea, accionVale, areaCompleta, costosArea, guardarArea, incidenciaArea, listarMateriales, listarVales, pedirVale, recibirTraspaso,
  subirArchivosOrden, validarTarea,
} from "@/lib/api";
import { dinero, fechaCorta, fechaHora, hace, hoyISO } from "@/lib/formato";
import { useRecurso } from "@/lib/recursos";
import { useSesion } from "@/lib/sesion";
import { SelectorPersona, SelectorPersonas } from "@/components/Selectores";
import { Alerta, Boton, Campo, Cargando, EntradaEstrellas, Modal, Panel, cx, useAviso } from "@/components/ui";
import { CambioModal } from "./acciones";
import { AreaChip, CampoFormato, Checklist, Dato, EstadoOA, FichaFormato, PrioridadOrden } from "./piezas";

const PASOS = [["G1", "Entrada"], ["E3", "Ejecución"], ["G4", "Cliente"], ["G3", "Calidad"], ["G2", "Salida"]];

function Compuertas({ oa }) {
  const hecho = {
    G1: !!oa.g1_fecha && oa.estado !== "RECHAZADA",
    E3: ["EN_EJECUCION", "EN_APROBACION", "TERMINADA"].includes(oa.estado) || oa.g3_resultado === "APROBADO",
    G4: oa.g4_aprobado,
    G3: oa.g3_resultado === "APROBADO",
    G2: oa.estado === "TERMINADA",
  };
  const pasos = PASOS.filter(([k]) => k !== "G4" || oa.requiere_g4);
  const actual = pasos.findIndex(([k]) => !hecho[k]);
  return (
    <ol className={cx("grid gap-1", pasos.length === 5 ? "grid-cols-5" : "grid-cols-4")} aria-label="Compuertas">
      {pasos.map(([k, t], i) => (
        <li key={k} aria-current={i === actual ? "step" : undefined}>
          <span className={cx("block h-1.5 rounded-full", hecho[k] ? "bg-azul" : i === actual ? "bg-amarillo" : "bg-linea")} />
          <span className={cx("mt-1.5 block truncate text-xs", i === actual ? "font-semibold" : "text-gris")}><span className="num">{k}</span> · {t}</span>
        </li>
      ))}
    </ol>
  );
}

function Recepcion({ oa, formato, onHecho }) {
  const [g1, setG1] = useState(oa.g1 || {});
  const [resp, setResp] = useState(oa.responsable ? String(oa.responsable) : "");
  const [equipo, setEquipo] = useState([]);
  const [fecha, setFecha] = useState(oa.fecha_entrega_interna || "");
  const [causa, setCausa] = useState("");
  const [rechazando, setRechazando] = useState(false);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [catalogo] = useRecurso("catalogo");
  const depto = catalogo?.areas.find((a) => a.codigo === oa.area)?.departamento;
  const ir = async (fn, msg) => { setEnviando(true); setError(""); try { await fn(); onHecho(msg); } catch (e) { setError(e.message); } setEnviando(false); };
  return (
    <Panel titulo={`G1 · Recibir ${oa.numero}`}>
      <div className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        <Checklist items={formato.g1} valor={g1} onCambio={setG1} ayuda="El área no inicia si falta una casilla: si falta algo, recházala y di qué." />
        {!rechazando ? (
          <>
            <div className="grid gap-4 sm:grid-cols-2">
              <SelectorPersona etiqueta="Ejecutor" valor={resp} onCambio={setResp} filtro={depto ? (g) => g.departamento === depto : undefined} ayuda={depto && `Personas de ${depto}.`} />
              <Campo etiqueta="Entrega interna">{(id) => <input id={id} type="date" min={hoyISO()} className="campo" value={fecha} onChange={(e) => setFecha(e.target.value)} />}</Campo>
            </div>
            <SelectorPersonas leyenda="Apoyo (opcional)" valor={equipo} onCambio={setEquipo} excluir={[resp]} filtro={depto ? (g) => g.departamento === depto : undefined} />
            <div className="flex flex-wrap justify-end gap-2">
              <Boton variante="secundario" icono={Undo2} onClick={() => setRechazando(true)}>Rechazar</Boton>
              <Boton icono={CircleCheckBig} cargando={enviando} onClick={() => ir(() => accionArea(oa.id, "recibir", { g1, responsable: Number(resp) || null, equipo: equipo.map(Number), fecha_entrega_interna: fecha || null }),
                "Recibida (E2). El ejecutor tiene su tarea con las etapas del formato.")}>Recibir y asignar</Boton>
            </div>
          </>
        ) : (
          <>
            <Campo etiqueta="¿Qué falta? (se devuelve a Coordinación)">{(id) => <textarea id={id} rows={3} className="campo" value={causa} onChange={(e) => setCausa(e.target.value)} autoFocus />}</Campo>
            <div className="flex justify-end gap-2"><Boton variante="secundario" onClick={() => setRechazando(false)}>Volver</Boton>
              <Boton variante="peligro" icono={Undo2} cargando={enviando} disabled={causa.trim().length < 3} onClick={() => ir(() => accionArea(oa.id, "rechazar", { g1, causa: causa.trim() }), "Rechazada en G1. Coordinación recibió el aviso.")}>Rechazar en G1</Boton></div>
          </>
        )}
      </div>
    </Panel>
  );
}

function AprobacionCliente({ oa, onHecho }) {
  const [catalogo] = useRecurso("catalogo");
  const [f, setF] = useState({ aprobado: true, canales: [], aprobado_por: "", version: "", con_cambios: false, comentario: "" });
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const enviar = async () => {
    setEnviando(true); setError("");
    try { const r = await accionArea(oa.id, "registrar_g4", f); onHecho(r.aviso || (f.aprobado ? "Aprobación del cliente registrada (G4)." : `Cambios pedidos (ronda ${oa.g4_ronda}).`), r.aviso ? "amarillo" : undefined); }
    catch (e) { setError(e.message); }
    setEnviando(false);
  };
  return (
    <Panel titulo={`G4 · Respuesta del cliente (ronda ${oa.g4_ronda})`}>
      <div className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        <div className="grid grid-cols-2 gap-2">
          {[[true, "Aprobó"], [false, "Pidió cambios"]].map(([v, t]) => (
            <label key={t} className={cx("flex cursor-pointer items-center gap-2 rounded-lg border p-3", f.aprobado === v ? "border-azul bg-azul/5" : "border-linea")}>
              <input type="radio" name="g4" checked={f.aprobado === v} onChange={() => setF({ ...f, aprobado: v })} className="accent-azul" />{t}</label>
          ))}
        </div>
        {f.aprobado ? (
          <>
            <fieldset><legend className="etiqueta">Aprobación por escrito</legend>
              <div className="flex flex-wrap gap-2">{(catalogo?.g4_canales || []).map((c) => {
                const on = f.canales.includes(c);
                return <button key={c} type="button" aria-pressed={on} onClick={() => setF({ ...f, canales: on ? f.canales.filter((x) => x !== c) : [...f.canales, c] })}
                  className={cx("min-h-10 rounded-full border px-3.5 text-sm font-medium", on ? "border-azul bg-azul text-white" : "border-linea bg-white")}>{c}</button>;
              })}</div>
              <p className="ayuda">Sube la captura o el correo en «Archivos» como «Aprobación del cliente».</p></fieldset>
            <div className="grid gap-4 sm:grid-cols-2">
              <Campo etiqueta="Aprobó (nombre)">{(id) => <input id={id} className="campo" value={f.aprobado_por} onChange={(e) => setF({ ...f, aprobado_por: e.target.value })} />}</Campo>
              <Campo etiqueta="Versión aprobada">{(id) => <input id={id} className="campo" value={f.version} onChange={(e) => setF({ ...f, version: e.target.value })} placeholder="v3" />}</Campo>
            </div>
            <label className="flex items-center gap-2 text-[15px]"><input type="checkbox" checked={f.con_cambios} onChange={(e) => setF({ ...f, con_cambios: e.target.checked })} className="size-4 accent-azul" />Aprobado con cambios menores</label>
          </>
        ) : <Campo etiqueta="¿Qué pidió cambiar?">{(id) => <textarea id={id} rows={3} className="campo" value={f.comentario} onChange={(e) => setF({ ...f, comentario: e.target.value })} />}</Campo>}
        <div className="flex justify-end"><Boton icono={ShieldCheck} cargando={enviando} onClick={enviar}>Registrar respuesta</Boton></div>
      </div>
    </Panel>
  );
}

function ValidarAqui({ oa, tarea, formato, onHecho }) {
  const [g3, setG3] = useState(oa.g3 || {});
  const [nota, setNota] = useState(0);
  const [comentario, setComentario] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  return (
    <Panel titulo="G3 · Control de calidad interno">
      <div className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        <p className="text-sm text-gris">El ejecutor entregó. Revisa y firma: validar la tarea es firmar el G3. Para devolverla con comentarios, usa «Por validar».</p>
        <Checklist items={formato.g3} valor={g3} onCambio={setG3} />
        <EntradaEstrellas valor={nota} onCambio={setNota} nombre={`g3-${oa.id}`} />
        <Campo etiqueta="Observaciones (opcional)">{(id) => <textarea id={id} rows={2} className="campo" value={comentario} onChange={(e) => setComentario(e.target.value)} />}</Campo>
        <div className="flex flex-wrap justify-end gap-2">
          <Link to="/validar" className="inline-flex h-11 items-center rounded-lg border border-linea px-4 text-[15px] font-medium hover:bg-fondo">Devolver desde «Por validar»</Link>
          <Boton icono={ClipboardCheck} cargando={enviando} onClick={async () => {
            if (!nota) return setError("Califica la calidad (1 a 5 estrellas).");
            setEnviando(true); setError("");
            try { await validarTarea(tarea.id, nota, comentario, { g3 }); onHecho("Control de calidad aprobado (G3). Ya puede entregarse."); } catch (e) { setError(e.message); }
            setEnviando(false);
          }}>Firmar G3</Boton>
        </div>
      </div>
    </Panel>
  );
}

function Salida({ oa, formato, hermanas, onHecho }) {
  const siguientes = hermanas.filter((h) => h.secuencia > oa.secuencia && !["TERMINADA", "CANCELADA"].includes(h.estado));
  const minimo = Math.min(...siguientes.map((h) => h.secuencia));
  const [destino, setDestino] = useState(siguientes.find((h) => h.secuencia === minimo)?.id ?? "");
  const [g2, setG2] = useState(oa.g2 || {});
  const [que, setQue] = useState(oa.que_produce);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  return (
    <Panel titulo={destino ? "G2 · Traspaso a la siguiente área" : "G5 · Salida a Coordinación (para entregar al cliente)"}>
      <div className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        <Checklist items={formato.g2} valor={g2} onCambio={setG2} ayuda="Sin la lista completa y la firma de quien recibe, el trabajo no avanza." />
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Se entrega a">{(id) => (
            <select id={id} className="campo" value={destino} onChange={(e) => setDestino(e.target.value)}>
              {siguientes.map((h) => <option key={h.id} value={h.id}>{h.numero} · {h.nombre}</option>)}
              <option value="">Coordinación (sale al cliente)</option>
            </select>
          )}</Campo>
          <Campo etiqueta="Qué se entrega">{(id) => <input id={id} className="campo" value={que} onChange={(e) => setQue(e.target.value)} />}</Campo>
        </div>
        <div className="flex justify-end"><Boton icono={Send} cargando={enviando} onClick={async () => {
          setEnviando(true); setError("");
          try { await accionArea(oa.id, "traspasar", { g2, destino_oa: destino ? Number(destino) : null, que_entrega: que }); onHecho("Entregado. Falta la firma de quien recibe."); } catch (e) { setError(e.message); }
          setEnviando(false);
        }}>Entregar con vale de traspaso</Boton></div>
      </div>
    </Panel>
  );
}

function RecibirTraspaso({ t, onHecho }) {
  const [catalogo] = useRecurso("catalogo");
  const [v, setV] = useState({});
  const [causa, setCausa] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const ir = async (aceptar) => {
    setEnviando(true); setError("");
    try { await recibirTraspaso(t.id, { aceptar, verificacion: v, causa }); onHecho(aceptar ? "Traspaso aceptado: el área terminó (E5)." : "Traspaso rechazado: vuelve al área con tu causa."); } catch (e) { setError(e.message); }
    setEnviando(false);
  };
  return (
    <Panel titulo={`Recibir ${t.numero} · ${t.entrega_area} → ${t.recibe_area}`}>
      <div className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        <p className="text-[15px]"><span className="font-medium">{t.que_entrega}</span><span className="block text-sm text-gris">Entregó {t.entrega_por_nombre} · {hace(t.entrega_fecha)}</span></p>
        <Checklist items={catalogo?.verificacion_traspaso || []} valor={v} onCambio={setV} titulo="Verificación de quien recibe" />
        <Campo etiqueta="Causa (si lo rechazas)">{(id) => <input id={id} className="campo" value={causa} onChange={(e) => setCausa(e.target.value)} />}</Campo>
        <div className="flex flex-wrap justify-end gap-2">
          <Boton variante="peligro" icono={X} cargando={enviando} disabled={causa.trim().length < 3} onClick={() => ir(false)}>Rechazar</Boton>
          <Boton icono={CircleCheckBig} cargando={enviando} onClick={() => ir(true)}>Aceptar y firmar</Boton>
        </div>
      </div>
    </Panel>
  );
}

function PedirMaterial({ oa, abierto, onCerrar, onHecho }) {
  const [materiales, setMateriales] = useState([]);
  const [lineas, setLineas] = useState([{ material: "", cantidad: "" }]);
  const [notas, setNotas] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  useEffect(() => { if (abierto) { setLineas([{ material: "", cantidad: "" }]); setNotas(""); setError(""); listarMateriales({ activos: 1 }).then(setMateriales).catch(() => {}); } }, [abierto]);
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo="Vale de salida de materiales (F-11)" descripcion={`${oa.numero} · lo autoriza Coordinación y lo despacha Almacén.`} ancho="md:max-w-2xl"
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton icono={Package} cargando={enviando} onClick={async () => {
        setEnviando(true); setError("");
        try { await pedirVale({ oa: oa.id, notas, lineas: lineas.filter((l) => l.material && l.cantidad).map((l) => ({ material: Number(l.material), cantidad: l.cantidad })) }); onHecho("Vale pedido. Coordinación recibió el aviso para autorizarlo."); }
        catch (e) { setError(e.message); }
        setEnviando(false);
      }}>Pedir material</Boton></>}>
      <div className="space-y-3">
        {error && <Alerta>{error}</Alerta>}
        {lineas.map((l, i) => {
          const m = materiales.find((x) => String(x.id) === String(l.material));
          return (
            <div key={i} className="grid grid-cols-[minmax(0,1fr)_110px_40px] items-end gap-2">
              <Campo etiqueta={i === 0 ? "Material" : undefined}>{(id) => (
                <select id={id} aria-label={`Material ${i + 1}`} className="campo" value={l.material} onChange={(e) => setLineas(lineas.map((x, j) => (j === i ? { ...x, material: e.target.value } : x)))}>
                  <option value="">Elige…</option>{materiales.map((x) => <option key={x.id} value={x.id}>{x.nombre} ({Number(x.existencia).toLocaleString("es-DO")} {x.unidad}){x.bajo_minimo ? " · bajo mínimo" : ""}</option>)}
                </select>
              )}</Campo>
              <Campo etiqueta={i === 0 ? "Cantidad" : undefined}>{(id) => <input id={id} aria-label={`Cantidad ${i + 1}`} type="number" min={0} step="any" className="campo" value={l.cantidad} placeholder={m?.unidad} onChange={(e) => setLineas(lineas.map((x, j) => (j === i ? { ...x, cantidad: e.target.value } : x)))} />}</Campo>
              <button type="button" aria-label="Quitar" className="h-11 text-gris hover:text-rojo" onClick={() => setLineas(lineas.length > 1 ? lineas.filter((_, j) => j !== i) : [{ material: "", cantidad: "" }])}>×</button>
            </div>
          );
        })}
        <button type="button" className="text-sm font-medium text-azul hover:underline" onClick={() => setLineas([...lineas, { material: "", cantidad: "" }])}>+ Otro material</button>
        <Campo etiqueta="Notas (opcional)">{(id) => <input id={id} className="campo" value={notas} onChange={(e) => setNotas(e.target.value)} />}</Campo>
      </div>
    </Modal>
  );
}

function Costos({ oa, onGuardar }) {
  const [c, setC] = useState(null);
  const [edit, setEdit] = useState(null);
  useEffect(() => { costosArea(oa.id).then(setC).catch(() => setC(false)); }, [oa.id, oa.servicios_externos, oa.otros_materiales]);
  if (!c) return null;
  return (
    <Panel titulo="Consumo y costos" accion={oa.puedo.costos && !edit && <Boton variante="fantasma" tam="sm" icono={Pencil} onClick={() => setEdit({ servicios_externos: oa.servicios_externos, otros_materiales: oa.otros_materiales })}>Anotar</Boton>}>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Dato etiqueta="Horas reales">{c.horas}</Dato>
        <Dato etiqueta="Mano de obra">{dinero(c.mano_obra)}</Dato>
        <Dato etiqueta="Materiales">{dinero(c.materiales)}</Dato>
        <Dato etiqueta="Servicios externos">{dinero(c.servicios_externos)}</Dato>
        <Dato etiqueta="Retrabajo">{dinero(c.retrabajo)}</Dato>
        <Dato etiqueta="Total"><span className="text-lg">{dinero(c.total)}</span></Dato>
      </dl>
      {Number(c.desperdicio) > 0 && <p className="mt-2 text-sm text-[#a86a00]">Desperdicio: {dinero(c.desperdicio)}</p>}
      {edit && (
        <div className="mt-4 grid gap-3 rounded-lg bg-fondo p-3 sm:grid-cols-[1fr_1fr_auto]">
          <Campo etiqueta="Servicios externos RD$">{(id) => <input id={id} type="number" min={0} step="any" className="campo bg-white" value={edit.servicios_externos} onChange={(e) => setEdit({ ...edit, servicios_externos: e.target.value })} />}</Campo>
          <Campo etiqueta="Material sin vale RD$">{(id) => <input id={id} type="number" min={0} step="any" className="campo bg-white" value={edit.otros_materiales} onChange={(e) => setEdit({ ...edit, otros_materiales: e.target.value })} />}</Campo>
          <div className="flex items-end gap-2"><Boton variante="secundario" onClick={() => setEdit(null)}>Cancelar</Boton><Boton onClick={async () => { await onGuardar(edit); setEdit(null); }}>Guardar</Boton></div>
        </div>
      )}
    </Panel>
  );
}

export default function OrdenArea() {
  const { id, oaId } = useParams();
  const avisar = useAviso();
  const { usuario, esCoordinacion, esAlmacen } = useSesion();
  const [d, setD] = useState(null);
  const [vales, setVales] = useState([]);
  const [error, setError] = useState("");
  const [modal, setModal] = useState(null);
  const [editEsp, setEditEsp] = useState(null);
  const [inc, setInc] = useState({ descripcion: "", minutos_perdidos: "", resolucion: "" });
  const archivoRef = useRef(null);

  const cargar = useCallback(() => {
    areaCompleta(oaId).then(setD).catch((e) => setError(e.message));
    listarVales({ oa: oaId }).then(setVales).catch(() => setVales([]));
  }, [oaId]);
  useEffect(() => { cargar(); }, [cargar]);
  if (error) return <Alerta>{error}</Alerta>;
  if (!d) return <Cargando />;
  const { oa, formato, orden } = d;
  const listo = (msg, tono) => { setModal(null); if (msg) avisar(msg, tono); cargar(); };
  const accion = async (fn, msg) => { try { await fn(); listo(msg); } catch (e) { avisar(e.message, "rojo"); } };
  const t = oa.traspaso_pendiente;
  const tarea = oa.tarea;
  const puedeSalir = oa.g3_resultado === "APROBADO" && !t && oa.estado !== "TERMINADA" && oa.puedo.operar;
  const porValidar = tarea?.estado === "EN_REVISION" && oa.puedo.supervisa;

  return (
    <div>
      <Link to={`/ordenes/${id}`} className="mb-3 inline-flex items-center gap-1.5 text-sm font-medium text-azul hover:underline"><ArrowLeft className="size-4" />{orden.codigo} · {orden.titulo}</Link>
      <header className="mb-5 rounded-2xl border border-linea bg-white p-5">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-gris num">{oa.numero}</span>
          <AreaChip area={oa.area} nombre={oa.area_nombre} />
          <span className="text-xs text-gris">{oa.formato.formato}</span>
          <EstadoOA estado={oa.estado} />
          <PrioridadOrden prioridad={oa.prioridad} />
          <a href={`/imprimir/oa/${oa.id}`} target="_blank" rel="noopener" className="ml-auto inline-flex items-center gap-1 text-sm font-medium text-azul hover:underline"><Printer className="size-4" />{oa.formato.formato}</a>
        </div>
        <h1 className="text-2xl font-semibold leading-tight">{oa.que_produce}</h1>
        <p className="mt-1 text-gris">{oa.cliente_nombre} · secuencia {oa.secuencia}{oa.fecha_entrega_interna && <> · entrega interna <span className={cx(oa.vencida && "font-medium text-rojo")}>{fechaCorta(oa.fecha_entrega_interna)}</span></>}{oa.responsable_nombre && ` · ${oa.responsable_nombre}`}</p>
        <div className="mt-4"><Compuertas oa={oa} /></div>
        {oa.estado === "RECHAZADA" && <Alerta className="mt-4"><span className="font-medium">Rechazada en G1:</span> {oa.g1_rechazo}</Alerta>}
        {oa.bloqueada_por?.length > 0 && <Alerta tono="azul" className="mt-4">Espera a que terminen: {oa.bloqueada_por.join(", ")}. Puedes revisar el G1 mientras tanto.</Alerta>}
        {oa.formato.nota && <p className="mt-3 text-sm text-gris">{oa.formato.nota}</p>}
        <div className="mt-4 flex flex-wrap gap-2">
          {oa.puedo.reemitir && <Boton icono={Send} onClick={() => accion(() => accionArea(oa.id, "reemitir", { nota: "Completada" }), "Reemitida al área.")}>Reemitir al área</Boton>}
          {tarea && <Link to={tarea && usuario.id === oa.responsable ? `/mis-tareas?tarea=${tarea.id}` : `/equipo?ver=tareas&tarea=${tarea.id}`} className="inline-flex h-11 items-center gap-2 rounded-lg border border-linea bg-white px-4 text-[15px] font-medium hover:bg-fondo">
            <ClipboardCheck className="size-4" />Tarea · {tarea.pasos_hechos}/{tarea.pasos} etapas · {tarea.estado_nombre}</Link>}
          {oa.requiere_g4 && ["RECIBIDA", "EN_EJECUCION"].includes(oa.estado) && oa.puedo.operar && !oa.g4_aprobado &&
            <Boton variante="secundario" icono={Send} onClick={() => accion(() => accionArea(oa.id, "enviar_aprobacion"), "Enviada al cliente (E4).")}>Enviar al cliente (G4)</Boton>}
          {["RECIBIDA", "EN_EJECUCION", "EN_APROBACION"].includes(oa.estado) && oa.puedo.operar && <Boton variante="secundario" icono={Package} onClick={() => setModal("vale")}>Pedir material</Boton>}
          {oa.estado !== "CANCELADA" && <Boton variante="secundario" icono={Wrench} onClick={() => setModal("cambio")}>Cambio / retrabajo</Boton>}
        </div>
      </header>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-5">
          {oa.puedo.recibir && <Recepcion oa={oa} formato={formato} onHecho={listo} />}
          {t?.puedo_recibir && <RecibirTraspaso t={t} onHecho={listo} />}
          {t && !t.puedo_recibir && <Alerta tono="amarillo">Traspaso {t.numero} entregado a {t.recibe_area}: falta la firma de quien recibe.</Alerta>}
          {oa.estado === "EN_APROBACION" && oa.puedo.operar && <AprobacionCliente oa={oa} onHecho={listo} />}
          {porValidar && <ValidarAqui oa={oa} tarea={tarea} formato={formato} onHecho={listo} />}
          {puedeSalir && <Salida oa={oa} formato={formato} hermanas={d.hermanas} onHecho={listo} />}

          <Panel titulo={`Especificación · ${oa.formato.formato}`} accion={(oa.puedo.editar || oa.puedo.operar) && !editEsp && oa.estado !== "TERMINADA" &&
            <Boton variante="fantasma" tam="sm" icono={Pencil} onClick={() => setEditEsp({ ...oa.especificacion })}>Editar</Boton>}>
            {editEsp ? (
              <div className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">{formato.especificacion.map((c) => <CampoFormato key={c.clave} campo={c} valor={editEsp[c.clave]} onCambio={(v) => setEditEsp({ ...editEsp, [c.clave]: v })} />)}</div>
                <div className="flex justify-end gap-2"><Boton variante="secundario" onClick={() => setEditEsp(null)}>Cancelar</Boton>
                  <Boton onClick={async () => { try { await guardarArea(oa.id, { especificacion: editEsp }); setEditEsp(null); listo("Especificación guardada."); } catch (e) { avisar(e.message, "rojo"); } }}>Guardar</Boton></div>
              </div>
            ) : <FichaFormato campos={formato.especificacion} datos={oa.especificacion} />}
          </Panel>

          <Panel titulo="Seguimiento de etapas" cuerpo="p-5">
            <ol className="space-y-1.5">{formato.etapas.map((e, i) => (
              <li key={e} className="flex items-center gap-2 text-[15px]"><span className={cx("flex size-6 items-center justify-center rounded-full text-xs num", tarea && i < tarea.pasos_hechos ? "bg-verde text-white" : "bg-linea-suave text-gris")}>{i + 1}</span>{e}</li>
            ))}</ol>
            <p className="mt-2 text-sm text-gris">El ejecutor las marca en su tarea, con el cronómetro de tiempo.</p>
          </Panel>

          <Panel titulo="Compuertas firmadas">
            <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
              <Dato etiqueta="G1 · Entrada">{oa.g1_fecha && `Entregó ${oa.g1_entrega_por_nombre || "Coordinación"} · recibió ${oa.g1_recibe_por_nombre} · ${fechaHora(oa.g1_fecha)}`}</Dato>
              {oa.requiere_g4 && <Dato etiqueta="G4 · Cliente">{oa.g4_aprobado ? `Aprobó ${oa.g4_aprobado_por} · ${oa.g4_canales.join(", ")} · ${oa.g4_version || ""} · ronda ${oa.g4_ronda}` : oa.g4_ronda ? `Ronda ${oa.g4_ronda} en curso` : "Pendiente"}</Dato>}
              <Dato etiqueta="G3 · Calidad">{oa.g3_resultado && `${oa.g3_resultado === "APROBADO" ? "Aprobado" : "Rechazado"} · ${oa.g3_supervisor_nombre} · ${fechaHora(oa.g3_fecha)}${oa.g3_observaciones ? ` · ${oa.g3_observaciones}` : ""}`}</Dato>
              <Dato etiqueta="Retrabajos">{oa.pase_retrabajo > 0 && `${oa.pase_retrabajo} pase(s)`}</Dato>
            </dl>
            {d.traspasos.length > 0 && <ul className="mt-3 space-y-1 border-t border-linea-suave pt-3 text-sm">{d.traspasos.map((x) => (
              <li key={x.id}><span className="font-medium num">{x.numero}</span> · {x.compuerta} · {x.entrega_area} → {x.recibe_area} · <span className={cx(x.resultado === "RECHAZADO" ? "text-rojo" : x.resultado === "ACEPTADO" ? "text-verde" : "text-[#a86a00]")}>{x.resultado_nombre}</span>{x.causa_rechazo && ` · ${x.causa_rechazo}`}</li>
            ))}</ul>}
          </Panel>
        </div>

        <aside className="space-y-5">
          <Panel titulo="Materiales (vales F-11)" accion={["RECIBIDA", "EN_EJECUCION", "EN_APROBACION"].includes(oa.estado) && oa.puedo.operar && <Boton variante="fantasma" tam="sm" icono={Package} onClick={() => setModal("vale")}>Pedir</Boton>}>
            {vales.length === 0 ? <p className="text-sm text-gris">Sin vale no sale material del almacén.</p> : (
              <ul className="space-y-3">{vales.map((v) => (
                <li key={v.id} className="rounded-lg border border-linea p-3 text-sm">
                  <div className="flex items-center justify-between"><span className="font-semibold num">{v.numero}</span><span className="text-gris">{v.estado_nombre}</span></div>
                  <ul className="mt-1 text-gris">{v.lineas.map((l) => <li key={l.id}>{(Number(l.cantidad_despachada) > 0 ? Number(l.cantidad_despachada) : Number(l.cantidad_solicitada)).toLocaleString("es-DO")} {l.unidad} · {l.material_nombre}</li>)}</ul>
                  {v.estado === "DESPACHADO" && !v.recibido_por_nombre && oa.puedo.operar &&
                    <Boton tam="sm" className="mt-2" onClick={() => accion(() => accionVale(v.id, "recibir"), "Recepción firmada.")}>Firmar que lo recibí</Boton>}
                  {v.estado === "SOLICITADO" && esCoordinacion && <Boton tam="sm" className="mt-2" onClick={() => accion(() => accionVale(v.id, "autorizar"), "Vale autorizado.")}>Autorizar</Boton>}
                  {v.estado === "AUTORIZADO" && esAlmacen && <Link to={`/almacen?vale=${v.id}`} className="mt-2 inline-block text-sm font-medium text-azul">Despachar en Almacén →</Link>}
                </li>
              ))}</ul>
            )}
          </Panel>

          {oa.puedo.costos && <Costos oa={oa} onGuardar={async (x) => { try { await guardarArea(oa.id, x); listo("Costos anotados."); } catch (e) { avisar(e.message, "rojo"); } }} />}

          <Panel titulo="Incidencias y tiempos muertos">
            {d.incidencias.length > 0 && <ul className="mb-3 space-y-2 text-sm">{d.incidencias.map((i) => (
              <li key={i.id}><span className="font-medium">{i.descripcion}</span>{i.minutos_perdidos > 0 && <span className="text-[#a86a00]"> · {i.minutos_perdidos} min</span>}
                <span className="block text-gris">{i.reporta_nombre} · {hace(i.fecha)}{i.resolucion && ` · ${i.resolucion}`}</span></li>
            ))}</ul>}
            {oa.estado !== "CANCELADA" && (
              <form className="space-y-2" onSubmit={async (e) => {
                e.preventDefault();
                if (inc.descripcion.trim().length < 3) return;
                try { await incidenciaArea(oa.id, { ...inc, minutos_perdidos: Number(inc.minutos_perdidos) || 0 }); setInc({ descripcion: "", minutos_perdidos: "", resolucion: "" }); listo("Incidencia registrada."); } catch (err) { avisar(err.message, "rojo"); }
              }}>
                <input className="campo" aria-label="Incidencia" placeholder="Ej.: se fue la luz, cabezal obstruido…" value={inc.descripcion} onChange={(e) => setInc({ ...inc, descripcion: e.target.value })} />
                <div className="flex gap-2">
                  <input className="campo w-28" aria-label="Minutos perdidos" type="number" min={0} placeholder="Minutos" value={inc.minutos_perdidos} onChange={(e) => setInc({ ...inc, minutos_perdidos: e.target.value })} />
                  <input className="campo" aria-label="Cómo se resolvió" placeholder="Cómo se resolvió" value={inc.resolucion} onChange={(e) => setInc({ ...inc, resolucion: e.target.value })} />
                </div>
                <Boton type="submit" variante="secundario" tam="sm" disabled={inc.descripcion.trim().length < 3}>Registrar</Boton>
              </form>
            )}
          </Panel>

          <Panel titulo="Archivos del área" accion={<Boton variante="fantasma" tam="sm" icono={Upload} onClick={() => archivoRef.current?.click()}>Subir</Boton>}>
            <input ref={archivoRef} type="file" multiple className="sr-only" tabIndex={-1} onChange={async (e) => {
              const lista = Array.from(e.target.files || []); e.target.value = "";
              if (!lista.length) return;
              try { await subirArchivosOrden(orden.id, lista, { oa: oa.id, categoria: oa.estado === "EN_APROBACION" ? "APROBACION" : "ARTE" }); listo("Archivo(s) agregado(s)."); } catch (err) { avisar(err.message, "rojo"); }
            }} />
            {d.archivos.length === 0 ? <p className="text-sm text-gris">Artes, pruebas, aprobaciones del cliente y fotos de esta área.</p> : (
              <ul className="space-y-1.5 text-sm">{d.archivos.map((a) => <li key={a.id}><a href={a.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 hover:text-azul"><FileText className="size-4 text-gris" />{a.nombre_original}</a></li>)}</ul>
            )}
          </Panel>

          {d.cambios.length > 0 && (
            <Panel titulo="Cambios y retrabajos">
              <ul className="space-y-2 text-sm">{d.cambios.map((c) => <li key={c.id}><span className="font-medium num">{c.numero}</span> · {c.tipo_nombre.split(" (")[0]} · {c.estado_nombre}<span className="block text-gris">{c.descripcion}</span></li>)}</ul>
            </Panel>
          )}
        </aside>
      </div>

      <PedirMaterial oa={oa} abierto={modal === "vale"} onCerrar={() => setModal(null)} onHecho={listo} />
      <CambioModal orden={orden} areas={[{ id: oa.id, numero: oa.numero }]} inicial={{ oa: String(oa.id), area_responsable: oa.area, tipo: "RETRABAJO" }}
        abierto={modal === "cambio"} onCerrar={() => setModal(null)} onHecho={(_, m) => listo(m)} />
    </div>
  );
}
