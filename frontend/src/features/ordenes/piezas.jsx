// Piezas comunes de las órdenes de trabajo: estado, ícono del área, tarjeta y avance.
import { Clapperboard, Code, Headset, Landmark, Megaphone, Printer, Tv } from "lucide-react";
import { ESTADOS_ORDEN, PRIORIDADES_OT, fechaCorta, vencimiento } from "@/lib/formato";
import { cx } from "@/components/ui";

export const ICONOS = { printer: Printer, tv: Tv, headset: Headset, megaphone: Megaphone, clapperboard: Clapperboard, code: Code, landmark: Landmark };
export const ICONO_TIPO = { IMPRESION: Printer, ADZONE_TV: Tv, CALL_CENTER: Headset, MARKETING: Megaphone, AUDIOVISUAL: Clapperboard, DESARROLLO: Code, ADMINISTRATIVA: Landmark };

export const COLUMNAS = ["SOLICITADA", "APROBADA", "EN_PRODUCCION", "CONTROL_CALIDAD", "LISTA", "ENTREGADA", "EN_PAUSA"];

export const ESTILO_ESTADO = {
  SOLICITADA: { punto: "bg-[#8a94a8]", insignia: "bg-linea-suave text-tinta" },
  APROBADA: { punto: "bg-azul/50", insignia: "bg-azul/10 text-azul" },
  EN_PRODUCCION: { punto: "bg-azul", insignia: "bg-azul text-white" },
  CONTROL_CALIDAD: { punto: "bg-amarillo-600", insignia: "bg-amarillo-50 text-[#7a5000]" },
  LISTA: { punto: "bg-verde", insignia: "bg-verde-50 text-verde" },
  ENTREGADA: { punto: "bg-verde", insignia: "bg-verde text-white" },
  EN_PAUSA: { punto: "bg-gris/40", insignia: "bg-linea-suave text-gris" },
  CANCELADA: { punto: "bg-gris/30", insignia: "bg-linea-suave text-gris line-through" },
};

export function EstadoOrden({ estado, className }) {
  return <span className={cx("inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium", ESTILO_ESTADO[estado]?.insignia, className)}>{ESTADOS_ORDEN[estado]}</span>;
}

export function PrioridadOrden({ prioridad }) {
  if (prioridad === "NORMAL" || prioridad === "BAJA") return null;
  return <span className={cx("rounded-full px-2 py-0.5 text-xs font-semibold", prioridad === "URGENTE" ? "bg-rojo text-white" : "bg-rojo-50 text-[#a3170f]")}>{PRIORIDADES_OT[prioridad]}</span>;
}

export function TipoOrden({ orden, conNombre = true }) {
  const Icono = ICONO_TIPO[orden.tipo] || Printer;
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium" style={{ color: orden.color, backgroundColor: orden.color_fondo }}>
      <Icono className="size-3.5" aria-hidden />{conNombre && orden.tipo_nombre}
    </span>
  );
}

export function Plazo({ orden }) {
  if (orden.estado === "ENTREGADA") {
    return <span className={cx("text-sm", orden.a_tiempo === false ? "text-[#a86a00]" : "text-verde")}>
      {orden.a_tiempo === false ? "Entregada tarde" : "Entregada"} {fechaCorta(orden.fecha_entrega)}</span>;
  }
  if (orden.estado === "CANCELADA") return <span className="text-sm text-gris">Cancelada</span>;
  const fecha = orden.fecha_compromiso || orden.fecha_requerida;
  if (!fecha) return <span className="text-sm text-gris">Sin fecha</span>;
  if (orden.estado === "LISTA") return <span className="text-sm text-verde">Lista · {fechaCorta(fecha)}</span>;
  const v = vencimiento(fecha);
  return <span className={cx("text-sm", v.tono === "rojo" ? "font-medium text-rojo" : v.tono === "amarillo" ? "font-medium text-[#a86a00]" : "text-gris")}>
    {orden.fecha_compromiso ? v.texto : `Pedida para ${fechaCorta(fecha)}`}</span>;
}

export function AvanceOrden({ progreso }) {
  if (!progreso?.pasos) return null;
  const pct = Math.round((progreso.pasos_hechos / progreso.pasos) * 100);
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-gris" title={`${progreso.pasos_hechos} de ${progreso.pasos} pasos`}>
      <span className="h-1.5 w-14 overflow-hidden rounded-full bg-linea"><span className={cx("block h-full rounded-full", pct === 100 ? "bg-verde" : "bg-azul")} style={{ width: `${pct}%` }} /></span>
      <span className="num">{pct}%</span>
    </span>
  );
}

/** Tarjeta del tablero y de las listas del celular. */
export function TarjetaOrden({ orden, onAbrir, arrastrable, onArrastrar }) {
  return (
    <button type="button" onClick={() => onAbrir(orden)} draggable={arrastrable}
      onDragStart={(e) => { e.dataTransfer.setData("text/plain", String(orden.id)); e.dataTransfer.effectAllowed = "move"; onArrastrar?.(orden); }}
      className={cx("block w-full rounded-xl border bg-white p-3 text-left shadow-[0_1px_0_rgba(22,51,107,0.04)] transition hover:border-azul/40 hover:shadow-md",
        orden.vencida ? "border-rojo/40" : "border-linea", arrastrable && "cursor-grab active:cursor-grabbing")}>
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-gris num">{orden.numero}</span>
        <TipoOrden orden={orden} conNombre={false} />
      </div>
      <p className="line-clamp-2 text-[15px] font-medium leading-snug">{orden.titulo}</p>
      <p className="mt-0.5 truncate text-sm text-gris">{orden.cliente_nombre}</p>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
        <Plazo orden={orden} />
        <PrioridadOrden prioridad={orden.prioridad} />
        <AvanceOrden progreso={orden.progreso} />
      </div>
      {orden.responsable_nombre && (
        <p className="mt-2 truncate border-t border-linea-suave pt-2 text-xs text-gris">
          {orden.responsable_nombre}{orden.equipo_nombres?.length ? ` +${orden.equipo_nombres.length}` : ""}
        </p>
      )}
    </button>
  );
}
