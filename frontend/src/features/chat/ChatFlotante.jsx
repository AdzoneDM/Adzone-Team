// Chat de la plataforma: botón fijo en la esquina que abre una ventana como los mensajes de Instagram.
// En PC: tus chats a la izquierda y la conversación a la derecha (cambias de chat con un clic).
// En celular: la lista y, al tocar una, la conversación a pantalla completa con flecha para volver.
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { ArrowLeft, Info, MessageCircle, MessagesSquare, Users, X } from "lucide-react";
import { chatAbrir } from "@/lib/api";
import { useSesion } from "@/lib/sesion";
import { Avatar, cx } from "@/components/ui";
import GrupoModal from "./GrupoModal";
import PanelChats from "./PanelChats";
import TiraChats from "./TiraChats";
import VistaConversacion from "./VistaConversacion";
import { useConversaciones } from "./useChat";

const esEscritorio = () => window.matchMedia("(min-width: 640px)").matches;

// Si recargas la página con el chat abierto, vuelve a abrirse en la misma conversación
const LLAVE_CHAT = "adzone:chat";
const leerChat = () => { try { return JSON.parse(sessionStorage.getItem(LLAVE_CHAT) || "null"); } catch { return null; } };
const guardarChat = (v) => { try { if (v) sessionStorage.setItem(LLAVE_CHAT, JSON.stringify(v)); else sessionStorage.removeItem(LLAVE_CHAT); } catch { /* sin almacenamiento */ } };

function Cabecera({ conv, titulo, onAtras, onCerrar, soloMovil, etiquetaAtras = "Todos los chats", onGrupo }) {
  const global = conv?.tipo === "GLOBAL";
  const grupo = conv?.tipo === "GRUPO";
  const subtitulo = !conv ? "Tu equipo, en un solo lugar"
    : global ? "Conversación de todo el equipo"
      : grupo ? `Grupo · ${conv.grupo?.n_miembros ?? ""} personas${conv.grupo?.departamento ? ` · ${conv.grupo.departamento}` : ""}`
        : [conv.persona?.puesto, conv.persona?.departamento].filter(Boolean).join(" · ") || "Chat privado";
  return (
    <header className={cx("flex shrink-0 items-center gap-2 bg-noche px-3 py-3 text-white", soloMovil && "sm:hidden")} style={{ paddingTop: "max(0.75rem, env(safe-area-inset-top))" }}>
      {onAtras && (
        <button type="button" onClick={onAtras} aria-label={etiquetaAtras} className="rounded-lg p-2 text-white/80 hover:bg-white/10 hover:text-white sm:hidden">
          <ArrowLeft className="size-5" aria-hidden />
        </button>
      )}
      {conv && (global
        ? <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-amarillo text-tinta" aria-hidden><Users className="size-4" /></span>
        : grupo ? <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-white/15 text-white" aria-hidden><Users className="size-4" /></span>
          : <Avatar nombre={conv.titulo} tam="sm" className="!bg-white/15 !text-white" />)}
      <div className={cx("min-w-0 flex-1", !conv && "pl-1")}>
        <h2 id={titulo} className="truncate font-display text-base font-semibold leading-tight !text-white">{conv ? conv.titulo : "Chat de Adzone"}</h2>
        <p className="truncate text-xs text-white/70">{subtitulo}</p>
      </div>
      {grupo && onGrupo && (
        <button type="button" onClick={onGrupo} aria-label={conv.grupo?.puede_gestionar ? "Administrar el grupo" : "Ver quién participa en el grupo"} title={conv.grupo?.puede_gestionar ? "Administrar el grupo" : "Participantes"}
          className="rounded-lg p-2 text-white/80 hover:bg-white/10 hover:text-white"><Info className="size-5" aria-hidden /></button>
      )}
      <button type="button" onClick={onCerrar} aria-label="Cerrar el chat" className="rounded-lg p-2 text-white/80 hover:bg-white/10 hover:text-white">
        <X className="size-5" aria-hidden />
      </button>
    </header>
  );
}

export default function ChatFlotante() {
  const { usuario } = useSesion();
  const recordado = useRef(leerChat()); // { conv } si estaba abierto al recargar
  const [abierto, setAbierto] = useState(() => !!recordado.current);
  const [conv, setConv] = useState(null); // conversación abierta a la derecha
  const [listaMovil, setListaMovil] = useState(false); // celular: lista completa con buscador (si no, la conversación con su tira)
  const [error, setError] = useState("");
  const [modalGrupo, setModalGrupo] = useState(null); // null | 'nuevo' | 'ver' (el grupo abierto)
  const { conversaciones, noLeidos, cargando, error: errorLista, refrescar, grupos } = useConversaciones({ abierto, activo: !!usuario, usuarioId: usuario?.id, activaId: conv?.id });
  const titulo = useId();
  const boton = useRef(null);
  const eligioAlgo = useRef(false);

  const cerrar = useCallback(() => { setAbierto(false); setConv(null); setListaMovil(false); eligioAlgo.current = false; guardarChat(null); boton.current?.focus(); }, []);

  // Recuerda el chat abierto y su conversación
  useEffect(() => { if (abierto) guardarChat({ conv: conv?.id ?? null }); }, [abierto, conv?.id]);
  // Al recargar: vuelve a la conversación que tenías (cuando llega la lista)
  useEffect(() => {
    if (!recordado.current || !conversaciones.length) return;
    const guardada = conversaciones.find((c) => c.id === recordado.current.conv);
    recordado.current = null;
    if (guardada) { eligioAlgo.current = true; setConv(guardada); }
  }, [conversaciones]);
  const verLista = useCallback(() => { setListaMovil(true); setError(""); refrescar(); }, [refrescar]);

  // Al abrir ya hay una conversación a la vista (la de la empresa), en PC y en celular
  useEffect(() => {
    if (!abierto || conv || eligioAlgo.current) return;
    const sala = conversaciones.find((c) => c.tipo === "GLOBAL");
    if (sala) setConv(sala);
  }, [abierto, conv, conversaciones]);

  // Esc: en el celular, desde la lista completa vuelve a la conversación; en los demás casos cierra el chat
  useEffect(() => {
    if (!abierto) return undefined;
    const tecla = (e) => { if (e.key === "Escape") (listaMovil && !esEscritorio() ? () => setListaMovil(false) : cerrar)(); };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [abierto, listaMovil, cerrar]);

  // En el celular el chat ocupa toda la pantalla: la página de atrás no debe desplazarse
  useEffect(() => {
    if (!abierto || esEscritorio()) return undefined;
    const antes = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = antes; };
  }, [abierto]);

  const abrirConversacion = (c) => { eligioAlgo.current = true; setError(""); setListaMovil(false); setConv(c); };
  const abrirConPersona = async (persona) => {
    try {
      const c = await chatAbrir(persona.id);
      abrirConversacion({ ...c, persona: c.persona || persona });
    } catch (e) {
      setError(e.message);
    }
  };

  if (!usuario) return null;
  const n = noLeidos;
  const mensajeError = error || errorLista;

  return (
    <>
      <button ref={boton} type="button" onClick={() => setAbierto(true)} aria-label={n ? `Abrir el chat, ${n} sin leer` : "Abrir el chat"} data-guia="chat"
        className={cx("fixed right-4 z-40 flex size-14 items-center justify-center rounded-full bg-azul text-white shadow-lg ring-4 ring-white/70 transition-transform hover:scale-105 hover:bg-azul-700 active:scale-95",
          "bottom-[calc(4.75rem+env(safe-area-inset-bottom))] lg:bottom-6 lg:right-6", abierto && "hidden")}>
        <MessageCircle className="size-6" aria-hidden />
        {n > 0 && <span className="absolute -right-1 -top-1 min-w-5 rounded-full bg-rojo px-1.5 text-center text-[11px] font-semibold leading-5 text-white num">{n > 99 ? "99+" : n}</span>}
      </button>

      {abierto && (
        <section role="dialog" aria-modal="false" aria-labelledby={titulo}
          className="fixed inset-0 z-50 flex bg-white sm:inset-auto sm:bottom-6 sm:right-6 sm:h-[min(640px,calc(100dvh-3rem))] sm:w-[min(780px,calc(100vw-3rem))] sm:overflow-hidden sm:rounded-2xl sm:border sm:border-linea sm:shadow-2xl"
          style={{ paddingBottom: "env(safe-area-inset-bottom)" }}>
          {/* Izquierda: buscador y conversaciones (en el celular, solo cuando no hay una abierta) */}
          <aside className={cx("min-h-0 w-full flex-col sm:flex sm:w-[290px] sm:shrink-0 sm:border-r sm:border-linea", listaMovil ? "flex" : "hidden")} aria-label="Conversaciones">
            <Cabecera conv={null} onCerrar={cerrar} onAtras={conv ? () => setListaMovil(false) : undefined} etiquetaAtras="Volver a la conversación" soloMovil />
            <div className="hidden bg-white px-4 pb-1 pt-4 sm:block"><p className="font-display text-lg font-semibold text-noche">Chats</p></div>
            <PanelChats conversaciones={conversaciones} cargando={cargando} usuarioId={usuario.id} activaId={conv?.id} onAbrir={abrirConversacion} onPersona={abrirConPersona}
              puedeCrearGrupos={grupos.puedeCrear} onNuevoGrupo={() => setModalGrupo("nuevo")} />
          </aside>

          {/* Derecha: la conversación (en el celular, pantalla completa) */}
          <div className={cx("min-h-0 min-w-0 flex-1 flex-col sm:flex", listaMovil ? "hidden" : "flex")}>
            {conv ? (
              <>
                <Cabecera conv={conv} titulo={titulo} onAtras={verLista} onCerrar={cerrar} onGrupo={() => setModalGrupo("ver")} />
                <TiraChats conversaciones={conversaciones} activaId={conv.id} onAbrir={abrirConversacion} onTodos={verLista} />
                {mensajeError && (
                  <div role="alert" className="flex shrink-0 items-center justify-between gap-2 bg-rojo-50 px-4 py-2 text-xs text-rojo">
                    <span>{mensajeError}</span>
                    {error && <button type="button" onClick={() => setError("")} className="font-semibold underline">Cerrar</button>}
                  </div>
                )}
                <VistaConversacion key={conv.id} conversacion={conv} usuarioId={usuario.id} alLeer={refrescar} />
              </>
            ) : (
              <div className="relative flex min-h-0 flex-1 flex-col items-center justify-center bg-fondo px-8 text-center">
                <button type="button" onClick={cerrar} aria-label="Cerrar el chat" className="absolute right-3 top-3 rounded-lg p-2 text-gris hover:bg-white"><X className="size-5" aria-hidden /></button>
                <MessagesSquare className="size-12 text-azul/40" aria-hidden />
                <p className="mt-3 font-display text-base font-semibold text-tinta">{cargando ? "Cargando…" : "Tus mensajes"}</p>
                {!cargando && <p className="mt-1 text-sm text-gris">Elige un chat de la lista o busca a un compañero para escribirle.</p>}
              </div>
            )}
          </div>
        </section>
      )}
      <GrupoModal abierto={!!modalGrupo} grupo={modalGrupo === "ver" ? conv : null} departamentos={grupos.departamentos} usuarioId={usuario.id}
        onCerrar={() => setModalGrupo(null)}
        onGuardado={(c) => { const nuevo = modalGrupo === "nuevo"; setModalGrupo(null); refrescar(); if (nuevo) abrirConversacion(c); else setConv((x) => (x ? { ...x, ...c } : x)); }}
        onEliminado={() => { setModalGrupo(null); setConv(null); eligioAlgo.current = false; refrescar(); }} />
    </>
  );
}
