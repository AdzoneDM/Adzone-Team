// Ventanas de las acciones de la OT: liberar (G0), rechazar, excepción, pausar/cancelar, cambios (F-14), acta (F-12) y agregar área.
import { useEffect, useState } from "react";
import { Ban, CircleCheckBig, FileSignature, PackageCheck, Send, Undo2 } from "lucide-react";
import {
  accionActa, accionCambio, agregarArea, crearActa, crearCambio, excepcionG0, liberarOrden, rechazarG0,
} from "@/lib/api";
import { dinero, fechaCorta, hoyISO } from "@/lib/formato";
import { useRecurso } from "@/lib/recursos";
import { useSesion } from "@/lib/sesion";
import FirmaCanvas from "@/components/FirmaCanvas";
import { SelectorPersona } from "@/components/Selectores";
import { Alerta, Boton, Campo, Modal, cx } from "@/components/ui";
import { CaminoAreas, Checklist } from "./piezas";

function useEnvio(onHecho) {
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  const enviar = async (fn, msg) => {
    setEnviando(true); setError("");
    try { const r = await fn(); onHecho(r, msg); } catch (e) { setError(e.message); }
    setEnviando(false);
  };
  return { enviando, error, setError, enviar };
}

export function LiberarModal({ orden, abierto, onCerrar, onHecho }) {
  const { usuario } = useSesion();
  const [responsable, setResponsable] = useState("");
  const [fecha, setFecha] = useState("");
  const { enviando, error, setError, enviar } = useEnvio(onHecho);
  useEffect(() => { if (abierto) { setResponsable(String(usuario.id)); setFecha(""); setError(""); } }, [abierto, usuario, setError]);
  if (!orden) return null;
  const faltan = orden.g0_faltan || [];
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={`Liberar ${orden.solicitud}`} descripcion="Recibes conforme (G0): se le asigna su número OT y se emiten las Órdenes de Área." ancho="md:max-w-xl"
      pie={<><Boton variante="secundario" onClick={onCerrar}>Volver</Boton>
        <Boton icono={CircleCheckBig} cargando={enviando} disabled={faltan.length > 0} onClick={() => enviar(() => liberarOrden(orden.id, { responsable: Number(responsable) || null, fecha_compromiso: fecha || null }), "OT liberada y numerada. Las áreas recibieron su Orden de Área.")}>Liberar y numerar</Boton></>}>
      <div className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        {faltan.length > 0 ? (
          <Alerta tono="amarillo"><p className="font-medium">El área no inicia si falta una casilla. Falta:</p><ul className="mt-1 list-disc pl-5">{faltan.map((x) => <li key={x}>{x}</li>)}</ul>
            <p className="mt-2 text-sm">Devuélvela a Comercial, o — si es solo el anticipo — pide a Gerencia General la excepción.</p></Alerta>
        ) : <Alerta tono="verde">G0 completo: {orden.g0 && Object.keys(orden.g0).length} casillas verificadas{orden.excepcion_g0_por_nombre ? ` (anticipo por excepción de ${orden.excepcion_g0_por_nombre})` : ""}.</Alerta>}
        <div><p className="mb-1.5 text-sm text-gris">Áreas que se emiten</p><CaminoAreas areas={orden.plan_areas} /></div>
        <div className="grid gap-4 sm:grid-cols-2">
          <SelectorPersona etiqueta="Coordinador a cargo" valor={responsable} onCambio={setResponsable} />
          <Campo etiqueta="Fecha comprometida" ayuda="Vacía = la calcula la plataforma (sección 4).">{(id) => <input id={id} type="date" min={hoyISO()} className="campo" value={fecha} onChange={(e) => setFecha(e.target.value)} />}</Campo>
        </div>
      </div>
    </Modal>
  );
}

export function RechazarG0Modal({ orden, abierto, onCerrar, onHecho }) {
  const [causa, setCausa] = useState("");
  const [a, setA] = useState("Comercial");
  const { enviando, error, enviar } = useEnvio(onHecho);
  useEffect(() => { if (abierto) setCausa(""); }, [abierto]);
  if (!orden) return null;
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={`Rechazar en G0 · ${orden.solicitud}`} ancho="max-w-md" descripcion="Vuelve a quien la pidió con la causa. Queda en el historial."
      pie={<><Boton variante="secundario" onClick={onCerrar}>Volver</Boton><Boton variante="peligro" icono={Undo2} cargando={enviando} disabled={causa.trim().length < 3}
        onClick={() => enviar(() => rechazarG0(orden.id, causa.trim(), a), "Devuelta a Comercial.")}>Devolver</Boton></>}>
      {error && <Alerta className="mb-3">{error}</Alerta>}
      <div className="space-y-4">
        <Campo etiqueta="Causa del rechazo">{(id) => <textarea id={id} rows={3} className="campo" value={causa} onChange={(e) => setCausa(e.target.value)} autoFocus placeholder="Ej.: faltan medidas confirmadas" />}</Campo>
        <Campo etiqueta="Se devuelve a">{(id) => <input id={id} className="campo" value={a} onChange={(e) => setA(e.target.value)} />}</Campo>
      </div>
    </Modal>
  );
}

export function ExcepcionModal({ orden, abierto, onCerrar, onHecho }) {
  const [motivo, setMotivo] = useState("");
  const { enviando, error, enviar } = useEnvio(onHecho);
  useEffect(() => { if (abierto) setMotivo(""); }, [abierto]);
  if (!orden) return null;
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo="Autorizar inicio sin anticipo" ancho="max-w-md" descripcion="Solo Gerencia General. Administración debe regularizar el anticipo en máximo 24 horas (le llega el aviso)."
      pie={<><Boton variante="secundario" onClick={onCerrar}>Volver</Boton><Boton icono={CircleCheckBig} cargando={enviando} disabled={motivo.trim().length < 5}
        onClick={() => enviar(() => excepcionG0(orden.id, motivo.trim()), "Excepción autorizada. Coordinación ya puede liberarla.")}>Autorizar</Boton></>}>
      {error && <Alerta className="mb-3">{error}</Alerta>}
      <Campo etiqueta="Motivo">{(id) => <textarea id={id} rows={3} className="campo" value={motivo} onChange={(e) => setMotivo(e.target.value)} autoFocus placeholder="Ej.: cliente de iguala con crédito aprobado" />}</Campo>
    </Modal>
  );
}

export function MotivoModal({ titulo, descripcion, boton, peligro, abierto, onCerrar, onConfirmar }) {
  const [motivo, setMotivo] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { if (abierto) { setMotivo(""); setError(""); } }, [abierto]);
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={titulo} descripcion={descripcion} ancho="max-w-md"
      pie={<><Boton variante="secundario" onClick={onCerrar}>Volver</Boton>
        <Boton variante={peligro ? "peligro" : "primario"} icono={peligro ? Ban : undefined} cargando={enviando} disabled={motivo.trim().length < 3} onClick={async () => {
          setEnviando(true);
          try { await onConfirmar(motivo.trim()); } catch (e) { setError(e.message); }
          setEnviando(false);
        }}>{boton}</Boton></>}>
      {error && <Alerta className="mb-3">{error}</Alerta>}
      <Campo etiqueta="Motivo">{(id) => <textarea id={id} rows={3} className="campo" value={motivo} onChange={(e) => setMotivo(e.target.value)} autoFocus />}</Campo>
    </Modal>
  );
}

export function AgregarAreaModal({ orden, abierto, onCerrar, onHecho }) {
  const [catalogo] = useRecurso("catalogo");
  const [f, setF] = useState({});
  const { enviando, error, enviar } = useEnvio(onHecho);
  useEffect(() => { if (abierto) setF({ area: "", secuencia: (orden?.areas_resumen?.length || 0) + 1, que_produce: "", tiempo_estandar_dias: "" }); }, [abierto, orden]);
  if (!orden) return null;
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={`Agregar área a ${orden.codigo}`} ancho="max-w-lg"
      pie={<><Boton variante="secundario" onClick={onCerrar}>Volver</Boton><Boton cargando={enviando} disabled={!f.area || !f.que_produce?.trim()}
        onClick={() => enviar(() => agregarArea(orden.id, { ...f, tiempo_estandar_dias: f.tiempo_estandar_dias || undefined }), "Orden de Área emitida.")}>Emitir Orden de Área</Boton></>}>
      {error && <Alerta className="mb-3">{error}</Alerta>}
      <div className="grid gap-4 sm:grid-cols-2">
        <Campo etiqueta="Área">{(id) => <select id={id} className="campo" value={f.area} onChange={(e) => setF({ ...f, area: e.target.value })}>
          <option value="">Elige…</option>{(catalogo?.areas || []).map((a) => <option key={a.codigo} value={a.codigo}>{a.codigo} · {a.nombre}</option>)}</select>}</Campo>
        <Campo etiqueta="Orden en la secuencia">{(id) => <input id={id} type="number" min={1} className="campo" value={f.secuencia} onChange={(e) => setF({ ...f, secuencia: e.target.value })} />}</Campo>
        <Campo etiqueta="Qué produce" className="sm:col-span-2">{(id) => <input id={id} className="campo" value={f.que_produce} onChange={(e) => setF({ ...f, que_produce: e.target.value })} />}</Campo>
        <Campo etiqueta="Días estándar">{(id) => <input id={id} type="number" min={0} step="0.5" className="campo" value={f.tiempo_estandar_dias} onChange={(e) => setF({ ...f, tiempo_estandar_dias: e.target.value })} />}</Campo>
      </div>
    </Modal>
  );
}

const IMPACTOS = [["horas", "Horas"], ["material", "Material"], ["costo", "Costo RD$"], ["fecha", "Fecha de entrega"]];

/** F-14 · Solicitud de cambio (la paga el cliente) o registro de retrabajo (lo asume AdZone). */
export function CambioModal({ orden, areas = [], abierto, onCerrar, onHecho, inicial }) {
  const [catalogo] = useRecurso("catalogo");
  const [f, setF] = useState({});
  const { enviando, error, setError, enviar } = useEnvio(onHecho);
  useEffect(() => {
    if (abierto) { setError(""); setF({ tipo: "CAMBIO", clasificacion: [], descripcion: "", aprobado_original: "", impacto: {}, area_responsable: "", oa: "", costo_retrabajo: "", monto_cliente: "", areas_notificadas: [], accion_preventiva: "", ...inicial }); }
  }, [abierto, inicial, setError]);
  if (!orden || !catalogo || !f.tipo) return null;
  const opciones = f.tipo === "CAMBIO" ? catalogo.cambios_alcance : [...catalogo.correcciones, ...catalogo.causas_retrabajo.filter((c) => !catalogo.correcciones.includes(c))];
  const marcar = (lista, v) => (lista.includes(v) ? lista.filter((x) => x !== v) : [...lista, v]);
  const impacto = (k, cuando, v) => setF({ ...f, impacto: { ...f.impacto, [k]: { ...(f.impacto?.[k] || {}), [cuando]: v } } });
  const guardar = () => enviar(() => crearCambio(orden.id, {
    ...f, oa: f.oa ? Number(f.oa) : null, costo_retrabajo: f.costo_retrabajo || 0, monto_cliente: f.monto_cliente || 0,
  }), f.tipo === "CAMBIO" ? "Solicitud de cambio registrada. Coordinación la revisa." : "Retrabajo registrado.");
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo="Solicitud de cambio / retrabajo (F-14)" descripcion={`${orden.codigo} · ${orden.titulo}`} ancho="md:max-w-3xl"
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton icono={Send} cargando={enviando} disabled={f.descripcion?.trim().length < 5} onClick={guardar}>Registrar</Boton></>}>
      <div className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        <div className="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Tipo">
          {[["CAMBIO", "Cambio de alcance", "Lo pide el cliente: se cotiza y lo paga."], ["RETRABAJO", "Retrabajo / corrección", "Error nuestro: lo asume AdZone."]].map(([v, t, d]) => (
            <label key={v} className={cx("flex cursor-pointer gap-3 rounded-lg border p-3", f.tipo === v ? "border-azul bg-azul/5" : "border-linea")}>
              <input type="radio" name="tipo-cambio" checked={f.tipo === v} onChange={() => setF({ ...f, tipo: v, clasificacion: [] })} className="mt-1 accent-azul" />
              <span><span className="block font-medium">{t}</span><span className="text-sm text-gris">{d}</span></span>
            </label>
          ))}
        </div>
        <fieldset><legend className="etiqueta">Clasificación</legend>
          <div className="flex flex-wrap gap-2">{opciones.map((o) => {
            const on = f.clasificacion.includes(o);
            return <button key={o} type="button" aria-pressed={on} onClick={() => setF({ ...f, clasificacion: marcar(f.clasificacion, o) })}
              className={cx("min-h-10 rounded-full border px-3.5 text-sm font-medium", on ? "border-azul bg-azul text-white" : "border-linea bg-white")}>{o}</button>;
          })}</div></fieldset>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="¿Qué se cambia o qué falló?" className="sm:col-span-2">{(id) => <textarea id={id} rows={3} className="campo" value={f.descripcion} onChange={(e) => setF({ ...f, descripcion: e.target.value })} />}</Campo>
          <Campo etiqueta="¿Qué se aprobó originalmente?" className="sm:col-span-2">{(id) => <textarea id={id} rows={2} className="campo" value={f.aprobado_original} onChange={(e) => setF({ ...f, aprobado_original: e.target.value })} />}</Campo>
          <Campo etiqueta="Orden de Área">{(id) => <select id={id} className="campo" value={f.oa} onChange={(e) => setF({ ...f, oa: e.target.value })}>
            <option value="">Toda la OT</option>{areas.map((a) => <option key={a.id} value={a.id}>{a.numero}</option>)}</select>}</Campo>
          <Campo etiqueta="Área responsable">{(id) => <select id={id} className="campo" value={f.area_responsable} onChange={(e) => setF({ ...f, area_responsable: e.target.value })}>
            <option value="">—</option>{catalogo.areas.map((a) => <option key={a.codigo} value={a.codigo}>{a.codigo} · {a.nombre}</option>)}</select>}</Campo>
          {f.tipo === "CAMBIO"
            ? <Campo etiqueta="Monto adicional al cliente RD$" ayuda="Cero = sin costo: lo autoriza Gerencia General.">{(id) => <input id={id} type="number" min={0} step="any" className="campo" value={f.monto_cliente} onChange={(e) => setF({ ...f, monto_cliente: e.target.value })} />}</Campo>
            : <Campo etiqueta="Costo del retrabajo RD$">{(id) => <input id={id} type="number" min={0} step="any" className="campo" value={f.costo_retrabajo} onChange={(e) => setF({ ...f, costo_retrabajo: e.target.value })} />}</Campo>}
        </div>
        <fieldset><legend className="etiqueta">Impacto (antes → después)</legend>
          <div className="grid gap-2 sm:grid-cols-2">{IMPACTOS.map(([k, t]) => (
            <div key={k} className="flex items-center gap-2"><span className="w-28 shrink-0 text-sm text-gris">{t}</span>
              <input aria-label={`${t} antes`} type={k === "fecha" ? "date" : "text"} className="campo h-10" value={f.impacto?.[k]?.antes || ""} onChange={(e) => impacto(k, "antes", e.target.value)} />
              <span aria-hidden>→</span>
              <input aria-label={`${t} después`} type={k === "fecha" ? "date" : "text"} className="campo h-10" value={f.impacto?.[k]?.despues || ""} onChange={(e) => impacto(k, "despues", e.target.value)} />
            </div>
          ))}</div>
          <p className="mt-1 text-xs text-gris">Si cambia la fecha, al autorizarla se actualiza la fecha comprometida.</p></fieldset>
        <fieldset><legend className="etiqueta">Áreas a notificar</legend>
          <div className="flex flex-wrap gap-2">{catalogo.areas.map((a) => {
            const on = f.areas_notificadas.includes(a.codigo);
            return <button key={a.codigo} type="button" aria-pressed={on} onClick={() => setF({ ...f, areas_notificadas: marcar(f.areas_notificadas, a.codigo) })}
              className={cx("h-9 rounded-full border px-3 text-sm", on ? "border-azul bg-azul text-white" : "border-linea bg-white")}>{a.codigo}</button>;
          })}</div></fieldset>
        <Campo etiqueta="Acción preventiva" ayuda="Qué hacemos para que no se repita.">{(id) => <textarea id={id} rows={2} className="campo" value={f.accion_preventiva} onChange={(e) => setF({ ...f, accion_preventiva: e.target.value })} />}</Campo>
      </div>
    </Modal>
  );
}

export function AutorizarCambioModal({ cambio, abierto, onCerrar, onHecho }) {
  const [catalogo] = useRecurso("catalogo");
  const [marcas, setMarcas] = useState({});
  const { enviando, error, enviar } = useEnvio(onHecho);
  useEffect(() => { if (abierto) setMarcas({}); }, [abierto]);
  if (!cambio || !catalogo) return null;
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={`Autorizar ${cambio.numero}`} descripcion={cambio.descripcion} ancho="max-w-lg"
      pie={<><Boton variante="peligro" onClick={() => enviar(() => accionCambio(cambio.id, "rechazar", { motivo: "No procede" }), "Solicitud rechazada.")} className="mr-auto">Rechazar</Boton>
        <Boton variante="secundario" onClick={onCerrar}>Volver</Boton><Boton icono={CircleCheckBig} cargando={enviando}
          onClick={() => enviar(() => accionCambio(cambio.id, "autorizar", { autorizaciones: marcas }), "Autorizada. Las áreas recibieron el aviso.")}>Autorizar</Boton></>}>
      {error && <Alerta className="mb-3">{error}</Alerta>}
      {cambio.tipo === "CAMBIO" && <p className="mb-3 text-sm">Monto adicional al cliente: <span className="font-semibold">{dinero(cambio.monto_cliente)}</span>{Number(cambio.monto_cliente) === 0 && " · sin costo: requiere Gerencia General"}</p>}
      <Checklist items={catalogo.autorizaciones_cambio} valor={marcas} onCambio={setMarcas} titulo="Autorizaciones" />
    </Modal>
  );
}

/** Prepara el acta de entrega (F-12). */
export function ActaModal({ orden, abierto, onCerrar, onHecho }) {
  const [f, setF] = useState({});
  const { enviando, error, enviar } = useEnvio(onHecho);
  useEffect(() => {
    if (abierto && orden) setF({ modalidad: (orden.areas_resumen || []).some((a) => a.area === "INS") ? "INSTALACION" : "ENTREGA", fecha: hoyISO(), direccion: orden.direccion_entrega || "", contacto_sitio: orden.contacto || "", garantia: "" });
  }, [abierto, orden]);
  if (!orden) return null;
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo="Preparar acta de entrega (F-12)" descripcion="Administración libera la salida (G5) y el cliente firma al recibir." ancho="max-w-lg"
      pie={<><Boton variante="secundario" onClick={onCerrar}>Volver</Boton><Boton icono={FileSignature} cargando={enviando} onClick={() => enviar(() => crearActa(orden.id, f), "Acta preparada. Administración recibió el aviso para liberar la salida.")}>Preparar acta</Boton></>}>
      {error && <Alerta className="mb-3">{error}</Alerta>}
      <div className="grid gap-4 sm:grid-cols-2">
        <Campo etiqueta="Modalidad">{(id) => <select id={id} className="campo" value={f.modalidad} onChange={(e) => setF({ ...f, modalidad: e.target.value })}>
          <option value="ENTREGA">Entrega</option><option value="INSTALACION">Instalación</option><option value="RETIRO">Retiro en taller</option></select>}</Campo>
        <Campo etiqueta="Fecha">{(id) => <input id={id} type="date" className="campo" value={f.fecha} onChange={(e) => setF({ ...f, fecha: e.target.value })} />}</Campo>
        <Campo etiqueta="Dirección" className="sm:col-span-2">{(id) => <input id={id} className="campo" value={f.direccion} onChange={(e) => setF({ ...f, direccion: e.target.value })} />}</Campo>
        <Campo etiqueta="Contacto en sitio">{(id) => <input id={id} className="campo" value={f.contacto_sitio} onChange={(e) => setF({ ...f, contacto_sitio: e.target.value })} />}</Campo>
        <Campo etiqueta="Garantía (opcional)">{(id) => <input id={id} className="campo" value={f.garantia} onChange={(e) => setF({ ...f, garantia: e.target.value })} placeholder="Ej.: 1 año en instalación" />}</Campo>
      </div>
    </Modal>
  );
}

export function LiberarG5Modal({ acta, saldo, abierto, onCerrar, onHecho }) {
  const [catalogo] = useRecurso("catalogo");
  const { esAdmin } = useSesion();
  const [marcas, setMarcas] = useState({});
  const { enviando, error, enviar } = useEnvio(onHecho);
  useEffect(() => { if (abierto) setMarcas({}); }, [abierto]);
  if (!acta || !catalogo) return null;
  const items = catalogo.g5_acta.map((x) => x.texto);
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={`Liberar salida (G5) · ${acta.numero}`} ancho="max-w-lg"
      descripcion="Sale con el saldo pagado o con autorización escrita de Gerencia General."
      pie={<><Boton variante="secundario" onClick={onCerrar}>Volver</Boton><Boton icono={PackageCheck} cargando={enviando}
        onClick={() => enviar(() => accionActa(acta.id, "liberar", { g5: marcas }), "Salida liberada. Ya se puede cargar.")}>Liberar salida</Boton></>}>
      {error && <Alerta className="mb-3">{error}</Alerta>}
      {saldo != null && <Alerta tono={Number(saldo) > 0 ? "amarillo" : "verde"} className="mb-3">Saldo del cliente en esta OT: <span className="font-semibold">{dinero(saldo)}</span>
        {Number(saldo) > 0 && (esAdmin ? " · como Gerencia puedes autorizar la salida (marca la segunda casilla)." : " · necesita autorización de Gerencia General.")}</Alerta>}
      <Checklist items={items} valor={marcas} onCambio={setMarcas} />
    </Modal>
  );
}

export function FirmarActaModal({ acta, abierto, onCerrar, onHecho }) {
  const [catalogo] = useRecurso("catalogo");
  const [f, setF] = useState({});
  const { enviando, error, enviar } = useEnvio(onHecho);
  useEffect(() => { if (abierto && acta) setF({ verificacion: {}, conformidad: "CONFORME", cliente_nombre: "", cliente_cedula: "", firma: "", hallazgos: "", material_devuelto: "", observaciones_cliente: "", garantia: acta.garantia || "", instrucciones_mantenimiento: false, proxima_revision: "" }); }, [abierto, acta]);
  if (!acta || !catalogo || !f.verificacion) return null;
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={`Acta ${acta.numero} · conformidad del cliente`} descripcion="Sin acta firmada no se cierra la OT ni se factura." ancho="md:max-w-2xl"
      pie={<><Boton variante="secundario" onClick={onCerrar}>Volver</Boton><Boton variante="acento" icono={FileSignature} cargando={enviando}
        onClick={() => enviar(() => accionActa(acta.id, "firmar", { ...f, proxima_revision: f.proxima_revision || null }), "Entregada (E6). Administración ya puede facturar.")}>Firmar y entregar</Boton></>}>
      <div className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        <Checklist items={catalogo.verificacion_sitio} valor={f.verificacion} onCambio={(v) => setF({ ...f, verificacion: v })} titulo="Verificación en sitio" />
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Hallazgos / pendientes (opcional)">{(id) => <textarea id={id} rows={2} className="campo" value={f.hallazgos} onChange={(e) => setF({ ...f, hallazgos: e.target.value })} />}</Campo>
          <Campo etiqueta="Material devuelto al taller (opcional)">{(id) => <textarea id={id} rows={2} className="campo" value={f.material_devuelto} onChange={(e) => setF({ ...f, material_devuelto: e.target.value })} />}</Campo>
        </div>
        <fieldset><legend className="etiqueta">Conformidad del cliente</legend>
          <div className="grid gap-2 sm:grid-cols-3">{[["CONFORME", "Recibido conforme"], ["OBSERVACIONES", "Con observaciones"], ["PENDIENTE", "Pendiente por el cliente"]].map(([v, t]) => (
            <label key={v} className={cx("flex cursor-pointer items-center gap-2 rounded-lg border p-3 text-[15px]", f.conformidad === v ? "border-azul bg-azul/5" : "border-linea")}>
              <input type="radio" name="conformidad" checked={f.conformidad === v} onChange={() => setF({ ...f, conformidad: v })} className="accent-azul" />{t}</label>
          ))}</div></fieldset>
        {f.conformidad !== "CONFORME" && <Campo etiqueta="Observaciones del cliente">{(id) => <textarea id={id} rows={2} className="campo" value={f.observaciones_cliente} onChange={(e) => setF({ ...f, observaciones_cliente: e.target.value })} />}</Campo>}
        <div className="grid gap-4 sm:grid-cols-3">
          <Campo etiqueta="Garantía">{(id) => <input id={id} className="campo" value={f.garantia} onChange={(e) => setF({ ...f, garantia: e.target.value })} />}</Campo>
          <Campo etiqueta="Próxima revisión (opcional)">{(id) => <input id={id} type="date" className="campo" value={f.proxima_revision} onChange={(e) => setF({ ...f, proxima_revision: e.target.value })} />}</Campo>
          <label className="flex items-end gap-2 pb-3 text-[15px]"><input type="checkbox" checked={f.instrucciones_mantenimiento} onChange={(e) => setF({ ...f, instrucciones_mantenimiento: e.target.checked })} className="size-4 accent-azul" />Instrucciones de mantenimiento entregadas</label>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Nombre de quien recibe">{(id) => <input id={id} className="campo" value={f.cliente_nombre} onChange={(e) => setF({ ...f, cliente_nombre: e.target.value })} />}</Campo>
          <Campo etiqueta="Cédula (opcional)">{(id) => <input id={id} className="campo" inputMode="numeric" value={f.cliente_cedula} onChange={(e) => setF({ ...f, cliente_cedula: e.target.value })} maxLength={20} />}</Campo>
        </div>
        <FirmaCanvas onCambio={(firma) => setF((x) => ({ ...x, firma }))} />
        <p className="text-xs text-gris">Acta de {fechaCorta(acta.fecha)} · {acta.direccion}</p>
      </div>
    </Modal>
  );
}
