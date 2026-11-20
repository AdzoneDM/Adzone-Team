// Buscador de «Mi equipo» con autocompletado: al escribir sugiere personas del equipo y tareas (de cualquier mes).
// Elegir una persona muestra sus tareas; elegir una tarea la abre; Enter busca el texto en todas las tareas.
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { ClipboardList, CornerDownLeft, Search, UserRound, X } from "lucide-react";
import { listarTareas } from "@/lib/api";
import { fechaCorta } from "@/lib/formato";
import { ESTADOS } from "@/lib/formato";
import { Avatar, cx } from "@/components/ui";

const normal = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** Pone en negrita lo que coincide con lo escrito (sin distinguir mayúsculas ni tildes). */
function Resaltado({ texto, consulta }) {
  const q = normal(consulta.trim());
  if (!q) return texto;
  const base = [...texto].map((c) => c.normalize("NFD")[0]).join("").toLowerCase();
  const i = base.indexOf(q);
  if (i < 0) return texto;
  return <>{texto.slice(0, i)}<mark className="rounded bg-amarillo/50 px-0.5 text-inherit">{texto.slice(i, i + q.length)}</mark>{texto.slice(i + q.length)}</>;
}

export default function BuscadorEquipo({ gente, onPersona, onTarea, onBuscar, className }) {
  const id = useId();
  const [texto, setTexto] = useState("");
  const [abierto, setAbierto] = useState(false);
  const [activo, setActivo] = useState(-1);
  const [tareas, setTareas] = useState([]);
  const [cargando, setCargando] = useState(false);
  const turno = useRef(0);
  const q = texto.trim();

  // Tareas que coinciden (de cualquier mes), con una pausa corta para no consultar en cada tecla
  useEffect(() => {
    if (q.length < 2) { setTareas([]); setCargando(false); return undefined; }
    const mio = ++turno.current;
    setCargando(true);
    const t = setTimeout(() => {
      listarTareas({ ambito: "equipo", buscar: q })
        .then((r) => { if (mio === turno.current) setTareas((r || []).slice(0, 6)); })
        .catch(() => { if (mio === turno.current) setTareas([]); })
        .finally(() => { if (mio === turno.current) setCargando(false); });
    }, 220);
    return () => clearTimeout(t);
  }, [q]);

  const personas = useMemo(() => {
    if (!q) return [];
    const n = normal(q);
    return (gente || []).filter((g) => !g.es_yo && [g.nombre, g.puesto, g.departamento].some((x) => normal(x).includes(n))).slice(0, 5);
  }, [gente, q]);

  // Lista plana de opciones, en el orden en que se ven (para el teclado)
  const opciones = useMemo(() => {
    if (!q) return [];
    return [
      ...personas.map((p) => ({ clave: `p${p.id}`, tipo: "persona", dato: p })),
      ...tareas.map((t) => ({ clave: `t${t.id}`, tipo: "tarea", dato: t })),
      { clave: "buscar", tipo: "buscar", dato: q },
    ];
  }, [personas, tareas, q]);

  useEffect(() => { setActivo(-1); }, [q, tareas.length]);

  const cerrar = () => { setAbierto(false); setActivo(-1); };
  const elegir = (op) => {
    cerrar();
    if (op.tipo === "persona") { setTexto(""); onPersona(op.dato); }
    else if (op.tipo === "tarea") { setTexto(""); onTarea(op.dato); }
    else { onBuscar(op.dato); setTexto(""); }
  };
  const alTeclear = (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setAbierto(true); setActivo((a) => (opciones.length ? (a + 1) % opciones.length : -1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActivo((a) => (opciones.length ? (a <= 0 ? opciones.length - 1 : a - 1) : -1)); }
    else if (e.key === "Enter") { e.preventDefault(); if (activo >= 0 && opciones[activo]) elegir(opciones[activo]); else if (q) elegir({ tipo: "buscar", dato: q }); }
    else if (e.key === "Escape") { if (abierto) { e.preventDefault(); cerrar(); } else setTexto(""); }
  };

  const idLista = `${id}-lista`;
  const mostrar = abierto && q.length > 0;
  return (
    <div className={cx("relative", className)} onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) cerrar(); }}>
      <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-gris" aria-hidden />
      <input type="text" role="combobox" aria-expanded={mostrar} aria-controls={idLista} aria-autocomplete="list" aria-label="Buscar personas o tareas"
        aria-activedescendant={activo >= 0 ? `${id}-${opciones[activo]?.clave}` : undefined}
        className="campo h-12 !rounded-xl !pl-10 !pr-10 text-[15px]" placeholder="Buscar una persona o una tarea…" autoComplete="off"
        value={texto} onChange={(e) => { setTexto(e.target.value); setAbierto(true); }} onFocus={() => setAbierto(true)} onKeyDown={alTeclear} />
      {texto && <button type="button" onClick={() => { setTexto(""); cerrar(); }} aria-label="Borrar la búsqueda" className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded-full p-1.5 text-gris hover:bg-linea"><X className="size-4" aria-hidden /></button>}

      {mostrar && (
        <ul id={idLista} role="listbox" aria-label="Sugerencias" className="absolute inset-x-0 top-full z-40 mt-1.5 max-h-[70vh] overflow-y-auto rounded-xl border border-linea bg-white p-1.5 shadow-xl">
          {personas.length > 0 && <li role="presentation" className="px-2.5 pb-1 pt-2 text-xs font-semibold text-gris">Personas</li>}
          {opciones.map((op, i) => {
            const base = cx("flex w-full cursor-pointer items-center gap-3 rounded-lg px-2.5 py-2 text-left", i === activo ? "bg-azul/10" : "hover:bg-fondo");
            const encabezadoTareas = op.tipo === "tarea" && opciones[i - 1]?.tipo !== "tarea";
            return (
              <li key={op.clave} role="presentation">
                {encabezadoTareas && <p role="presentation" className="px-2.5 pb-1 pt-2 text-xs font-semibold text-gris">Tareas</p>}
                <div id={`${id}-${op.clave}`} role="option" aria-selected={i === activo} className={base} onMouseDown={(e) => e.preventDefault()} onClick={() => elegir(op)} onMouseEnter={() => setActivo(i)}>
                  {op.tipo === "persona" && (<>
                    <Avatar nombre={op.dato.nombre} tam="sm" />
                    <span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium text-tinta"><Resaltado texto={op.dato.nombre} consulta={q} /></span>
                      <span className="block truncate text-xs text-gris">{[op.dato.puesto, op.dato.departamento].filter(Boolean).join(" · ") || "Sin puesto"}</span></span>
                    <span className="shrink-0 text-xs text-gris">Ver sus tareas</span>
                  </>)}
                  {op.tipo === "tarea" && (<>
                    <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-fondo text-gris"><ClipboardList className="size-4" aria-hidden /></span>
                    <span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium text-tinta"><Resaltado texto={op.dato.titulo} consulta={q} /></span>
                      <span className="block truncate text-xs text-gris">{op.dato.colaborador_nombre} · {ESTADOS[op.dato.estado] || op.dato.estado} · {fechaCorta(op.dato.fecha_limite)}</span></span>
                  </>)}
                  {op.tipo === "buscar" && (<>
                    <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-azul/10 text-azul"><Search className="size-4" aria-hidden /></span>
                    <span className="min-w-0 flex-1 truncate text-sm text-tinta">Buscar «<b>{op.dato}</b>» en todas las tareas</span>
                    <CornerDownLeft className="size-4 shrink-0 text-gris" aria-hidden />
                  </>)}
                </div>
              </li>
            );
          })}
          {cargando && <li role="presentation" className="px-3 py-2 text-xs text-gris">Buscando tareas…</li>}
          {!cargando && personas.length === 0 && tareas.length === 0 && q.length >= 2 && <li role="presentation" className="px-3 py-1.5 text-xs text-gris">No hay personas ni tareas con ese nombre.</li>}
        </ul>
      )}
    </div>
  );
}
