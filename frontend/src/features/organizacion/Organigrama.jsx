// Organigrama de la empresa: gráfico jerárquico con color por departamento, zoom, búsqueda, contraer/expandir,
// vista de lista (celular y lectores de pantalla) y versión para imprimir.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowLeft, ChevronDown, Maximize2, Minus, Network, Plus, Printer, Search, X, ZoomIn } from "lucide-react";
import { organigrama } from "@/lib/api";
import { plural } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import { Alerta, Boton, Cargando, Vacio, cx } from "@/components/ui";

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

/** Copia del árbol solo con los puestos de un departamento: los de otros departamentos son otras áreas. */
const podar = (nodo, depto) => ({ ...nodo, hijos: nodo.hijos.filter((h) => h.departamento_id === depto).map((h) => podar(h, depto)) });

/** Las áreas (departamentos) de la empresa y cómo se conectan. La cabeza de un área son sus puestos cuyo superior es de otro
 *  departamento (o no tiene); el área depende del departamento del superior de su cabeza. Devuelve las áreas de primer nivel. */
function construirAreas(todos) {
  const padre = new Map();
  todos.forEach((n) => n.hijos.forEach((h) => padre.set(h.id, n)));
  const areas = new Map();
  todos.forEach((n) => {
    if (!areas.has(n.departamento_id)) areas.set(n.departamento_id, { id: n.departamento_id, nombre: n.departamento, puestos: [], cabezas: [], personas: 0, vacantes: 0, hijos: [], padre: null });
    const a = areas.get(n.departamento_id);
    a.puestos.push(n);
    a.personas += n.personas.length;
    if (!n.personas.length) a.vacantes += 1;
    const sup = padre.get(n.id);
    if (!sup || sup.departamento_id !== n.departamento_id) a.cabezas.push(n);
  });
  areas.forEach((a) => {
    const sup = a.cabezas.map((c) => padre.get(c.id)).find(Boolean);
    a.padre = sup ? areas.get(sup.departamento_id) : null;
    a.depende = sup ? { puesto: sup.nombre, area: sup.departamento } : null;
  });
  // Un ciclo entre áreas (A reporta a B y B a A) dejaría áreas sin raíz: se cortan y quedan de primer nivel
  areas.forEach((a) => {
    const vistos = new Set([a.id]);
    for (let p = a.padre; p; p = p.padre) { if (vistos.has(p.id)) { a.padre = null; break; } vistos.add(p.id); }
  });
  areas.forEach((a) => { if (a.padre) a.padre.hijos.push(a); });
  const orden = (x, y) => x.nombre.localeCompare(y.nombre, "es");
  areas.forEach((a) => a.hijos.sort(orden));
  return { areas, raices: [...areas.values()].filter((a) => !a.padre).sort(orden) };
}

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

function Tarjeta({ nodo, admin, resumen, abierto, onAlternar, atenuado, destacado, funciones, ancho = "w-[260px]" }) {
  const color = colorDe(nodo.departamento_id);
  const titulo = admin ? <Link to={`/puestos/${nodo.id}`} className="hover:text-azul hover:underline">{nodo.nombre}</Link> : nodo.nombre;
  return (
    <div data-nodo={nodo.id} data-depto={nodo.departamento_id} data-coincide={destacado ? "1" : undefined}
      className={cx("relative overflow-hidden rounded-xl border bg-white shadow-sm transition", ancho, atenuado && "opacity-35", destacado ? "border-azul ring-2 ring-azul/30" : "border-linea hover:shadow-md")}>
      <span className="absolute inset-y-0 left-0 w-1" style={{ background: color.acento }} aria-hidden />
      <div className="py-3 pl-4 pr-3">
        <span className="inline-flex max-w-full items-center rounded-full px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide" style={{ background: color.suave, color: color.acento }}>
          <span className="truncate">{nodo.departamento}</span>
        </span>
        <h3 className="mt-1.5 !text-[15px] font-semibold leading-snug !text-noche">{titulo}</h3>
        <Personas lista={nodo.personas} color={color} />
        {funciones && nodo.funciones && <p className="mt-2 line-clamp-3 text-xs leading-relaxed text-gris" title={nodo.funciones}>{nodo.funciones}</p>}
        {nodo.hijos.length > 0 && (
          <button type="button" onClick={onAlternar} aria-expanded={abierto} aria-label={`${abierto ? "Contraer" : "Expandir"} ${nodo.nombre}`}
            className="mt-2.5 flex w-full items-center justify-between rounded-lg bg-fondo px-2.5 py-1.5 text-xs font-medium text-gris transition-colors hover:bg-linea-suave hover:text-tinta">
            <span>{plural(resumen.puestos - 1, "puesto a cargo", "puestos a cargo")} · {plural(resumen.personas - nodo.personas.length, "persona", "personas")}</span>
            <ChevronDown className={cx("size-4 transition-transform", !abierto && "-rotate-90")} aria-hidden />
          </button>
        )}
      </div>
    </div>
  );
}

// ── Gráfico ─────────────────────────────────────────────────────────────────────────────────────────────────────────
/** Puestos de niveles inferiores: lista vertical con conectores, para que el gráfico no se haga infinitamente ancho. */
function Rama({ nodos, ctx }) {
  return (
    <ul className="relative ml-5 space-y-3 pt-3">
      <span className="absolute bottom-6 left-0 top-0 w-px bg-linea" aria-hidden />
      {nodos.map((n) => <NodoVertical key={n.id} nodo={n} ctx={ctx} />)}
    </ul>
  );
}

function NodoVertical({ nodo, ctx }) {
  const abierto = ctx.abierto(nodo);
  return (
    <li className="relative pl-5">
      <span className="absolute left-0 top-7 h-px w-5 bg-linea" aria-hidden />
      <Tarjeta nodo={nodo} admin={ctx.admin} resumen={contar(nodo)} abierto={abierto} onAlternar={() => ctx.alternar(nodo.id)}
        atenuado={ctx.atenuado(nodo)} destacado={ctx.destacado(nodo)} funciones={ctx.funciones} ancho="w-[236px]" />
      {abierto && nodo.hijos.length > 0 && <Rama nodos={nodo.hijos} ctx={ctx} />}
    </li>
  );
}

/** Una raíz: la cadena de mando de un solo puesto va en vertical (Presidente → Vicepresidente → CEO…) y, donde se abre el
 *  abanico (la dirección con sus áreas), las áreas van en fila, unidas por conectores. */
function Arbol({ raiz, ctx }) {
  // Sigue hacia abajo mientras cada puesto tenga un único puesto a cargo
  const cadena = [raiz];
  while (ctx.abierto(cadena[cadena.length - 1]) && cadena[cadena.length - 1].hijos.length === 1) cadena.push(cadena[cadena.length - 1].hijos[0]);
  const ultimo = cadena[cadena.length - 1];
  const hijos = ctx.abierto(ultimo) ? ultimo.hijos : [];
  const n = hijos.length;
  return (
    <div className="inline-flex flex-col items-center">
      {cadena.map((nodo, i) => (
        <div key={nodo.id} className="flex flex-col items-center">
          {i > 0 && <span className="h-6 w-px bg-linea" aria-hidden />}
          <Tarjeta nodo={nodo} admin={ctx.admin} resumen={contar(nodo)} abierto={ctx.abierto(nodo)} onAlternar={() => ctx.alternar(nodo.id)}
            atenuado={ctx.atenuado(nodo)} destacado={ctx.destacado(nodo)} funciones={ctx.funciones} ancho="w-[300px]" />
        </div>
      ))}
      {n > 0 && (
        <>
          <span className="h-7 w-px bg-linea" aria-hidden />
          <div className="flex items-start justify-center">
            {hijos.map((h, i) => (
              <div key={h.id} className="relative flex flex-col items-center px-3 pt-7">
                {/* Conector horizontal: de la mitad al borde en los extremos, completo en el medio */}
                {n > 1 && <span className={cx("absolute top-0 h-px bg-linea", i === 0 ? "left-1/2 right-0" : i === n - 1 ? "left-0 right-1/2" : "inset-x-0")} aria-hidden />}
                <span className="absolute left-1/2 top-0 h-7 w-px bg-linea" aria-hidden />
                <Tarjeta nodo={h} admin={ctx.admin} resumen={contar(h)} abierto={ctx.abierto(h)} onAlternar={() => ctx.alternar(h.id)}
                  atenuado={ctx.atenuado(h)} destacado={ctx.destacado(h)} funciones={ctx.funciones} />
                {ctx.abierto(h) && h.hijos.length > 0 && (
                  <div className="self-start">
                    <Rama nodos={h.hijos} ctx={ctx} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
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
      <div ref={interior} data-lienzo className="inline-block origin-top-left" style={{ transform: `scale(${escala})`, minWidth: "max-content" }}>{children}</div>
    </div>
  );
}

// ── Organigrama general: las áreas de AdZone ────────────────────────────────────────────────────────────────────────
function TarjetaArea({ area, onAbrir, atenuado, destacado, coincidencias = [], ancho = "w-[212px]" }) {
  const color = colorDe(area.id);
  const jefe = area.cabezas[0];
  const nombreJefe = jefe?.personas.map((p) => p.nombre).join(" · ");
  return (
    <button type="button" data-area={area.id} onClick={(e) => onAbrir(area.id, e.currentTarget)} aria-label={`Abrir el organigrama de ${area.nombre}`}
      className={cx("group relative overflow-hidden rounded-xl border bg-white text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg focus-visible:outline-2 focus-visible:outline-offset-2",
        ancho, atenuado && "opacity-35", destacado ? "border-azul ring-2 ring-azul/30" : "border-linea")} style={{ outlineColor: color.acento }}>
      <span className="absolute inset-x-0 top-0 h-1.5" style={{ background: color.acento }} aria-hidden />
      <div className="px-4 pb-3 pt-4">
        <h3 className="!text-[15px] font-semibold leading-snug !text-noche">{area.nombre}</h3>
        <div className="mt-2 flex items-center gap-2">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-full text-[11px] font-bold" style={{ background: color.suave, color: color.acento }} aria-hidden>{nombreJefe ? iniciales(nombreJefe) : "?"}</span>
          <div className="min-w-0">
            <p className={cx("truncate text-[13px] font-medium", nombreJefe ? "text-tinta" : "italic text-gris")}>{nombreJefe || "Vacante"}</p>
            <p className="truncate text-xs text-gris">{jefe ? jefe.nombre : "Sin responsable"}{area.cabezas.length > 1 ? ` +${area.cabezas.length - 1}` : ""}</p>
          </div>
        </div>
        <p className="mt-2.5 text-xs text-gris">{plural(area.personas, "persona", "personas")} · {plural(area.puestos.length, "puesto", "puestos")}{area.vacantes > 0 && ` · ${plural(area.vacantes, "vacante", "vacantes")}`}</p>
        {coincidencias.length > 0 && <p className="mt-1 truncate text-xs font-medium text-azul">Coincide: {coincidencias.join(", ")}</p>}
        <p className="mt-2 flex items-center gap-1 text-xs font-semibold opacity-80 transition-opacity group-hover:opacity-100" style={{ color: color.acento }}>
          <ZoomIn className="size-3.5" aria-hidden />Ver organigrama</p>
      </div>
    </button>
  );
}

/** Las áreas y quién depende de quién: cada área en su tarjeta, unidas por líneas. */
function NodoArea({ area, ctx }) {
  const n = area.hijos.length;
  return (
    <div className="inline-flex flex-col items-center">
      <TarjetaArea area={area} onAbrir={ctx.abrirArea} atenuado={ctx.areaAtenuada(area)} destacado={ctx.areaDestacada(area)} coincidencias={ctx.areaCoincidencias(area)} />
      {n > 0 && (
        <>
          <span className="h-7 w-px bg-linea" aria-hidden />
          <div className="flex items-start justify-center">
            {area.hijos.map((h, i) => (
              <div key={h.id} className="relative flex flex-col items-center px-3 pt-7">
                {n > 1 && <span className={cx("absolute top-0 h-px bg-linea", i === 0 ? "left-1/2 right-0" : i === n - 1 ? "left-0 right-1/2" : "inset-x-0")} aria-hidden />}
                <span className="absolute left-1/2 top-0 h-7 w-px bg-linea" aria-hidden />
                <NodoArea area={h} ctx={ctx} />
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

/** Encabezado del organigrama interno de un área: responsable, de quién depende y cifras, con la salida al organigrama general. */
function CabeceraArea({ area, onVolver }) {
  const color = colorDe(area.id);
  return (
    <section aria-label={`Organigrama de ${area.nombre}`} className="no-imprimir mb-4 overflow-hidden rounded-xl border bg-white" style={{ borderColor: color.acento }}>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3" style={{ background: color.suave }}>
        <Boton variante="secundario" tam="sm" icono={ArrowLeft} onClick={onVolver}>Organigrama general</Boton>
        <h2 className="!text-lg font-semibold" style={{ color: color.acento }}>{area.nombre}</h2>
        <p className="text-sm text-tinta">{plural(area.personas, "persona", "personas")} · {plural(area.puestos.length, "puesto", "puestos")}{area.vacantes > 0 && ` · ${plural(area.vacantes, "vacante", "vacantes")}`}</p>
      </div>
      <dl className="grid gap-x-6 gap-y-3 px-4 py-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-xs font-medium text-gris">{area.cabezas.length > 1 ? "Responsables del área" : "Responsable del área"}</dt>
          {area.cabezas.map((c) => (
            <dd key={c.id} className="mt-0.5"><span className="font-medium text-tinta">{c.personas.length ? c.personas.map((p) => p.nombre).join(" · ") : <em className="text-gris">Vacante</em>}</span>
              <span className="text-gris"> · {c.nombre}</span></dd>
          ))}
        </div>
        <div>
          <dt className="text-xs font-medium text-gris">Depende de</dt>
          <dd className="mt-0.5 text-tinta">{area.depende ? <>{area.depende.puesto} <span className="text-gris">· {area.depende.area}</span></> : <span className="text-gris">Es el nivel más alto de la empresa</span>}</dd>
        </div>
      </dl>
    </section>
  );
}

// ── Resumen de un departamento: todas sus personas y puestos, estén en la rama que estén ────────────────────────────
function PanelDepartamento({ departamento, nodos, onIr, onQuitar }) {
  const color = colorDe(departamento.id);
  const puestos = nodos.filter((n) => n.departamento_id === departamento.id);
  const personas = puestos.reduce((a, n) => a + n.personas.length, 0);
  const vacantes = puestos.filter((n) => !n.personas.length).length;
  return (
    <section aria-label={`Equipo de ${departamento.nombre}`} className="no-imprimir mb-4 overflow-hidden rounded-xl border bg-white" style={{ borderColor: color.acento }}>
      <header className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3" style={{ background: color.suave }}>
        <h2 className="!text-base font-semibold" style={{ color: color.acento }}>{departamento.nombre}</h2>
        <p className="text-sm text-tinta">{plural(personas, "persona", "personas")} · {plural(puestos.length, "puesto", "puestos")}{vacantes > 0 && ` · ${plural(vacantes, "vacante", "vacantes")}`}</p>
        <button type="button" onClick={onQuitar} className="ml-auto rounded px-2 py-1 text-xs font-medium text-azul hover:underline">Quitar filtro</button>
      </header>
      <ul className="grid gap-2 p-3 sm:grid-cols-2 lg:grid-cols-3">
        {puestos.map((n) => (
          <li key={n.id}>
            <button type="button" onClick={() => onIr(n.id)} className="h-full w-full rounded-lg border border-linea px-3 py-2 text-left transition-colors hover:border-azul/40 hover:bg-fondo" aria-label={`Ir a ${n.nombre}`}>
              <p className="text-xs font-medium text-gris">{n.nombre}</p>
              {n.personas.length ? <p className="mt-0.5 text-sm font-medium text-tinta">{n.personas.map((p) => p.nombre).join(" · ")}</p> : <p className="mt-0.5 text-sm italic text-gris">Vacante</p>}
            </button>
          </li>
        ))}
      </ul>
    </section>
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
          {ctx.funciones && nodo.funciones && <p className="mt-1 line-clamp-3 text-xs text-gris">{nodo.funciones}</p>}
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
  // «areas»: el organigrama general por áreas, que se abren con zoom · «completo»: todos los puestos en un gráfico · «lista»
  const [vista, setVista] = useState("areas");
  const [movil] = useState(() => window.matchMedia("(max-width: 767px)").matches);
  const [params, setParams] = useSearchParams();
  const areaId = Number(params.get("area")) || null; // el área abierta va en la dirección: al recargar o volver atrás sigues donde estabas
  const [zoom, setZoom] = useState(null); // acercamiento en curso hacia la tarjeta elegida
  const [movimiento, setMovimiento] = useState(null); // «entrar» (al abrir un área) o «volver»
  const contenedor = useRef(null);

  useEffect(() => { organigrama().then(setDatos).catch((e) => setError(e.message)); }, []);

  const todos = useMemo(() => (datos ? aplanar(datos.raices) : []), [datos]);
  const padres = useMemo(() => { const m = new Map(); todos.forEach((n) => n.hijos.forEach((h) => m.set(h.id, n.id))); return m; }, [todos]);
  const departamentos = useMemo(() => {
    const m = new Map();
    todos.forEach((n) => { if (!m.has(n.departamento_id)) m.set(n.departamento_id, { id: n.departamento_id, nombre: n.departamento, puestos: 0, personas: 0 }); const d = m.get(n.departamento_id); d.puestos += 1; d.personas += n.personas.length; });
    return [...m.values()].sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
  }, [todos]);
  const { areas, raices: raicesAreas } = useMemo(() => construirAreas(todos), [todos]);
  const area = areaId ? areas.get(areaId) || null : null;
  const enAreas = vista === "areas";
  const total = useMemo(() => ({ puestos: todos.length, personas: todos.reduce((a, n) => a + n.personas.length, 0), vacantes: todos.filter((n) => !n.personas.length).length }), [todos]);

  const t = normal(buscar.trim());
  const coincidencias = t ? todos.filter((n) => coincideNodo(n, t)).length : 0;

  const sinMovimiento = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const irAArea = useCallback((id) => setParams((p) => { const n = new URLSearchParams(p); if (id) n.set("area", id); else n.delete("area"); return n; }), [setParams]);
  // Al elegir un área la vista se acerca a su tarjeta (zoom) y se muestra su organigrama interno
  const abrirArea = useCallback((id, tarjeta) => {
    setMovimiento("entrar");
    const caja = contenedor.current?.firstElementChild;
    if (!tarjeta || !caja || sinMovimiento()) { irAArea(id); window.scrollTo({ top: 0 }); return; }
    const c = caja.getBoundingClientRect(), r = tarjeta.getBoundingClientRect();
    setZoom({ x: r.left + r.width / 2 - c.left, y: r.top + r.height / 2 - c.top });
    setTimeout(() => { irAArea(id); setZoom(null); }, 420);
  }, [irAArea]);
  const volverAlGeneral = useCallback(() => { setMovimiento("volver"); irAArea(null); }, [irAArea]);
  const cambiarVista = (v) => { setVista(v); setDepto(null); if (v !== "areas") irAArea(null); setMovimiento(null); };
  const alternar = useCallback((id) => setCerrados((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; }), []);
  const ctx = useMemo(() => ({
    admin: esAdmin, alternar,
    // Con una búsqueda activa se abren las ramas que contienen coincidencias; si no, manda lo que la persona contrajo
    abierto: (n) => (t ? ramaCoincide(n, t) : !cerrados.has(n.id)),
    atenuado: (n) => (t ? !ramaCoincide(n, t) : depto != null && n.departamento_id !== depto),
    destacado: (n) => (t ? coincideNodo(n, t) : false),
    funciones: enAreas && !!area, // dentro de un área se muestran las funciones de cada cargo
    abrirArea,
    areaDestacada: (a) => !!t && a.puestos.some((n) => coincideNodo(n, t)),
    areaAtenuada: (a) => !!t && !a.puestos.some((n) => coincideNodo(n, t)),
    areaCoincidencias: (a) => (t ? a.puestos.filter((n) => coincideNodo(n, t)).flatMap((n) => (n.personas.length ? n.personas.map((p) => p.nombre) : [n.nombre])).slice(0, 3) : []),
  }), [esAdmin, alternar, t, cerrados, depto, enAreas, area, abrirArea]);

  // Ajusta el gráfico al ancho disponible (sin bajar de `minimo`, para que el texto siga leyéndose)
  const ajustar = useCallback((minimo = 0.4) => {
    const caja = contenedor.current;
    const interior = caja?.querySelector("[data-lienzo]");
    if (!caja || !interior) return;
    setEscala(1);
    requestAnimationFrame(() => setEscala(Math.max(minimo, Math.min(1, (caja.clientWidth - 48) / interior.scrollWidth))));
  }, []);
  // Al abrir, el gráfico entra completo en pantalla si se puede leer (mínimo 60 %)
  useEffect(() => {
    if (!datos || vista === "lista") return undefined;
    const t = setTimeout(() => ajustar(0.6), 80);
    return () => clearTimeout(t);
  }, [datos, vista, areaId, ajustar]);
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
    const id = setTimeout(() => irA(`[data-depto="${depto}"]`), 120);
    return () => clearTimeout(id);
  }, [depto, irA, vista]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!t) return undefined;
    const id = setTimeout(() => irA('[data-coincide="1"]'), 350); // espera a que se abran las ramas con coincidencias
    return () => clearTimeout(id);
  }, [t, irA]);

  const expandirTodo = () => setCerrados(new Set());
  const raicesVista = area ? area.cabezas.map((c) => podar(c, area.id)) : datos?.raices || [];
  const verLista = vista === "lista" || (enAreas && movil && !!area);
  const animacion = zoom
    ? { transformOrigin: `${zoom.x}px ${zoom.y}px`, transform: "scale(2.6)", opacity: 0, transition: "transform .42s cubic-bezier(.55,0,.75,.45), opacity .42s ease-in" }
    : movimiento ? { animation: `${movimiento === "volver" ? "zoom-volver" : "zoom-entrar"} .42s cubic-bezier(.2,.7,.2,1)` } : undefined;

  if (error) return <Alerta>{error}</Alerta>;
  if (!datos) return <Cargando />;
  if (!datos.raices.length) return <Vacio icono={Network} titulo="Todavía no hay puestos">Los puestos y a quién reportan se crean en Departamentos y puestos.</Vacio>;

  return (
    <div>
      <header className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-[26px] font-semibold leading-tight md:text-3xl">Organigrama</h1>
          <p className="mt-1 max-w-[70ch] text-gris">Quién reporta a quién. El supervisor de cada persona es quien ocupa el puesto del que depende: asigna y valida sus tareas.</p>
        </div>
        <Boton variante="secundario" icono={Printer} onClick={() => window.print()} className="no-imprimir">Imprimir</Boton>
      </header>

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
            <div className="inline-flex rounded-lg border border-linea bg-fondo p-0.5" role="group" aria-label="Tipo de vista">
              {[["areas", "Por áreas"], ["completo", "Completo"], ["lista", "Lista"]].map(([v, txt]) => (
                <button key={v} type="button" onClick={() => cambiarVista(v)} aria-pressed={vista === v}
                  className={cx("rounded-md px-3 py-1.5 text-sm font-medium transition-colors", vista === v ? "bg-white text-noche shadow-sm" : "text-gris hover:text-tinta")}>{txt}</button>
              ))}
            </div>
            <div className="inline-flex items-center gap-1" role="group" aria-label="Contraer o expandir">
              <Boton variante="fantasma" tam="sm" onClick={expandirTodo}>Expandir todo</Boton>
              <Boton variante="fantasma" tam="sm" onClick={() => setCerrados(new Set(todos.filter((n) => n.hijos.length && !datos.raices.some((r) => r.id === n.id)).map((n) => n.id)))}>Contraer</Boton>
            </div>
            {!verLista && !(enAreas && movil) && (
              <div className="inline-flex items-center gap-1 rounded-lg border border-linea px-1" role="group" aria-label="Zoom">
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
            const activo = enAreas ? areaId === d.id : depto === d.id;
            return (
              <button key={d.id} type="button" onClick={() => (enAreas ? (activo ? volverAlGeneral() : abrirArea(d.id)) : setDepto(activo ? null : d.id))} aria-pressed={activo}
                className={cx("inline-flex h-8 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-3 text-xs font-medium transition-colors", activo ? "text-white" : "bg-white text-tinta hover:bg-fondo")}
                style={activo ? { background: c.acento, borderColor: c.acento } : { borderColor: "#e3e8f1" }}>
                <span className="size-2 rounded-full" style={{ background: activo ? "#fff" : c.acento }} aria-hidden />
                {d.nombre}<span className="num opacity-70">{d.personas}</span>
              </button>
            );
          })}
          {!enAreas && depto != null && <button type="button" onClick={() => setDepto(null)} className="shrink-0 whitespace-nowrap rounded px-2 text-xs font-medium text-azul hover:underline">Quitar filtro</button>}
        </div>
      </div>

      {enAreas && area && <CabeceraArea area={area} onVolver={volverAlGeneral} />}
      {enAreas && !area && !t && <p className="no-imprimir mb-3 text-sm text-gris">Toca un área para acercarte a su organigrama: su responsable, sus cargos y su equipo.</p>}

      {!enAreas && depto != null && (
        <PanelDepartamento departamento={departamentos.find((d) => d.id === depto) || { id: depto, nombre: "Departamento" }} nodos={todos}
          onIr={(id) => irA(`[data-nodo="${id}"]`)} onQuitar={() => setDepto(null)} />
      )}

      {verLista ? (
        <ul className="space-y-3" style={animacion}>{raicesVista.map((r) => <ItemLista key={r.id} nodo={r} nivel={0} ctx={ctx} />)}</ul>
      ) : enAreas && !area && movil ? (
        <ul className="grid gap-3 sm:grid-cols-2" style={animacion}>
          {[...areas.values()].sort((a, b) => a.nombre.localeCompare(b.nombre, "es")).map((a) => (
            <li key={a.id}><TarjetaArea area={a} onAbrir={abrirArea} atenuado={ctx.areaAtenuada(a)} destacado={ctx.areaDestacada(a)} coincidencias={ctx.areaCoincidencias(a)} ancho="w-full" /></li>
          ))}
        </ul>
      ) : (
        <div ref={contenedor} className="overflow-auto rounded-xl border border-linea bg-[radial-gradient(circle,#dfe5f1_1px,transparent_1px)] [background-size:22px_22px] bg-white p-6 print:overflow-visible print:border-0">
          <div key={area ? `area-${area.id}` : "general"} style={animacion} onAnimationEnd={() => setMovimiento(null)}>
            <Lienzo escala={escala}>
              <div className="space-y-12">
                {enAreas && !area
                  ? raicesAreas.map((a) => <NodoArea key={a.id} area={a} ctx={ctx} />)
                  : raicesVista.map((r) => <Arbol key={r.id} raiz={r} ctx={ctx} />)}
              </div>
            </Lienzo>
          </div>
        </div>
      )}
    </div>
  );
}
