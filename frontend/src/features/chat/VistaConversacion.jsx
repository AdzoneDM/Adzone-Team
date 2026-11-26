import { useEffect, useState } from "react";
import { chatGrupo, chatPersonas } from "@/lib/api";
import Compositor from "./Compositor";
import ListaMensajes from "./ListaMensajes";
import { useMensajes } from "./useChat";

/** Una conversación abierta. Se monta con `key` = id para empezar limpia en cada una. */
export default function VistaConversacion({ conversacion, usuarioId, alLeer }) {
  const chat = useMensajes(conversacion.id, { alLeer, usuarioId });
  const [respondiendo, setRespondiendo] = useState(null);   // mensaje al que se está respondiendo (deslizar o la flechita)
  // A quién se puede mencionar con @: los miembros del grupo, o todo el equipo en la sala de la empresa (en un chat privado no hace falta)
  const [participantes, setParticipantes] = useState([]);
  useEffect(() => {
    let vivo = true;
    const poner = (l) => vivo && setParticipantes((l || []).filter((p) => p.usuario && p.id !== usuarioId));
    if (conversacion.tipo === "GRUPO") chatGrupo(conversacion.id).then((r) => poner(r.grupo?.miembros)).catch(() => {});
    else if (conversacion.tipo !== "DIRECTA") chatPersonas().then(poner).catch(() => {});
    return () => { vivo = false; };
  }, [conversacion.id, conversacion.tipo, usuarioId]);
  return (
    <>
      {chat.error && (
        <div role="alert" className="flex shrink-0 items-center justify-between gap-2 bg-rojo-50 px-4 py-2 text-xs text-rojo">
          <span>{chat.error}</span>
          <button type="button" onClick={() => { chat.limpiarError(); if (!chat.mensajes.length) chat.reintentar(); }} className="font-semibold underline">Cerrar</button>
        </div>
      )}
      <ListaMensajes mensajes={chat.mensajes} lectores={chat.lectores} usuarioId={usuarioId} hayMas={chat.hayMas} cargando={chat.cargando}
        privado={conversacion.tipo === "DIRECTA"} nombreOtro={conversacion.titulo}
        onMas={chat.cargarAnteriores} onBorrar={chat.borrar} onEditar={chat.editar} onResponder={setRespondiendo} />
      <Compositor clave={conversacion.id} participantes={participantes} enviando={chat.enviando} progreso={chat.progreso} autoFoco
        respondiendo={respondiendo} onCancelarRespuesta={() => setRespondiendo(null)}
        onEnviar={async (texto, archivos) => { const r = await chat.enviar(texto, archivos, respondiendo?.id); if (r.ok) setRespondiendo(null); return r; }} />
    </>
  );
}
