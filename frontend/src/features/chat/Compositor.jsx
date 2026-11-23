import { useEffect, useRef, useState } from "react";
import { FileText, Paperclip, SendHorizontal, X } from "lucide-react";
import { limites } from "@/lib/archivos";
import { cx } from "@/components/ui";

const LIMITE = 2000;
const MAX_ARCHIVO = 15 * 1024 * 1024;
const PERMITIDOS = /\.(jpe?g|png|webp|gif|pdf|docx?|xlsx?|pptx?|txt|csv|zip|odt|ods|mp4|mov|m4v|webm|avi|mkv|3gp|mpe?g)$/i;
const esVideo = (f) => (f.type || "").startsWith("video/") || /\.(mp4|mov|m4v|webm|avi|mkv|3gp|mpe?g)$/i.test(f.name);
const tamano = (b) => (b < 1024 * 1024 ? `${Math.max(1, Math.round(b / 1024))} KB` : `${(b / 1024 / 1024).toFixed(1)} MB`);

/** Caja para escribir. Enter envía; Mayús+Enter hace un salto de línea. El clip adjunta un documento, una imagen (hasta 15 MB) o un video. */
export default function Compositor({ enviando, onEnviar, autoFoco }) {
  const [texto, setTexto] = useState("");
  const [archivo, setArchivo] = useState(null);
  const [vista, setVista] = useState(null); // miniatura de la imagen elegida
  const [aviso, setAviso] = useState("");
  const [arrastrando, setArrastrando] = useState(false);
  const ref = useRef(null);
  const entrada = useRef(null);

  useEffect(() => { if (autoFoco) ref.current?.focus(); }, [autoFoco]);

  // Crece con el texto, hasta un máximo
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 220)}px`;
  }, [texto]);

  // Miniatura de la imagen antes de enviarla (se libera al cambiar o cerrar)
  useEffect(() => {
    if (!archivo || !(archivo.type.startsWith("image/") || esVideo(archivo))) { setVista(null); return undefined; }
    const url = URL.createObjectURL(archivo);
    setVista(url);
    return () => URL.revokeObjectURL(url);
  }, [archivo]);

  // Un archivo elegido con el clip, pegado (Ctrl + V / captura de pantalla) o arrastrado a la conversación
  const aceptar = (f0) => {
    if (!f0) return;
    // Una captura pegada llega como «image.png»: se le da un nombre útil (y la hora para que no se repita)
    const f = /^image\.(png|jpe?g|gif|webp)$/i.test(f0.name) ? new File([f0], `captura-${new Date().toTimeString().slice(0, 8).replace(/:/g, "")}.${f0.type.split("/")[1] === "jpeg" ? "jpg" : f0.type.split("/")[1] || "png"}`, { type: f0.type }) : f0;
    if (!PERMITIDOS.test(f.name)) return setAviso("Solo imágenes, videos y documentos (PDF, Word, Excel, PowerPoint, texto, CSV o ZIP).");
    if (esVideo(f) ? f.size > limites.videoMB * 1024 * 1024 : f.size > MAX_ARCHIVO) {
      return setAviso(esVideo(f) ? `El video pesa más de ${limites.videoMB} MB. Para uno más largo, súbelo a Drive y pega el enlace.` : "El archivo pesa más de 15 MB.");
    }
    setAviso("");
    setArchivo(f);
    ref.current?.focus();
  };
  const elegir = (e) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    aceptar(f);
  };
  const alPegar = (e) => {
    const f = Array.from(e.clipboardData?.files || []).find((x) => x.size > 0);
    if (!f) return; // texto normal: se pega como siempre
    e.preventDefault();
    aceptar(f);
  };
  const alSoltar = (e) => {
    const f = e.dataTransfer?.files?.[0];
    if (!f) return;
    e.preventDefault();
    setArrastrando(false);
    aceptar(f);
  };

  const puedeEnviar = (texto.trim() || archivo) && !enviando;
  const enviar = async () => {
    const limpio = texto.trim();
    if (!puedeEnviar) return;
    if (await onEnviar(limpio, archivo)) { setTexto(""); setArchivo(null); setAviso(""); }
    ref.current?.focus();
  };

  const alTeclear = (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); enviar(); }
  };

  const cerca = texto.length > LIMITE - 200;
  return (
    <form onSubmit={(e) => { e.preventDefault(); enviar(); }} className={cx("border-t border-linea bg-white p-3 transition-colors", arrastrando && "bg-azul/5 ring-2 ring-inset ring-azul/40")}
      onDragOver={(e) => { if (e.dataTransfer?.types?.includes("Files")) { e.preventDefault(); setArrastrando(true); } }} onDragLeave={() => setArrastrando(false)} onDrop={alSoltar}>
      {archivo && (
        <div className="mb-2 flex items-center gap-3 rounded-xl border border-linea bg-fondo p-2">
          {vista ? (esVideo(archivo) ? <video src={vista} muted playsInline preload="metadata" className="size-20 rounded-lg bg-black object-cover" aria-label={archivo.name} /> : <img src={vista} alt="Vista previa" className="size-20 rounded-lg object-cover" />)
            : <span className="flex size-20 items-center justify-center rounded-lg bg-white text-azul"><FileText className="size-6" aria-hidden /></span>}
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-tinta">{archivo.name}</p>
            <p className="text-xs text-gris">{tamano(archivo.size)} · se envía con tu mensaje · <button type="button" onClick={() => setArchivo(null)} className="font-medium text-rojo hover:underline">Cancelar</button></p>
          </div>
          <button type="button" onClick={() => setArchivo(null)} aria-label="Quitar el archivo" className="rounded-lg p-2 text-gris hover:bg-white hover:text-rojo"><X className="size-4" aria-hidden /></button>
        </div>
      )}
      {aviso && <p role="alert" className="mb-2 text-xs text-rojo">{aviso}</p>}
      <div className="flex items-end gap-2">
        <input ref={entrada} type="file" className="hidden" onChange={elegir} aria-label="Elegir un archivo"
          accept="image/*,video/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.zip,.odt,.ods" />
        <button type="button" onClick={() => entrada.current?.click()} aria-label="Adjuntar un documento, una imagen o un video" title="Adjuntar un documento, una imagen o un video"
          className={cx("flex size-10 shrink-0 items-center justify-center rounded-lg text-gris transition-colors hover:bg-fondo hover:text-azul", archivo && "text-azul")}>
          <Paperclip className="size-5" aria-hidden />
        </button>
        <textarea ref={ref} value={texto} onChange={(e) => setTexto(e.target.value)} onKeyDown={alTeclear} onPaste={alPegar} rows={2} maxLength={LIMITE}
          placeholder={archivo ? "Agrega un mensaje (opcional)…" : "Escribe un mensaje o pega una imagen (Ctrl + V)…"} aria-label="Mensaje" enterKeyHint="send"
          className="campo max-h-[220px] min-h-[3.25rem] flex-1 resize-none !py-2.5" />
        <button type="submit" disabled={!puedeEnviar} aria-label="Enviar mensaje"
          className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-azul text-white transition-colors hover:bg-azul-700 disabled:cursor-not-allowed disabled:opacity-40">
          <SendHorizontal className="size-5" aria-hidden />
        </button>
      </div>
      {cerca && <p className="mt-1 text-right text-xs text-gris num">{texto.length}/{LIMITE}</p>}
    </form>
  );
}
