import { Fragment, useEffect, useLayoutEffect, useRef, useState } from "react";
import { ArrowDown, Download, FileSpreadsheet, FileText, Trash2 } from "lucide-react";
import { urlArchivoChat } from "@/lib/api";
import { Avatar, cx } from "@/components/ui";

const MINUTOS_AGRUPAR = 5;

const hora = (iso) => new Date(iso).toLocaleTimeString("es-DO", { hour: "numeric", minute: "2-digit" });

function etiquetaDia(iso) {
  const d = new Date(iso);
  const hoy = new Date();
  const ayer = new Date(); ayer.setDate(hoy.getDate() - 1);
  if (d.toDateString() === hoy.toDateString()) return "Hoy";
  if (d.toDateString() === ayer.toDateString()) return "Ayer";
  return d.toLocaleDateString("es-DO", { weekday: "long", day: "numeric", month: "long" });
}

const URL_RE = /(https?:\/\/[^\s<]+[^\s<.,;:!?)\]'"])/g;

/** Texto con enlaces clicables. Se construye con elementos de React (nunca HTML), así que no hay inyección. */
function Texto({ texto }) {
  return texto.split(URL_RE).map((parte, i) => (i % 2 === 1
    ? <a key={i} href={parte} target="_blank" rel="noopener noreferrer nofollow" className="underline underline-offset-2 break-all">{parte}</a>
    : <Fragment key={i}>{parte}</Fragment>));
}

const tamano = (b) => (b < 1024 * 1024 ? `${Math.max(1, Math.round(b / 1024))} KB` : `${(b / 1024 / 1024).toFixed(1)} MB`);

/** Un archivo adjunto: la imagen se ve en el mensaje (y se abre en grande); un documento sale como tarjeta con su nombre, tamaño y descarga. */
function Adjunto({ m, mio }) {
  const a = m.archivo;
  const abrir = urlArchivoChat(m.id), bajar = urlArchivoChat(m.id, true);
  if (a.es_imagen) {
    return (
      <span className="group/img relative mb-1 block overflow-hidden rounded-2xl ring-1 ring-linea">
        <a href={abrir} target="_blank" rel="noopener" aria-label={`Abrir ${a.nombre}`}><img src={abrir} alt={a.nombre} loading="lazy" className="max-h-56 max-w-full object-cover" /></a>
        <a href={bajar} aria-label={`Descargar ${a.nombre}`} title="Descargar" className="absolute right-1.5 top-1.5 rounded-lg bg-white/90 p-1.5 text-tinta opacity-100 shadow hover:text-azul sm:opacity-0 sm:group-hover/img:opacity-100"><Download className="size-4" /></a>
      </span>
    );
  }
  const Icono = /\.(xlsx?|csv|ods)$/i.test(a.nombre) ? FileSpreadsheet : FileText;
  return (
    <a href={bajar} className={cx("mb-1 flex min-w-48 items-center gap-3 rounded-2xl px-3 py-2.5 transition-colors", mio ? "bg-azul-700 text-white hover:bg-azul-700/90" : "bg-white text-tinta ring-1 ring-linea hover:bg-fondo")}
      aria-label={`Descargar ${a.nombre}`}>
      <span className={cx("flex size-10 shrink-0 items-center justify-center rounded-lg", mio ? "bg-white/15" : "bg-azul/10 text-azul")}><Icono className="size-5" aria-hidden /></span>
      <span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium">{a.nombre}</span><span className={cx("block text-xs", mio ? "text-white/70" : "text-gris")}>{tamano(a.tamano)} · Descargar</span></span>
      <Download className="size-4 shrink-0 opacity-70" aria-hidden />
    </a>
  );
}

function Burbuja({ m, mio, primero, privado, onBorrar }) {
  const [confirmar, setConfirmar] = useState(false);
  if (m.eliminado) {
    return <p className={cx("my-0.5 text-xs italic text-gris", mio ? "text-right" : privado ? "" : "pl-10")}>Mensaje eliminado</p>;
  }
  return (
    <div className={cx("group flex items-end gap-2", mio ? "flex-row-reverse" : "", primero ? "mt-3" : "mt-0.5")}>
      {!mio && !privado && (primero ? <Avatar nombre={m.autor_nombre} tam="sm" /> : <span className="size-8 shrink-0" aria-hidden />)}
      <div className={cx("flex max-w-[80%] flex-col", mio ? "items-end" : "items-start")}>
        {primero && !mio && !privado && <span className="mb-0.5 px-1 text-xs font-medium text-gris">{m.autor_nombre}</span>}
        <div className="flex items-center gap-1.5">
          {m.puede_borrar && (
            <button type="button" onClick={() => (confirmar ? onBorrar(m.id) : setConfirmar(true))} onBlur={() => setConfirmar(false)}
              aria-label={confirmar ? "Confirmar: borrar mensaje" : "Borrar mensaje"}
              className={cx("order-last rounded p-1 text-xs transition-opacity focus-visible:opacity-100 sm:opacity-0 sm:group-hover:opacity-100",
                mio && "order-first", confirmar ? "bg-rojo text-white opacity-100" : "text-gris hover:bg-rojo-50 hover:text-rojo")}>
              {confirmar ? "¿Borrar?" : <Trash2 className="size-3.5" aria-hidden />}
            </button>
          )}
          <div className={cx("flex min-w-0 flex-col", mio ? "items-end" : "items-start")}>
            {m.archivo && <Adjunto m={m} mio={mio} />}
            {m.texto && (
              <p className={cx("whitespace-pre-wrap break-words rounded-2xl px-3 py-2 text-[14px] leading-snug",
                mio ? "rounded-br-md bg-azul text-white" : "rounded-bl-md bg-white text-tinta shadow-sm ring-1 ring-linea")}>
                <Texto texto={m.texto} />
              </p>
            )}
          </div>
        </div>
        <time dateTime={m.creado} className="px-1 pt-0.5 text-[11px] text-gris">{hora(m.creado)}</time>
      </div>
    </div>
  );
}

/** Lista con desplazamiento inteligente: si estás al final sigue los mensajes nuevos; si lees arriba, no te mueve y te avisa. */
export default function ListaMensajes({ mensajes, usuarioId, hayMas, cargando, privado = false, nombreOtro = "", onMas, onBorrar }) {
  const caja = useRef(null);
  const alFinal = useRef(true);
  const previo = useRef({ n: 0, primero: null, alto: 0 });
  const [nuevos, setNuevos] = useState(false);

  const irAlFinal = (suave) => {
    const el = caja.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: suave ? "smooth" : "auto" });
    setNuevos(false);
  };

  useLayoutEffect(() => {
    const el = caja.current;
    if (!el) return;
    const p = previo.current;
    const primero = mensajes[0]?.id ?? null;
    if (p.n === 0 || (mensajes.length && mensajes[mensajes.length - 1].autor === usuarioId && mensajes.length > p.n)) {
      el.scrollTop = el.scrollHeight; // primera carga o mensaje propio
    } else if (primero !== p.primero && p.primero !== null && primero < p.primero) {
      el.scrollTop += el.scrollHeight - p.alto; // se cargaron anteriores: conserva el lugar
    } else if (mensajes.length > p.n) {
      if (alFinal.current) el.scrollTop = el.scrollHeight;
      else setNuevos(true);
    }
    previo.current = { n: mensajes.length, primero, alto: el.scrollHeight };
  }, [mensajes, usuarioId]);

  useEffect(() => { previo.current.alto = caja.current?.scrollHeight ?? 0; });

  const alDesplazar = () => {
    const el = caja.current;
    alFinal.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    if (alFinal.current) setNuevos(false);
  };

  let diaPrevio = "";
  return (
    <div className="relative min-h-0 flex-1">
      <div ref={caja} onScroll={alDesplazar} className="h-full overflow-y-auto overscroll-contain bg-fondo px-3 py-3" role="log" aria-live="polite" aria-label="Mensajes del chat">
        {hayMas && (
          <div className="pb-2 text-center">
            <button type="button" onClick={onMas} className="rounded-full border border-linea bg-white px-3 py-1 text-xs font-medium text-azul hover:bg-azul/5">Ver mensajes anteriores</button>
          </div>
        )}
        {!cargando && mensajes.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center px-6 text-center">
            <p className="font-display text-base font-semibold text-tinta">Aún no hay mensajes</p>
            <p className="mt-1 text-sm text-gris">{privado ? `Escribe el primero para saludar a ${nombreOtro}.` : "Escribe el primero para saludar al equipo."} También puedes adjuntar un documento o una imagen con el clip.</p>
          </div>
        )}
        {mensajes.map((m, i) => {
          const antes = mensajes[i - 1];
          const dia = etiquetaDia(m.creado);
          const nuevoDia = dia !== diaPrevio;
          diaPrevio = dia;
          const primero = nuevoDia || !antes || antes.autor !== m.autor || antes.eliminado
            || (new Date(m.creado) - new Date(antes.creado)) / 60000 > MINUTOS_AGRUPAR;
          return (
            <Fragment key={m.id}>
              {nuevoDia && <p className="my-3 text-center text-xs font-medium capitalize text-gris">{dia}</p>}
              <Burbuja m={m} mio={m.autor === usuarioId} primero={primero} privado={privado} onBorrar={onBorrar} />
            </Fragment>
          );
        })}
      </div>
      {nuevos && (
        <button type="button" onClick={() => irAlFinal(true)}
          className="absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-1.5 rounded-full bg-azul px-3 py-1.5 text-xs font-medium text-white shadow-lg">
          <ArrowDown className="size-3.5" aria-hidden /> Mensajes nuevos
        </button>
      )}
    </div>
  );
}
