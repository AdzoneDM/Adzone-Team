// Versión para imprimir o guardar como PDF de una cotización o factura (Ctrl+P → Guardar como PDF).
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Printer } from "lucide-react";
import { obtenerDocumento } from "@/lib/api";
import { EMPRESA } from "@/lib/empresa";
import { dinero, fechaCorta } from "@/lib/formato";
import Marca from "@/components/Marca";
import { Alerta, Boton, Cargando } from "@/components/ui";

export default function Imprimir() {
  const { tipo, id } = useParams();
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const esCot = tipo === "cotizaciones";
  useEffect(() => { obtenerDocumento(tipo, id).then(setD).catch((e) => setError(e.message)); }, [tipo, id]);
  useEffect(() => { if (d) document.title = `${d.numero} · ${d.cliente_nombre}`; }, [d]);
  if (error) return <div className="p-6"><Alerta>{error}</Alerta></div>;
  if (!d) return <Cargando />;
  return (
    <div className="min-h-dvh bg-fondo py-6 print:bg-white print:py-0">
      <div className="mx-auto mb-4 flex max-w-[210mm] justify-end px-4 print:hidden"><Boton icono={Printer} onClick={() => window.print()}>Imprimir o guardar PDF</Boton></div>
      <article className="mx-auto max-w-[210mm] bg-white p-10 text-[13px] text-tinta shadow-sm print:max-w-none print:p-0 print:shadow-none">
        <header className="flex items-start justify-between gap-6 border-b-4 border-amarillo pb-5">
          <div>
            <Marca oscuro={false} className="text-xl" />
            <p className="mt-2 font-medium">{EMPRESA.nombre}</p>
            <p className="text-gris">RNC {EMPRESA.rnc}</p>
            <p className="max-w-xs text-gris">{EMPRESA.direccion}</p>
          </div>
          <div className="text-right">
            <p className="font-display text-2xl font-semibold text-noche">{esCot ? "Cotización" : "Factura"}</p>
            <p className="text-lg font-semibold num">{d.numero}</p>
            {!esCot && d.ncf && <p>NCF: <span className="font-medium">{d.ncf}</span></p>}
            <p className="text-gris">Fecha: {fechaCorta(d.fecha)}</p>
            {esCot && d.valida_hasta && <p className="text-gris">Válida hasta: {fechaCorta(d.valida_hasta)}</p>}
            {!esCot && d.vencimiento && <p className="text-gris">Vence: {fechaCorta(d.vencimiento)}</p>}
          </div>
        </header>
        <section className="my-5">
          <p className="text-xs uppercase tracking-wide text-gris">Cliente</p>
          <p className="text-base font-semibold">{d.cliente_nombre}</p>
          {d.cliente_rnc && <p>RNC / cédula: {d.cliente_rnc}</p>}
          {d.titulo && <p className="mt-2 font-medium">{d.titulo}</p>}
        </section>
        <table className="w-full">
          <thead><tr className="bg-noche text-left text-white"><th className="px-3 py-2">Descripción</th><th className="px-3 text-right">Cant.</th><th className="px-3 text-right">Precio</th><th className="px-3 text-right">Importe</th></tr></thead>
          <tbody>{d.lineas.map((l, i) => (
            <tr key={i} className="border-b border-linea"><td className="px-3 py-2">{l.descripcion}{!l.aplica_itbis && " (exento de ITBIS)"}</td>
              <td className="px-3 text-right num">{Number(l.cantidad).toLocaleString("es-DO")}</td><td className="px-3 text-right num">{dinero(l.precio, d.moneda)}</td><td className="px-3 text-right num">{dinero(l.importe, d.moneda)}</td></tr>))}</tbody>
        </table>
        <dl className="ml-auto mt-4 w-72 space-y-1">
          <div className="flex justify-between"><dt>Subtotal</dt><dd className="num">{dinero(d.subtotal, d.moneda)}</dd></div>
          <div className="flex justify-between"><dt>ITBIS (18%)</dt><dd className="num">{dinero(d.itbis, d.moneda)}</dd></div>
          <div className="flex justify-between border-t-2 border-noche pt-1 text-base font-semibold"><dt>Total</dt><dd className="num">{dinero(d.total, d.moneda)}</dd></div>
          {!esCot && Number(d.pagado) > 0 && <><div className="flex justify-between"><dt>Pagado</dt><dd className="num">{dinero(d.pagado, d.moneda)}</dd></div>
            <div className="flex justify-between font-semibold"><dt>Saldo</dt><dd className="num">{dinero(d.saldo, d.moneda)}</dd></div></>}
        </dl>
        {esCot && d.condiciones && <section className="mt-6"><p className="font-semibold">Condiciones</p><p className="whitespace-pre-line">{d.condiciones}</p></section>}
        {d.notas && <section className="mt-4"><p className="font-semibold">Notas</p><p className="whitespace-pre-line">{d.notas}</p></section>}
        <footer className="mt-10 border-t border-linea pt-3 text-center text-xs text-gris">{EMPRESA.marca} · {EMPRESA.web}{!esCot && !d.ncf && " · Documento interno: el comprobante fiscal lo emite el sistema contable."}</footer>
      </article>
    </div>
  );
}
