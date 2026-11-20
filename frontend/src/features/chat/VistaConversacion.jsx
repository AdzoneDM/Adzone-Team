import Compositor from "./Compositor";
import ListaMensajes from "./ListaMensajes";
import { useMensajes } from "./useChat";

/** Una conversación abierta. Se monta con `key` = id para empezar limpia en cada una. */
export default function VistaConversacion({ conversacion, usuarioId, alLeer }) {
  const chat = useMensajes(conversacion.id, { alLeer });
  return (
    <>
      {chat.error && (
        <div role="alert" className="flex shrink-0 items-center justify-between gap-2 bg-rojo-50 px-4 py-2 text-xs text-rojo">
          <span>{chat.error}</span>
          <button type="button" onClick={() => { chat.limpiarError(); if (!chat.mensajes.length) chat.reintentar(); }} className="font-semibold underline">Cerrar</button>
        </div>
      )}
      <ListaMensajes mensajes={chat.mensajes} usuarioId={usuarioId} hayMas={chat.hayMas} cargando={chat.cargando}
        privado={conversacion.tipo === "DIRECTA"} nombreOtro={conversacion.titulo}
        onMas={chat.cargarAnteriores} onBorrar={chat.borrar} />
      <Compositor enviando={chat.enviando} onEnviar={chat.enviar} autoFoco />
    </>
  );
}
