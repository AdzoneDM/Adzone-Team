// Integración con Cashflow: estado de la conexión, prueba, sincronización de pagos y bitácora de cada llamada.
import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, PlugZap, RefreshCw, XCircle } from "lucide-react";
import { estadoCashflow, probarCashflow, sincronizarCashflow } from "@/lib/api";
import { fechaHora } from "@/lib/formato";
import { Alerta, Boton, Cargando, Panel, cx, useAviso } from "@/components/ui";

export default function Cashflow() {
  const avisar = useAviso();
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(null);
  const cargar = useCallback(() => estadoCashflow().then(setD).catch((e) => setError(e.message)), []);
  useEffect(() => { cargar(); }, [cargar]);
  if (error) return <Alerta>{error}</Alerta>;
  if (!d) return <Cargando />;
  const real = d.modo === "real";
  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Panel titulo="Conexión">
          <div className="flex items-start gap-3">
            <span className={cx("flex size-11 shrink-0 items-center justify-center rounded-xl", real ? "bg-verde-50 text-verde" : "bg-amarillo-50 text-[#7a5000]")}><PlugZap className="size-5" /></span>
            <div className="min-w-0">
              <p className="font-semibold">{real ? "Conectado a Cashflow" : "Modo prueba (simulador)"}</p>
              <p className="text-sm text-gris">{real ? d.url : "Sin API key configurada: las facturas reciben un NCF de prueba y nada sale de la plataforma."}</p>
              {d.ultima_llamada && <p className="mt-1 text-sm text-gris">Última llamada {fechaHora(d.ultima_llamada)}{d.errores_hoy > 0 && <span className="text-rojo"> · {d.errores_hoy} error(es) hoy</span>}</p>}
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Boton variante="secundario" icono={PlugZap} cargando={ocupado === "probar"} onClick={async () => {
              setOcupado("probar");
              try { const r = await probarCashflow(); avisar(`Conexión correcta: ${r.empresa}.`); } catch (e) { avisar(e.message, "rojo"); }
              setOcupado(null); cargar();
            }}>Probar conexión</Boton>
            <Boton icono={RefreshCw} cargando={ocupado === "sinc"} onClick={async () => {
              setOcupado("sinc");
              try { const r = await sincronizarCashflow(); avisar(`${r.facturas} factura(s) revisada(s), ${r.pagos} pago(s) nuevo(s)${r.errores ? `, ${r.errores} con error` : ""}.`); } catch (e) { avisar(e.message, "rojo"); }
              setOcupado(null); cargar();
            }}>Traer pagos ahora</Boton>
          </div>
        </Panel>
        <Panel titulo="Qué hace la integración">
          <ul className="space-y-1.5 text-[15px]">
            <li>• <span className="font-medium">Clientes:</span> se buscan en Cashflow por RNC y, si no existen, se crean.</li>
            <li>• <span className="font-medium">Cotizaciones:</span> «Enviar a Cashflow» desde la cotización.</li>
            <li>• <span className="font-medium">Factura fiscal:</span> «Emitir en Cashflow» crea la factura allá, que asigna el NCF / e-CF (crédito fiscal con RNC, consumo sin él).</li>
            <li>• <span className="font-medium">Pagos y saldo:</span> cada día (y con «Traer pagos ahora») se leen los cobros; si cubren el anticipo de una OT, la casilla G0 se marca sola.</li>
          </ul>
          {!real && <p className="mt-3 text-sm text-gris">Para conectar: el administrador del servidor pone <code className="rounded bg-fondo px-1">CASHFLOW_API_KEY</code> en el archivo <code className="rounded bg-fondo px-1">.env</code> (nunca en el chat ni en GitHub) y reinicia la aplicación.</p>}
        </Panel>
      </div>
      <Panel titulo="Bitácora de llamadas" cuerpo="p-0">
        {d.bitacora.length === 0 ? <p className="p-5 text-sm text-gris">Todavía no hay llamadas.</p> : (
          <ul className="divide-y divide-linea-suave">
            {d.bitacora.map((b) => (
              <li key={b.id} className="flex flex-wrap items-center gap-x-3 gap-y-0.5 px-5 py-2.5 text-sm">
                {b.exito ? <CheckCircle2 className="size-4 text-verde" aria-label="Correcta" /> : <XCircle className="size-4 text-rojo" aria-label="Con error" />}
                <span className="font-medium">{b.operacion.replace(/_/g, " ")}</span>
                <span className="text-gris">{b.objeto}</span>
                {b.modo !== "real" && <span className="rounded bg-amarillo-50 px-1.5 text-xs text-[#7a5000]">prueba</span>}
                <span className="ml-auto text-gris">{b.usuario} · {fechaHora(b.fecha)}</span>
                {!b.exito && <span className="w-full text-[#a3170f]">{b.detalle}</span>}
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
