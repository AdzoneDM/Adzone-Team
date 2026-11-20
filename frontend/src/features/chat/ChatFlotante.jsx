// Chat global: botón fijo en la esquina que abre la sala de toda la plataforma.
import { useEffect, useId, useRef, useState } from "react";
import { MessageCircle, X } from "lucide-react";
import { useSesion } from "@/lib/sesion";
import { cx } from "@/components/ui";
import Compositor from "./Compositor";
import ListaMensajes from "./ListaMensajes";
import { useChat } from "./useChat";

export default function ChatFlotante() {
  const { usuario } = useSesion();
  const [abierto, setAbierto] = useState(false);
  const chat = useChat({ abierto, usuarioId: usuario?.id });
  const titulo = useId();
  const boton = useRef(null);

  // Esc cierra y devuelve el foco al botón
  useEffect(() => {
    if (!abierto) return undefined;
    const tecla = (e) => { if (e.key === "Escape") { setAbierto(false); boton.current?.focus(); } };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [abierto]);

  // En el celular el chat ocupa toda la pantalla: la página de atrás no debe desplazarse
  useEffect(() => {
    if (!abierto || !window.matchMedia("(max-width: 639px)").matches) return undefined;
    const antes = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = antes; };
  }, [abierto]);

  if (!usuario) return null;
  const n = chat.noLeidos;

  return (
    <>
      <button ref={boton} type="button" onClick={() => setAbierto(true)} aria-label={n ? `Abrir el chat, ${n} sin leer` : "Abrir el chat"} data-guia="chat"
        className={cx("fixed right-4 z-40 flex size-14 items-center justify-center rounded-full bg-azul text-white shadow-lg ring-4 ring-white/70 transition-transform hover:scale-105 hover:bg-azul-700 active:scale-95",
          "bottom-[calc(4.75rem+env(safe-area-inset-bottom))] lg:bottom-6 lg:right-6", abierto && "hidden")}>
        <MessageCircle className="size-6" aria-hidden />
        {n > 0 && (
          <span className="absolute -right-1 -top-1 min-w-5 rounded-full bg-rojo px-1.5 text-center text-[11px] font-semibold leading-5 text-white num">{n > 99 ? "99+" : n}</span>
        )}
      </button>

      {abierto && (
        <section role="dialog" aria-modal="false" aria-labelledby={titulo}
          className="fixed inset-0 z-50 flex flex-col bg-white sm:inset-auto sm:bottom-6 sm:right-6 sm:h-[min(600px,calc(100dvh-3rem))] sm:w-[380px] sm:overflow-hidden sm:rounded-2xl sm:border sm:border-linea sm:shadow-2xl"
          style={{ paddingBottom: "env(safe-area-inset-bottom)" }}>
          <header className="flex shrink-0 items-center justify-between bg-noche px-4 py-3 text-white" style={{ paddingTop: "max(0.75rem, env(safe-area-inset-top))" }}>
            <div>
              <h2 id={titulo} className="!text-white font-display text-base font-semibold leading-tight">Chat de Adzone</h2>
              <p className="text-xs text-white/70">Conversación de todo el equipo</p>
            </div>
            <button type="button" onClick={() => { setAbierto(false); boton.current?.focus(); }} aria-label="Cerrar el chat" className="rounded-lg p-2 text-white/80 hover:bg-white/10 hover:text-white">
              <X className="size-5" aria-hidden />
            </button>
          </header>

          {chat.error && (
            <div role="alert" className="flex shrink-0 items-center justify-between gap-2 bg-rojo-50 px-4 py-2 text-xs text-rojo">
              <span>{chat.error}</span>
              <button type="button" onClick={() => { chat.limpiarError(); if (!chat.mensajes.length) chat.reintentar(); }} className="font-semibold underline">Cerrar</button>
            </div>
          )}

          <ListaMensajes mensajes={chat.mensajes} usuarioId={usuario.id} hayMas={chat.hayMas} cargando={chat.cargando}
            onMas={chat.cargarAnteriores} onBorrar={chat.borrar} />
          <Compositor enviando={chat.enviando} onEnviar={chat.enviar} autoFoco />
        </section>
      )}
    </>
  );
}
