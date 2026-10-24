// Piezas comunes de la interfaz: mismas formas, colores y palabras en todas las pantallas.
import { createContext, useCallback, useContext, useEffect, useId, useRef, useState } from "react";
import { X, Star, ChevronLeft, ChevronRight, LoaderCircle, CircleAlert, CircleCheck, Info } from "lucide-react";
import { ESTADOS, PRIORIDADES, iniciales, mesActual, nombreMes } from "@/lib/formato";

export const cx = (...c) => c.filter(Boolean).join(" ");

// ---------------------------------------------------------------- Botones
const VARIANTES = {
  primario: "bg-azul text-white hover:bg-noche disabled:bg-azul/50",
  acento: "bg-amarillo text-tinta hover:bg-amarillo-600 disabled:bg-amarillo/50",
  secundario: "bg-white text-tinta border border-linea hover:border-azul/40 hover:bg-fondo disabled:text-gris",
  peligro: "bg-white text-rojo border border-rojo/30 hover:bg-rojo-50",
  fantasma: "text-azul hover:bg-azul/5",
};

export function Boton({ variante = "primario", tam = "md", icono: Icono, cargando, className, children, ...props }) {
  return (
    <button
      type="button"
      {...props}
      disabled={props.disabled || cargando}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:cursor-not-allowed",
        tam === "sm" ? "h-9 px-3 text-sm" : tam === "lg" ? "h-12 px-5 text-base" : "h-11 px-4 text-[15px]",
        VARIANTES[variante],
        className
      )}
    >
      {cargando ? <LoaderCircle className="size-4 animate-spin" aria-hidden /> : Icono && <Icono className="size-4 shrink-0" aria-hidden />}
      {children}
    </button>
  );
}

// ---------------------------------------------------------------- Insignias
const TONOS = {
  neutro: "bg-linea-suave text-gris",
  azul: "bg-azul/10 text-azul",
  amarillo: "bg-amarillo-50 text-[#7a5000]",
  verde: "bg-verde-50 text-verde",
  rojo: "bg-rojo-50 text-[#a3170f]",
  noche: "bg-noche text-white",
};

export function Insignia({ tono = "neutro", className, children }) {
  return <span className={cx("inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium", TONOS[tono], className)}>{children}</span>;
}

const TONO_ESTADO = { PENDIENTE: "neutro", EN_PROGRESO: "azul", EN_REVISION: "amarillo", COMPLETADA: "verde", CANCELADA: "neutro" };
export const EstadoTarea = ({ estado }) => <Insignia tono={TONO_ESTADO[estado]}>{ESTADOS[estado] || estado}</Insignia>;

const TONO_PRIORIDAD = { ALTA: "rojo", MEDIA: "amarillo", BAJA: "neutro" };
export const PrioridadTarea = ({ prioridad }) => <Insignia tono={TONO_PRIORIDAD[prioridad]}>{PRIORIDADES[prioridad]}</Insignia>;

// ---------------------------------------------------------------- Superficies
export function Panel({ titulo, accion, className, cuerpo = "p-5", children }) {
  return (
    <section className={cx("rounded-xl border border-linea bg-white", className)}>
      {(titulo || accion) && (
        <header className="flex items-center justify-between gap-3 border-b border-linea-suave px-5 py-3.5">
          {titulo && <h2 className="text-[17px] font-semibold">{titulo}</h2>}
          {accion}
        </header>
      )}
      <div className={cuerpo}>{children}</div>
    </section>
  );
}

export function Cabecera({ titulo, descripcion, children }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-[26px] font-semibold leading-tight md:text-3xl">{titulo}</h1>
        {descripcion && <p className="mt-1 max-w-[70ch] text-gris">{descripcion}</p>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </header>
  );
}

export function Vacio({ icono: Icono, titulo, children, accion }) {
  return (
    <div className="flex flex-col items-center rounded-xl border border-dashed border-linea bg-white px-6 py-10 text-center">
      {Icono && <Icono className="mb-3 size-8 text-azul/60" aria-hidden />}
      <p className="font-medium text-tinta">{titulo}</p>
      {children && <p className="mt-1 max-w-md text-sm text-gris">{children}</p>}
      {accion && <div className="mt-4">{accion}</div>}
    </div>
  );
}

export const Cargando = ({ texto = "Cargando…" }) => (
  <div className="flex items-center justify-center gap-2 py-16 text-gris" role="status">
    <LoaderCircle className="size-5 animate-spin" aria-hidden /> {texto}
  </div>
);

export function Alerta({ tono = "rojo", children, className }) {
  const Icono = tono === "rojo" ? CircleAlert : tono === "verde" ? CircleCheck : Info;
  const estilos = { rojo: "bg-rojo-50 text-[#7a1610]", amarillo: "bg-amarillo-50 text-[#5c3d00]", azul: "bg-azul/8 text-noche", verde: "bg-verde-50 text-verde" };
  return (
    <div className={cx("flex items-start gap-2.5 rounded-lg px-4 py-3 text-sm", estilos[tono], className)} role={tono === "rojo" ? "alert" : "status"}>
      <Icono className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="min-w-0">{children}</div>
    </div>
  );
}

export function Avatar({ nombre, tam = "md", className }) {
  const t = tam === "sm" ? "size-8 text-xs" : tam === "lg" ? "size-12 text-base" : "size-10 text-sm";
  return (
    <span className={cx("inline-flex shrink-0 items-center justify-center rounded-full bg-azul/10 font-semibold text-azul", t, className)} aria-hidden>
      {iniciales(nombre)}
    </span>
  );
}

// ---------------------------------------------------------------- Formularios
export function Campo({ etiqueta, ayuda, error, children, className }) {
  const id = useId();
  const hijo = typeof children === "function" ? children(id) : children;
  return (
    <div className={className}>
      {etiqueta && <label htmlFor={id} className="etiqueta">{etiqueta}</label>}
      {hijo}
      {error ? <p className="mt-1 text-[13px] text-rojo">{error}</p> : ayuda && <p className="ayuda">{ayuda}</p>}
    </div>
  );
}

// ---------------------------------------------------------------- Ventanas
export function Modal({ abierto, onCerrar, titulo, descripcion, ancho = "max-w-lg", children, pie }) {
  const ref = useRef(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (abierto && !d.open) d.showModal();
    if (!abierto && d.open) d.close();
  }, [abierto]);
  return (
    <dialog
      ref={ref}
      onCancel={(e) => { e.preventDefault(); onCerrar?.(); }}
      onClick={(e) => { if (e.target === ref.current) onCerrar?.(); }}
      className={cx(
        "m-0 mt-auto w-full max-w-none rounded-t-2xl bg-white p-0 text-tinta backdrop:bg-noche-900/50 md:m-auto md:rounded-2xl",
        ancho, "max-h-[92dvh]"
      )}
    >
      {abierto && (
        <div className="flex max-h-[92dvh] flex-col">
          <header className="flex items-start justify-between gap-4 border-b border-linea-suave px-5 py-4">
            <div className="min-w-0">
              <h2 className="text-xl font-semibold">{titulo}</h2>
              {descripcion && <p className="mt-0.5 text-sm text-gris">{descripcion}</p>}
            </div>
            <button type="button" onClick={onCerrar} className="-mr-2 rounded-lg p-2 text-gris hover:bg-fondo" aria-label="Cerrar">
              <X className="size-5" />
            </button>
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 py-4">{children}</div>
          {pie && <footer className="flex flex-wrap justify-end gap-2 border-t border-linea-suave px-5 py-3.5 pb-[max(0.875rem,env(safe-area-inset-bottom))]">{pie}</footer>}
        </div>
      )}
    </dialog>
  );
}

// Confirmación con texto propio (en vez de window.confirm)
const ConfirmarCtx = createContext(null);
export function ConfirmarProvider({ children }) {
  const [estado, setEstado] = useState(null);
  const confirmar = useCallback((opciones) => new Promise((resolver) => setEstado({ ...opciones, resolver })), []);
  const cerrar = (valor) => { estado?.resolver(valor); setEstado(null); };
  return (
    <ConfirmarCtx.Provider value={confirmar}>
      {children}
      <Modal abierto={!!estado} onCerrar={() => cerrar(false)} titulo={estado?.titulo} ancho="max-w-md"
        pie={<>
          <Boton variante="secundario" onClick={() => cerrar(false)}>Volver</Boton>
          <Boton variante={estado?.peligro ? "peligro" : "primario"} onClick={() => cerrar(true)}>{estado?.boton || "Confirmar"}</Boton>
        </>}>
        <p className="text-[15px] text-gris">{estado?.mensaje}</p>
      </Modal>
    </ConfirmarCtx.Provider>
  );
}
export const useConfirmar = () => useContext(ConfirmarCtx);

// Avisos breves abajo a la derecha
const AvisoCtx = createContext(null);
export function AvisosProvider({ children }) {
  const [lista, setLista] = useState([]);
  const avisar = useCallback((texto, tono = "verde") => {
    const id = Math.random();
    setLista((l) => [...l, { id, texto, tono }]);
    setTimeout(() => setLista((l) => l.filter((a) => a.id !== id)), tono === "rojo" ? 8000 : 4500);
  }, []);
  return (
    <AvisoCtx.Provider value={avisar}>
      {children}
      <div className="pointer-events-none fixed inset-x-3 bottom-20 z-[60] flex flex-col items-end gap-2 md:bottom-6 md:right-6 md:left-auto" aria-live="polite">
        {lista.map((a) => (
          <div key={a.id} className={cx("pointer-events-auto flex max-w-sm items-start gap-2 rounded-xl px-4 py-3 text-sm font-medium shadow-lg",
            a.tono === "rojo" ? "bg-[#7a1610] text-white" : "bg-noche text-white")}>
            {a.tono === "rojo" ? <CircleAlert className="mt-0.5 size-4 shrink-0" /> : <CircleCheck className="mt-0.5 size-4 shrink-0 text-amarillo" />}
            {a.texto}
          </div>
        ))}
      </div>
    </AvisoCtx.Provider>
  );
}
export const useAviso = () => useContext(AvisoCtx);

// ---------------------------------------------------------------- Pestañas
export function Pestanas({ opciones, valor, onCambio, className }) {
  return (
    <div role="tablist" className={cx("flex gap-1 overflow-x-auto rounded-xl border border-linea bg-white p-1 [scrollbar-width:none]", className)}>
      {opciones.map((o) => (
        <button key={o.valor} role="tab" type="button" aria-selected={valor === o.valor} onClick={() => onCambio(o.valor)}
          className={cx("flex min-h-10 flex-1 items-center justify-center gap-2 whitespace-nowrap rounded-lg px-3 text-sm font-medium transition-colors",
            valor === o.valor ? "bg-azul text-white" : "text-gris hover:bg-fondo hover:text-tinta")}>
          {o.etiqueta}
          {o.cuenta != null && <span className={cx("rounded-full px-1.5 text-xs num", valor === o.valor ? "bg-white/20" : "bg-linea-suave")}>{o.cuenta}</span>}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- Mes
export function SelectorMes({ valor, onCambio, hastaActual = true }) {
  const mover = (delta) => {
    const [a, m] = valor.split("-").map(Number);
    const f = new Date(a, m - 1 + delta, 1);
    onCambio(`${f.getFullYear()}-${String(f.getMonth() + 1).padStart(2, "0")}`);
  };
  const enActual = valor >= mesActual();
  return (
    <div className="inline-flex h-11 items-center rounded-lg border border-linea bg-white">
      <button type="button" onClick={() => mover(-1)} className="flex h-full items-center px-2.5 text-gris hover:text-azul" aria-label="Mes anterior"><ChevronLeft className="size-4" /></button>
      <span className="min-w-[8.5rem] text-center text-sm font-medium first-letter:uppercase">{nombreMes(valor)}</span>
      <button type="button" onClick={() => mover(1)} disabled={hastaActual && enActual} className="flex h-full items-center px-2.5 text-gris hover:text-azul disabled:opacity-30" aria-label="Mes siguiente"><ChevronRight className="size-4" /></button>
    </div>
  );
}

// ---------------------------------------------------------------- Estrellas
export const ETIQUETAS_CALIDAD = ["", "Muy por debajo", "Por debajo", "Cumple", "Bueno", "Excelente"];

export function EntradaEstrellas({ valor, onCambio, nombre }) {
  return (
    <fieldset>
      <legend className="etiqueta">Calidad del trabajo</legend>
      <div className="flex items-center gap-1">
        {[1, 2, 3, 4, 5].map((n) => (
          <label key={n} className="cursor-pointer rounded-md p-1.5 has-[:focus-visible]:outline has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-amarillo" title={ETIQUETAS_CALIDAD[n]}>
            <input type="radio" name={nombre} value={n} checked={valor === n} onChange={() => onCambio(n)} className="sr-only" />
            <Star className={cx("size-7 transition-colors", n <= (valor || 0) ? "fill-amarillo text-amarillo" : "text-linea")} aria-hidden />
            <span className="sr-only">{n} · {ETIQUETAS_CALIDAD[n]}</span>
          </label>
        ))}
        <span className="ml-2 text-sm font-medium text-gris">{valor ? ETIQUETAS_CALIDAD[valor] : "Sin calificar"}</span>
      </div>
    </fieldset>
  );
}

export function Estrellas({ valor }) {
  if (!valor) return <span className="text-gris">—</span>;
  return (
    <span className="inline-flex items-center gap-0.5" title={`${valor} de 5 · ${ETIQUETAS_CALIDAD[valor]}`}>
      {[1, 2, 3, 4, 5].map((n) => <Star key={n} className={cx("size-3.5", n <= valor ? "fill-amarillo text-amarillo" : "text-linea")} aria-hidden />)}
      <span className="sr-only">{valor} de 5</span>
    </span>
  );
}

// ---------------------------------------------------------------- Tira del mes
/**
 * El avance del mes hecho de tareas: un segmento por tarea.
 * Amarillo = validada · contorno = en revisión · rojo = venció sin entregar · gris = pendiente.
 */
export function TiraMes({ validadas = 0, revision = 0, vencidas = 0, pendientes = 0, oscuro = false, className }) {
  const total = validadas + revision + vencidas + pendientes;
  if (!total) return <div className={cx("h-3 rounded-full", oscuro ? "bg-white/15" : "bg-linea-suave", className)} />;
  const segmentos = [
    ...Array(validadas).fill("validada"), ...Array(revision).fill("revision"),
    ...Array(vencidas).fill("vencida"), ...Array(pendientes).fill("pendiente"),
  ];
  const estilo = {
    validada: "bg-amarillo",
    revision: oscuro ? "border-2 border-amarillo/80" : "border-2 border-amarillo-600",
    vencida: "bg-rojo",
    pendiente: oscuro ? "bg-white/20" : "bg-linea",
  };
  const muchos = total > 40;
  return (
    <div className={cx("flex h-3", muchos ? "gap-px" : "gap-1", className)} role="img"
      aria-label={`${validadas} validadas, ${revision} en revisión, ${vencidas} vencidas y ${pendientes} pendientes`}>
      {segmentos.map((s, i) => <span key={i} className={cx("min-w-[3px] flex-1 rounded-[3px]", estilo[s])} />)}
    </div>
  );
}

export function LeyendaTira({ oscuro }) {
  const t = oscuro ? "text-white/70" : "text-gris";
  return (
    <ul className={cx("flex flex-wrap gap-x-4 gap-y-1 text-xs", t)}>
      <li className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-amarillo" />Validada</li>
      <li className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm border-2 border-amarillo-600" />En revisión</li>
      <li className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-rojo" />Vencida</li>
      <li className="flex items-center gap-1.5"><span className={cx("size-2.5 rounded-sm", oscuro ? "bg-white/20" : "bg-linea")} />Pendiente</li>
    </ul>
  );
}

/** Puntaje 0-100 con color según el rango. */
export function Puntaje({ valor, className }) {
  if (valor == null) return <span className={cx("text-gris", className)}>—</span>;
  const color = valor >= 90 ? "text-verde" : valor >= 70 ? "text-noche" : valor >= 50 ? "text-[#a86a00]" : "text-rojo";
  return <span className={cx("font-display font-semibold num", color, className)}>{Number(valor).toLocaleString("es-DO", { maximumFractionDigits: 1 })}</span>;
}

export function Barra({ valor, className }) {
  const v = Math.max(0, Math.min(100, valor || 0));
  const color = v >= 90 ? "bg-verde" : v >= 70 ? "bg-azul" : v >= 50 ? "bg-amarillo-600" : "bg-rojo";
  return <div className={cx("h-1.5 w-full overflow-hidden rounded-full bg-linea-suave", className)}><div className={cx("h-full rounded-full", color)} style={{ width: `${v}%` }} /></div>;
}

