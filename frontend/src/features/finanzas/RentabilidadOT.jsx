// Rentabilidad real por OT, cliente y departamento: ingreso (facturado o vendido) − mano de obra − materiales − gastos, en RD$.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, Download, Plus, Trash2, Wallet } from "lucide-react";
import { borrarTasa, guardarTasa, rentabilidadOrden, rentabilidadOrdenes, tasasCambio, urlRentabilidadCsv } from "@/lib/api";
import { dinero, hoyISO } from "@/lib/formato";
import { Alerta, Boton, Campo, Cargando, Insignia, Modal, Panel, Pestanas, Vacio, cx, useAviso } from "@/components/ui";

const pct = (v) => (v == null ? "—" : `${Number(v).toLocaleString("es-DO", { maximumFractionDigits: 1 })} %`);

function Margen({ valor, minimo }) {
  if (valor == null) return <span className="text-gris">—</span>;
  return <span className={cx("font-semibold num", valor < 0 ? "text-rojo" : valor < minimo ? "text-[#a86a00]" : "text-verde")}>{pct(valor)}</span>;
}

export default function RentabilidadOT() {
  const [desde, setDesde] = useState(`${hoyISO().slice(0, 7)}-01`);
  const [hasta, setHasta] = useState(hoyISO());
  const [ver, setVer] = useState("ordenes");
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [abierta, setAbierta] = useState(null);
  useEffect(() => { setD(null); setError(""); rentabilidadOrdenes({ desde, hasta }).then(setD).catch((e) => setError(e.message)); }, [desde, hasta]);
  const t = d?.totales;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <Campo etiqueta="Desde">{(id) => <input id={id} type="date" className="campo h-11" value={desde} onChange={(e) => setDesde(e.target.value)} />}</Campo>
        <Campo etiqueta="Hasta">{(id) => <input id={id} type="date" className="campo h-11" value={hasta} onChange={(e) => setHasta(e.target.value)} />}</Campo>
        <a href={urlRentabilidadCsv({ desde, hasta })} className="inline-flex h-11 items-center gap-2 rounded-lg border border-linea bg-white px-4 text-sm font-medium hover:border-azul"><Download className="size-4" />Excel</a>
      </div>
      {error ? <Alerta>{error}</Alerta> : !d ? <Cargando /> : (
        <>
          {d.montos_sin_tasa > 0 && <Alerta tono="amarillo">{d.montos_sin_tasa} monto(s) en dólares quedaron fuera porque no hay tasa de cambio. Agrégala abajo.</Alerta>}
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            {[["Ingreso", dinero(t.ingreso), `${t.ordenes} OT`], ["Costo total", dinero(t.costo), `Mano de obra ${dinero(t.mano_obra)}`],
              ["Utilidad bruta", dinero(t.utilidad), null], ["Margen", <Margen key="m" valor={t.margen} minimo={d.margen_minimo} />, `Mínimo ${d.margen_minimo} %`],
              ["Materiales", dinero(t.materiales), "Almacén y compras"], ["OT bajo el margen", t.en_alerta, t.horas_sin_costo ? `${t.horas_sin_costo} h sin costo por hora` : null]].map(([a, b, c]) => (
              <div key={a} className="rounded-xl border border-linea bg-white p-4"><p className="text-sm text-gris">{a}</p><p className="mt-1 font-display text-2xl font-semibold num">{b}</p>{c && <p className="text-xs text-gris">{c}</p>}</div>
            ))}
          </div>
          <Pestanas className="!flex" opciones={[{ valor: "ordenes", etiqueta: "Por OT", cuenta: d.ordenes.length }, { valor: "clientes", etiqueta: "Por cliente", cuenta: d.clientes.length },
            { valor: "departamentos", etiqueta: "Por departamento", cuenta: d.departamentos.length }]} valor={ver} onCambio={setVer} />
          {ver === "ordenes" ? (!d.ordenes.length ? <Vacio icono={Wallet} titulo="Sin OT con movimiento en el período">Aparecen las OT con horas, vales, gastos, facturas o entregas en esas fechas.</Vacio> : (
            <div className="overflow-x-auto rounded-xl border border-linea bg-white"><table className="tabla">
              <thead><tr><th>OT</th><th className="text-right">Ingreso</th><th className="text-right">Mano de obra</th><th className="text-right">Materiales</th>
                <th className="text-right">Otros costos</th><th className="text-right">Utilidad</th><th className="text-right">Margen</th><th className="text-right">Horas</th></tr></thead>
              <tbody>{d.ordenes.map((o) => (
                <tr key={o.id} className="cursor-pointer hover:bg-fondo" onClick={() => setAbierta(o.id)}>
                  <td className="min-w-56"><span className="font-medium">{o.numero}</span> <span className="text-sm">{o.titulo}</span>{o.alerta && <AlertTriangle className="ml-1 inline size-4 text-rojo" />}
                    <span className="block text-xs text-gris">{o.cliente} · {o.departamento} · {o.estado}</span></td>
                  <td className="text-right num">{dinero(o.ingreso)}<span className="block text-xs text-gris">{o.base === "FACTURADO" ? "facturado" : "vendido"}</span></td>
                  <td className="text-right num">{dinero(o.mano_obra)}</td><td className="text-right num">{dinero(o.materiales)}</td>
                  <td className="text-right num">{dinero(o.equipos + o.externos + o.transporte + o.otros)}</td>
                  <td className={cx("text-right font-semibold num", o.utilidad < 0 && "text-rojo")}>{dinero(o.utilidad)}</td>
                  <td className="text-right"><Margen valor={o.margen} minimo={d.margen_minimo} /></td><td className="text-right num">{o.horas}</td>
                </tr>))}</tbody>
            </table></div>
          )) : (
            <div className="overflow-x-auto rounded-xl border border-linea bg-white"><table className="tabla">
              <thead><tr><th>{ver === "clientes" ? "Cliente" : "Departamento"}</th><th className="text-right">OT</th><th className="text-right">Ingreso</th><th className="text-right">Costo</th>
                <th className="text-right">Mano de obra</th><th className="text-right">Utilidad</th><th className="text-right">Margen</th><th className="text-right">Horas</th></tr></thead>
              <tbody>{d[ver].map((g) => (
                <tr key={g.id}><td className="font-medium">{ver === "clientes" ? <Link to={`/clientes/${g.id}`} className="hover:text-azul">{g.nombre}</Link> : g.nombre}</td>
                  <td className="text-right num">{g.ordenes}</td><td className="text-right num">{dinero(g.ingreso)}</td><td className="text-right num">{dinero(g.costo)}</td>
                  <td className="text-right num">{dinero(g.mano_obra)}</td><td className={cx("text-right font-semibold num", g.utilidad < 0 && "text-rojo")}>{dinero(g.utilidad)}</td>
                  <td className="text-right"><Margen valor={g.margen} minimo={d.margen_minimo} /></td><td className="text-right num">{g.horas}</td></tr>))}</tbody>
            </table></div>
          )}
          <p className="text-sm text-gris">Ingreso: lo facturado sin ITBIS, o lo vendido si la OT aún no se factura. Costo: horas del cronómetro × costo por hora de cada persona, materiales despachados por almacén y gastos registrados en la OT. Todo en RD$.</p>
        </>
      )}
      <Tasas />
      {abierta && <DetalleOT id={abierta} onCerrar={() => setAbierta(null)} />}
    </div>
  );
}

function DetalleOT({ id, onCerrar }) {
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { rentabilidadOrden(id).then(setD).catch((e) => setError(e.message)); }, [id]);
  return (
    <Modal abierto onCerrar={onCerrar} ancho="max-w-3xl" titulo={d ? `${d.numero} · ${d.titulo}` : "Rentabilidad de la OT"} descripcion={d?.cliente}>
      {error ? <Alerta>{error}</Alerta> : !d ? <Cargando /> : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[["Vendido", d.vendido], ["Facturado", d.facturado], ["Costo", d.costo], ["Utilidad", d.utilidad]].map(([a, v]) => (
              <div key={a} className="rounded-lg bg-fondo p-3"><p className="text-xs text-gris">{a}</p><p className={cx("font-semibold num", a === "Utilidad" && v < 0 && "text-rojo")}>{dinero(v)}</p></div>))}
          </div>
          <table className="tabla"><tbody>
            {[["Mano de obra", d.mano_obra], ["Materiales", d.materiales], ["Equipos", d.equipos], ["Freelance y pauta", d.externos], ["Transporte", d.transporte], ["Otros", d.otros]].map(([a, v]) => (
              <tr key={a}><td>{a}</td><td className="text-right num">{dinero(v)}</td><td className="w-24 text-right text-xs text-gris">{d.costo ? pct((v / d.costo) * 100) : "—"}</td></tr>))}
            <tr className="font-semibold"><td>Margen</td><td className="text-right">{pct(d.margen)}</td><td /></tr>
          </tbody></table>
          {d.retrabajo > 0 && <p className="text-sm text-[#a86a00]">Retrabajo estimado por solicitudes de cambio: {dinero(d.retrabajo)}.</p>}
          {d.personas.length > 0 && <Panel titulo="Mano de obra" cuerpo="p-0"><ul className="divide-y divide-linea-suave">{d.personas.map((p) => (
            <li key={p.nombre} className="flex justify-between px-4 py-2 text-sm"><span>{p.nombre}</span><span className="num">{p.horas} h · {dinero(p.costo)}</span></li>))}</ul></Panel>}
          {(d.vales.length > 0 || d.gastos.length > 0) && <Panel titulo="Materiales y gastos" cuerpo="p-0"><ul className="divide-y divide-linea-suave">
            {d.vales.map((v) => <li key={v.numero} className="flex justify-between px-4 py-2 text-sm"><span>Vale {v.numero} · {v.estado}</span><span className="num">{dinero(v.costo)}</span></li>)}
            {d.gastos.map((g, i) => <li key={i} className="flex justify-between px-4 py-2 text-sm"><span>{g.concepto} · {g.categoria}</span><span className="num">{g.moneda === "USD" ? `US$ ${g.monto} = ` : ""}{dinero(g.en_dop)}</span></li>)}
          </ul></Panel>}
          {d.facturas.length > 0 && <Panel titulo="Facturas" cuerpo="p-0"><ul className="divide-y divide-linea-suave">{d.facturas.map((f) => (
            <li key={f.numero} className="flex justify-between px-4 py-2 text-sm"><span>{f.numero} · {f.estado}</span><span className="num">{f.moneda === "USD" ? `US$ ${f.subtotal} = ` : ""}{dinero(f.en_dop)}</span></li>))}</ul></Panel>}
        </div>
      )}
    </Modal>
  );
}

function Tasas() {
  const avisar = useAviso();
  const [lista, setLista] = useState(null);
  const [nueva, setNueva] = useState(null);
  const [error, setError] = useState("");
  const cargar = () => tasasCambio().then(setLista).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);
  const guardar = async () => {
    setError("");
    try { await guardarTasa(nueva); setNueva(null); avisar("Tasa guardada."); cargar(); } catch (e) { setError(e.message); }
  };
  return (
    <Panel titulo="Tasa de cambio (RD$ por US$ 1)" accion={<Boton tam="sm" variante="secundario" icono={Plus} onClick={() => setNueva({ fecha: hoyISO(), usd_dop: "", fuente: "Banco Central" })}>Tasa</Boton>}>
      {error && <Alerta className="mb-3">{error}</Alerta>}
      {!lista ? <Cargando /> : !lista.length ? <p className="text-sm text-gris">Sin tasas: las facturas y gastos en dólares no se pueden convertir. Agrega la del Banco Central.</p> : (
        <ul className="flex flex-wrap gap-2">{lista.slice(0, 12).map((t) => (
          <li key={t.id}><Insignia>{t.fecha} · RD$ {Number(t.usd_dop).toLocaleString("es-DO", { maximumFractionDigits: 4 })}
            <button type="button" aria-label="Borrar tasa" className="ml-1 text-gris hover:text-rojo" onClick={async () => { await borrarTasa(t.id); cargar(); }}><Trash2 className="size-3" /></button></Insignia></li>))}</ul>
      )}
      {nueva && (
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <Campo etiqueta="Fecha">{(id) => <input id={id} type="date" className="campo h-10" value={nueva.fecha} onChange={(e) => setNueva({ ...nueva, fecha: e.target.value })} />}</Campo>
          <Campo etiqueta="RD$ por US$ 1">{(id) => <input id={id} type="number" step="0.0001" min="1" className="campo h-10 w-32" value={nueva.usd_dop} onChange={(e) => setNueva({ ...nueva, usd_dop: e.target.value })} />}</Campo>
          <Campo etiqueta="Fuente">{(id) => <input id={id} className="campo h-10 w-40" value={nueva.fuente} onChange={(e) => setNueva({ ...nueva, fuente: e.target.value })} />}</Campo>
          <Boton onClick={guardar}>Guardar</Boton>
        </div>
      )}
    </Panel>
  );
}
