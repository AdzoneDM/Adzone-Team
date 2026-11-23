// Solo en el celular: tus chats en una tira horizontal sobre la conversación, para cambiar de chat con un toque.
import { Search, Users } from "lucide-react";
import { Avatar, cx } from "@/components/ui";
import { primerNombre } from "@/lib/formato";

export default function TiraChats({ conversaciones, activaId, onAbrir, onTodos }) {
  return (
    <nav aria-label="Cambiar de chat" className="flex shrink-0 gap-3 overflow-x-auto border-b border-linea bg-white px-3 py-2 sm:hidden [scrollbar-width:none]">
      <button type="button" onClick={onTodos} className="flex w-14 shrink-0 flex-col items-center gap-1 text-[11px] font-medium text-azul">
        <span className="flex size-11 items-center justify-center rounded-full border border-dashed border-azul/40 bg-azul/5"><Search className="size-5" aria-hidden /></span>
        Buscar
      </button>
      {conversaciones.map((c) => {
        const activa = c.id === activaId;
        return (
          <button key={c.id} type="button" onClick={() => onAbrir(c)} aria-current={activa ? "true" : undefined} aria-label={c.no_leidos ? `${c.titulo}, ${c.no_leidos} sin leer` : c.titulo}
            className="flex w-14 shrink-0 flex-col items-center gap-1 text-[11px] text-tinta">
            <span className={cx("relative rounded-full p-0.5", activa ? "ring-2 ring-azul" : "ring-2 ring-transparent")}>
              {c.tipo === "GLOBAL"
                ? <span className="flex size-11 items-center justify-center rounded-full bg-amarillo text-tinta" aria-hidden><Users className="size-5" /></span>
                : c.tipo === "GRUPO" ? <span className="flex size-11 items-center justify-center rounded-full bg-azul text-white" aria-hidden><Users className="size-5" /></span>
                  : <Avatar nombre={c.titulo} className="!size-11" />}
              {c.no_leidos > 0 && <span className="absolute -right-0.5 -top-0.5 min-w-4 rounded-full bg-rojo px-1 text-center text-[10px] font-semibold leading-4 text-white num">{c.no_leidos > 9 ? "9+" : c.no_leidos}</span>}
            </span>
            <span className={cx("w-full truncate text-center", activa ? "font-semibold" : c.no_leidos ? "font-medium" : "text-gris")}>{c.tipo === "GLOBAL" ? "Todos" : c.tipo === "GRUPO" ? c.titulo : primerNombre(c.titulo)}</span>
          </button>
        );
      })}
    </nav>
  );
}
