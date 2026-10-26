// Finanzas operativas: lo que entra, lo que se debe, lo que se gasta y qué deja ganancia.
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { FileText, Paperclip, Pencil, Plus, Receipt, Search, Trash2, Wallet } from "lucide-react";
import { eliminarDocumento, facturarOrden, guardarGasto, listarDocumentos, listarProyectos, obtenerDocumento, rentabilidad, resumenFinanzas } from "@/lib/api";
import { dinero, fechaCorta, hoyISO, horas, mesActual } from "@/lib/formato";
import { Alerta, Boton, Cabecera, Campo, Cargando, Modal, Panel, Pestanas, SelectorMes, Vacio, cx, useAviso, useConfirmar } from "@/components/ui";
import { DetalleDocumento, EditorDocumento, EstadoDoc } from "./documentos";

function Tarjeta({ etiqueta, valor, nota, tono }) {
  return (
    <div className="rounded-xl border border-linea bg-white px-4 py-3.5">
      <p className="text-sm text-gris">{etiqueta}</p>
      <p className={cx("font-display text-[22px] font-semibold leading-tight num", tono)}>{valor}</p>
      {nota && <p className="mt-0.5 text-xs text-gris">{nota}</p>}
    </div>
  );
}

const TRAMOS = [["al_dia", "Al día", "bg-verde"], ["1_30", "1–30 días", "bg-amarillo"], ["31_60", "31–60", "bg-amarillo-600"], ["61_90", "61–90", "bg-rojo/70"], ["mas_90", "Más de 90", "bg-rojo"]];

function Resumen({ onFacturar }) {
  const [mes, setMes] = useState(mesActual());
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const cargar = useCallback(() => resumenFinanzas(mes).then(setD).catch((e) => setError(e.message)), [mes]);
  useEffect(() => { cargar(); }, [cargar]);
  if (error) return <Alerta>{error}</Alerta>;
  if (!d) return <Cargando />;
  const totalCxc = TRAMOS.reduce((s, [k]) => s + Number(d.antiguedad[k]), 0);
  const maxGasto = Math.max(1, ...d.gastos_por_categoria.map((g) => Number(g.monto)));
  return (
    <div className="space-y-5">
      <SelectorMes valor={mes} onCambio={setMes} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
        <Tarjeta etiqueta="Facturado" valor={dinero(d.facturado)} nota={`+ ${dinero(d.itbis)} de ITBIS`} />
        <Tarjeta etiqueta="Cobrado" valor={dinero(d.cobrado)} tono="text-verde" />
        <Tarjeta etiqueta="Gastos" valor={dinero(d.gastos)} />
        <Tarjeta etiqueta="Resultado del mes" valor={dinero(d.resultado)} tono={Number(d.resultado) < 0 ? "text-rojo" : "text-noche"} nota="Facturado − gastos" />
        <Tarjeta etiqueta="Por cobrar" valor={dinero(d.por_cobrar)} tono="text-[#a86a00]" />
        <Tarjeta etiqueta="Vencido" valor={dinero(d.vencido)} tono={Number(d.vencido) > 0 ? "text-rojo" : ""} />
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Panel titulo="Órdenes listas o entregadas sin facturar" cuerpo="p-0">
          {d.por_facturar.length === 0 ? <p className="p-5 text-sm text-gris">Todo lo entregado está facturado.</p> : (
            <ul className="divide-y divide-linea-suave">
              {d.por_facturar.map((o) => (
                <li key={o.id} className="flex items-center gap-3 px-5 py-3">
                  <Link to={`/ordenes/${o.id}`} className="min-w-0 flex-1 hover:text-azul"><span className="block truncate font-medium">{o.numero} · {o.titulo}</span>
                    <span className="text-sm text-gris">{o.cliente} · {o.estado_nombre}{o.fecha_entrega ? ` ${fechaCorta(o.fecha_entrega)}` : ""}</span></Link>
                  <span className="text-sm num">{o.monto ? dinero(o.monto) : "Sin monto"}</span>
                  <Boton tam="sm" icono={Receipt} onClick={() => onFacturar(o)}>Facturar</Boton>
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <Panel titulo="Cuentas por cobrar por antigüedad">
          <div className="mb-3 flex h-4 overflow-hidden rounded-full bg-linea-suave">
            {TRAMOS.map(([k, , c]) => Number(d.antiguedad[k]) > 0 && <span key={k} className={c} style={{ width: `${(100 * d.antiguedad[k]) / totalCxc}%` }} />)}
          </div>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-5">
            {TRAMOS.map(([k, t, c]) => <div key={k}><dt className="flex items-center gap-1.5 text-gris"><span className={cx("size-2.5 rounded-sm", c)} />{t}</dt><dd className="font-medium num">{dinero(d.antiguedad[k])}</dd></div>)}
          </dl>
          {d.deudores.length > 0 && (
            <ul className="mt-4 divide-y divide-linea-suave border-t border-linea-suave text-sm">
              {d.deudores.map((x) => (
                <li key={x.cliente_id} className="flex justify-between py-2"><Link to={`/clientes/${x.cliente_id}`} className="hover:text-azul">{x.cliente}</Link>
                  <span className="num">{dinero(x.saldo)}{Number(x.vencido) > 0 && <span className="ml-2 text-rojo">({dinero(x.vencido)} vencido)</span>}</span></li>
              ))}
            </ul>
          )}
        </Panel>
        <Panel titulo="Gastos del mes por categoría">
          {d.gastos_por_categoria.length === 0 ? <p className="text-sm text-gris">Sin gastos registrados este mes.</p> : (
            <ul className="space-y-2.5">
              {d.gastos_por_categoria.map((g) => (
                <li key={g.categoria} className="grid grid-cols-[130px_minmax(0,1fr)_110px] items-center gap-3 text-sm">
                  <span className="truncate">{g.categoria}</span>
                  <span className="h-2 rounded-full bg-azul/70" style={{ width: `${(100 * g.monto) / maxGasto}%` }} />
                  <span className="text-right num">{dinero(g.monto)}</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <Panel titulo="Cotizaciones abiertas">
          <p className="font-display text-2xl font-semibold num">{dinero(d.cotizaciones_abiertas.monto)}</p>
          <p className="text-sm text-gris">{d.cotizaciones_abiertas.cantidad} cotización(es) en borrador o enviadas esperando respuesta del cliente.</p>
        </Panel>
      </div>
    </div>
  );
}

function ListaDocumentos({ tipo, abrirId }) {
  const avisar = useAviso();
  const [params, setParams] = useSearchParams();
  const [lista, setLista] = useState(null);
  const [filtro, setFiltro] = useState("");
  const [buscar, setBuscar] = useState("");
  const [detalle, setDetalle] = useState(null);
  const [editor, setEditor] = useState(null);
  const esCot = tipo === "cotizaciones";
  const cargar = useCallback(() => {
    const p = esCot ? { estado: filtro } : filtro === "vencidas" ? { vencidas: 1 } : filtro === "por_cobrar" ? { por_cobrar: 1 } : { estado: filtro };
    listarDocumentos(tipo, p).then(setLista).catch((e) => avisar(e.message, "rojo"));
  }, [tipo, filtro, esCot, avisar]);
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => { if (abrirId) obtenerDocumento(tipo, abrirId).then(setDetalle).catch(() => {}); }, [abrirId, tipo]);
  const cerrar = () => { setDetalle(null); params.delete("id"); setParams(params, { replace: true }); };
  useEffect(() => { if (params.get("nueva") === "1") { setEditor({}); params.delete("nueva"); setParams(params, { replace: true }); } }, [params, setParams]);
  const filtrada = useMemo(() => (lista || []).filter((d) => !buscar || `${d.numero} ${d.cliente_nombre} ${d.titulo} ${d.ncf || ""}`.toLowerCase().includes(buscar.toLowerCase())), [lista, buscar]);
  const opciones = esCot
    ? [["", "Todas"], ["BORRADOR,ENVIADA", "Abiertas"], ["APROBADA", "Aprobadas"], ["RECHAZADA", "Rechazadas"]]
    : [["", "Todas"], ["por_cobrar", "Por cobrar"], ["vencidas", "Vencidas"], ["BORRADOR", "Borradores"], ["PAGADA", "Pagadas"]];
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <select className="campo h-11 w-auto" value={filtro} onChange={(e) => setFiltro(e.target.value)} aria-label="Filtrar">
          {opciones.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
        </select>
        <div className="relative min-w-48 flex-1 md:max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" />
          <input className="campo h-11 pl-9" placeholder="Número, cliente o NCF" value={buscar} onChange={(e) => setBuscar(e.target.value)} aria-label="Buscar" />
        </div>
        <Boton icono={Plus} className="ml-auto" onClick={() => setEditor({})}>{esCot ? "Nueva cotización" : "Nueva factura"}</Boton>
      </div>
      {!lista ? <Cargando /> : filtrada.length === 0 ? <Vacio icono={FileText} titulo={esCot ? "Sin cotizaciones" : "Sin facturas"}>
        {esCot ? "Cotiza aquí, márcala aprobada cuando el cliente diga que sí y crea la orden de trabajo y la factura con un clic." : "Factura desde una orden entregada o una cotización aprobada, o crea una aquí."}</Vacio> : (
        <div className="overflow-x-auto rounded-xl border border-linea bg-white">
          <table className="tabla">
            <thead><tr><th>Número</th><th>Cliente</th><th className="hidden md:table-cell">Fecha</th>{!esCot && <th className="hidden md:table-cell">Vence</th>}<th className="text-right">Total</th>{!esCot && <th className="text-right">Saldo</th>}<th>Estado</th></tr></thead>
            <tbody>
              {filtrada.map((d) => (
                <tr key={d.id} className="cursor-pointer" onClick={() => setDetalle(d)}>
                  <td><p className="font-medium num">{d.numero}</p>{d.ncf && <p className="text-xs text-gris">{d.ncf}</p>}</td>
                  <td><p>{d.cliente_nombre}</p>{d.titulo && <p className="max-w-xs truncate text-xs text-gris">{d.titulo}</p>}</td>
                  <td className="hidden whitespace-nowrap text-sm md:table-cell">{fechaCorta(d.fecha)}</td>
                  {!esCot && <td className={cx("hidden whitespace-nowrap text-sm md:table-cell", d.vencida && "font-medium text-rojo")}>{d.vencimiento ? fechaCorta(d.vencimiento) : "—"}</td>}
                  <td className="whitespace-nowrap text-right num">{dinero(d.total, d.moneda)}</td>
                  {!esCot && <td className="whitespace-nowrap text-right num">{d.estado === "ANULADA" ? "—" : dinero(d.saldo, d.moneda)}</td>}
                  <td><EstadoDoc doc={d} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <DetalleDocumento tipo={tipo} doc={detalle} onCerrar={cerrar} onEditar={(d) => { setDetalle(null); setEditor(d); }}
        onCambio={(d) => { setDetalle(d && d.numero?.startsWith(esCot ? "COT" : "FAC") ? d : null); cargar(); }} />
      <EditorDocumento tipo={tipo} abierto={!!editor} inicial={editor} onCerrar={() => setEditor(null)}
        onGuardado={(d) => { setEditor(null); avisar(`${d.numero} guardada en borrador.`); cargar(); setDetalle(d); }} />
    </div>
  );
}

const CATEGORIAS = { MATERIALES: "Materiales e insumos", PERSONAL: "Personal / freelance", PAUTA: "Pauta publicitaria", TRANSPORTE: "Transporte y viáticos",
  EQUIPOS: "Equipos", SOFTWARE: "Software y servicios", ALQUILER: "Alquiler y servicios básicos", IMPUESTOS: "Impuestos", OTRO: "Otro" };

function Gastos() {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const [mes, setMes] = useState(mesActual());
  const [lista, setLista] = useState(null);
  const [form, setForm] = useState(null);
  const [archivo, setArchivo] = useState(null);
  const [proyectos, setProyectos] = useState([]);
  const [error, setError] = useState("");
  const cargar = useCallback(() => {
    const [a, m] = mes.split("-").map(Number);
    const fin = new Date(a, m, 0).getDate();
    listarDocumentos("gastos", { desde: `${mes}-01`, hasta: `${mes}-${fin}` }).then(setLista).catch((e) => avisar(e.message, "rojo"));
  }, [mes, avisar]);
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => { if (form) { setError(""); setArchivo(null); listarProyectos({ activos: 1 }).then(setProyectos).catch(() => {}); } }, [form]);
  const total = (lista || []).reduce((s, g) => s + Number(g.monto), 0);
  const guardar = async (e) => {
    e.preventDefault();
    if (!form.concepto?.trim() || !form.monto) return setError("Escribe el concepto y el monto.");
    try {
      await guardarGasto({ id: form.id, fecha: form.fecha, concepto: form.concepto.trim(), categoria: form.categoria, monto: form.monto, moneda: form.moneda || "DOP",
        proveedor: form.proveedor || "", proyecto: form.proyecto ? Number(form.proyecto) : null }, archivo);
      setForm(null); avisar("Gasto guardado."); cargar();
    } catch (err) { setError(err.message); }
  };
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <SelectorMes valor={mes} onCambio={setMes} />
        <p className="text-sm text-gris">Total: <span className="font-semibold text-tinta num">{dinero(total)}</span></p>
        <Boton icono={Plus} className="ml-auto" onClick={() => setForm({ fecha: hoyISO(), categoria: "MATERIALES", concepto: "", monto: "", proveedor: "", proyecto: "" })}>Nuevo gasto</Boton>
      </div>
      {!lista ? <Cargando /> : lista.length === 0 ? <Vacio icono={Wallet} titulo="Sin gastos este mes">Anota los gastos y conéctalos al proyecto o la orden: así se sabe cuánto deja cada trabajo.</Vacio> : (
        <div className="overflow-x-auto rounded-xl border border-linea bg-white">
          <table className="tabla">
            <thead><tr><th>Fecha</th><th>Concepto</th><th className="hidden md:table-cell">Categoría</th><th className="hidden md:table-cell">Proyecto</th><th className="text-right">Monto</th><th className="w-24" /></tr></thead>
            <tbody>
              {lista.map((g) => (
                <tr key={g.id}>
                  <td className="whitespace-nowrap text-sm">{fechaCorta(g.fecha)}</td>
                  <td><p className="font-medium">{g.concepto}</p>{g.proveedor && <p className="text-xs text-gris">{g.proveedor}</p>}</td>
                  <td className="hidden text-sm md:table-cell">{g.categoria_nombre}</td>
                  <td className="hidden text-sm md:table-cell">{g.proyecto_nombre || g.orden_numero || "—"}</td>
                  <td className="whitespace-nowrap text-right num">{dinero(g.monto, g.moneda)}</td>
                  <td className="whitespace-nowrap text-right">
                    {g.tiene_comprobante && <a href={`/api/finanzas/gastos/${g.id}/comprobante/`} target="_blank" rel="noopener" className="inline-flex rounded p-1.5 text-gris hover:text-azul" aria-label="Ver comprobante"><Paperclip className="size-4" /></a>}
                    <Boton variante="fantasma" tam="sm" icono={Pencil} aria-label="Editar" onClick={() => setForm({ ...g, proyecto: g.proyecto || "" })} />
                    <Boton variante="fantasma" tam="sm" icono={Trash2} aria-label="Borrar" className="text-rojo" onClick={async () => {
                      if (await confirmar({ titulo: "¿Borrar este gasto?", mensaje: g.concepto, boton: "Borrar", peligro: true })) { await eliminarDocumento("gastos", g.id); cargar(); }
                    }} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Modal abierto={!!form} onCerrar={() => setForm(null)} titulo={form?.id ? "Editar gasto" : "Nuevo gasto"} ancho="max-w-xl"
        pie={<><Boton variante="secundario" onClick={() => setForm(null)}>Cancelar</Boton><Boton type="submit" form="form-gasto">Guardar</Boton></>}>
        {form && (
          <form id="form-gasto" onSubmit={guardar} className="grid gap-4 sm:grid-cols-2">
            {error && <Alerta className="sm:col-span-2">{error}</Alerta>}
            <Campo etiqueta="Concepto" className="sm:col-span-2">{(id) => <input id={id} className="campo" value={form.concepto} onChange={(e) => setForm({ ...form, concepto: e.target.value })} maxLength={200} autoFocus />}</Campo>
            <Campo etiqueta="Monto">{(id) => <input id={id} type="number" min="0.01" step="any" className="campo" value={form.monto} onChange={(e) => setForm({ ...form, monto: e.target.value })} />}</Campo>
            <Campo etiqueta="Fecha">{(id) => <input id={id} type="date" className="campo" value={form.fecha} onChange={(e) => setForm({ ...form, fecha: e.target.value })} />}</Campo>
            <Campo etiqueta="Categoría">{(id) => <select id={id} className="campo" value={form.categoria} onChange={(e) => setForm({ ...form, categoria: e.target.value })}>{Object.entries(CATEGORIAS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>}</Campo>
            <Campo etiqueta="Proveedor">{(id) => <input id={id} className="campo" value={form.proveedor || ""} onChange={(e) => setForm({ ...form, proveedor: e.target.value })} maxLength={150} />}</Campo>
            <Campo etiqueta="Proyecto (opcional)" className="sm:col-span-2">{(id) => <select id={id} className="campo" value={form.proyecto || ""} onChange={(e) => setForm({ ...form, proyecto: e.target.value })}>
              <option value="">Gasto general</option>{proyectos.map((p) => <option key={p.id} value={p.id}>{p.codigo} · {p.nombre} ({p.cliente_nombre})</option>)}</select>}</Campo>
            <Campo etiqueta="Comprobante (foto o PDF, opcional)" className="sm:col-span-2">{(id) => <input id={id} type="file" accept="image/*,application/pdf" capture="environment" className="block text-sm" onChange={(e) => setArchivo(e.target.files?.[0] || null)} />}</Campo>
          </form>
        )}
      </Modal>
    </div>
  );
}

function Rentabilidad() {
  const [por, setPor] = useState("proyecto");
  const [desde, setDesde] = useState(`${hoyISO().slice(0, 4)}-01-01`);
  const [hasta, setHasta] = useState(hoyISO());
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { rentabilidad({ por, desde, hasta }).then(setD).catch((e) => setError(e.message)); }, [por, desde, hasta]);
  if (error) return <Alerta>{error}</Alerta>;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <Campo etiqueta="Ver por">{(id) => <select id={id} className="campo h-11 w-auto" value={por} onChange={(e) => setPor(e.target.value)}><option value="proyecto">Proyecto</option><option value="cliente">Cliente</option></select>}</Campo>
        <Campo etiqueta="Desde">{(id) => <input id={id} type="date" className="campo h-11" value={desde} onChange={(e) => setDesde(e.target.value)} />}</Campo>
        <Campo etiqueta="Hasta">{(id) => <input id={id} type="date" className="campo h-11" value={hasta} onChange={(e) => setHasta(e.target.value)} />}</Campo>
      </div>
      {!d ? <Cargando /> : d.filas.length === 0 ? <Vacio icono={Wallet} titulo="Sin datos en ese periodo">Aparece cuando hay facturas, gastos u horas conectadas a proyectos o clientes.</Vacio> : (
        <div className="overflow-x-auto rounded-xl border border-linea bg-white">
          <table className="tabla">
            <thead><tr><th>{por === "cliente" ? "Cliente" : "Proyecto"}</th><th className="text-right">Facturado</th><th className="text-right">Gastos</th><th className="text-right">Horas</th><th className="text-right">Costo horas</th><th className="text-right">Margen</th></tr></thead>
            <tbody>
              {d.filas.map((f) => (
                <tr key={f.id}>
                  <td className="font-medium"><Link className="hover:text-azul" to={por === "cliente" ? `/clientes/${f.id}` : `/proyectos/${f.id}`}>{f.nombre}</Link></td>
                  <td className="text-right num">{dinero(f.facturado)}</td>
                  <td className="text-right num">{dinero(f.gastos)}</td>
                  <td className="text-right num">{horas(f.horas * 60)}</td>
                  <td className="text-right num">{dinero(f.costo_horas)}</td>
                  <td className={cx("text-right font-semibold num", Number(f.margen) < 0 ? "text-rojo" : "text-verde")}>{dinero(f.margen)}{f.margen_pct != null && <span className="ml-1 text-xs font-normal text-gris">{f.margen_pct}%</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-sm text-gris">Facturado sin ITBIS. El costo de las horas usa el costo por hora de cada persona (se configura en Personas). Sin ese dato, la hora cuenta como cero.</p>
    </div>
  );
}

export default function Finanzas() {
  const avisar = useAviso();
  const [params, setParams] = useSearchParams();
  const ver = params.get("ver") || "resumen";
  const abrirId = params.get("id");
  const cambiar = (v) => { params.delete("id"); if (v === "resumen") params.delete("ver"); else params.set("ver", v); setParams(params, { replace: true }); };
  const facturar = async (o) => {
    try { const f = await facturarOrden(o.id); avisar(`Factura ${f.numero} creada en borrador. Revísala y emítela.`); setParams({ ver: "facturas", id: String(f.id) }); } catch (e) { avisar(e.message, "rojo"); }
  };
  return (
    <div>
      <Cabecera titulo="Finanzas" descripcion="Cotizaciones, facturas, cobros y gastos conectados a las órdenes y proyectos. La contabilidad formal y los comprobantes fiscales siguen en el sistema contable." />
      <Pestanas className="mb-5 max-w-3xl" valor={ver} onCambio={cambiar} opciones={[
        { valor: "resumen", etiqueta: "Resumen" }, { valor: "cotizaciones", etiqueta: "Cotizaciones" }, { valor: "facturas", etiqueta: "Facturas" },
        { valor: "gastos", etiqueta: "Gastos" }, { valor: "rentabilidad", etiqueta: "Rentabilidad" },
      ]} />
      {ver === "cotizaciones" ? <ListaDocumentos key="c" tipo="cotizaciones" abrirId={abrirId} />
        : ver === "facturas" ? <ListaDocumentos key="f" tipo="facturas" abrirId={abrirId} />
          : ver === "gastos" ? <Gastos /> : ver === "rentabilidad" ? <Rentabilidad /> : <Resumen onFacturar={facturar} />}
    </div>
  );
}
