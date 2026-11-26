// Organigrama de la empresa: gráfico jerárquico con color por departamento, zoom, búsqueda, contraer/expandir,
// vista de lista (celular y lectores de pantalla) y versión para imprimir.
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { BadgeCheck, ChevronDown, Maximize2, Minus, Network, Plus, Printer, Search, X } from "lucide-react";
import { aprobarOrganigrama, organigrama } from "@/lib/api";
import { Cambios, Matriz } from "./MatrizOrganigrama";
import { plural } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import { Alerta, Boton, Campo, Cargando, Modal, Pestanas, Vacio, cx, useAviso } from "@/components/ui";

// ── Color por departamento: paleta fija y sobria, estable entre visitas ─────────────────────────────────────────────
const PALETA = [
  { acento: "#224b9a", suave: "#e8eefb" }, { acento: "#0d7a5f", suave: "#e3f5ee" }, { acento: "#b7791f", suave: "#fff4d6" },
  { acento: "#c2410c", suave: "#fdeee3" }, { acento: "#6d4ac8", suave: "#f0ebfb" }, { acento: "#0e7490", suave: "#e0f3f8" },
  { acento: "#be185d", suave: "#fce8f1" }, { acento: "#3b5bdb", suave: "#e7ecfd" }, { acento: "#4d7c0f", suave: "#eef6dc" }, { acento: "#475569", suave: "#eef1f6" },
];
const colorDe = (id) => PALETA[Math.abs(Number(id) || 0) % PALETA.length];

const normal = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const iniciales = (n = "") => n.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]).join("").toUpperCase();

/** Personas, puestos y vacantes de un nodo y todo lo que cuelga de él. */
function contar(nodo) {
  return nodo.hijos.reduce((a, h) => { const c = contar(h); return { personas: a.personas + c.personas, puestos: a.puestos + c.puestos }; },
    { personas: nodo.personas.length, puestos: 1 });
}
const aplanar = (nodos) => nodos.flatMap((n) => [n, ...aplanar(n.hijos)]);
const coincideNodo = (n, t) => !t || [n.nombre, n.departamento, ...n.personas.map((p) => p.nombre)].some((x) => normal(x).includes(t));
const ramaCoincide = (n, t) => coincideNodo(n, t) || n.hijos.some((h) => ramaCoincide(h, t));

// ── Tarjeta de un puesto ────────────────────────────────────────────────────────────────────────────────────────────
function Personas({ lista, color }) {
  const [todas, setTodas] = useState(false);
  if (!lista.length) return <p className="mt-2 inline-flex rounded-md border border-dashed border-linea px-2 py-0.5 text-xs text-gris">Vacante</p>;
  const mostrar = todas ? lista : lista.slice(0, 4);
  return (
    <ul className="mt-2 space-y-1.5">
      {mostrar.map((p) => (
        <li key={p.id} className="flex items-center gap-2 text-[13px] text-tinta">
          <span className="flex size-6 shrink-0 items-center justify-center rounded-full text-[10px] font-bold" style={{ background: color.suave, color: color.acento }} aria-hidden>{iniciales(p.nombre)}</span>
          <span className="truncate">{p.nombre}</span>
        </li>
      ))}
      {lista.length > 4 && (
        <li><button type="button" onClick={() => setTodas((v) => !v)} className="rounded px-1 text-xs font-medium text-azul hover:underline">{todas ? "Ver menos" : `+ ${lista.length - 4} más`}</button></li>
      )}
    </ul>
  );
}

// Estilo del organigrama oficial (PDF «Organigramas Adzone 2026»): la cadena de mando y quien dirige gerencias en amarillo,
// las direcciones y gerencias en azul, y debajo, en columna, los departamentos (texto azul en negrita) y sus áreas (blancas).
const TONOS = {
  oro: { caja: "border-amarillo-600 bg-amarillo text-noche", titulo: "text-noche", sub: "text-noche/65", chip: "bg-noche/10 text-noche", boton: "bg-noche/10 text-noche hover:bg-noche/15", centro: true },
  azul: { caja: "border-azul bg-azul text-white", titulo: "text-white", sub: "text-white/70", chip: "bg-white/15 text-white", boton: "bg-white/15 text-white hover:bg-white/25", centro: true },
  jefe: { caja: "border-azul/35 bg-white text-tinta", titulo: "text-azul font-bold", sub: "text-gris", chip: null, boton: "bg-fondo text-gris hover:bg-linea-suave hover:text-tinta" },
  hoja: { caja: "border-linea bg-white text-tinta", titulo: "text-tinta font-medium", sub: "text-gris", chip: null, boton: "bg-fondo text-gris hover:bg-linea-suave hover:text-tinta" },
};
const LINEA = "bg-azul/45";

function Tarjeta({ nodo, tono = "hoja", admin, resumen, abierto, onAlternar, atenuado, destacado, onDepto, ancho = "w-[230px]", modo = "nominal" }) {
  const color = colorDe(nodo.departamento_id);
  const t = TONOS[tono];
  const estructural = modo === "estructural";
  const texto = estructural ? (nodo.unidad || nodo.nombre) : nodo.nombre;
  const titulo = admin ? <Link to={`/puestos/${nodo.id}`} className="hover:underline">{texto}</Link> : texto;
  return (
    <div data-nodo={nodo.id} data-depto={nodo.departamento_id} data-coincide={destacado ? "1" : undefined}
      className={cx("relative rounded-[3px] border shadow-[0_1px_2px_rgb(15_37_80/0.08)] transition", t.caja, ancho, atenuado && "opacity-30",
        destacado ? "ring-4 ring-amarillo/70" : "hover:shadow-md")}>
      <div className={cx("px-3 py-2.5", t.centro && "text-center")}>
        <h3 className={cx("!text-[14px] leading-snug", t.centro ? "font-bold" : "", t.titulo)}>{titulo}</h3>
        {/* El cargo y su unidad quedan vinculados: en el estructural se ve el cargo debajo; en el nominal, la unidad */}
        {(estructural ? nodo.unidad && nodo.unidad !== nodo.nombre : nodo.unidad) && <p className={cx("mt-0.5 text-[11.5px] leading-snug", t.sub)}>{estructural ? nodo.nombre : nodo.unidad}</p>}
        <button type="button" onClick={() => onDepto?.(nodo.departamento_id)} title={`Acercar a ${nodo.departamento}`} aria-label={`Acercar el organigrama a ${nodo.departamento}`}
          className={cx("mt-1 inline-flex max-w-full items-center gap-1.5 rounded text-[10.5px] font-semibold uppercase tracking-wide hover:underline", t.sub)}>
          <span className="size-2 shrink-0 rounded-full ring-1 ring-white/60" style={{ background: color.acento }} aria-hidden />
          <span className="truncate">{nodo.departamento}</span>
        </button>
        {estructural ? null : nodo.personas.length ? (
          <ul className={cx("mt-1.5 space-y-1", t.centro && "flex flex-col items-center")}>
            {nodo.personas.slice(0, 4).map((p) => (
              <li key={p.id} className="flex max-w-full items-center gap-1.5 text-[12.5px]">
                <span className={cx("flex size-5 shrink-0 items-center justify-center rounded-full text-[9px] font-bold", t.chip || "")} style={t.chip ? undefined : { background: color.suave, color: color.acento }} aria-hidden>{iniciales(p.nombre)}</span>
                <span className="truncate">{p.nombre}</span>
              </li>
            ))}
            {nodo.personas.length > 4 && <li className={cx("text-[11.5px]", t.sub)}>+ {nodo.personas.length - 4} más</li>}
          </ul>
        ) : !nodo.cubre?.length && <p className={cx("mt-1.5 inline-flex rounded border border-dashed px-1.5 text-[11px] italic", t.centro ? "border-current/40" : "border-gris/50", t.sub)}>Vacante</p>}
        {!estructural && nodo.situacion === "COMPARTIDO" && (
          <p className={cx("mt-1.5 text-[11px]", t.sub)}><span className={cx("rounded px-1.5 py-px font-semibold", t.chip || "bg-[#f0ebfb] text-[#6d4ac8]")}>Compartido</span>{nodo.cubre?.length ? ` · lo cubre ${nodo.cubre.join(", ")}` : ""}</p>
        )}
        {nodo.hijos.length > 0 && (
          <button type="button" onClick={onAlternar} aria-expanded={abierto} aria-label={`${abierto ? "Contraer" : "Expandir"} ${nodo.nombre}`}
            className={cx("mt-2 inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-medium transition-colors", t.boton)}>
            {plural(resumen.puestos - 1, "puesto", "puestos")} · {plural(resumen.personas - nodo.personas.length, "persona", "personas")}
            <ChevronDown className={cx("size-3.5 transition-transform", !abierto && "-rotate-90")} aria-hidden />
          </button>
        )}
      </div>
    </div>
  );
}

const tarjeta = (nodo, ctx, tono, ancho) => (
  <Tarjeta nodo={nodo} tono={tono} modo={ctx.modo} admin={ctx.admin} resumen={contar(nodo)} abierto={ctx.abierto(nodo)} onAlternar={() => ctx.alternar(nodo.id)}
    atenuado={ctx.atenuado(nodo)} destacado={ctx.destacado(nodo)} onDepto={ctx.alDepto} ancho={ancho} />
);

// ── Gráfico ─────────────────────────────────────────────────────────────────────────────────────────────────────────
/** Debajo de una gerencia: lista vertical con la línea a la izquierda (como en el PDF); los que tienen gente a cargo, en negrita. */
function Rama({ nodos, ctx, nivel = 0 }) {
  return (
    <ul className={cx("relative space-y-2 pt-2", nivel === 0 ? "ml-3" : "ml-3")}>
      <span className={cx("absolute bottom-5 left-0 top-0 w-px", LINEA)} aria-hidden />
      {nodos.map((n) => {
        const abierto = ctx.abierto(n);
        return (
          <li key={n.id} className="relative pl-4">
            <span className={cx("absolute left-0 top-5 h-px w-4", LINEA)} aria-hidden />
            {tarjeta(n, ctx, n.hijos.length ? "jefe" : "hoja", nivel === 0 ? "w-[210px]" : "w-[196px]")}
            {abierto && n.hijos.length > 0 && <Rama nodos={n.hijos} ctx={ctx} nivel={nivel + 1} />}
          </li>
        );
      })}
    </ul>
  );
}

/** ¿Dirige gerencias? (varios puestos a cargo que a su vez tienen gente): sus puestos van en fila, como Director de Operaciones. */
const dirigeGerencias = (n) => n.hijos.filter((h) => h.hijos.length > 0).length >= 2;

/** Una fila de puestos unidos por la línea horizontal (direcciones, o las gerencias de Operaciones). */
function Abanico({ nodos, ctx }) {
  const n = nodos.length;
  return (
    <div className="flex items-start justify-center">
      {nodos.map((h, i) => (
        <div key={h.id} className="relative flex flex-col items-center px-2.5 pt-6">
          {n > 1 && <span className={cx("absolute top-0 h-px", LINEA, i === 0 ? "left-1/2 right-0" : i === n - 1 ? "left-0 right-1/2" : "inset-x-0")} aria-hidden />}
          <span className={cx("absolute left-1/2 top-0 h-6 w-px", LINEA)} aria-hidden />
          <Columna nodo={h} ctx={ctx} />
        </div>
      ))}
    </div>
  );
}

function Columna({ nodo, ctx }) {
  const abierto = ctx.abierto(nodo);
  if (dirigeGerencias(nodo)) {
    return (
      <div className="flex flex-col items-center">
        {tarjeta(nodo, ctx, "oro", "w-[260px]")}
        {abierto && <><span className={cx("h-6 w-px", LINEA)} aria-hidden /><Abanico nodos={nodo.hijos} ctx={ctx} /></>}
      </div>
    );
  }
  return (
    <div className="flex flex-col items-start">
      {tarjeta(nodo, ctx, "azul", "w-[220px]")}
      {abierto && nodo.hijos.length > 0 && <Rama nodos={nodo.hijos} ctx={ctx} />}
    </div>
  );
}

/** Una raíz: la cadena de mando de un solo puesto va en vertical, en amarillo (Consejo → Dirección General) y, donde se abre
 *  el abanico, las direcciones van en fila, unidas por la línea. */
function Arbol({ raiz, ctx }) {
  const cadena = [raiz];
  while (ctx.abierto(cadena[cadena.length - 1]) && cadena[cadena.length - 1].hijos.length === 1) cadena.push(cadena[cadena.length - 1].hijos[0]);
  const ultimo = cadena[cadena.length - 1];
  const hijos = ctx.abierto(ultimo) ? ultimo.hijos : [];
  return (
    <div className="inline-flex flex-col items-center">
      {cadena.map((nodo, i) => (
        <div key={nodo.id} className="flex flex-col items-center">
          {i > 0 && <span className={cx("h-3 w-px", LINEA)} aria-hidden />}
          {tarjeta(nodo, ctx, "oro", "w-[300px]")}
        </div>
      ))}
      {hijos.length > 0 && <><span className={cx("h-6 w-px", LINEA)} aria-hidden /><Abanico nodos={hijos} ctx={ctx} /></>}
    </div>
  );
}

// ── Coordinación operativa: líneas punteadas entre puestos (debajo de las tarjetas, sin cruzar los títulos) ──────────
const COORD = "#d0452f";
function LineasCoordinacion({ todos, clave }) {
  const svg = useRef(null);
  const [lineas, setLineas] = useState([]);
  useLayoutEffect(() => {
    const caja = svg.current?.parentElement;
    if (!caja) return undefined;
    const medir = () => {
      const base = caja.getBoundingClientRect();
      const k = base.width / (caja.offsetWidth || 1) || 1;   // el zoom del lienzo
      const rect = (id) => { const el = caja.querySelector(`[data-nodo="${id}"]`); if (!el) return null; const r = el.getBoundingClientRect(); return { x: (r.left + r.width / 2 - base.left) / k, arriba: (r.top - base.top) / k, abajo: (r.bottom - base.top) / k, izq: (r.left - base.left) / k, der: (r.right - base.left) / k }; };
      const nuevas = [];
      todos.forEach((n) => (n.coordina_con || []).forEach((destino, i) => {
        const a = rect(n.id), b = rect(destino);
        if (!a || !b) return;
        if (Math.abs(a.arriba - b.arriba) < 30) {   // en la misma fila: por encima de las tarjetas (entre la línea de reporte y ellas), sin cruzar ninguna tarjeta
          const y = Math.min(a.arriba, b.arriba) - 9 - i * 4;
          const ax = a.x + (b.x > a.x ? 1 : -1) * Math.min(40, (a.der - a.izq) / 4), bx = b.x + (b.x > a.x ? -1 : 1) * Math.min(40, (b.der - b.izq) / 4);
          nuevas.push({ id: `${n.id}-${destino}`, d: `M${ax},${a.arriba} V${y} H${bx} V${b.arriba}`, puntos: [[ax, a.arriba], [bx, b.arriba]] });
        } else {   // en filas distintas: sale por el lado y entra por el lado
          const sale = b.x > a.x ? a.der : a.izq, entra = b.x > a.x ? b.izq : b.der;
          const ya = (a.arriba + a.abajo) / 2, yb = (b.arriba + b.abajo) / 2, xm = (sale + entra) / 2;
          nuevas.push({ id: `${n.id}-${destino}`, d: `M${sale},${ya} H${xm} V${yb} H${entra}`, puntos: [[sale, ya], [entra, yb]] });
        }
      }));
      setLineas(nuevas);
    };
    const t = setTimeout(medir, 60);
    const obs = new ResizeObserver(medir);
    obs.observe(caja);
    return () => { clearTimeout(t); obs.disconnect(); };
  }, [todos, clave]);
  return (
    <svg ref={svg} className="pointer-events-none absolute inset-0 !mt-0 size-full overflow-visible" aria-hidden>
      {lineas.map((l) => (
        <g key={l.id}>
          <path d={l.d} fill="none" stroke={COORD} strokeWidth="1.6" strokeDasharray="5 3" />
          {l.puntos.map(([x, y], i) => <circle key={i} cx={x} cy={y} r="2.5" fill={COORD} />)}
        </g>
      ))}
    </svg>
  );
}

/** Zoom real: se escala el gráfico y se reserva su tamaño para que el desplazamiento sea correcto. */
function Lienzo({ escala, children }) {
  const interior = useRef(null);
  const [medida, setMedida] = useState({ w: 0, h: 0 });
  useEffect(() => {
    const el = interior.current;
    if (!el) return undefined;
    const medir = () => setMedida({ w: el.scrollWidth, h: el.scrollHeight });
    medir();
    const obs = new ResizeObserver(medir);
    obs.observe(el);
    return () => obs.disconnect();
  }, [children]);
  return (
    <div className="mx-auto" style={{ width: medida.w * escala || undefined, height: medida.h * escala || undefined }}>
      <div ref={interior} data-lienzo className="inline-block origin-top-left transition-transform duration-200 ease-out motion-reduce:transition-none" style={{ transform: `scale(${escala})`, minWidth: "max-content" }}>{children}</div>
    </div>
  );
}

// ── Lista (celular y accesibilidad) ─────────────────────────────────────────────────────────────────────────────────
function ItemLista({ nodo, nivel, ctx }) {
  const color = colorDe(nodo.departamento_id);
  const abierto = ctx.abierto(nodo);
  return (
    <li>
      <div data-nodo={nodo.id} data-depto={nodo.departamento_id} data-coincide={ctx.destacado(nodo) ? "1" : undefined}
        className={cx("flex items-start gap-3 rounded-lg border bg-white px-3 py-2.5", ctx.atenuado(nodo) && "opacity-35", ctx.destacado(nodo) ? "border-azul ring-2 ring-azul/30" : "border-linea")} style={{ borderLeftColor: color.acento, borderLeftWidth: 4 }}>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: color.acento }}>{nodo.departamento}</p>
          <p className="font-semibold leading-snug text-noche">{ctx.admin ? <Link to={`/puestos/${nodo.id}`} className="hover:underline">{nodo.nombre}</Link> : nodo.nombre}</p>
          {nodo.personas.length ? <p className="mt-0.5 text-sm text-gris">{nodo.personas.map((p) => p.nombre).join(" · ")}</p> : <p className="mt-0.5 text-sm italic text-gris">Vacante</p>}
        </div>
        {nodo.hijos.length > 0 && (
          <button type="button" onClick={() => ctx.alternar(nodo.id)} aria-expanded={abierto} aria-label={`${abierto ? "Contraer" : "Expandir"} ${nodo.nombre}`}
            className="flex shrink-0 items-center gap-1 rounded-lg bg-fondo px-2 py-1 text-xs font-medium text-gris hover:bg-linea-suave">
            {nodo.hijos.length}<ChevronDown className={cx("size-4 transition-transform", !abierto && "-rotate-90")} aria-hidden />
          </button>
        )}
      </div>
      {abierto && nodo.hijos.length > 0 && (
        <ul className={cx("mt-2 space-y-2 border-l border-linea", nivel < 3 ? "ml-4 pl-3" : "ml-2 pl-2")}>
          {nodo.hijos.map((h) => <ItemLista key={h.id} nodo={h} nivel={nivel + 1} ctx={ctx} />)}
        </ul>
      )}
    </li>
  );
}

// ── Página ──────────────────────────────────────────────────────────────────────────────────────────────────────────
export default function Organigrama() {
  const { esAdmin } = useSesion();
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  const [buscar, setBuscar] = useState("");
  const [depto, setDepto] = useState(null);
  const [cerrados, setCerrados] = useState(() => new Set());
  const [escala, setEscala] = useState(1);
  const [vista, setVista] = useState(() => (window.matchMedia("(max-width: 767px)").matches ? "lista" : "grafico"));
  const [modo, setModo] = useState("nominal");   // estructural: unidades; nominal: cargos y personas
  const [params, setParams] = useSearchParams();
  const pestana = params.get("ver") || "organigrama";
  const [aprobando, setAprobando] = useState(false);
  const contenedor = useRef(null);

  useEffect(() => { organigrama().then(setDatos).catch((e) => setError(e.message)); }, []);

  const todos = useMemo(() => (datos ? aplanar(datos.raices) : []), [datos]);
  const padres = useMemo(() => { const m = new Map(); todos.forEach((n) => n.hijos.forEach((h) => m.set(h.id, n.id))); return m; }, [todos]);
  const departamentos = useMemo(() => {
    const m = new Map();
    todos.forEach((n) => { if (!m.has(n.departamento_id)) m.set(n.departamento_id, { id: n.departamento_id, nombre: n.departamento, puestos: 0, personas: 0 }); const d = m.get(n.departamento_id); d.puestos += 1; d.personas += n.personas.length; });
    return [...m.values()].sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
  }, [todos]);
  const total = useMemo(() => ({ puestos: todos.length, personas: todos.reduce((a, n) => a + n.personas.length, 0), vacantes: todos.filter((n) => !n.personas.length).length }), [todos]);

  const t = normal(buscar.trim());
  const coincidencias = t ? todos.filter((n) => coincideNodo(n, t)).length : 0;

  const alternar = useCallback((id) => setCerrados((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; }), []);
  const ctx = useMemo(() => ({
    admin: esAdmin, alternar, modo,
    // Con una búsqueda activa se abren las ramas que contienen coincidencias; si no, manda lo que la persona contrajo
    abierto: (n) => (t ? ramaCoincide(n, t) : !cerrados.has(n.id)),
    atenuado: (n) => (t ? !ramaCoincide(n, t) : depto != null && n.departamento_id !== depto),
    destacado: (n) => (t ? coincideNodo(n, t) : false),
    alDepto: (id) => setDepto((d) => (d === id ? d : id)),
  }), [esAdmin, alternar, t, cerrados, depto, modo]);

  // Ajusta el gráfico al ancho disponible (sin bajar de `minimo`, para que el texto siga leyéndose)
  // La «cámara» del organigrama: el zoom y el desplazamiento se animan JUNTOS, cuadro a cuadro (300 ms), en un solo movimiento
  // continuo. Se escribe directo en el elemento (sin pasar por React en cada cuadro) y al final se confirma el valor.
  const escalaRef = useRef(1);
  escalaRef.current = escala;
  const animacion = useRef(0);
  const animar = useCallback((s1, izquierda, arriba) => {
    const caja = contenedor.current;
    const interior = caja?.querySelector("[data-lienzo]");
    cancelAnimationFrame(animacion.current);
    if (!caja || !interior || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setEscala(s1);
      if (caja) { caja.scrollLeft = izquierda; window.scrollTo(0, arriba); }
      return;
    }
    const fuera = interior.parentElement;
    const w0 = interior.scrollWidth, h0 = interior.scrollHeight;
    const s0 = escalaRef.current || 1, x0 = caja.scrollLeft, y0 = window.scrollY;
    const inicio = performance.now(), duracion = 300;
    interior.style.transition = "none";
    interior.style.willChange = "transform";
    const paso = (ahora) => {
      const t = Math.min(1, (ahora - inicio) / duracion), e = 1 - (1 - t) ** 3; // frena suave al llegar
      const s = s0 + (s1 - s0) * e;
      interior.style.transform = `scale(${s})`;
      fuera.style.width = `${w0 * s}px`;
      fuera.style.height = `${h0 * s}px`;
      caja.scrollLeft = x0 + (izquierda - x0) * e;
      window.scrollTo(0, y0 + (arriba - y0) * e);
      if (t < 1) animacion.current = requestAnimationFrame(paso);
      else { interior.style.transition = ""; interior.style.willChange = ""; setEscala(s1); }
    };
    animacion.current = requestAnimationFrame(paso);
  }, []);
  useEffect(() => () => cancelAnimationFrame(animacion.current), []);

  // Ajusta el gráfico al ancho disponible (sin bajar de `minimo`, para que el texto siga leyéndose)
  const ajustar = useCallback((minimo = 0.4, animado = true, arriba = null) => {
    const caja = contenedor.current;
    const interior = caja?.querySelector("[data-lienzo]");
    if (!caja || !interior) return;
    const s = +Math.max(minimo, Math.min(1, (caja.clientWidth - 48) / interior.scrollWidth)).toFixed(2);
    if (animado) animar(s, 0, arriba ?? window.scrollY); else setEscala(s);
  }, [animar]);
  // Moverse con el ratón: arrastrar el fondo mueve el organigrama (como un mapa) y Ctrl + rueda acerca o aleja. Con el dedo se usa el desplazamiento normal.
  useEffect(() => {
    const caja = contenedor.current;
    if (!caja || vista !== "grafico") return undefined;
    let arrastre = null, suprimirClic = false;
    const abajo = (e) => {
      if (e.pointerType === "touch" || e.button !== 0 || e.target.closest("button, a, input, select, textarea, summary")) return;
      cancelAnimationFrame(animacion.current);
      arrastre = { x: e.clientX, y: e.clientY, movido: false };
    };
    const mover = (e) => {
      if (!arrastre) return;
      const dx = e.clientX - arrastre.x, dy = e.clientY - arrastre.y;
      if (!arrastre.movido) {
        if (Math.hypot(dx, dy) < 4) return; // un clic quieto no es un arrastre
        arrastre.movido = true;
        caja.classList.add("arrastrando");
      }
      caja.scrollLeft -= dx;
      window.scrollBy(0, -dy);
      arrastre.x = e.clientX;
      arrastre.y = e.clientY;
    };
    const arriba = () => {
      if (!arrastre) return;
      suprimirClic = arrastre.movido; // al soltar, el clic que sigue al arrastre no abre ni cierra nada
      arrastre = null;
      caja.classList.remove("arrastrando");
      if (suprimirClic) setTimeout(() => { suprimirClic = false; }, 0);
    };
    const clic = (e) => { if (suprimirClic) { e.stopPropagation(); e.preventDefault(); } };
    const rueda = (e) => {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      setEscala((v) => +Math.min(1.4, Math.max(0.4, v * (e.deltaY < 0 ? 1.08 : 0.92))).toFixed(2));
    };
    caja.addEventListener("pointerdown", abajo);
    window.addEventListener("pointermove", mover);
    window.addEventListener("pointerup", arriba);
    window.addEventListener("pointercancel", arriba);
    caja.addEventListener("click", clic, true);
    caja.addEventListener("wheel", rueda, { passive: false });
    return () => {
      caja.removeEventListener("pointerdown", abajo);
      window.removeEventListener("pointermove", mover);
      window.removeEventListener("pointerup", arriba);
      window.removeEventListener("pointercancel", arriba);
      caja.removeEventListener("click", clic, true);
      caja.removeEventListener("wheel", rueda);
    };
  }, [vista, datos]); // eslint-disable-line react-hooks/exhaustive-deps

  // Al abrir, el gráfico entra completo en pantalla si se puede leer (mínimo 60 %)
  useEffect(() => {
    if (!datos || vista !== "grafico") return undefined;
    const t = setTimeout(() => ajustar(0.6, false), 80);
    return () => clearTimeout(t);
  }, [datos, vista, ajustar]);
  // Al elegir un departamento o buscar, el organigrama te lleva solo hasta lo que pediste: encuadra TODAS sus tarjetas
  // (un departamento puede estar repartido en varias ramas), dentro del gráfico y en la página.
  const irA = useCallback((selector) => {
    const els = [...document.querySelectorAll(selector)];
    if (!els.length) return;
    const suave = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
    const r = els.map((e) => e.getBoundingClientRect());
    const arriba = Math.min(...r.map((x) => x.top)), abajo = Math.max(...r.map((x) => x.bottom));
    const izq = Math.min(...r.map((x) => x.left)), der = Math.max(...r.map((x) => x.right));
    const caja = contenedor.current;
    if (caja) { // horizontal: centra el grupo dentro del gráfico
      const c = caja.getBoundingClientRect();
      caja.scrollBy({ left: (izq + der) / 2 - (c.left + c.width / 2), behavior: suave });
    }
    // vertical: si cabe, lo centra en el espacio visible (debajo de las barras fijas); si no, deja su inicio a la vista
    const margen = 190;
    const alto = abajo - arriba;
    const y = alto < window.innerHeight - margen - 40 ? (arriba + alto / 2) - (margen + (window.innerHeight - margen) / 2) : arriba - margen - 12;
    window.scrollBy({ top: y, behavior: suave });
  }, []);
  // Zoom hacia lo elegido: se escala el MISMO organigrama hasta que las tarjetas del departamento llenen la pantalla y se centra en ellas
  const enfocar = useCallback((selector) => {
    const caja = contenedor.current;
    const interior = caja?.querySelector("[data-lienzo]");
    const els = interior ? [...interior.querySelectorAll(selector)] : [];
    if (!els.length) return;
    const base = interior.getBoundingClientRect(), k = escalaRef.current || 1;
    const r = els.map((e) => e.getBoundingClientRect());
    const izq = Math.min(...r.map((x) => x.left)), der = Math.max(...r.map((x) => x.right));
    const sup = Math.min(...r.map((x) => x.top)), inf = Math.max(...r.map((x) => x.bottom));
    const nueva = +Math.max(0.4, Math.min(1.4, (caja.clientWidth - 64) / ((der - izq) / k), (window.innerHeight - 260) / ((inf - sup) / k))).toFixed(2);
    const centro = { x: ((izq + der) / 2 - base.left) / k, y: ((sup + inf) / 2 - base.top) / k };
    const c = caja.getBoundingClientRect();
    const izquierda = Math.max(0, centro.x * nueva + 24 - caja.clientWidth / 2);
    const arriba = Math.max(0, c.top + window.scrollY + 24 + centro.y * nueva - (190 + (window.innerHeight - 190) / 2));
    animar(nueva, izquierda, arriba); // zoom y desplazamiento a la vez, no uno después del otro
  }, [animar]);
  const verTodo = () => { setDepto(null); setTimeout(() => ajustar(0.6, true, 0), 30); };
  useEffect(() => {
    if (depto == null) return undefined;
    // Se abren las ramas que llevan hasta ese departamento (por si se habían contraído)
    setCerrados((cs) => {
      if (!cs.size) return cs;
      const abrir = new Set();
      todos.filter((n) => n.departamento_id === depto).forEach((n) => { for (let p = padres.get(n.id); p != null; p = padres.get(p)) abrir.add(p); });
      const nuevo = new Set([...cs].filter((id) => !abrir.has(id)));
      return nuevo.size === cs.size ? cs : nuevo;
    });
    const id = setTimeout(() => (vista === "grafico" ? enfocar(`[data-depto="${depto}"]`) : irA(`[data-depto="${depto}"]`)), 40);
    return () => clearTimeout(id);
  }, [depto, irA, enfocar, vista]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!t) return undefined;
    const id = setTimeout(() => irA('[data-coincide="1"]'), 350); // espera a que se abran las ramas con coincidencias
    return () => clearTimeout(id);
  }, [t, irA]);

  const expandirTodo = () => setCerrados(new Set());

  if (error) return <Alerta>{error}</Alerta>;
  if (!datos) return <Cargando />;
  if (!datos.raices.length) return <Vacio icono={Network} titulo="Todavía no hay puestos">Los puestos y a quién reportan se crean en Departamentos y puestos.</Vacio>;

  return (
    <div>
      <header className="mb-5 flex flex-wrap items-end justify-between gap-4 overflow-hidden rounded-xl bg-azul px-5 py-5 text-white md:px-7 print:rounded-none">
        <div className="min-w-0">
          <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-amarillo">Adzone D. M. / {new Date().getFullYear()}</p>
          <h1 className="mt-1 text-[26px] font-bold leading-tight !text-white md:text-3xl">{pestana === "matriz" ? "Matriz de reporte y coordinación" : pestana === "cambios" ? "Cambios y versiones" : `Organigrama ${modo}`}</h1>
          <p className="mt-1 max-w-[70ch] text-sm text-white/75">¿A quién le reporto?, ¿con quién coordino? y ¿por dónde escalo un caso? El supervisor de cada persona es quien ocupa el puesto del que depende.</p>
          <p className="mt-2 text-xs font-semibold text-white">
            {datos.version ? <>Versión {datos.version.numero} · vigente desde {new Date(`${datos.version.vigente_desde}T12:00`).toLocaleDateString("es-DO")} · aprobada por {datos.version.aprobada_por}</> : "Borrador: todavía sin versión aprobada por Dirección General"}
            {datos.cambios_pendientes > 0 && <span className="ml-2 rounded-full bg-amarillo px-2 py-0.5 text-[11px] text-noche">{plural(datos.cambios_pendientes, "cambio pendiente", "cambios pendientes")} de aprobar</span>}
          </p>
        </div>
        <div className="no-imprimir flex flex-wrap gap-2">
          {datos.puede_aprobar && (datos.cambios_pendientes > 0 || !datos.version) && (
            <button type="button" onClick={() => setAprobando(true)} className="inline-flex h-10 items-center gap-2 rounded-lg bg-amarillo px-4 text-sm font-semibold text-noche hover:bg-amarillo-600"><BadgeCheck className="size-4" aria-hidden />Aprobar versión</button>
          )}
          <button type="button" onClick={() => window.print()} className="inline-flex h-10 items-center gap-2 rounded-lg bg-white/15 px-4 text-sm font-semibold text-white ring-1 ring-white/25 hover:bg-white/25">
            <Printer className="size-4" aria-hidden />Imprimir / PDF
          </button>
        </div>
      </header>
      <ModalAprobar abierto={aprobando} pendientes={datos.cambios_pendientes} onCerrar={() => setAprobando(false)} onHecho={() => { setAprobando(false); organigrama().then(setDatos).catch(() => {}); }} />
      <Pestanas className="no-imprimir mb-5" opciones={[{ valor: "organigrama", etiqueta: "Organigrama" }, { valor: "matriz", etiqueta: "Matriz de reporte" }, { valor: "cambios", etiqueta: "Cambios y versiones" }]}
        valor={pestana} onCambio={(v) => setParams(v === "organigrama" ? {} : { ver: v })} />
      {pestana === "matriz" ? <Matriz /> : pestana === "cambios" ? <Cambios /> : <>

      {/* Cifras de la empresa */}
      <dl className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
        {[["Personas activas", total.personas], ["Puestos", total.puestos], ["Departamentos", departamentos.length], ["Vacantes", total.vacantes]].map(([nombre, valor]) => (
          <div key={nombre} className="rounded-xl border border-linea bg-white px-4 py-3">
            <dt className="text-xs font-medium text-gris">{nombre}</dt>
            <dd className="num mt-0.5 font-display text-2xl font-semibold text-noche">{valor}</dd>
          </div>
        ))}
      </dl>
      {datos.sin_puesto > 0 && esAdmin && (
        <Alerta tono="amarillo" className="mb-5">{plural(datos.sin_puesto, "persona activa no tiene", "personas activas no tienen")} puesto: no tienen supervisor ni KPIs. <Link to="/personas" className="font-medium underline">Asignar puestos</Link></Alerta>
      )}

      {/* Barra de herramientas: queda fija arriba al desplazarte, para cambiar de departamento sin volver a subir.
          En el celular («contents») solo se fija la fila de departamentos; el buscador queda en su lugar. */}
      <div className="no-imprimir mb-4 max-md:contents md:sticky md:top-14 md:z-20 md:space-y-3 md:rounded-xl md:border md:border-linea md:bg-white/95 md:p-3 md:shadow-sm md:backdrop-blur lg:top-16">
        <div className="flex flex-wrap items-center gap-2 max-md:mb-3 max-md:rounded-xl max-md:border max-md:border-linea max-md:bg-white max-md:p-3">
          <div className="relative min-w-52 flex-1 md:max-w-sm">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" aria-hidden />
            <input className="campo h-10 !pl-9 !pr-9" placeholder="Buscar persona, puesto o departamento" value={buscar} onChange={(e) => setBuscar(e.target.value)} aria-label="Buscar en el organigrama" />
            {buscar && <button type="button" onClick={() => setBuscar("")} aria-label="Borrar la búsqueda" className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full p-1 text-gris hover:bg-linea"><X className="size-4" aria-hidden /></button>}
          </div>
          {t && <p className="text-sm text-gris" aria-live="polite">{coincidencias ? plural(coincidencias, "coincidencia", "coincidencias") : "Sin coincidencias"}</p>}
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <div className="inline-flex rounded-lg border border-linea bg-fondo p-0.5" role="group" aria-label="Estructural o nominal">
              {[["estructural", "Estructural"], ["nominal", "Nominal"]].map(([v, txt]) => (
                <button key={v} type="button" onClick={() => setModo(v)} aria-pressed={modo === v} title={v === "estructural" ? "Unidades organizativas y sus dependencias" : "Cargos, personas y vacantes"}
                  className={cx("rounded-md px-3 py-1.5 text-sm font-medium transition-colors", modo === v ? "bg-white text-noche shadow-sm" : "text-gris hover:text-tinta")}>{txt}</button>
              ))}
            </div>
            <div className="inline-flex rounded-lg border border-linea bg-fondo p-0.5" role="group" aria-label="Tipo de vista">
              {[["grafico", "Gráfico"], ["lista", "Lista"]].map(([v, txt]) => (
                <button key={v} type="button" onClick={() => setVista(v)} aria-pressed={vista === v}
                  className={cx("rounded-md px-3 py-1.5 text-sm font-medium transition-colors", vista === v ? "bg-white text-noche shadow-sm" : "text-gris hover:text-tinta")}>{txt}</button>
              ))}
            </div>
            <div className="inline-flex items-center gap-1" role="group" aria-label="Contraer o expandir">
              <Boton variante="fantasma" tam="sm" onClick={expandirTodo}>Expandir todo</Boton>
              <Boton variante="fantasma" tam="sm" onClick={() => setCerrados(new Set(todos.filter((n) => n.hijos.length && !datos.raices.some((r) => r.id === n.id)).map((n) => n.id)))}>Contraer</Boton>
            </div>
            {vista === "grafico" && (
              <div className="inline-flex items-center gap-1 rounded-lg border border-linea px-1" role="group" aria-label="Zoom" title="Arrastra el fondo para moverte · Ctrl + rueda para acercar o alejar">
                <button type="button" onClick={() => setEscala((e) => Math.max(0.4, +(e - 0.1).toFixed(2)))} aria-label="Alejar" className="rounded p-1.5 text-gris hover:bg-fondo"><Minus className="size-4" aria-hidden /></button>
                <span className="num w-11 text-center text-sm text-gris" aria-live="polite">{Math.round(escala * 100)}%</span>
                <button type="button" onClick={() => setEscala((e) => Math.min(1.4, +(e + 0.1).toFixed(2)))} aria-label="Acercar" className="rounded p-1.5 text-gris hover:bg-fondo"><Plus className="size-4" aria-hidden /></button>
                <button type="button" onClick={() => ajustar()} aria-label="Ajustar al ancho" title="Ajustar al ancho" className="rounded p-1.5 text-gris hover:bg-fondo"><Maximize2 className="size-4" aria-hidden /></button>
              </div>
            )}
          </div>
        </div>
        {/* Leyenda de departamentos: al elegir uno, el resto se atenúa */}
        <div className="flex items-center gap-1.5 max-md:sticky max-md:top-14 max-md:z-20 max-md:-mx-4 max-md:mb-3 max-md:overflow-x-auto max-md:border-b max-md:border-linea max-md:bg-fondo/95 max-md:px-4 max-md:py-2 max-md:backdrop-blur max-md:[scrollbar-width:none] md:flex-wrap" role="group" aria-label="Departamentos">
          {departamentos.map((d) => {
            const c = colorDe(d.id);
            const activo = depto === d.id;
            return (
              <button key={d.id} type="button" onClick={() => (activo ? verTodo() : setDepto(d.id))} aria-pressed={activo}
                className={cx("inline-flex h-8 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-3 text-xs font-medium transition-colors", activo ? "text-white" : "bg-white text-tinta hover:bg-fondo")}
                style={activo ? { background: c.acento, borderColor: c.acento } : { borderColor: "#e3e8f1" }}>
                <span className="size-2 rounded-full" style={{ background: activo ? "#fff" : c.acento }} aria-hidden />
                {d.nombre}<span className="num opacity-70">{d.personas}</span>
              </button>
            );
          })}
          {depto != null && <button type="button" onClick={verTodo} className="shrink-0 whitespace-nowrap rounded px-2 text-xs font-medium text-azul hover:underline">Ver todo el organigrama</button>}
        </div>
      </div>

      {vista === "grafico" ? (
        <div ref={contenedor} className="cursor-grab overflow-auto rounded-xl border border-linea [&.arrastrando]:cursor-grabbing [&.arrastrando]:select-none bg-white p-6 print:overflow-visible print:border-0">
          <Lienzo escala={escala}>
            <div className="relative space-y-12">
              {datos.raices.map((r) => <Arbol key={r.id} raiz={r} ctx={ctx} />)}
              <LineasCoordinacion todos={todos} clave={`${[...cerrados].join(",")}|${t}|${modo}|${depto}`} />
            </div>
          </Lienzo>
          <p className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-1 text-[11px] text-gris">
            <span className="inline-flex items-center gap-1.5"><span className={cx("h-px w-6", LINEA)} aria-hidden />Reporte directo</span>
            <span className="inline-flex items-center gap-1.5"><svg width="26" height="4" aria-hidden><line x1="0" y1="2" x2="26" y2="2" stroke={COORD} strokeWidth="1.6" strokeDasharray="5 3" /></svg>Coordinación operativa (no es reporte)</span>
            <span className="inline-flex items-center gap-1.5"><span className="size-3 rounded-[2px] bg-amarillo" aria-hidden />Dirección</span>
            <span className="inline-flex items-center gap-1.5"><span className="size-3 rounded-[2px] bg-azul" aria-hidden />Dirección de área o gerencia</span>
            <span className="inline-flex items-center gap-1.5"><span className="size-3 rounded-[2px] border border-azul/35 bg-white" aria-hidden /><b className="font-bold text-azul">Departamento</b> (con puestos a cargo)</span>
            <span className="inline-flex items-center gap-1.5"><span className="size-3 rounded-[2px] border border-linea bg-white" aria-hidden />Área o puesto</span>
          </p>
        </div>
      ) : (
        <ul className="space-y-3">{datos.raices.map((r) => <ItemLista key={r.id} nodo={r} nivel={0} ctx={ctx} />)}</ul>
      )}
      </>}
    </div>
  );
}

function ModalAprobar({ abierto, pendientes, onCerrar, onHecho }) {
  const [fecha, setFecha] = useState(() => new Date().toLocaleDateString("en-CA"));
  const [notas, setNotas] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const avisar = useAviso();
  const aprobar = async () => {
    setEnviando(true); setError("");
    try { const v = await aprobarOrganigrama({ vigente_desde: fecha, notas }); avisar(`Versión ${v.numero} aprobada`); onHecho(); } catch (e) { setError(e.message); }
    setEnviando(false);
  };
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo="Aprobar versión del organigrama" descripcion={`Dirección General aprueba la versión que se comunica al personal. Incluye ${plural(pendientes, "cambio registrado", "cambios registrados")}.`}
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton icono={BadgeCheck} onClick={aprobar} cargando={enviando}>Aprobar</Boton></>}>
      <div className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        <Campo etiqueta="Vigente desde">{(id) => <input id={id} type="date" className="campo" value={fecha} onChange={(e) => setFecha(e.target.value)} />}</Campo>
        <Campo etiqueta="Notas (opcional)" ayuda="Qué cambia en esta versión; las áreas ya revisaron sus puestos y dependencias.">{(id) => <textarea id={id} rows={3} className="campo" value={notas} onChange={(e) => setNotas(e.target.value)} />}</Campo>
      </div>
    </Modal>
  );
}
