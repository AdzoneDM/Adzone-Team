import { useEffect, useRef, useState } from "react";
import { FileArchive, FileText, Paperclip, SendHorizontal, X } from "lucide-react";
import { limites } from "@/lib/archivos";
import { cx } from "@/components/ui";

const LIMITE = 20000;          // caracteres por mensaje (unas 3 000 palabras); el servidor usa el mismo
const MAX_ARCHIVOS = 10;       // por envío; cada uno sale como su propio mensaje
const MAX_ARCHIVO = 15 * 1024 * 1024;
const PERMITIDOS = /\.(jpe?g|png|webp|gif|pdf|docx?|xlsx?|pptx?|txt|csv|zip|odt|ods|mp4|mov|m4v|webm|avi|mkv|3gp|mpe?g)$/i;
const esVideo = (f) => (f.type || "").startsWith("video/") || /\.(mp4|mov|m4v|webm|avi|mkv|3gp|mpe?g)$/i.test(f.name);
const esZip = (f) => /\.zip$/i.test(f.name);
const tamano = (b) => (b < 1024 * 1024 ? `${Math.max(1, Math.round(b / 1024))} KB` : `${(b / 1024 / 1024).toFixed(1)} MB`);
const miles = (n) => n.toLocaleString("es-DO");

/** Miniatura de un archivo por enviar (foto, video o documento); se puede quitar antes de enviar. */
function Pieza({ archivo, onQuitar }) {
  const [vista, setVista] = useState(null);
  useEffect(() => {
    if (!(archivo.type.startsWith("image/") || esVideo(archivo))) { setVista(null); return undefined; }
    const url = URL.createObjectURL(archivo);
    setVista(url);
    return () => URL.revokeObjectURL(url);
  }, [archivo]);
  return (
    <li className="relative w-24">
      {vista ? (esVideo(archivo)
        ? <video src={vista} muted playsInline preload="metadata" className="size-24 rounded-lg bg-black object-cover" aria-label={archivo.name} />
        : <img src={vista} alt={`Vista previa de ${archivo.name}`} className="size-24 rounded-lg object-cover" />)
        : <span className="flex size-24 flex-col items-center justify-center gap-1 rounded-lg bg-white text-azul ring-1 ring-linea">{esZip(archivo) ? <><FileArchive className="size-8" aria-hidden /><span className="rounded bg-azul/10 px-1.5 text-[10px] font-bold">ZIP</span></> : <FileText className="size-8" aria-hidden />}</span>}
      <button type="button" onClick={onQuitar} aria-label={`Quitar ${archivo.name}`}
        className="absolute -right-1.5 -top-1.5 flex size-6 items-center justify-center rounded-full border-2 border-white bg-tinta text-white hover:bg-rojo"><X className="size-3" aria-hidden /></button>
      <p className="mt-1 truncate text-[11px] leading-tight text-tinta" title={archivo.name}>{archivo.name}</p>
      <p className="text-[11px] leading-tight text-gris">{tamano(archivo.size)}</p>
    </li>
  );
}

/** Caja para escribir. Enter envía; Mayús+Enter hace un salto de línea. El clip adjunta (varios a la vez) documentos, imágenes o videos;
 *  también se pueden pegar con Ctrl + V o arrastrar a la conversación. */
export default function Compositor({ enviando, progreso, onEnviar, autoFoco, participantes = [] }) {
  const [texto, setTexto] = useState("");
  const [archivos, setArchivos] = useState([]);
  const [aviso, setAviso] = useState("");
  const [arrastrando, setArrastrando] = useState(false);
  const ref = useRef(null);
  const entrada = useRef(null);
  const [cursor, setCursor] = useState(0);     // dónde está el cursor: la mención que se escribe es la que queda justo antes
  const [sel, setSel] = useState(0);           // sugerencia resaltada
  const [cerrada, setCerrada] = useState(false); // Esc cierra la lista hasta que se siga escribiendo
  const caretPendiente = useRef(null);

  useEffect(() => { if (autoFoco) ref.current?.focus(); }, [autoFoco]);

  // Crece con el texto (hasta casi media pantalla; después tiene su propia barra) para escribir y revisar mensajes largos
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, Math.max(220, Math.round(window.innerHeight * 0.4)))}px`;
  }, [texto]);

  // Uno o varios archivos elegidos con el clip, pegados (Ctrl + V / captura de pantalla) o arrastrados
  const aceptar = (lista) => {
    const buenos = [];
    let falla = "";
    for (const f0 of lista) {
      if (!f0) continue;
      // Una captura pegada llega como «image.png»: se le da un nombre útil (y la hora para que no se repita)
      const f = /^image\.(png|jpe?g|gif|webp)$/i.test(f0.name)
        ? new File([f0], `captura-${new Date().toTimeString().slice(0, 8).replace(/:/g, "")}-${buenos.length + 1}.${f0.type.split("/")[1] === "jpeg" ? "jpg" : f0.type.split("/")[1] || "png"}`, { type: f0.type }) : f0;
      if (!PERMITIDOS.test(f.name)) { falla = "Solo imágenes, videos y documentos (PDF, Word, Excel, PowerPoint, texto, CSV o ZIP)."; continue; }
      const tope = esVideo(f) ? limites.videoMB : esZip(f) ? limites.zipMB : 15;
      if (f.size > tope * 1024 * 1024) {
        falla = esVideo(f) ? `«${f.name}» pesa más de ${limites.videoMB} MB. Para uno más largo, súbelo a Drive y pega el enlace.`
          : esZip(f) ? `«${f.name}» pesa más de ${limites.zipMB} MB. Para uno más grande, súbelo a Drive y pega el enlace.` : `«${f.name}» pesa más de 15 MB.`;
        continue;
      }
      buenos.push(f);
    }
    const total = [...archivos, ...buenos];
    if (total.length > MAX_ARCHIVOS) falla = `Máximo ${MAX_ARCHIVOS} archivos por envío; se agregaron los primeros.`;
    setAviso(falla);
    if (buenos.length) setArchivos(total.slice(0, MAX_ARCHIVOS));
    ref.current?.focus();
  };
  const elegir = (e) => {
    const lista = Array.from(e.target.files || []);
    e.target.value = "";
    aceptar(lista);
  };
  const alPegar = (e) => {
    const lista = Array.from(e.clipboardData?.files || []).filter((x) => x.size > 0);
    if (!lista.length) return; // texto normal: se pega como siempre
    e.preventDefault();
    aceptar(lista);
  };
  const alSoltar = (e) => {
    const lista = Array.from(e.dataTransfer?.files || []);
    if (!lista.length) return;
    e.preventDefault();
    setArrastrando(false);
    aceptar(lista);
  };

  const puedeEnviar = (texto.trim() || archivos.length) && !enviando;
  const enviar = async () => {
    const limpio = texto.trim();
    if (!puedeEnviar) return;
    // El texto y los archivos se quedan en pantalla mientras se envía; solo se limpian lo que ya salió
    const r = await onEnviar(limpio, archivos);
    if (r.ok) { setTexto(""); setArchivos([]); setAviso(""); }
    else {
      if (r.hechos > 0) { setTexto(""); setArchivos((l) => l.slice(r.hechos)); }
      setAviso(r.mensaje || "No se pudo enviar. Inténtalo de nuevo."); // se queda a la vista (la actualización automática del chat borra el error de arriba)
    }
    ref.current?.focus();
  };

  // Mención en curso: «@bas» justo antes del cursor → personas cuyo nombre, usuario o puesto lo contienen (las que empiezan con eso, primero)
  const sinTilde = (t) => (t || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const consulta = (() => { const m = /(^|\s)@([\w.-]*)$/.exec(texto.slice(0, cursor)); return m ? sinTilde(m[2]) : null; })();
  const sugeridos = consulta == null || cerrada ? [] : participantes
    .map((p) => ({ p, c: [p.nombre, p.usuario, p.puesto].map(sinTilde) }))
    .filter(({ c }) => c.some((x) => x.includes(consulta)))
    .sort((a, b) => Number(b.c[0].startsWith(consulta) || b.c[1].startsWith(consulta)) - Number(a.c[0].startsWith(consulta) || a.c[1].startsWith(consulta)))
    .slice(0, 6).map(({ p }) => p);
  const mencionar = (p) => {
    const antes = texto.slice(0, cursor).replace(/@([\w.-]*)$/, `@${p.usuario} `);
    caretPendiente.current = antes.length;
    setTexto(antes + texto.slice(cursor));
    setCursor(antes.length);
    setSel(0);
    ref.current?.focus();
  };
  useEffect(() => {
    if (caretPendiente.current != null && ref.current) { ref.current.setSelectionRange(caretPendiente.current, caretPendiente.current); caretPendiente.current = null; }
  });

  const alTeclear = (e) => {
    if (sugeridos.length) {
      if (e.key === "ArrowDown") { e.preventDefault(); return setSel((s) => (s + 1) % sugeridos.length); }
      if (e.key === "ArrowUp") { e.preventDefault(); return setSel((s) => (s - 1 + sugeridos.length) % sugeridos.length); }
      if (e.key === "Enter" || e.key === "Tab") { e.preventDefault(); return mencionar(sugeridos[Math.min(sel, sugeridos.length - 1)]); }
      if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); return setCerrada(true); } // cierra solo la lista, no el chat
    }
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); enviar(); }
  };

  const cerca = texto.length > LIMITE * 0.8;
  const palabras = texto.trim() ? texto.trim().split(/\s+/).length : 0;
  return (
    <form onSubmit={(e) => { e.preventDefault(); enviar(); }} className={cx("border-t border-linea bg-white p-3 transition-colors", arrastrando && "bg-azul/5 ring-2 ring-inset ring-azul/40")}
      onDragOver={(e) => { if (e.dataTransfer?.types?.includes("Files")) { e.preventDefault(); setArrastrando(true); } }} onDragLeave={() => setArrastrando(false)} onDrop={alSoltar}>
      {archivos.length > 0 && (
        <div className="mb-2 rounded-xl border border-linea bg-fondo p-2">
          <ul className="flex max-h-48 flex-wrap gap-3 overflow-y-auto p-1">
            {archivos.map((a, i) => <Pieza key={`${a.name}-${a.size}-${i}`} archivo={a} onQuitar={() => setArchivos((l) => l.filter((_, j) => j !== i))} />)}
          </ul>
          <p className="mt-1 flex items-center justify-between gap-2 px-1 text-xs text-gris">
            <span>{archivos.length === 1 ? "1 archivo" : `${archivos.length} archivos`} · cada uno sale como un mensaje{texto.trim() ? " (tu texto va con el primero)" : ""}</span>
            <button type="button" onClick={() => setArchivos([])} className="font-medium text-rojo hover:underline">{archivos.length === 1 ? "Cancelar" : "Quitar todos"}</button>
          </p>
        </div>
      )}
      {sugeridos.length > 0 && (
        <ul className="mb-2 overflow-hidden rounded-xl border border-linea bg-white shadow-lg" role="listbox" aria-label="Mencionar a una persona">
          <li className="border-b border-linea-suave bg-fondo/70 px-3 py-1 text-[11px] font-medium uppercase tracking-wide text-gris">Mencionar · le llega un aviso</li>
          {sugeridos.map((p, i) => (
            <li key={p.id} role="option" aria-selected={i === sel}>
              <button type="button" onMouseDown={(e) => { e.preventDefault(); mencionar(p); }} onMouseEnter={() => setSel(i)}
                className={cx("flex w-full items-center gap-2.5 px-3 py-2 text-left", i === sel ? "bg-azul/10" : "hover:bg-fondo")}>
                <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-azul/10 text-xs font-semibold text-azul" aria-hidden>{(p.nombre || "?").split(" ").map((x) => x[0]).slice(0, 2).join("").toUpperCase()}</span>
                <span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium text-tinta">{p.nombre}</span><span className="block truncate text-xs text-gris">{p.puesto || p.departamento || ""}</span></span>
                <span className="shrink-0 text-xs text-gris">@{p.usuario}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {aviso && <p role="alert" className="mb-2 text-xs text-rojo">{aviso}</p>}
      {progreso && (
        <div className="mb-2 rounded-xl border border-azul/30 bg-azul/5 px-3 py-2" role="status" aria-live="polite">
          <p className="flex items-center justify-between gap-2 text-xs text-azul">
            <span className="truncate font-medium">Enviando {progreso.total > 1 ? `${progreso.actual} de ${progreso.total}: ` : ""}{progreso.nombre}</span>
            <span className="num shrink-0 font-semibold">{progreso.pct === 100 ? "Revisando…" : `${progreso.pct} %`}</span>
          </p>
          <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-azul/15"><div className="h-full rounded-full bg-azul transition-[width] duration-200" style={{ width: `${progreso.pct}%` }} /></div>
        </div>
      )}
      <div className="flex items-end gap-2">
        <input ref={entrada} type="file" multiple className="hidden" onChange={elegir} aria-label="Elegir archivos"
          accept="image/*,video/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.zip,.odt,.ods" />
        <button type="button" onClick={() => entrada.current?.click()} disabled={archivos.length >= MAX_ARCHIVOS} aria-label="Adjuntar documentos, imágenes o videos" title="Adjuntar documentos, imágenes o videos (puedes elegir varios)"
          className={cx("flex size-10 shrink-0 items-center justify-center rounded-lg text-gris transition-colors hover:bg-fondo hover:text-azul disabled:opacity-40", archivos.length > 0 && "text-azul")}>
          <Paperclip className="size-5" aria-hidden />
        </button>
        <textarea ref={ref} value={texto} onChange={(e) => { setTexto(e.target.value); setCursor(e.target.selectionStart); setSel(0); setCerrada(false); }} onKeyDown={alTeclear} onKeyUp={(e) => setCursor(e.target.selectionStart)} onClick={(e) => setCursor(e.target.selectionStart)} onPaste={alPegar} rows={2} maxLength={LIMITE}
          placeholder={archivos.length ? "Agrega un mensaje…" : "Escribe un mensaje o pega imágenes (Ctrl + V)…"} aria-label="Mensaje" enterKeyHint="send"
          className="campo min-h-[3.25rem] flex-1 resize-none !py-2.5" />
        <button type="submit" disabled={!puedeEnviar} aria-label="Enviar mensaje"
          className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-azul text-white transition-colors hover:bg-azul-700 disabled:cursor-not-allowed disabled:opacity-40">
          <SendHorizontal className="size-5" aria-hidden />
        </button>
      </div>
      {(cerca || palabras > 300) && (
        <p className={cx("mt-1 text-right text-xs num", texto.length >= LIMITE ? "font-semibold text-rojo" : "text-gris")}>
          {miles(palabras)} palabras · {miles(texto.length)} / {miles(LIMITE)} caracteres
        </p>
      )}
    </form>
  );
}
