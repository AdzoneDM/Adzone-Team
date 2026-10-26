// Cotizaciones y facturas: editor de líneas, detalle con acciones y pagos.
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Ban, CheckCircle2, CloudUpload, Copy, Plus, Printer, Receipt, RefreshCw, Send, Trash2, X } from "lucide-react";
import { accionDocumento, borrarPago, eliminarDocumento, guardarDocumento, listarProyectos, registrarPago } from "@/lib/api";
import { dinero, fechaCorta, hoyISO, sumarDias } from "@/lib/formato";
import { SelectorCliente } from "@/components/Selectores";
import { Alerta, Boton, Campo, Modal, cx, useAviso, useConfirmar } from "@/components/ui";

export const TONO_DOC = {
  BORRADOR: "bg-linea-suave text-tinta", ENVIADA: "bg-azul/10 text-azul", APROBADA: "bg-verde-50 text-verde", RECHAZADA: "bg-rojo-50 text-[#a3170f]",
  EMITIDA: "bg-azul/10 text-azul", PAGADA: "bg-verde text-white", ANULADA: "bg-linea-suave text-gris line-through", VENCIDA: "bg-rojo text-white",
};
export const EstadoDoc = ({ doc }) => {
  const e = doc.vencida ? "VENCIDA" : doc.estado;
  return <span className={cx("whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium", TONO_DOC[e])}>{doc.vencida ? "Vencida" : doc.estado_nombre}</span>;
};

const ITBIS = 0.18;
const r2 = (n) => Math.round(n * 100) / 100;

function totales(lineas) {
  let sub = 0, itb = 0;
  for (const l of lineas) {
    const imp = r2(Number(l.cantidad || 0) * Number(l.precio || 0));
    sub += imp;
    if (l.aplica_itbis) itb += r2(imp * ITBIS);
  }
  return { subtotal: r2(sub), itbis: r2(itb), total: r2(sub + itb) };
}

export function EditorDocumento({ tipo, abierto, inicial, onCerrar, onGuardado }) {
  const esCot = tipo === "cotizaciones";
  const [f, setF] = useState({});
  const [proyectos, setProyectos] = useState([]);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  useEffect(() => {
    if (!abierto) return;
    setError("");
    setF(inicial?.id ? { ...inicial, cliente: String(inicial.cliente), proyecto: inicial.proyecto ? String(inicial.proyecto) : "", lineas: inicial.lineas.map((l) => ({ ...l })) }
      : { cliente: inicial?.cliente ? String(inicial.cliente) : "", proyecto: "", titulo: "", fecha: hoyISO(), moneda: "DOP", notas: "",
        ...(esCot ? { valida_hasta: sumarDias(hoyISO(), 15), condiciones: "50% de anticipo para iniciar y 50% contra entrega." } : { vencimiento: sumarDias(hoyISO(), 30), ncf: "" }),
        lineas: [{ descripcion: "", cantidad: 1, precio: "", aplica_itbis: true }] });
  }, [abierto, inicial, esCot]);
  useEffect(() => {
    if (!f.cliente) { setProyectos([]); return; }
    listarProyectos({ cliente: f.cliente }).then(setProyectos).catch(() => {});
  }, [f.cliente]);
  const t = useMemo(() => totales(f.lineas || []), [f.lineas]);
  const linea = (i, campo, v) => setF((x) => ({ ...x, lineas: x.lineas.map((l, j) => (j === i ? { ...l, [campo]: v } : l)) }));

  const guardar = async (e) => {
    e.preventDefault();
    const lineas = (f.lineas || []).filter((l) => l.descripcion?.trim());
    if (!f.cliente) return setError("Elige el cliente.");
    if (!lineas.length) return setError("Agrega al menos una línea con descripción y precio.");
    if (lineas.some((l) => l.precio === "" || Number(l.cantidad) <= 0)) return setError("Cada línea necesita cantidad y precio.");
    setGuardando(true); setError("");
    try {
      const d = await guardarDocumento(tipo, {
        id: f.id, cliente: Number(f.cliente), proyecto: f.proyecto ? Number(f.proyecto) : null, titulo: f.titulo || "", fecha: f.fecha,
        moneda: f.moneda, notas: f.notas || "", ...(esCot ? { valida_hasta: f.valida_hasta || null, condiciones: f.condiciones || "" } : { vencimiento: f.vencimiento || null, ncf: f.ncf || "" }),
        lineas: lineas.map((l) => ({ descripcion: l.descripcion.trim(), cantidad: l.cantidad, precio: l.precio, aplica_itbis: !!l.aplica_itbis })),
      });
      onGuardado(d);
    } catch (err) { setError(err.message); }
    setGuardando(false);
  };
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} ancho="md:max-w-4xl" titulo={f.id ? `Editar ${f.numero}` : esCot ? "Nueva cotización" : "Nueva factura"}
      pie={<><span className="mr-auto self-center text-sm text-gris">Total: <span className="font-display text-lg font-semibold text-tinta num">{dinero(t.total, f.moneda)}</span></span>
        <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton type="submit" form="form-doc" cargando={guardando}>Guardar borrador</Boton></>}>
      <form id="form-doc" onSubmit={guardar} className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <SelectorCliente valor={f.cliente} onCambio={(v) => setF({ ...f, cliente: v, proyecto: "" })} />
          <Campo etiqueta="Proyecto (opcional)">{(id) => <select id={id} className="campo" value={f.proyecto || ""} onChange={(e) => setF({ ...f, proyecto: e.target.value })}>
            <option value="">Ninguno</option>{proyectos.map((p) => <option key={p.id} value={p.id}>{p.codigo} · {p.nombre}</option>)}</select>}</Campo>
          <Campo etiqueta="Título">{(id) => <input id={id} className="campo" value={f.titulo || ""} onChange={(e) => setF({ ...f, titulo: e.target.value })} maxLength={200} placeholder="Ej.: Campaña de Navidad" />}</Campo>
          <Campo etiqueta="Fecha">{(id) => <input id={id} type="date" className="campo" value={f.fecha || ""} onChange={(e) => setF({ ...f, fecha: e.target.value })} />}</Campo>
          {esCot ? <Campo etiqueta="Válida hasta">{(id) => <input id={id} type="date" className="campo" value={f.valida_hasta || ""} onChange={(e) => setF({ ...f, valida_hasta: e.target.value })} />}</Campo>
            : <Campo etiqueta="Vence">{(id) => <input id={id} type="date" className="campo" value={f.vencimiento || ""} onChange={(e) => setF({ ...f, vencimiento: e.target.value })} />}</Campo>}
          <Campo etiqueta="Moneda">{(id) => <select id={id} className="campo" value={f.moneda} onChange={(e) => setF({ ...f, moneda: e.target.value })}><option value="DOP">RD$</option><option value="USD">US$</option></select>}</Campo>
        </div>

        <div className="overflow-x-auto rounded-xl border border-linea">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="bg-fondo text-left text-xs text-gris"><tr><th className="px-3 py-2">Descripción</th><th className="w-24 px-2">Cantidad</th><th className="w-36 px-2">Precio</th><th className="w-20 px-2 text-center">ITBIS</th><th className="w-32 px-3 text-right">Importe</th><th className="w-10" /></tr></thead>
            <tbody>
              {(f.lineas || []).map((l, i) => (
                <tr key={i} className="border-t border-linea-suave">
                  <td className="px-2 py-1.5"><input className="campo h-10" value={l.descripcion} onChange={(e) => linea(i, "descripcion", e.target.value)} aria-label={`Descripción línea ${i + 1}`} maxLength={255} /></td>
                  <td className="px-1"><input type="number" min="0.01" step="any" className="campo h-10" value={l.cantidad} onChange={(e) => linea(i, "cantidad", e.target.value)} aria-label="Cantidad" /></td>
                  <td className="px-1"><input type="number" min="0" step="any" className="campo h-10" value={l.precio} onChange={(e) => linea(i, "precio", e.target.value)} aria-label="Precio" /></td>
                  <td className="text-center"><input type="checkbox" checked={!!l.aplica_itbis} onChange={(e) => linea(i, "aplica_itbis", e.target.checked)} className="size-4 accent-azul" aria-label="Aplica ITBIS" /></td>
                  <td className="px-3 text-right num">{dinero(r2(Number(l.cantidad || 0) * Number(l.precio || 0)), f.moneda)}</td>
                  <td><button type="button" onClick={() => setF({ ...f, lineas: f.lineas.filter((_, j) => j !== i) })} className="rounded p-1.5 text-gris hover:text-rojo" aria-label="Quitar línea"><X className="size-4" /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex flex-wrap items-start justify-between gap-4 border-t border-linea-suave p-3">
            <Boton variante="fantasma" tam="sm" icono={Plus} onClick={() => setF({ ...f, lineas: [...f.lineas, { descripcion: "", cantidad: 1, precio: "", aplica_itbis: true }] })}>Línea</Boton>
            <dl className="min-w-56 space-y-1 text-sm">
              <div className="flex justify-between"><dt className="text-gris">Subtotal</dt><dd className="num">{dinero(t.subtotal, f.moneda)}</dd></div>
              <div className="flex justify-between"><dt className="text-gris">ITBIS 18%</dt><dd className="num">{dinero(t.itbis, f.moneda)}</dd></div>
              <div className="flex justify-between border-t border-linea-suave pt-1 font-semibold"><dt>Total</dt><dd className="num">{dinero(t.total, f.moneda)}</dd></div>
            </dl>
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {esCot ? <Campo etiqueta="Condiciones">{(id) => <textarea id={id} rows={2} className="campo" value={f.condiciones || ""} onChange={(e) => setF({ ...f, condiciones: e.target.value })} />}</Campo>
            : <Campo etiqueta="NCF / e-CF (opcional)" ayuda="Si la emites en Cashflow, el NCF llega solo.">{(id) => <input id={id} className="campo" value={f.ncf || ""} onChange={(e) => setF({ ...f, ncf: e.target.value })} maxLength={20} />}</Campo>}
          <Campo etiqueta="Notas">{(id) => <textarea id={id} rows={2} className="campo" value={f.notas || ""} onChange={(e) => setF({ ...f, notas: e.target.value })} />}</Campo>
        </div>
      </form>
    </Modal>
  );
}

/** Detalle de una cotización o factura con sus acciones. */
export function DetalleDocumento({ tipo, doc, onCerrar, onCambio, onEditar }) {
  const esCot = tipo === "cotizaciones";
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const navigate = useNavigate();
  const [pago, setPago] = useState(null);
  const [aprobar, setAprobar] = useState(null);
  const [ncf, setNcf] = useState("");
  useEffect(() => { setNcf(doc?.ncf || ""); setPago(null); setAprobar(null); }, [doc]);
  if (!doc) return null;
  const accion = async (nombre, body, msg) => {
    try { const r = await accionDocumento(tipo, doc.id, nombre, body); avisar(msg); onCambio(r); return r; } catch (e) { avisar(e.message, "rojo"); return null; }
  };
  const botones = [];
  if (doc.estado === "BORRADOR") {
    botones.push(<Boton key="ed" variante="secundario" onClick={() => onEditar(doc)}>Editar</Boton>);
    botones.push(<Boton key="bo" variante="fantasma" icono={Trash2} className="text-rojo" onClick={async () => {
      if (!(await confirmar({ titulo: `¿Borrar ${doc.numero}?`, mensaje: "Es un borrador: no queda rastro.", boton: "Borrar", peligro: true }))) return;
      await eliminarDocumento(tipo, doc.id); avisar("Borrado."); onCambio(null);
    }}>Borrar</Boton>);
  }
  if (esCot) {
    if (doc.estado === "BORRADOR") botones.push(<Boton key="en" icono={Send} onClick={() => accion("enviar", {}, "Marcada como enviada al cliente.")}>Marcar enviada</Boton>);
    if (!doc.cashflow_id && doc.estado !== "RECHAZADA") botones.push(<Boton key="cf" variante="secundario" icono={CloudUpload} onClick={() => accion("cashflow", {}, "Cotización enviada a Cashflow.")}>Enviar a Cashflow</Boton>);
    if (["BORRADOR", "ENVIADA"].includes(doc.estado)) {
      botones.push(<Boton key="re" variante="secundario" icono={X} onClick={() => accion("rechazar", {}, "Cotización rechazada.")}>Rechazada</Boton>);
      botones.push(<Boton key="ap" icono={CheckCircle2} onClick={() => setAprobar("")}>Aprobada por el cliente</Boton>);
    }
    if (doc.estado === "APROBADA") botones.push(<Boton key="fa" icono={Receipt} onClick={async () => { const f = await accion("facturar", {}, "Factura creada en borrador."); if (f) navigate(`/finanzas?ver=facturas&id=${f.id}`); }}>Facturar</Boton>);
    botones.push(<Boton key="du" variante="secundario" icono={Copy} onClick={async () => { const n = await accion("duplicar", {}, "Copia creada en borrador."); if (n) onEditar(n); }}>Duplicar</Boton>);
  } else {
    if (["BORRADOR", "EMITIDA"].includes(doc.estado) && !doc.cashflow_id) botones.push(<Boton key="cf" icono={CloudUpload} onClick={() => accion("cashflow", {}, "Factura emitida en Cashflow con su NCF.")}>Emitir en Cashflow (NCF)</Boton>);
    if (doc.estado === "BORRADOR") botones.push(<Boton key="em" variante="secundario" icono={Send} onClick={() => accion("emitir", {}, "Factura emitida solo aquí (sin Cashflow).")}>Emitir sin Cashflow</Boton>);
    if (doc.cashflow_id && ["EMITIDA", "PAGADA"].includes(doc.estado)) botones.push(<Boton key="cs" variante="secundario" icono={RefreshCw} onClick={async () => {
      const r = await accion("cashflow_actualizar", {}, "Actualizada desde Cashflow.");
      if (r?.pagos_nuevos) avisar(`${r.pagos_nuevos} pago(s) nuevo(s) desde Cashflow.`);
    }}>Traer pagos de Cashflow</Boton>);
    if (doc.estado === "EMITIDA") botones.push(<Boton key="pa" variante="acento" icono={Plus} onClick={() => setPago({ monto: doc.saldo, fecha: hoyISO(), metodo: "TRANSFERENCIA", referencia: "" })}>Registrar pago</Boton>);
    if (["BORRADOR", "EMITIDA"].includes(doc.estado) && !doc.pagos.length) botones.push(<Boton key="an" variante="peligro" icono={Ban} onClick={async () => {
      if (await confirmar({ titulo: `¿Anular ${doc.numero}?`, mensaje: "Deja de contar como facturado y por cobrar.", boton: "Anular", peligro: true })) accion("anular", { motivo: "" }, "Factura anulada.");
    }}>Anular</Boton>);
  }
  botones.push(<a key="im" href={`/imprimir/${tipo}/${doc.id}`} target="_blank" rel="noopener" className="inline-flex h-11 items-center gap-2 rounded-lg border border-linea bg-white px-4 text-[15px] font-medium hover:bg-fondo"><Printer className="size-4" />Imprimir / PDF</a>);

  return (
    <Modal abierto={!!doc} onCerrar={onCerrar} ancho="md:max-w-3xl" titulo={`${esCot ? "Cotización" : "Factura"} ${doc.numero}`} descripcion={`${doc.cliente_nombre}${doc.titulo ? ` · ${doc.titulo}` : ""}`}
      pie={<div className="flex w-full flex-wrap justify-end gap-2">{botones}</div>}>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <EstadoDoc doc={doc} />
          <span className="text-gris">Fecha {fechaCorta(doc.fecha)}</span>
          {esCot && doc.valida_hasta && <span className="text-gris">Válida hasta {fechaCorta(doc.valida_hasta)}</span>}
          {!esCot && doc.vencimiento && <span className={cx(doc.vencida ? "font-medium text-rojo" : "text-gris")}>Vence {fechaCorta(doc.vencimiento)}</span>}
          {doc.orden && <Link to={`/ordenes/${doc.orden}`} className="text-azul hover:underline">{doc.orden_numero}</Link>}
          {doc.cotizacion_numero && <span className="text-gris">De {doc.cotizacion_numero}</span>}
          {doc.es_anticipo && <span className="rounded-full bg-azul/10 px-2 py-0.5 text-xs font-medium text-azul">Anticipo</span>}
          {doc.cashflow_id && <span className="rounded-full bg-verde-50 px-2 py-0.5 text-xs font-medium text-verde">En Cashflow{doc.cashflow_numero ? ` · ${doc.cashflow_numero}` : ""}{doc.cashflow_estado ? ` · ${doc.cashflow_estado}` : ""}</span>}
        </div>
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-gris"><tr><th className="py-1.5">Descripción</th><th className="text-right">Cant.</th><th className="text-right">Precio</th><th className="text-right">Importe</th></tr></thead>
          <tbody>{doc.lineas.map((l, i) => (
            <tr key={i} className="border-t border-linea-suave"><td className="py-2">{l.descripcion}{!l.aplica_itbis && <span className="ml-1 text-xs text-gris">(exento)</span>}</td>
              <td className="text-right num">{Number(l.cantidad).toLocaleString("es-DO")}</td><td className="text-right num">{dinero(l.precio, doc.moneda)}</td><td className="text-right num">{dinero(l.importe, doc.moneda)}</td></tr>))}</tbody>
        </table>
        <dl className="ml-auto max-w-xs space-y-1 text-sm">
          <div className="flex justify-between"><dt className="text-gris">Subtotal</dt><dd className="num">{dinero(doc.subtotal, doc.moneda)}</dd></div>
          <div className="flex justify-between"><dt className="text-gris">ITBIS</dt><dd className="num">{dinero(doc.itbis, doc.moneda)}</dd></div>
          <div className="flex justify-between border-t border-linea pt-1 text-base font-semibold"><dt>Total</dt><dd className="num">{dinero(doc.total, doc.moneda)}</dd></div>
          {!esCot && <div className="flex justify-between"><dt className="text-gris">Pagado</dt><dd className="num">{dinero(doc.pagado, doc.moneda)}</dd></div>}
          {!esCot && doc.estado !== "ANULADA" && <div className="flex justify-between font-semibold"><dt>Saldo</dt><dd className={cx("num", Number(doc.saldo) > 0 && "text-[#a86a00]")}>{dinero(doc.saldo, doc.moneda)}</dd></div>}
        </dl>
        {!esCot && doc.estado !== "ANULADA" && (
          <div className="flex flex-wrap items-end gap-2 rounded-xl bg-fondo p-3">
            <Campo etiqueta={doc.cashflow_id ? "NCF / e-CF (lo asignó Cashflow)" : "NCF / e-CF (si se emitió fuera de Cashflow)"} className="flex-1">{(id) => <input id={id} className="campo bg-white" value={ncf} onChange={(e) => setNcf(e.target.value)} maxLength={20} placeholder="B0100000001 / E310000000001" />}</Campo>
            <Boton variante="secundario" disabled={ncf === (doc.ncf || "")} onClick={async () => { try { onCambio(await guardarDocumento(tipo, { id: doc.id, ncf })); avisar("NCF guardado."); } catch (e) { avisar(e.message, "rojo"); } }}>Guardar NCF</Boton>
          </div>
        )}
        {!esCot && doc.pagos.length > 0 && (
          <section>
            <h3 className="mb-2 font-semibold">Pagos</h3>
            <ul className="divide-y divide-linea-suave rounded-xl border border-linea text-sm">
              {doc.pagos.map((p) => (
                <li key={p.id} className="flex items-center gap-3 px-3 py-2">
                  <span className="flex-1">{fechaCorta(p.fecha)} · {p.metodo_nombre}{p.referencia ? ` · ${p.referencia}` : ""}</span>
                  <span className="font-medium num">{dinero(p.monto, doc.moneda)}</span>
                  <button type="button" className="rounded p-1 text-gris hover:text-rojo" aria-label="Borrar pago" onClick={async () => {
                    if (await confirmar({ titulo: "¿Borrar este pago?", mensaje: "El saldo vuelve a subir.", boton: "Borrar", peligro: true })) { onCambio(await borrarPago(p.id)); avisar("Pago borrado."); }
                  }}><Trash2 className="size-4" /></button>
                </li>
              ))}
            </ul>
          </section>
        )}
        {doc.notas && <p className="whitespace-pre-line text-sm text-gris">{doc.notas}</p>}
        {pago && (
          <form className="space-y-3 rounded-xl border border-amarillo bg-amarillo-50/60 p-4" onSubmit={async (e) => {
            e.preventDefault();
            try { onCambio(await registrarPago(doc.id, pago)); setPago(null); avisar("Pago registrado."); } catch (err) { avisar(err.message, "rojo"); }
          }}>
            <h3 className="font-semibold">Registrar pago</h3>
            <div className="grid gap-3 sm:grid-cols-4">
              <Campo etiqueta="Monto">{(id) => <input id={id} type="number" step="any" min="0.01" max={doc.saldo} className="campo bg-white" value={pago.monto} onChange={(e) => setPago({ ...pago, monto: e.target.value })} autoFocus />}</Campo>
              <Campo etiqueta="Fecha">{(id) => <input id={id} type="date" className="campo bg-white" value={pago.fecha} onChange={(e) => setPago({ ...pago, fecha: e.target.value })} />}</Campo>
              <Campo etiqueta="Forma">{(id) => <select id={id} className="campo bg-white" value={pago.metodo} onChange={(e) => setPago({ ...pago, metodo: e.target.value })}>
                <option value="TRANSFERENCIA">Transferencia</option><option value="EFECTIVO">Efectivo</option><option value="CHEQUE">Cheque</option><option value="TARJETA">Tarjeta</option><option value="OTRO">Otro</option></select>}</Campo>
              <Campo etiqueta="Referencia">{(id) => <input id={id} className="campo bg-white" value={pago.referencia} onChange={(e) => setPago({ ...pago, referencia: e.target.value })} maxLength={100} />}</Campo>
            </div>
            <div className="flex justify-end gap-2"><Boton variante="secundario" onClick={() => setPago(null)}>Cancelar</Boton><Boton type="submit">Guardar pago</Boton></div>
          </form>
        )}
        {aprobar !== null && (
          <div className="space-y-3 rounded-xl border border-verde/40 bg-verde-50/60 p-4">
            <h3 className="font-semibold">¿Crear la OT Maestra de una vez?</h3>
            <label className="flex items-center gap-2.5 text-[15px]"><input type="checkbox" className="size-4 accent-azul" checked={aprobar === "1"} onChange={(e) => setAprobar(e.target.checked ? "1" : "")} />
              Sí: crear la solicitud (F-01) con el cliente, el monto y la cotización marcada en G0. Comercial completa las áreas y la entrega a Coordinación.</label>
            <div className="flex justify-end gap-2"><Boton variante="secundario" onClick={() => setAprobar(null)}>Volver</Boton>
              <Boton icono={CheckCircle2} onClick={async () => {
                const r = await accion("aprobar", aprobar ? { crear_orden: true } : {}, aprobar ? "Aprobada. Se creó la solicitud de OT: completa las áreas." : "Cotización aprobada.");
                if (r?.orden_creada) navigate(`/ordenes/${r.orden_creada.id}`);
              }}>Confirmar</Boton></div>
          </div>
        )}
      </div>
    </Modal>
  );
}
