// Lo que se hace con un mensaje, como en WhatsApp: menú (flechita en PC, clic derecho, o mantener pulsado en el celular) con
// reacciones rápidas, Responder, Copiar, Reenviar, Editar, Info y Borrar; las reacciones debajo de la burbuja; y reenviar a otros chats.
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Check, Copy, Forward, Info, Pencil, Reply, Search, Trash2 } from "lucide-react";
import { chatConversaciones, chatReenviar } from "@/lib/api";
import { Alerta, Avatar, Boton, Cargando, Modal, cx, useAviso } from "@/components/ui";

const REACCIONES = ["👍", "✅", "❤️", "😂", "😮", "🙏"];

/** Menú de un mensaje. `en` = {x, y} (punto donde se abrió) o `hoja` = true para la hoja de abajo en el celular. */
export function MenuMensaje({ en, hoja, mia, acciones, onReaccion, onCerrar }) {
  const caja = useRef(null);
  const [pos, setPos] = useState(null);
  const [confirmar, setConfirmar] = useState(false);
  useLayoutEffect(() => {   // que quepa en la pantalla: si no hay sitio abajo, se abre hacia arriba
    if (hoja || !caja.current) return;
    const r = caja.current.getBoundingClientRect();
    const x = Math.min(Math.max(8, en.x - (en.derecha ? r.width : 0)), window.innerWidth - r.width - 8);
    const y = en.y + r.height + 8 > window.innerHeight ? Math.max(8, en.y - r.height) : en.y;
    setPos({ x, y });
  }, [en, hoja]);
  useEffect(() => {
    const tecla = (e) => { if (e.key === "Escape") { e.stopPropagation(); onCerrar(); } };
    const fuera = (e) => { if (!caja.current?.contains(e.target)) onCerrar(); };
    const mover = (e) => { if (!caja.current?.contains(e.target)) onCerrar(); };
    window.addEventListener("keydown", tecla, true);
    window.addEventListener("pointerdown", fuera, true);
    window.addEventListener("scroll", mover, true);
    window.addEventListener("resize", onCerrar);
    return () => {
      window.removeEventListener("keydown", tecla, true);
      window.removeEventListener("pointerdown", fuera, true);
      window.removeEventListener("scroll", mover, true);
      window.removeEventListener("resize", onCerrar);
    };
  }, [onCerrar]);

  const hacer = (f) => () => { onCerrar(); f(); };
  const items = [
    acciones.responder && { icono: Reply, texto: "Responder", f: acciones.responder },
    acciones.copiar && { icono: Copy, texto: "Copiar", f: acciones.copiar },
    acciones.reenviar && { icono: Forward, texto: "Reenviar", f: acciones.reenviar },
    acciones.editar && { icono: Pencil, texto: "Editar", f: acciones.editar },
    acciones.info && { icono: Info, texto: "Info del mensaje", f: acciones.info },
  ].filter(Boolean);

  const contenido = (
    <>
      {onReaccion && (
        <div className={cx("flex items-center justify-between gap-0.5 border-b border-linea-suave", hoja ? "px-3 py-3" : "px-1.5 py-1.5")} role="group" aria-label="Reaccionar">
          {REACCIONES.map((e) => (
            <button key={e} type="button" onClick={hacer(() => onReaccion(e))} aria-label={`Reaccionar con ${e}`} aria-pressed={mia === e}
              className={cx("flex items-center justify-center rounded-full transition-transform hover:scale-125 motion-reduce:hover:scale-100",
                hoja ? "size-11 text-[26px]" : "size-9 text-[22px]", mia === e && "bg-azul/15")}>{e}</button>
          ))}
        </div>
      )}
      <ul className="py-1" role="menu">
        {items.map((it) => (
          <li key={it.texto} role="none">
            <button type="button" role="menuitem" onClick={hacer(it.f)} className={cx("flex w-full items-center gap-3 px-4 text-left text-tinta hover:bg-fondo", hoja ? "py-3 text-[15px]" : "py-2 text-sm")}>
              <it.icono className="size-4 text-gris" aria-hidden />{it.texto}
            </button>
          </li>
        ))}
        {acciones.borrar && (
          <li role="none">
            <button type="button" role="menuitem" onClick={() => (confirmar ? hacer(acciones.borrar)() : setConfirmar(true))}
              className={cx("flex w-full items-center gap-3 px-4 text-left", hoja ? "py-3 text-[15px]" : "py-2 text-sm", confirmar ? "bg-rojo text-white" : "text-rojo hover:bg-rojo-50")}>
              <Trash2 className="size-4" aria-hidden />{confirmar ? "Toca otra vez para borrarlo" : "Borrar"}
            </button>
          </li>
        )}
      </ul>
    </>
  );

  if (hoja) {
    return createPortal(
      <div className="fixed inset-0 z-[90] flex items-end bg-black/30" role="presentation">
        <div ref={caja} role="dialog" aria-label="Opciones del mensaje" className="w-full rounded-t-2xl bg-white pb-[max(0.5rem,env(safe-area-inset-bottom))] shadow-2xl animate-[subir_160ms_ease-out]">
          <span className="mx-auto mt-2 block h-1 w-10 rounded-full bg-linea" aria-hidden />
          {contenido}
        </div>
      </div>, document.body);
  }
  return createPortal(
    <div ref={caja} role="dialog" aria-label="Opciones del mensaje" style={{ left: pos?.x ?? en.x, top: pos?.y ?? en.y, visibility: pos ? "visible" : "hidden" }}
      className="fixed z-[90] w-60 overflow-hidden rounded-xl border border-linea bg-white shadow-xl">
      {contenido}
    </div>, document.body);
}

/** Las reacciones debajo de la burbuja: tocar una pone (o quita) la tuya; al pasar el mouse dice quién reaccionó. */
export function Reacciones({ lista, mio, onReaccion }) {
  if (!lista?.length) return null;
  return (
    <div className={cx("relative z-[1] -mt-1.5 flex flex-wrap gap-1", mio ? "justify-end pr-2" : "pl-2")}>
      {lista.map((r) => (
        <button key={r.emoji} type="button" onClick={() => onReaccion?.(r.emoji)} title={r.nombres.join(", ")}
          aria-label={`${r.emoji} ${r.n}: ${r.nombres.join(", ")}${r.mia ? " (toca para quitar la tuya)" : ""}`}
          className={cx("inline-flex h-6 items-center gap-1 rounded-full border bg-white px-1.5 text-[13px] leading-none shadow-sm transition-colors",
            r.mia ? "border-azul/40 bg-azul/10" : "border-linea hover:bg-fondo")}>
          <span>{r.emoji}</span>{r.n > 1 && <span className="num text-[11px] font-medium text-gris">{r.n}</span>}
        </button>
      ))}
    </div>
  );
}

const MAX_REENVIAR = 5;

/** Reenviar un mensaje (texto y archivo) a hasta 5 conversaciones. */
export function ModalReenviar({ mensaje, conversacionActual, onCerrar }) {
  const [lista, setLista] = useState(null);
  const [error, setError] = useState("");
  const [buscar, setBuscar] = useState("");
  const [elegidas, setElegidas] = useState([]);
  const [enviando, setEnviando] = useState(false);
  const avisar = useAviso();
  useEffect(() => {
    if (!mensaje) return;
    setLista(null); setError(""); setElegidas([]); setBuscar("");
    chatConversaciones().then((r) => setLista(r.conversaciones)).catch((e) => setError(e.message));
  }, [mensaje]);
  const t = buscar.trim().toLowerCase();
  const visibles = useMemo(() => (lista || []).filter((c) => c.id !== conversacionActual && (!t || c.titulo.toLowerCase().includes(t))), [lista, t, conversacionActual]);
  if (!mensaje) return null;
  const alternar = (id) => setElegidas((l) => (l.includes(id) ? l.filter((x) => x !== id) : l.length >= MAX_REENVIAR ? l : [...l, id]));
  const enviar = async () => {
    setEnviando(true);
    try {
      await chatReenviar(mensaje.id, elegidas);
      avisar(elegidas.length === 1 ? "Mensaje reenviado" : `Mensaje reenviado a ${elegidas.length} conversaciones`);
      onCerrar();
    } catch (e) { setError(e.message); }
    setEnviando(false);
  };
  const resumen = mensaje.texto ? mensaje.texto.slice(0, 90) + (mensaje.texto.length > 90 ? "…" : "") : `📎 ${mensaje.archivo?.nombre || "Archivo"}`;
  return (
    <Modal abierto onCerrar={onCerrar} titulo="Reenviar mensaje" ancho="md:max-w-md" descripcion={resumen}
      pie={<div className="flex items-center justify-between gap-3">
        <span className="text-xs text-gris">{elegidas.length ? `${elegidas.length} de ${MAX_REENVIAR} elegidas` : `Elige hasta ${MAX_REENVIAR}`}</span>
        <Boton icono={Forward} onClick={enviar} disabled={!elegidas.length} cargando={enviando}>Reenviar</Boton>
      </div>}>
      {error && <Alerta className="mb-3">{error}</Alerta>}
      <label className="relative mb-2 block">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" aria-hidden />
        <input value={buscar} onChange={(e) => setBuscar(e.target.value)} placeholder="Buscar conversación" aria-label="Buscar conversación" className="campo w-full !pl-9" />
      </label>
      {!lista ? (!error && <Cargando />) : (
        <ul className="max-h-[50vh] divide-y divide-linea-suave overflow-y-auto">
          {visibles.map((c) => {
            const si = elegidas.includes(c.id);
            return (
              <li key={c.id}>
                <button type="button" onClick={() => alternar(c.id)} aria-pressed={si} disabled={!si && elegidas.length >= MAX_REENVIAR}
                  className="flex w-full items-center gap-3 py-2 text-left hover:bg-fondo disabled:opacity-50">
                  <Avatar nombre={c.titulo} tam="sm" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-tinta">{c.titulo}</span>
                    <span className="block truncate text-xs text-gris">{c.tipo === "GLOBAL" ? "Toda la empresa" : c.tipo === "GRUPO" ? "Grupo" : c.persona?.puesto || "Chat privado"}</span>
                  </span>
                  <span className={cx("flex size-5 shrink-0 items-center justify-center rounded-full border-2", si ? "border-azul bg-azul text-white" : "border-linea")}>{si && <Check className="size-3" aria-hidden />}</span>
                </button>
              </li>
            );
          })}
          {!visibles.length && <li className="py-6 text-center text-sm text-gris">No hay conversaciones con ese nombre.</li>}
        </ul>
      )}
    </Modal>
  );
}
