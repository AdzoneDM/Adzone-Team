// Columna izquierda del chat (como los mensajes de Instagram): buscador y lista de conversaciones.
// Al escribir en el buscador también aparecen los compañeros, para abrir un chat nuevo sin cambiar de pantalla.
import { useEffect, useState } from "react";
import { Plus, Search, Users, X } from "lucide-react";
import { chatPersonas } from "@/lib/api";
import { Avatar, cx } from "@/components/ui";

function cuando(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const hoy = new Date();
  if (d.toDateString() === hoy.toDateString()) return d.toLocaleTimeString("es-DO", { hour: "numeric", minute: "2-digit" });
  const ayer = new Date(); ayer.setDate(hoy.getDate() - 1);
  if (d.toDateString() === ayer.toDateString()) return "Ayer";
  return d.toLocaleDateString("es-DO", { day: "numeric", month: "short" });
}

const sinTildes = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

function FilaConversacion({ c, usuarioId, activa, onAbrir }) {
  const global = c.tipo === "GLOBAL";
  const grupo = c.tipo === "GRUPO";
  const previa = c.ultimo_texto ? `${c.ultimo_autor === usuarioId ? "Tú: " : ""}${c.ultimo_texto}`
    : global ? "Conversación de todo el equipo" : grupo ? `Grupo · ${c.grupo?.n_miembros ?? ""} personas${c.grupo?.departamento ? ` · ${c.grupo.departamento}` : ""}` : (c.persona?.puesto ?? "");
  return (
    <li>
      <button type="button" onClick={() => onAbrir(c)} aria-current={activa ? "true" : undefined}
        className={cx("flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-fondo focus-visible:bg-fondo", activa && "bg-azul/[0.07]")}>
        {global
          ? <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-amarillo text-tinta" aria-hidden><Users className="size-5" /></span>
          : grupo ? <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-azul text-white" aria-hidden><Users className="size-5" /></span>
            : <Avatar nombre={c.titulo} className="!size-11" />}
        <span className="min-w-0 flex-1">
          <span className="flex items-baseline justify-between gap-2">
            <span className={cx("truncate text-sm text-tinta", c.no_leidos ? "font-semibold" : "font-medium")}>{c.titulo}</span>
            <time className="shrink-0 text-[11px] text-gris">{cuando(c.ultima_actividad)}</time>
          </span>
          <span className="flex items-center justify-between gap-2">
            <span className={cx("truncate text-[13px]", c.no_leidos ? "font-medium text-tinta" : "text-gris")}>{previa}</span>
            {c.no_leidos > 0 && <span className="min-w-5 shrink-0 rounded-full bg-rojo px-1.5 text-center text-[11px] font-semibold leading-5 text-white num" aria-label={`${c.no_leidos} sin leer`}>{c.no_leidos > 99 ? "99+" : c.no_leidos}</span>}
          </span>
        </span>
      </button>
    </li>
  );
}

export default function PanelChats({ conversaciones, cargando, usuarioId, activaId, onAbrir, onPersona, puedeCrearGrupos = false, onNuevoGrupo }) {
  const [texto, setTexto] = useState("");
  const [personas, setPersonas] = useState([]);
  const [estado, setEstado] = useState("listo"); // listo | cargando | error
  const buscando = texto.trim().length > 0;

  // Compañeros que coinciden (nombre, usuario, cargo o área), con una pausa corta para no consultar en cada tecla
  useEffect(() => {
    if (!buscando) { setPersonas([]); setEstado("listo"); return undefined; }
    const control = new AbortController();
    setEstado("cargando");
    const t = setTimeout(async () => {
      try {
        setPersonas(await chatPersonas(texto.trim(), control.signal));
        setEstado("listo");
      } catch (e) {
        if (e.name !== "AbortError") setEstado("error");
      }
    }, 250);
    return () => { clearTimeout(t); control.abort(); };
  }, [texto, buscando]);

  const coincidentes = buscando ? conversaciones.filter((c) => sinTildes(c.titulo).includes(sinTildes(texto.trim()))) : conversaciones;
  const elegir = (p) => { setTexto(""); onPersona(p); };

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-white">
      <div className="space-y-2 border-b border-linea p-3">
        {puedeCrearGrupos && (
          <button type="button" onClick={onNuevoGrupo} className="flex w-full items-center justify-center gap-2 rounded-full border border-dashed border-azul/40 bg-azul/5 px-3 py-2 text-sm font-medium text-azul hover:bg-azul/10">
            <Plus className="size-4" aria-hidden />Nuevo grupo
          </button>
        )}
        <label className="relative block">
          <span className="sr-only">Buscar un compañero o una conversación</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" aria-hidden />
          <input type="text" value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Buscar compañero o chat…" className="campo !rounded-full !bg-fondo !pl-9 !pr-9" autoComplete="off" />
          {buscando && (
            <button type="button" onClick={() => setTexto("")} aria-label="Borrar la búsqueda" className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full p-1 text-gris hover:bg-linea">
              <X className="size-4" aria-hidden />
            </button>
          )}
        </label>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {cargando && conversaciones.length === 0 && <p className="px-4 py-8 text-center text-sm text-gris">Cargando…</p>}
        {coincidentes.length > 0 && (
          <ul>
            {buscando && <li className="px-3 pb-1 pt-3 text-xs font-semibold text-gris">Tus conversaciones</li>}
            {coincidentes.map((c) => <FilaConversacion key={c.id} c={c} usuarioId={usuarioId} activa={c.id === activaId} onAbrir={onAbrir} />)}
          </ul>
        )}

        {buscando && (
          <ul>
            <li className="px-3 pb-1 pt-3 text-xs font-semibold text-gris">Compañeros</li>
            {personas.map((p) => (
              <li key={p.id}>
                <button type="button" onClick={() => elegir(p)} className="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-fondo focus-visible:bg-fondo">
                  <Avatar nombre={p.nombre} className="!size-11" />
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium text-tinta">{p.nombre}</span>
                    <span className="block truncate text-xs text-gris">{[p.puesto, p.departamento].filter(Boolean).join(" · ") || "Sin puesto asignado"}</span>
                  </span>
                </button>
              </li>
            ))}
            {estado === "listo" && personas.length === 0 && <li className="px-4 py-4 text-center text-sm text-gris">No hay compañeros con «{texto.trim()}».</li>}
            {estado === "cargando" && personas.length === 0 && <li className="px-4 py-4 text-center text-sm text-gris">Buscando…</li>}
            {estado === "error" && <li role="alert" className="px-4 py-4 text-center text-sm text-rojo">No se pudo buscar. Inténtalo de nuevo.</li>}
          </ul>
        )}

        {!buscando && !cargando && conversaciones.length <= 1 && (
          <p className="px-6 py-6 text-center text-sm text-gris">Escribe un nombre arriba para empezar un chat privado con un compañero.</p>
        )}
      </div>
    </div>
  );
}
