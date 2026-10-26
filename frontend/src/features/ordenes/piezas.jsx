// Piezas comunes de las OT y las Órdenes de Área: estados, áreas, tarjetas, listas de verificación y campos de los formatos.
import {
  Check, Clapperboard, Code, Hammer, Headset, Landmark, Megaphone, Mic, Palette, Printer, Signpost, Tent, Truck,
} from "lucide-react";
import { ESTADOS_OA, ESTADOS_ORDEN, PRIORIDADES_OTM, dinero, fechaCorta, fechaHora, vencimiento } from "@/lib/formato";
import { Campo, cx } from "@/components/ui";

export const ICONOS_AREA = { palette: Palette, megaphone: Megaphone, clapperboard: Clapperboard, mic: Mic, printer: Printer, signpost: Signpost,
  hammer: Hammer, tent: Tent, code: Code, truck: Truck, headset: Headset, landmark: Landmark };
const ICONO_CODIGO = { DIS: Palette, MKT: Megaphone, AUD: Clapperboard, POD: Mic, IMP: Printer, LET: Signpost, FAB: Hammer, EVT: Tent,
  SOF: Code, INS: Truck, CCT: Headset, ADM: Landmark };
export const COLOR_AREA = {
  DIS: ["#7b3fa0", "#f3eafa"], MKT: ["#c2410c", "#fdeee5"], AUD: ["#b4235a", "#fce8ef"], POD: ["#0e7490", "#e3f5f9"],
  IMP: ["#1d4ed8", "#e6edfd"], LET: ["#a16207", "#fbf3dc"], FAB: ["#4d5b70", "#eceff3"], EVT: ["#15803d", "#e5f5ea"],
  SOF: ["#0f766e", "#e0f3f1"], INS: ["#334155", "#e9edf2"], CCT: ["#9333ea", "#f3e8fd"], ADM: ["#57534e", "#efedeb"],
};
export const NOMBRE_AREA = { DIS: "Diseño", MKT: "Marketing", AUD: "Audiovisual", POD: "Podcast · TV", IMP: "Impresión", LET: "Letreros",
  FAB: "Fabricación", EVT: "Eventos", SOF: "Software", INS: "Instalación", CCT: "Call Center", ADM: "Administración" };

export const COLUMNAS_OT = ["SOLICITADA", "DEVUELTA", "LIBERADA", "EN_PRODUCCION", "LISTA", "ENTREGADA", "EN_PAUSA"];
export const COLUMNAS_OA = ["EMITIDA", "RECIBIDA", "EN_EJECUCION", "EN_APROBACION", "TERMINADA"];

const ESTILO = {
  SOLICITADA: ["bg-[#8a94a8]", "bg-linea-suave text-tinta"], DEVUELTA: ["bg-rojo", "bg-rojo-50 text-[#a3170f]"],
  LIBERADA: ["bg-azul/50", "bg-azul/10 text-azul"], EN_PRODUCCION: ["bg-azul", "bg-azul text-white"],
  LISTA: ["bg-verde", "bg-verde-50 text-verde"], ENTREGADA: ["bg-verde", "bg-verde text-white"], CERRADA: ["bg-noche", "bg-noche text-white"],
  EN_PAUSA: ["bg-gris/40", "bg-linea-suave text-gris"], CANCELADA: ["bg-gris/30", "bg-linea-suave text-gris line-through"],
  EMITIDA: ["bg-[#8a94a8]", "bg-linea-suave text-tinta"], RECHAZADA: ["bg-rojo", "bg-rojo-50 text-[#a3170f]"], RECIBIDA: ["bg-azul/50", "bg-azul/10 text-azul"],
  EN_EJECUCION: ["bg-azul", "bg-azul text-white"], EN_APROBACION: ["bg-amarillo-600", "bg-amarillo-50 text-[#7a5000]"],
  TERMINADA: ["bg-verde", "bg-verde-50 text-verde"],
};
export const puntoEstado = (e) => ESTILO[e]?.[0];

export function EstadoOrden({ estado, className }) {
  return <span className={cx("inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium", ESTILO[estado]?.[1], className)}>{ESTADOS_ORDEN[estado] || estado}</span>;
}
export function EstadoOA({ estado, className }) {
  return <span className={cx("inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium", ESTILO[estado]?.[1], className)}>{ESTADOS_OA[estado] || estado}</span>;
}
export function PrioridadOrden({ prioridad }) {
  if (!prioridad || prioridad === "N") return null;
  return <span className={cx("rounded-full px-2 py-0.5 text-xs font-semibold", prioridad === "E" ? "bg-rojo text-white" : "bg-rojo-50 text-[#a3170f]")}>{PRIORIDADES_OTM[prioridad]}</span>;
}
export function AreaChip({ area, nombre, conNombre = true, className }) {
  const Icono = ICONO_CODIGO[area] || Printer;
  const [color, fondo] = COLOR_AREA[area] || ["#334155", "#eef1f5"];
  return (
    <span className={cx("inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium", className)} style={{ color, backgroundColor: fondo }} title={nombre || NOMBRE_AREA[area]}>
      <Icono className="size-3.5" aria-hidden />{conNombre && (nombre || NOMBRE_AREA[area])}
    </span>
  );
}

export function Plazo({ orden }) {
  if (["ENTREGADA", "CERRADA"].includes(orden.estado)) {
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

/** Las áreas de la OT en su orden, con su estado: el «camino» del trabajo. */
export function CaminoAreas({ areas, compacto }) {
  if (!areas?.length) return null;
  return (
    <ol className="flex flex-wrap items-center gap-1" aria-label="Áreas">
      {areas.map((a, i) => (
        <li key={a.id ?? i} className="flex items-center gap-1">
          {i > 0 && <span className="text-gris/60" aria-hidden>›</span>}
          <span className={cx("inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[11px] font-medium",
            a.estado === "TERMINADA" ? "border-verde/40 bg-verde-50 text-verde" : ["RECIBIDA", "EN_EJECUCION", "EN_APROBACION"].includes(a.estado)
              ? "border-azul/40 bg-azul/10 text-azul" : a.estado === "RECHAZADA" ? "border-rojo/40 bg-rojo-50 text-[#a3170f]" : "border-linea bg-white text-gris")}
            title={`${a.numero || ""} · ${ESTADOS_OA[a.estado] || "Planificada"}`}>
            {a.estado === "TERMINADA" && <Check className="size-3" aria-hidden />}{a.area}{!compacto && a.vencida && <span className="text-rojo">!</span>}
          </span>
        </li>
      ))}
    </ol>
  );
}

/** Tarjeta de OT para el tablero, el inicio y los clientes. */
export function TarjetaOrden({ orden, onAbrir }) {
  const areas = orden.areas_resumen?.length ? orden.areas_resumen : (orden.plan_areas || []).map((p) => ({ area: p.area }));
  return (
    <button type="button" onClick={() => onAbrir(orden)}
      className={cx("block w-full rounded-xl border bg-white p-3 text-left shadow-[0_1px_0_rgba(22,51,107,0.04)] transition hover:border-azul/40 hover:shadow-md",
        orden.vencida ? "border-rojo/40" : "border-linea")}>
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-gris num">{orden.codigo || orden.numero}</span>
        <PrioridadOrden prioridad={orden.prioridad} />
      </div>
      <p className="line-clamp-2 text-[15px] font-medium leading-snug">{orden.titulo}</p>
      <p className="mt-0.5 truncate text-sm text-gris">{orden.cliente_nombre}</p>
      <div className="mt-2"><CaminoAreas areas={areas} /></div>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1"><Plazo orden={orden} />
        {orden.g0_faltan?.length > 0 && ["SOLICITADA", "DEVUELTA"].includes(orden.estado) && <span className="text-xs text-[#a86a00]">G0: faltan {orden.g0_faltan.length}</span>}
      </div>
    </button>
  );
}

/** Tarjeta de Orden de Área para el tablero por área. */
export function TarjetaOA({ oa, onAbrir }) {
  return (
    <button type="button" onClick={() => onAbrir(oa)}
      className={cx("block w-full rounded-xl border bg-white p-3 text-left transition hover:border-azul/40 hover:shadow-md", oa.vencida ? "border-rojo/40" : "border-linea")}>
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-gris num">{oa.numero}</span>
        <AreaChip area={oa.area} conNombre={false} />
      </div>
      <p className="line-clamp-2 text-[15px] font-medium leading-snug">{oa.que_produce}</p>
      <p className="mt-0.5 truncate text-sm text-gris">{oa.cliente_nombre}</p>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
        {oa.fecha_entrega_interna && <span className={cx(oa.vencida ? "font-medium text-rojo" : "text-gris")}>{vencimiento(oa.fecha_entrega_interna).texto}</span>}
        <PrioridadOrden prioridad={oa.prioridad} />
        {oa.tarea && <span className="text-xs text-gris num">{oa.tarea.pasos_hechos}/{oa.tarea.pasos} etapas</span>}
        {oa.traspaso_pendiente && <span className="text-xs font-medium text-[#a86a00]">Traspaso por firmar</span>}
        {oa.bloqueada_por?.length > 0 && <span className="text-xs text-gris">Espera {oa.bloqueada_por.join(", ")}</span>}
      </div>
      {oa.responsable_nombre && <p className="mt-2 truncate border-t border-linea-suave pt-2 text-xs text-gris">{oa.responsable_nombre}</p>}
    </button>
  );
}

/** Lista de verificación de una compuerta (G0, G1, G3, G2…). Sin todas las casillas, no se avanza. */
export function Checklist({ items, valor = {}, onCambio, soloLectura, titulo, ayuda }) {
  const marcadas = items.filter((t) => valor[t]).length;
  return (
    <fieldset>
      {titulo && <legend className="mb-1 flex w-full items-center justify-between gap-2 font-semibold"><span>{titulo}</span>
        <span className={cx("text-sm font-medium num", marcadas === items.length ? "text-verde" : "text-gris")}>{marcadas}/{items.length}</span></legend>}
      {ayuda && <p className="mb-2 text-sm text-gris">{ayuda}</p>}
      <ul className="space-y-1">
        {items.map((t) => (
          <li key={t}>
            <label className={cx("flex items-start gap-2.5 rounded-lg px-2 py-1.5 text-[15px]", !soloLectura && "cursor-pointer hover:bg-fondo")}>
              <input type="checkbox" className="mt-1 size-4 shrink-0 accent-azul" checked={!!valor[t]} disabled={soloLectura}
                onChange={(e) => onCambio?.({ ...valor, [t]: e.target.checked })} />
              <span className={cx(valor[t] ? "text-tinta" : "text-tinta/80")}>{t}</span>
            </label>
          </li>
        ))}
      </ul>
      {!soloLectura && onCambio && (
        <button type="button" className="mt-1 text-sm font-medium text-azul hover:underline"
          onClick={() => onCambio(Object.fromEntries(items.map((t) => [t, marcadas !== items.length])))}>
          {marcadas === items.length ? "Desmarcar todas" : "Marcar todas"}
        </button>
      )}
    </fieldset>
  );
}

/** Campo de un formato (texto, número, opción, múltiple, sí/no, fecha, tabla). */
export function CampoFormato({ campo, valor, onCambio, error }) {
  const props = { className: "campo", value: valor ?? "", onChange: (e) => onCambio(e.target.value) };
  const ancho = campo.ancho === "completo" || ["largo", "multiple", "tabla"].includes(campo.tipo) ? "sm:col-span-2" : "";
  const etiqueta = campo.etiqueta + (campo.requerido ? "" : " (opcional)");
  if (campo.tipo === "multiple") {
    const lista = Array.isArray(valor) ? valor : [];
    return (
      <fieldset className={ancho}>
        <legend className="etiqueta">{etiqueta}</legend>
        <div className="flex flex-wrap gap-2">
          {campo.opciones.map((o) => {
            const on = lista.includes(o);
            return <button key={o} type="button" aria-pressed={on} onClick={() => onCambio(on ? lista.filter((x) => x !== o) : [...lista, o])}
              className={cx("min-h-10 rounded-full border px-3.5 text-sm font-medium", on ? "border-azul bg-azul text-white" : "border-linea bg-white hover:border-azul")}>{o}</button>;
          })}
        </div>
        {error && <p className="mt-1 text-[13px] text-rojo">{error}</p>}
      </fieldset>
    );
  }
  if (campo.tipo === "sino") {
    return (
      <label className={cx("flex min-h-11 items-center gap-2.5 self-end rounded-lg border border-linea px-3 text-[15px]", ancho)}>
        <input type="checkbox" checked={!!valor} onChange={(e) => onCambio(e.target.checked)} className="size-4 accent-azul" /> {campo.etiqueta}
      </label>
    );
  }
  if (campo.tipo === "tabla") {
    const filas = Array.isArray(valor) && valor.length ? valor : [{}];
    const poner = (i, clave, v) => onCambio(filas.map((f, j) => (j === i ? { ...f, [clave]: v } : f)));
    return (
      <fieldset className={ancho}>
        <legend className="etiqueta">{etiqueta}</legend>
        <div className="overflow-x-auto rounded-lg border border-linea">
          <table className="w-full min-w-[520px] text-sm">
            <thead className="bg-fondo text-left text-xs text-gris"><tr>{campo.columnas.map((c) => <th key={c.clave} className="px-2 py-1.5 font-medium">{c.etiqueta}</th>)}<th className="w-8" /></tr></thead>
            <tbody>{filas.map((f, i) => (
              <tr key={i} className="border-t border-linea-suave">
                {campo.columnas.map((c) => (
                  <td key={c.clave} className="p-1"><input aria-label={`${c.etiqueta} fila ${i + 1}`} className="h-9 w-full rounded-md border border-linea px-2"
                    type={c.tipo === "numero" ? "number" : c.tipo === "fecha" ? "date" : "text"} step="any" value={f[c.clave] ?? ""} onChange={(e) => poner(i, c.clave, e.target.value)} /></td>
                ))}
                <td className="p-1 text-center"><button type="button" aria-label={`Quitar fila ${i + 1}`} className="text-gris hover:text-rojo" onClick={() => onCambio(filas.filter((_, j) => j !== i))}>×</button></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
        <button type="button" className="mt-1.5 text-sm font-medium text-azul hover:underline" onClick={() => onCambio([...filas, {}])}>+ Agregar fila</button>
        {error && <p className="mt-1 text-[13px] text-rojo">{error}</p>}
      </fieldset>
    );
  }
  return (
    <Campo etiqueta={etiqueta} ayuda={campo.ayuda} error={error} className={ancho}>
      {(id) => campo.tipo === "opcion" ? (
        <select id={id} {...props}><option value="">Elige…</option>{campo.opciones.map((o) => <option key={o}>{o}</option>)}</select>
      ) : campo.tipo === "largo" ? <textarea id={id} rows={3} {...props} />
        : campo.tipo === "fecha" ? <input id={id} type="date" {...props} />
          : campo.tipo === "fechahora" ? <input id={id} type="datetime-local" {...props} />
            : ["numero", "dinero"].includes(campo.tipo) ? <input id={id} type="number" inputMode="decimal" min={0} step="any" {...props} />
              : <input id={id} {...props} maxLength={300} />}
    </Campo>
  );
}

export function valorCampo(campo, v) {
  if (v === undefined || v === null || v === "" || (Array.isArray(v) && !v.length)) return null;
  if (campo.tipo === "tabla") return v.map((f) => campo.columnas.map((c) => f[c.clave]).filter((x) => x !== undefined && x !== "").join(" · ")).join("\n");
  if (campo.tipo === "multiple") return v.join(", ");
  if (campo.tipo === "sino") return v ? "Sí" : "No";
  if (campo.tipo === "fecha") return fechaCorta(v);
  if (campo.tipo === "fechahora") return fechaHora(v);
  if (campo.tipo === "dinero") return dinero(v);
  if (campo.tipo === "numero") return Number(v).toLocaleString("es-DO");
  return v;
}

/** Ficha de datos de un formato (solo lectura). */
export function FichaFormato({ campos, datos }) {
  const filas = campos.map((c) => ({ c, v: valorCampo(c, datos?.[c.clave]) })).filter((x) => x.v !== null);
  if (!filas.length) return <p className="text-sm text-gris">Sin especificación todavía.</p>;
  return (
    <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
      {filas.map(({ c, v }) => <div key={c.clave} className={["largo", "tabla"].includes(c.tipo) ? "sm:col-span-2" : ""}><dt className="text-sm text-gris">{c.etiqueta}</dt><dd className="whitespace-pre-line font-medium">{v}</dd></div>)}
    </dl>
  );
}

export function Dato({ etiqueta, children, className }) {
  if (children === null || children === undefined || children === "" || children === false) return null;
  return <div className={className}><dt className="text-sm text-gris">{etiqueta}</dt><dd className="font-medium">{children}</dd></div>;
}

/** E1 → E7 de la OT. */
const PASOS_E = [["E1", "Liberada"], ["E2", "Recibida en área"], ["E3", "En ejecución"], ["E4", "Aprobación del cliente"], ["E5", "Terminada"], ["E6", "Entregada"], ["E7", "Cerrada"]];
export function etapaActual(orden, areas = []) {
  if (orden.estado === "CERRADA") return 7;
  if (orden.estado === "ENTREGADA") return 6;
  if (orden.estado === "LISTA") return 5;
  const abiertas = areas.filter((a) => !["TERMINADA", "CANCELADA"].includes(a.estado));
  if (orden.estado === "EN_PRODUCCION") {
    if (abiertas.some((a) => a.estado === "EN_APROBACION")) return 4;
    if (abiertas.some((a) => a.estado === "EN_EJECUCION")) return 3;
    if (abiertas.some((a) => a.estado === "RECIBIDA")) return 2;
    return 1;
  }
  if (orden.estado === "LIBERADA") return 1;
  return 0;
}
export function EtapasE({ orden, areas }) {
  const actual = etapaActual(orden, areas);
  return (
    <ol className="grid grid-cols-7 gap-1" aria-label="Estados E1 a E7">
      {PASOS_E.map(([e, texto], i) => {
        const n = i + 1;
        return (
          <li key={e} className="min-w-0" aria-current={n === actual ? "step" : undefined}>
            <span className={cx("block h-1.5 rounded-full", n < actual ? "bg-azul" : n === actual ? "bg-amarillo" : "bg-linea")} />
            <span className={cx("mt-1.5 block truncate text-[11px] md:text-xs", n === actual ? "font-semibold text-tinta" : "text-gris")}>
              <span className="num">{e}</span><span className="hidden md:inline"> · {texto}</span></span>
          </li>
        );
      })}
    </ol>
  );
}

/** Ventana de anticipación del contenido: ideal 15 días, seguro 10, emergencia 7 hábiles. */
export function Anticipacion({ a, className }) {
  if (!a) return null;
  const estilo = { ideal: "bg-verde-50 text-verde", seguro: "bg-azul/10 text-noche", emergencia: "bg-amarillo-50 text-[#7a5000]", insuficiente: "bg-rojo-50 text-[#a3170f]" }[a.nivel];
  const titulo = { ideal: "Ideal", seguro: "Seguro", emergencia: "Emergencia", insuficiente: "Por debajo del mínimo" }[a.nivel];
  return (
    <p className={cx("rounded-lg px-3 py-2 text-sm", estilo, className)}>
      <span className="font-semibold">Anticipación del contenido: {titulo}</span> · {a.dias} días ({a.habiles} hábiles). {a.texto}
    </p>
  );
}
