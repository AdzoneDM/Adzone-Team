import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ClipboardList, Mail, MapPin, Pencil, Phone, Plus } from "lucide-react";
import { obtenerCliente, resumenCliente } from "@/lib/api";
import { dinero, fechaCorta } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import { Alerta, Boton, Cargando, Panel, Vacio, cx, useAviso } from "@/components/ui";
import FormOrden from "@/features/ordenes/FormOrden";
import { TarjetaOrden } from "@/features/ordenes/piezas";
import { AvanceProyecto, EstadoProyecto, FormProyecto } from "@/features/proyectos/piezas";
import { FormCliente } from "./Clientes";

export default function ClienteDetalle() {
  const { id } = useParams();
  const { usuario } = useSesion();
  const avisar = useAviso();
  const navigate = useNavigate();
  const [c, setC] = useState(null);
  const [r, setR] = useState(null);
  const [error, setError] = useState("");
  const [modal, setModal] = useState(null);
  const cargar = useCallback(() => Promise.all([obtenerCliente(id), resumenCliente(id)]).then(([a, b]) => { setC(a); setR(b); }).catch((e) => setError(e.message)), [id]);
  useEffect(() => { cargar(); }, [cargar]);
  if (error) return <Alerta>{error}</Alerta>;
  if (!c || !r) return <Cargando />;
  const abiertas = r.ordenes.filter((o) => !["ENTREGADA", "CANCELADA"].includes(o.estado));
  const cerradas = r.ordenes.filter((o) => ["ENTREGADA", "CANCELADA"].includes(o.estado));
  const puedeEditar = usuario.gestiona || usuario.es_finanzas;
  return (
    <div>
      <Link to="/clientes" className="mb-3 inline-flex items-center gap-1.5 text-sm font-medium text-azul hover:underline"><ArrowLeft className="size-4" />Clientes</Link>
      <div className="grid gap-5 lg:grid-cols-[340px_minmax(0,1fr)]">
        <aside className="space-y-5">
          <Panel>
            <p className="text-sm text-gris">{c.tipo_nombre}{c.rnc ? ` · RNC ${c.rnc}` : ""}</p>
            <h1 className="mt-1 text-2xl font-semibold leading-tight">{c.nombre}</h1>
            {!c.activo && <p className="mt-1 text-sm font-medium text-rojo">Inactivo</p>}
            <ul className="mt-4 space-y-2 text-[15px]">
              {c.contacto && <li className="font-medium">{c.contacto}</li>}
              {c.telefono && <li><a href={`tel:${c.telefono}`} className="flex items-center gap-2 hover:text-azul"><Phone className="size-4 text-gris" />{c.telefono}</a></li>}
              {c.correo && <li><a href={`mailto:${c.correo}`} className="flex items-center gap-2 break-all hover:text-azul"><Mail className="size-4 shrink-0 text-gris" />{c.correo}</a></li>}
              {c.direccion && <li className="flex items-start gap-2"><MapPin className="mt-0.5 size-4 shrink-0 text-gris" />{c.direccion}</li>}
            </ul>
            {c.notas && <p className="mt-3 whitespace-pre-line border-t border-linea-suave pt-3 text-sm text-gris">{c.notas}</p>}
            <div className="mt-4 flex flex-wrap gap-2">
              <Boton tam="sm" icono={Plus} onClick={() => setModal("orden")}>Orden</Boton>
              {puedeEditar && <Boton tam="sm" variante="secundario" icono={Plus} onClick={() => setModal("proyecto")}>Proyecto</Boton>}
              {puedeEditar && <Boton tam="sm" variante="secundario" icono={Pencil} onClick={() => setModal("editar")}>Editar</Boton>}
            </div>
          </Panel>
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
        </aside>
        <div className="space-y-5">
          <Panel titulo={`Proyectos (${r.proyectos.length})`} cuerpo="p-0">
            {r.proyectos.length === 0 ? <p className="p-5 text-sm text-gris">Sin proyectos.</p> : (
              <ul className="divide-y divide-linea-suave">{r.proyectos.map((p) => (
                <li key={p.id}><Link to={`/proyectos/${p.id}`} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-5 py-3 hover:bg-fondo">
                  <span className="min-w-0 flex-1"><span className="block font-medium">{p.nombre}</span><span className="text-xs text-gris">{p.codigo}{p.fecha_fin ? ` · entrega ${fechaCorta(p.fecha_fin)}` : ""}</span></span>
                  <AvanceProyecto progreso={p.progreso} /><EstadoProyecto estado={p.estado} /></Link></li>))}</ul>
            )}
          </Panel>
          <section>
            <h2 className="mb-3 text-[17px] font-semibold">Órdenes abiertas ({abiertas.length})</h2>
            {abiertas.length === 0 ? <Vacio icono={ClipboardList} titulo="Nada en producción para este cliente" accion={<Boton icono={Plus} onClick={() => setModal("orden")}>Nueva orden</Boton>} />
              : <ul className="grid gap-3 md:grid-cols-2">{abiertas.map((o) => <li key={o.id}><TarjetaOrden orden={o} onAbrir={() => navigate(`/ordenes/${o.id}`)} /></li>)}</ul>}
          </section>
          {cerradas.length > 0 && (
            <Panel titulo="Historial de órdenes" cuerpo="p-0">
              <ul className="divide-y divide-linea-suave">{cerradas.map((o) => (
                <li key={o.id}><Link to={`/ordenes/${o.id}`} className="flex justify-between gap-3 px-5 py-2.5 text-sm hover:bg-fondo">
                  <span className="truncate"><span className="text-gris num">{o.numero}</span> · {o.titulo}</span>
                  <span className="shrink-0 text-gris">{o.estado === "CANCELADA" ? "Cancelada" : `Entregada ${fechaCorta(o.fecha_entrega)}`}</span></Link></li>))}</ul>
            </Panel>
          )}
        </div>
      </div>
      <FormCliente abierto={modal === "editar"} inicial={c} onCerrar={() => setModal(null)} onGuardado={() => { setModal(null); avisar("Cliente actualizado."); cargar(); }} />
      <FormOrden abierto={modal === "orden"} inicial={{ cliente: c.id }} onCerrar={() => setModal(null)} onGuardada={(o) => { setModal(null); avisar(`${o.numero} pedida.`); navigate(`/ordenes/${o.id}`); }} />
      <FormProyecto abierto={modal === "proyecto"} inicial={{ cliente: c.id }} onCerrar={() => setModal(null)} onGuardado={(p) => { setModal(null); navigate(`/proyectos/${p.id}`); }} />
    </div>
  );
}
