// Almacén: vales de salida (F-11) por autorizar, despachar y cerrar; catálogo de materiales con existencias, entradas y ajustes.
import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AlertTriangle, ArrowDownToLine, Boxes, ClipboardList, PackageCheck, Plus, Scale, Search, X } from "lucide-react";
import { accionMaterial, accionVale, guardarMaterial, listarMateriales, listarVales, movimientosMaterial, resumenVales } from "@/lib/api";
import { dinero, fechaHora, hace } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import { Alerta, Boton, Cabecera, Campo, Cargando, Modal, Panel, Pestanas, Vacio, cx, useAviso } from "@/components/ui";
import { AreaChip } from "@/features/ordenes/piezas";

const ESTADOS = [["SOLICITADO", "Por autorizar"], ["AUTORIZADO", "Por despachar"], ["DESPACHADO", "Despachados"], ["CERRADO", "Cerrados"]];

function Vale({ v, onCambio }) {
  const avisar = useAviso();
  const { esCoordinacion, esAlmacen } = useSesion();
  const [lineas, setLineas] = useState({});
  const [motivo, setMotivo] = useState(null);
  const [enviando, setEnviando] = useState(false);
  useEffect(() => setLineas(Object.fromEntries(v.lineas.map((l) => [l.id, { id: l.id, cantidad_despachada: l.cantidad_despachada > 0 ? l.cantidad_despachada : l.cantidad_solicitada, lote: l.lote, cantidad_devuelta: l.cantidad_devuelta, desperdicio: l.desperdicio, causa_desperdicio: l.causa_desperdicio }]))), [v]);
  const ir = async (accion, body, msg) => {
    setEnviando(true);
    try { onCambio(await accionVale(v.id, accion, body)); avisar(msg); } catch (e) { avisar(e.message, "rojo"); }
    setEnviando(false);
  };
  const poner = (id, k, val) => setLineas({ ...lineas, [id]: { ...lineas[id], [k]: val } });
  const despachar = v.estado === "AUTORIZADO" && esAlmacen;
  const cerrar = v.estado === "DESPACHADO" && esAlmacen;
  return (
    <article className="rounded-xl border border-linea bg-white p-4">
      <header className="flex flex-wrap items-center gap-2">
        <span className="font-semibold num">{v.numero}</span>
        {v.area && <AreaChip area={v.area} conNombre={false} />}
        <Link to={`/ordenes/${v.orden}${v.oa ? `/areas/${v.oa}` : ""}`} className="text-sm text-azul hover:underline">{v.oa_numero || v.orden_codigo}</Link>
        <span className="text-sm text-gris">· {v.cliente}</span>
        <span className="ml-auto text-sm text-gris">{v.solicitado_por_nombre} · {hace(v.fecha)}</span>
      </header>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[560px] text-sm">
          <thead className="text-left text-xs text-gris"><tr><th className="py-1">Material</th><th className="text-right">Pedido</th><th className="text-right">Existencia</th>
            {(despachar || v.estado !== "SOLICITADO") && <th className="text-right">Despachado</th>}{despachar && <th>Lote</th>}{cerrar && <><th className="text-right">Devuelto</th><th className="text-right">Desperdicio</th><th>Causa</th></>}
            {v.costo_total != null && <th className="text-right">Costo</th>}</tr></thead>
          <tbody>{v.lineas.map((l) => (
            <tr key={l.id} className="border-t border-linea-suave">
              <td className="py-1.5">{l.material_nombre}</td>
              <td className="text-right num">{Number(l.cantidad_solicitada).toLocaleString("es-DO")} {l.unidad}</td>
              <td className={cx("text-right num", Number(l.existencia) < Number(l.cantidad_solicitada) && "font-medium text-rojo")}>{Number(l.existencia).toLocaleString("es-DO")}</td>
              {despachar ? <>
                <td className="text-right"><input aria-label="Cantidad despachada" type="number" min={0} step="any" className="h-9 w-24 rounded-md border border-linea px-2 text-right" value={lineas[l.id]?.cantidad_despachada ?? ""} onChange={(e) => poner(l.id, "cantidad_despachada", e.target.value)} /></td>
                <td><input aria-label="Lote" className="h-9 w-28 rounded-md border border-linea px-2" value={lineas[l.id]?.lote ?? ""} onChange={(e) => poner(l.id, "lote", e.target.value)} /></td>
              </> : v.estado !== "SOLICITADO" && <td className="text-right num">{Number(l.cantidad_despachada).toLocaleString("es-DO")}{l.lote && <span className="block text-xs text-gris">{l.lote}</span>}</td>}
              {cerrar && <>
                <td className="text-right"><input aria-label="Devuelto" type="number" min={0} step="any" className="h-9 w-20 rounded-md border border-linea px-2 text-right" value={lineas[l.id]?.cantidad_devuelta ?? ""} onChange={(e) => poner(l.id, "cantidad_devuelta", e.target.value)} /></td>
                <td className="text-right"><input aria-label="Desperdicio" type="number" min={0} step="any" className="h-9 w-20 rounded-md border border-linea px-2 text-right" value={lineas[l.id]?.desperdicio ?? ""} onChange={(e) => poner(l.id, "desperdicio", e.target.value)} /></td>
                <td><input aria-label="Causa del desperdicio" className="h-9 w-36 rounded-md border border-linea px-2" value={lineas[l.id]?.causa_desperdicio ?? ""} onChange={(e) => poner(l.id, "causa_desperdicio", e.target.value)} /></td>
              </>}
              {v.costo_total != null && <td className="text-right num">{l.costo_unitario != null && dinero(Number(l.costo_unitario) * (Number(l.cantidad_despachada) > 0 ? Number(l.cantidad_despachada) : Number(l.cantidad_solicitada)))}</td>}
            </tr>
          ))}</tbody>
        </table>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gris">
        {v.autorizado_por_nombre && <span>Autorizó {v.autorizado_por_nombre}</span>}
        {v.despachado_por_nombre && <span>Despachó {v.despachado_por_nombre} · {fechaHora(v.fecha_despacho)}</span>}
        {v.recibido_por_nombre ? <span>Recibió {v.recibido_por_nombre}</span> : v.estado === "DESPACHADO" && <span className="text-[#a86a00]">Falta la firma de quien recibe</span>}
        {v.costo_total != null && ["DESPACHADO", "CERRADO"].includes(v.estado) && <span className="ml-auto text-sm font-medium text-tinta">Costo {dinero(v.costo_total)}</span>}
      </div>
      {v.notas && <p className="mt-1 whitespace-pre-line text-sm text-gris">{v.notas}</p>}
      {motivo !== null ? (
        <div className="mt-3 flex gap-2"><input className="campo" aria-label="Motivo" placeholder="Motivo del rechazo" value={motivo} onChange={(e) => setMotivo(e.target.value)} autoFocus />
          <Boton variante="secundario" onClick={() => setMotivo(null)}>Volver</Boton><Boton variante="peligro" disabled={motivo.trim().length < 3} onClick={() => ir("rechazar", { motivo }, "Vale rechazado.")}>Rechazar</Boton></div>
      ) : (
        <div className="mt-3 flex flex-wrap justify-end gap-2">
          {["SOLICITADO", "AUTORIZADO"].includes(v.estado) && (esCoordinacion || esAlmacen) && <Boton variante="fantasma" icono={X} onClick={() => setMotivo("")}>Rechazar</Boton>}
          {v.estado === "SOLICITADO" && esCoordinacion && <Boton icono={ClipboardList} cargando={enviando} onClick={() => ir("autorizar", {}, "Vale autorizado. Almacén recibió el aviso.")}>Autorizar</Boton>}
          {despachar && <Boton icono={PackageCheck} cargando={enviando} onClick={() => ir("despachar", { lineas: Object.values(lineas) }, "Despachado. La existencia ya se descontó.")}>Despachar</Boton>}
          {cerrar && <Boton variante="secundario" cargando={enviando} onClick={() => ir("cerrar", { lineas: Object.values(lineas) }, "Vale cerrado. Lo devuelto volvió a la existencia.")}>Cerrar con devolución</Boton>}
        </div>
      )}
    </article>
  );
}

function FormMaterial({ inicial, abierto, onCerrar, onGuardado }) {
  const [f, setF] = useState({});
  const [error, setError] = useState("");
  useEffect(() => { if (abierto) { setError(""); setF(inicial?.id ? { ...inicial } : { codigo: "", nombre: "", unidad: "unidad", punto_reposicion: 0, costo_unitario: 0, proveedor: "", activo: true }); } }, [abierto, inicial]);
  const poner = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={f.id ? `Editar ${f.nombre}` : "Nuevo material"} ancho="max-w-lg"
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton onClick={async () => { try { onGuardado(await guardarMaterial(f)); } catch (e) { setError(e.message); } }}>Guardar</Boton></>}>
      {error && <Alerta className="mb-3">{error}</Alerta>}
      <div className="grid gap-4 sm:grid-cols-2">
        <Campo etiqueta="Código">{(id) => <input id={id} className="campo" value={f.codigo || ""} onChange={poner("codigo")} />}</Campo>
        <Campo etiqueta="Unidad" ayuda="pie², m², hoja, plancha, galón…">{(id) => <input id={id} className="campo" value={f.unidad || ""} onChange={poner("unidad")} />}</Campo>
        <Campo etiqueta="Nombre" className="sm:col-span-2">{(id) => <input id={id} className="campo" value={f.nombre || ""} onChange={poner("nombre")} />}</Campo>
        <Campo etiqueta="Punto de reposición" ayuda="Al llegar aquí, avisa para comprar.">{(id) => <input id={id} type="number" min={0} step="any" className="campo" value={f.punto_reposicion ?? ""} onChange={poner("punto_reposicion")} />}</Campo>
        <Campo etiqueta="Costo unitario RD$">{(id) => <input id={id} type="number" min={0} step="any" className="campo" value={f.costo_unitario ?? ""} onChange={poner("costo_unitario")} />}</Campo>
        <Campo etiqueta="Proveedor (opcional)" className="sm:col-span-2">{(id) => <input id={id} className="campo" value={f.proveedor || ""} onChange={poner("proveedor")} />}</Campo>
        {f.id && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!f.activo} onChange={poner("activo")} className="accent-azul" />Activo</label>}
      </div>
    </Modal>
  );
}

function Movimiento({ material, tipo, abierto, onCerrar, onHecho }) {
  const [f, setF] = useState({});
  const [error, setError] = useState("");
  useEffect(() => { if (abierto) { setError(""); setF({ cantidad: "", costo_unitario: material?.costo_unitario ?? "", existencia: material?.existencia ?? "", nota: "" }); } }, [abierto, material]);
  if (!material) return null;
  const entrada = tipo === "entrada";
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={`${entrada ? "Entrada" : "Ajuste por conteo"} · ${material.nombre}`} ancho="max-w-md"
      descripcion={entrada ? "Compra o recepción: suma a la existencia y recalcula el costo promedio." : "Pon lo que hay físicamente. La diferencia queda en el kardex."}
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton onClick={async () => {
        try { onHecho(await accionMaterial(material.id, entrada ? "entrada" : "ajustar", entrada ? { cantidad: f.cantidad, costo_unitario: f.costo_unitario, nota: f.nota } : { existencia: f.existencia, nota: f.nota })); }
        catch (e) { setError(e.message); }
      }}>Guardar</Boton></>}>
      {error && <Alerta className="mb-3">{error}</Alerta>}
      <div className="grid gap-4 sm:grid-cols-2">
        {entrada ? <>
          <Campo etiqueta={`Cantidad (${material.unidad})`}>{(id) => <input id={id} type="number" min={0} step="any" className="campo" value={f.cantidad} onChange={(e) => setF({ ...f, cantidad: e.target.value })} autoFocus />}</Campo>
          <Campo etiqueta="Costo unitario RD$">{(id) => <input id={id} type="number" min={0} step="any" className="campo" value={f.costo_unitario} onChange={(e) => setF({ ...f, costo_unitario: e.target.value })} />}</Campo>
        </> : <Campo etiqueta={`Existencia física (${material.unidad})`}>{(id) => <input id={id} type="number" min={0} step="any" className="campo" value={f.existencia} onChange={(e) => setF({ ...f, existencia: e.target.value })} autoFocus />}</Campo>}
        <Campo etiqueta={entrada ? "Factura / proveedor" : "Motivo"} className="sm:col-span-2">{(id) => <input id={id} className="campo" value={f.nota} onChange={(e) => setF({ ...f, nota: e.target.value })} />}</Campo>
      </div>
    </Modal>
  );
}

function Kardex({ material, onCerrar }) {
  const [m, setM] = useState(null);
  useEffect(() => { if (material) movimientosMaterial(material.id).then(setM).catch(() => setM([])); else setM(null); }, [material]);
  return (
    <Modal abierto={!!material} onCerrar={onCerrar} titulo={`Kardex · ${material?.nombre || ""}`} ancho="md:max-w-2xl">
      {!m ? <Cargando /> : m.length === 0 ? <p className="text-sm text-gris">Sin movimientos.</p> : (
        <table className="w-full text-sm"><thead className="text-left text-xs text-gris"><tr><th className="py-1">Fecha</th><th>Tipo</th><th className="text-right">Cantidad</th><th>Detalle</th></tr></thead>
          <tbody>{m.map((x) => <tr key={x.id} className="border-t border-linea-suave"><td className="py-1.5">{fechaHora(x.fecha)}</td><td>{x.tipo_nombre}</td>
            <td className={cx("text-right num", Number(x.cantidad) < 0 ? "text-rojo" : "text-verde")}>{Number(x.cantidad).toLocaleString("es-DO")}</td><td className="text-gris">{x.vale_numero || x.nota} · {x.usuario_nombre}</td></tr>)}</tbody></table>
      )}
    </Modal>
  );
}

export default function Almacen() {
  const avisar = useAviso();
  const { esAlmacen, esCoordinacion } = useSesion();
  const [params, setParams] = useSearchParams();
  const ver = params.get("ver") || "vales";
  const [estado, setEstado] = useState(esAlmacen && !esCoordinacion ? "AUTORIZADO" : "SOLICITADO");
  const [vales, setVales] = useState(null);
  const [materiales, setMateriales] = useState(null);
  const [resumen, setResumen] = useState(null);
  const [buscar, setBuscar] = useState("");
  const [modal, setModal] = useState(null);
  const [sel, setSel] = useState(null);
  const [error, setError] = useState("");

  const cargar = useCallback(() => {
    resumenVales().then(setResumen).catch(() => {});
    if (ver === "vales") listarVales({ estado }).then(setVales).catch((e) => setError(e.message));
    else listarMateriales({}).then(setMateriales).catch((e) => setError(e.message));
  }, [ver, estado]);
  useEffect(() => { cargar(); }, [cargar]);

  const cuenta = { SOLICITADO: resumen?.por_autorizar, AUTORIZADO: resumen?.por_despachar, DESPACHADO: resumen?.por_cerrar };
  const mats = (materiales || []).filter((m) => !buscar || `${m.codigo} ${m.nombre}`.toLowerCase().includes(buscar.toLowerCase()));
  if (error) return <Alerta>{error}</Alerta>;
  return (
    <div>
      <Cabecera titulo="Almacén" descripcion="Sin vale no sale material. Se descuenta al despachar; lo que sobra vuelve con la devolución y el desperdicio queda con su causa.">
        {ver === "materiales" && esAlmacen && <Boton icono={Plus} onClick={() => { setSel(null); setModal("material"); }}>Nuevo material</Boton>}
      </Cabecera>
      {resumen?.bajo_minimo > 0 && <Alerta tono="amarillo" className="mb-4">{resumen.bajo_minimo} material(es) en o bajo el punto de reposición. <button type="button" className="font-medium underline" onClick={() => { params.set("ver", "materiales"); setParams(params); setBuscar(""); }}>Ver materiales</button></Alerta>}
      <Pestanas className="mb-4 md:w-96" valor={ver} onCambio={(v) => { params.set("ver", v); setParams(params, { replace: true }); }} opciones={[
        { valor: "vales", etiqueta: <><ClipboardList className="size-4" />Vales F-11</> },
        { valor: "materiales", etiqueta: <><Boxes className="size-4" />Materiales</> },
      ]} />
      {ver === "vales" ? (
        <>
          <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="Estado de los vales">
            {ESTADOS.map(([e, t]) => (
              <button key={e} type="button" onClick={() => setEstado(e)} aria-pressed={estado === e}
                className={cx("inline-flex h-9 items-center gap-1.5 rounded-full border px-3.5 text-sm font-medium", estado === e ? "border-noche bg-noche text-white" : "border-linea bg-white")}>
                {t}{cuenta[e] ? <span className="num opacity-70">{cuenta[e]}</span> : null}</button>
            ))}
          </div>
          {!vales ? <Cargando /> : vales.length === 0 ? <Vacio icono={ClipboardList} titulo="Nada aquí">Los vales se piden desde la Orden de Área («Pedir material»).</Vacio> : (
            <div className="space-y-3">{vales.map((v) => <Vale key={v.id} v={v} onCambio={() => cargar()} />)}</div>
          )}
        </>
      ) : !materiales ? <Cargando /> : (
        <>
        <div className="relative mb-3 w-full max-w-xs"><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" /><input className="campo h-11 pl-9" placeholder="Buscar material" aria-label="Buscar material" value={buscar} onChange={(e) => setBuscar(e.target.value)} /></div>
        <Panel cuerpo="p-0">
          <div className="overflow-x-auto">
            <table className="tabla">
              <thead><tr><th>Código</th><th>Material</th><th className="text-right">Existencia</th><th className="text-right">Reposición</th><th className="text-right">Costo</th><th /></tr></thead>
              <tbody>{mats.map((m) => (
                <tr key={m.id} className={cx(!m.activo && "opacity-50")}>
                  <td className="num text-sm">{m.codigo}</td>
                  <td><span className="font-medium">{m.nombre}</span>{m.proveedor && <span className="block text-xs text-gris">{m.proveedor}</span>}</td>
                  <td className={cx("text-right num", m.bajo_minimo && "font-semibold text-rojo")}>{m.bajo_minimo && <AlertTriangle className="mr-1 inline size-4" aria-label="Bajo mínimo" />}{Number(m.existencia).toLocaleString("es-DO")} {m.unidad}</td>
                  <td className="text-right num text-gris">{Number(m.punto_reposicion).toLocaleString("es-DO")}</td>
                  <td className="text-right num">{m.costo_unitario != null ? dinero(m.costo_unitario) : "—"}</td>
                  <td className="whitespace-nowrap text-right">
                    {esAlmacen && <>
                      <button type="button" className="rounded p-2 text-azul hover:bg-fondo" aria-label={`Entrada de ${m.nombre}`} title="Entrada" onClick={() => { setSel(m); setModal("entrada"); }}><ArrowDownToLine className="size-4" /></button>
                      <button type="button" className="rounded p-2 text-gris hover:bg-fondo" aria-label={`Ajustar ${m.nombre}`} title="Ajuste" onClick={() => { setSel(m); setModal("ajuste"); }}><Scale className="size-4" /></button>
                      <button type="button" className="rounded px-2 py-1 text-sm text-gris hover:bg-fondo" onClick={() => { setSel(m); setModal("material"); }}>Editar</button>
                    </>}
                    <button type="button" className="rounded px-2 py-1 text-sm text-azul hover:bg-fondo" onClick={() => { setSel(m); setModal("kardex"); }}>Kardex</button>
                  </td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </Panel>
        </>
      )}
      <FormMaterial inicial={sel} abierto={modal === "material"} onCerrar={() => setModal(null)} onGuardado={() => { setModal(null); avisar("Material guardado."); cargar(); }} />
      <Movimiento material={sel} tipo={modal} abierto={modal === "entrada" || modal === "ajuste"} onCerrar={() => setModal(null)} onHecho={() => { setModal(null); avisar("Existencia actualizada."); cargar(); }} />
      <Kardex material={modal === "kardex" ? sel : null} onCerrar={() => setModal(null)} />
    </div>
  );
}
