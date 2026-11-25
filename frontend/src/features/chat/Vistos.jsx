// «¿Quién lo vio?»: por cada mensaje, quién lo vio (con fecha y hora), quién abrió el archivo y quién todavía no lo ha visto.
import { useEffect, useState } from "react";
import { Check, CheckCheck, Eye, FileCheck2 } from "lucide-react";
import { chatVistos } from "@/lib/api";
import { Alerta, Avatar, Cargando, Modal, cx } from "@/components/ui";

const cuando = (iso) => (iso ? new Date(iso).toLocaleString("es-DO", { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) : "");

function Persona({ p }) {
  const detalle = p.estado === "ABIERTO" ? `Vio ${p.sin_hora ? "(antes del registro detallado)" : cuando(p.visto)} · abrió el archivo ${cuando(p.abierto)}`
    : p.estado === "VISTO" ? (p.sin_hora ? "Lo vio (antes del registro detallado, sin hora exacta)" : `Visto ${cuando(p.visto)}`)
      : p.estado === "ENTREGADO" ? `Le llegó ${cuando(p.entregado)} · todavía no lo abre`
        : "No le ha llegado: no ha abierto la plataforma";
  const Icono = p.estado === "ABIERTO" ? FileCheck2 : p.estado === "VISTO" ? CheckCheck : p.estado === "ENTREGADO" ? CheckCheck : Check;
  return (
    <li className="flex items-center gap-3 py-2">
      <Avatar nombre={p.nombre} tam="sm" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{p.nombre}</p>
        <p className="truncate text-xs text-gris">{[p.puesto, p.departamento].filter(Boolean).join(" · ")}</p>
        <p className={cx("text-xs", p.estado === "VISTO" || p.estado === "ABIERTO" ? "text-azul" : "text-gris")}>{detalle}</p>
      </div>
      <Icono className={cx("size-4 shrink-0", p.estado === "VISTO" || p.estado === "ABIERTO" ? "text-azul" : "text-gris")} aria-hidden />
    </li>
  );
}

export function ModalVistos({ mensaje, onCerrar }) {
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!mensaje) return;
    setD(null); setError("");
    chatVistos(mensaje.id).then(setD).catch((e) => setError(e.message));
  }, [mensaje]);
  if (!mensaje) return null;
  return (
    <Modal abierto onCerrar={onCerrar} titulo="¿Quién lo vio?" ancho="md:max-w-md"
      descripcion={mensaje.texto ? `«${mensaje.texto.slice(0, 80)}${mensaje.texto.length > 80 ? "…" : ""}»` : mensaje.archivo?.nombre}>
      {error ? <Alerta>{error}</Alerta> : !d ? <Cargando /> : (
        <div className="space-y-4">
          <div className="grid grid-cols-4 gap-2 text-center">
            {[["Integrantes", d.integrantes], ["Visto", d.vistos.length], ["Pendiente", d.pendientes.length], ["Lectura", `${d.porcentaje} %`]].map(([e, v]) => (
              <div key={e} className="rounded-lg bg-fondo px-1 py-2"><p className="num text-lg font-semibold">{v}</p><p className="text-[11px] text-gris">{e}</p></div>
            ))}
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-linea" role="progressbar" aria-valuenow={d.porcentaje} aria-valuemin={0} aria-valuemax={100} aria-label="Porcentaje de lectura">
            <div className="h-full rounded-full bg-azul" style={{ width: `${d.porcentaje}%` }} />
          </div>
          {d.tiene_archivo && <p className="text-xs text-gris">Abrieron el archivo: <b className="text-tinta">{d.abiertos}</b> de {d.integrantes}.</p>}
          <section>
            <h3 className="flex items-center gap-1.5 text-sm font-semibold text-azul"><CheckCheck className="size-4" aria-hidden />Visto ({d.vistos.length})</h3>
            {d.vistos.length ? <ul className="divide-y divide-linea">{d.vistos.map((p) => <Persona key={p.id} p={p} />)}</ul> : <p className="py-2 text-sm text-gris">Nadie lo ha visto todavía.</p>}
          </section>
          <section>
            <h3 className="flex items-center gap-1.5 text-sm font-semibold text-gris"><Check className="size-4" aria-hidden />Pendiente ({d.pendientes.length})</h3>
            {d.pendientes.length ? <ul className="divide-y divide-linea">{d.pendientes.map((p) => <Persona key={p.id} p={p} />)}</ul> : <p className="py-2 text-sm text-gris">Todos lo vieron.</p>}
          </section>
        </div>
      )}
    </Modal>
  );
}

/** Botón del ojo junto al mensaje. */
export function BotonVistos({ onClick, className }) {
  return (
    <button type="button" onClick={onClick} aria-label="Ver quién lo vio" title="Ver quién lo vio"
      className={cx("rounded p-1 text-gris transition-opacity hover:bg-azul/10 hover:text-azul focus-visible:opacity-100", className)}>
      <Eye className="size-3.5" aria-hidden />
    </button>
  );
}
