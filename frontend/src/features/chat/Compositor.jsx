import { useEffect, useRef, useState } from "react";
import { SendHorizontal } from "lucide-react";

const LIMITE = 2000;

/** Caja para escribir. Enter envía; Mayús+Enter hace un salto de línea. */
export default function Compositor({ enviando, onEnviar, autoFoco }) {
  const [texto, setTexto] = useState("");
  const ref = useRef(null);

  useEffect(() => { if (autoFoco) ref.current?.focus(); }, [autoFoco]);

  // Crece con el texto, hasta un máximo
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  }, [texto]);

  const enviar = async () => {
    const limpio = texto.trim();
    if (!limpio || enviando) return;
    if (await onEnviar(limpio)) setTexto("");
    ref.current?.focus();
  };

  const alTeclear = (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); enviar(); }
  };

  const cerca = texto.length > LIMITE - 200;
  return (
    <form onSubmit={(e) => { e.preventDefault(); enviar(); }} className="border-t border-linea bg-white p-3">
      <div className="flex items-end gap-2">
        <textarea ref={ref} value={texto} onChange={(e) => setTexto(e.target.value)} onKeyDown={alTeclear} rows={1} maxLength={LIMITE}
          placeholder="Escribe un mensaje…" aria-label="Mensaje" enterKeyHint="send"
          className="campo max-h-[120px] min-h-10 flex-1 resize-none !py-2" />
        <button type="submit" disabled={!texto.trim() || enviando} aria-label="Enviar mensaje"
          className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-azul text-white transition-colors hover:bg-azul-700 disabled:cursor-not-allowed disabled:opacity-40">
          <SendHorizontal className="size-5" aria-hidden />
        </button>
      </div>
      {cerca && <p className="mt-1 text-right text-xs text-gris num">{texto.length}/{LIMITE}</p>}
    </form>
  );
}
