import { useEffect, useRef, useState } from "react";
import { FileText, Paperclip, SendHorizontal, X } from "lucide-react";
import { cx } from "@/components/ui";

const LIMITE = 2000;
const MAX_ARCHIVO = 15 * 1024 * 1024;
const PERMITIDOS = /\.(jpe?g|png|webp|gif|pdf|docx?|xlsx?|pptx?|txt|csv|zip|odt|ods)$/i;
const tamano = (b) => (b < 1024 * 1024 ? `${Math.max(1, Math.round(b / 1024))} KB` : `${(b / 1024 / 1024).toFixed(1)} MB`);

/** Caja para escribir. Enter envía; Mayús+Enter hace un salto de línea. El clip adjunta un documento o una imagen (hasta 15 MB). */
export default function Compositor({ enviando, onEnviar, autoFoco }) {
  const [texto, setTexto] = useState("");
  const [archivo, setArchivo] = useState(null);
  const [vista, setVista] = useState(null); // miniatura de la imagen elegida
  const [aviso, setAviso] = useState("");
  const ref = useRef(null);
  const entrada = useRef(null);

  useEffect(() => { if (autoFoco) ref.current?.focus(); }, [autoFoco]);

  // Crece con el texto, hasta un máximo
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  }, [texto]);

  // Miniatura de la imagen antes de enviarla (se libera al cambiar o cerrar)
  useEffect(() => {
    if (!archivo || !archivo.type.startsWith("image/")) { setVista(null); return undefined; }
    const url = URL.createObjectURL(archivo);
    setVista(url);
    return () => URL.revokeObjectURL(url);
  }, [archivo]);

  const elegir = (e) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    if (!PERMITIDOS.test(f.name)) return setAviso("Solo imágenes y documentos (PDF, Word, Excel, PowerPoint, texto, CSV o ZIP).");
    if (f.size > MAX_ARCHIVO) return setAviso("El archivo pesa más de 15 MB.");
    setAviso("");
    setArchivo(f);
    ref.current?.focus();
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
    <form onSubmit={(e) => { e.preventDefault(); enviar(); }} className="border-t border-linea bg-white p-3">
      {archivo && (
        <div className="mb-2 flex items-center gap-3 rounded-xl border border-linea bg-fondo p-2">
          {vista ? <img src={vista} alt="" className="size-12 rounded-lg object-cover" />
            : <span className="flex size-12 items-center justify-center rounded-lg bg-white text-azul"><FileText className="size-6" aria-hidden /></span>}
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-tinta">{archivo.name}</p>
            <p className="text-xs text-gris">{tamano(archivo.size)} · se envía con tu mensaje</p>
          </div>
          <button type="button" onClick={() => setArchivo(null)} aria-label="Quitar el archivo" className="rounded-lg p-2 text-gris hover:bg-white hover:text-rojo"><X className="size-4" aria-hidden /></button>
        </div>
      )}
      {aviso && <p role="alert" className="mb-2 text-xs text-rojo">{aviso}</p>}
      <div className="flex items-end gap-2">
        <input ref={entrada} type="file" className="hidden" onChange={elegir} aria-label="Elegir un archivo"
          accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.zip,.odt,.ods" />
        <button type="button" onClick={() => entrada.current?.click()} aria-label="Adjuntar un documento o una imagen" title="Adjuntar un documento o una imagen"
          className={cx("flex size-10 shrink-0 items-center justify-center rounded-lg text-gris transition-colors hover:bg-fondo hover:text-azul", archivo && "text-azul")}>
          <Paperclip className="size-5" aria-hidden />
        </button>
        <textarea ref={ref} value={texto} onChange={(e) => setTexto(e.target.value)} onKeyDown={alTeclear} rows={1} maxLength={LIMITE}
          placeholder={archivo ? "Agrega un mensaje (opcional)…" : "Escribe un mensaje…"} aria-label="Mensaje" enterKeyHint="send"
          className="campo max-h-[120px] min-h-10 flex-1 resize-none !py-2" />
        <button type="submit" disabled={!puedeEnviar} aria-label="Enviar mensaje"
          className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-azul text-white transition-colors hover:bg-azul-700 disabled:cursor-not-allowed disabled:opacity-40">
          <SendHorizontal className="size-5" aria-hidden />
        </button>
      </div>
      {cerca && <p className="mt-1 text-right text-xs text-gris num">{texto.length}/{LIMITE}</p>}
    </form>
  );
}
