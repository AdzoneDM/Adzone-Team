// Conversación de una orden o un proyecto. Escribe @ para mencionar a alguien: le llega el aviso.
import { useMemo, useRef, useState } from "react";
import { AtSign, Send } from "lucide-react";
import { hace } from "@/lib/formato";
import { useRecurso } from "@/lib/recursos";
import { Avatar, Boton, cx } from "@/components/ui";

function Texto({ texto }) {
  return texto.split(/(@[\w.-]+)/g).map((parte, i) =>
    parte.startsWith("@") ? <span key={i} className="rounded bg-azul/10 px-1 font-medium text-azul">{parte}</span> : parte);
}

export default function Comentarios({ lista, onEnviar }) {
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  const [gente] = useRecurso("directorio");
  const ref = useRef(null);
  const consulta = useMemo(() => {
    const m = /@([\w.-]*)$/.exec(texto.slice(0, ref.current?.selectionStart ?? texto.length));
    return m ? m[1].toLowerCase() : null;
  }, [texto]);
  const sugeridos = consulta == null ? [] : (gente || []).filter((g) =>
    g.username.toLowerCase().includes(consulta) || g.nombre.toLowerCase().includes(consulta)).slice(0, 5);

  const elegir = (g) => {
    const pos = ref.current?.selectionStart ?? texto.length;
    const antes = texto.slice(0, pos).replace(/@([\w.-]*)$/, `@${g.username} `);
    setTexto(antes + texto.slice(pos));
    ref.current?.focus();
  };
  const enviar = async (e) => {
    e.preventDefault();
    if (!texto.trim()) return;
    setEnviando(true); setError("");
    try { await onEnviar(texto.trim()); setTexto(""); } catch (err) { setError(err.message); }
    setEnviando(false);
  };

  return (
    <div className="space-y-4">
      {lista.length === 0 ? <p className="text-sm text-gris">Todavía no hay comentarios. Pregunta, aclara o deja un enlace aquí: queda todo junto.</p> : (
        <ul className="space-y-3">
          {lista.map((c) => (
            <li key={c.id} className={cx("flex gap-2.5", c.es_mio && "flex-row-reverse")}>
              <Avatar nombre={c.autor_nombre} tam="sm" />
              <div className={cx("max-w-[85%] rounded-2xl px-3.5 py-2.5", c.es_mio ? "rounded-tr-sm bg-azul/8" : "rounded-tl-sm bg-fondo")}>
                <p className="text-xs text-gris"><span className="font-medium text-tinta">{c.autor_nombre}</span> · {hace(c.fecha)}</p>
                <p className="mt-0.5 whitespace-pre-line break-words text-[15px]"><Texto texto={c.texto} /></p>
              </div>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={enviar} className="relative">
        {sugeridos.length > 0 && (
          <ul className="absolute bottom-full left-0 z-10 mb-1 w-72 overflow-hidden rounded-xl border border-linea bg-white shadow-lg" role="listbox" aria-label="Mencionar a">
            {sugeridos.map((g) => (
              <li key={g.id}>
                <button type="button" onMouseDown={(e) => { e.preventDefault(); elegir(g); }} className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-fondo">
                  <Avatar nombre={g.nombre} tam="sm" />
                  <span className="min-w-0"><span className="block truncate text-sm font-medium">{g.nombre}</span><span className="block truncate text-xs text-gris">@{g.username}{g.puesto ? ` · ${g.puesto}` : ""}</span></span>
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="flex items-end gap-2 rounded-xl border border-linea bg-white p-2 focus-within:border-azul focus-within:ring-2 focus-within:ring-azul/20">
          <textarea ref={ref} rows={2} value={texto} onChange={(e) => setTexto(e.target.value)} aria-label="Escribe un comentario"
            onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) enviar(e); }}
            placeholder="Escribe un comentario… usa @ para mencionar" className="min-h-11 flex-1 resize-none border-0 bg-transparent px-1.5 py-1 text-[15px] focus:outline-none" />
          <button type="button" onClick={() => { setTexto((t) => t + (t && !t.endsWith(" ") ? " @" : "@")); ref.current?.focus(); }}
            className="rounded-lg p-2 text-gris hover:bg-fondo hover:text-azul" aria-label="Mencionar a alguien"><AtSign className="size-5" /></button>
          <Boton type="submit" icono={Send} cargando={enviando} disabled={!texto.trim()} aria-label="Enviar comentario" className="px-3" />
        </div>
        {error && <p className="mt-1 text-sm text-rojo">{error}</p>}
      </form>
    </div>
  );
}
