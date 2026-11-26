import { Fragment, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Check, CheckCheck, ChevronDown, Download, Forward, Reply, FileArchive, FileSpreadsheet, FileText, Film, ShieldCheck } from "lucide-react";
import { chatAbierto, urlArchivoChat } from "@/lib/api";
import { ModalVistos } from "./Vistos";
import { MenuMensaje, ModalReenviar, Reacciones } from "./AccionesMensaje";
import { copiarTexto } from "@/lib/portapapeles";
import { Avatar, cx, useAviso } from "@/components/ui";
import { useVisor } from "@/components/VisorImagen";

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

const ALTO_MAX = 288; // px (unas 15 líneas): un mensaje que no cabe en esta altura se muestra recortado, con «Ver todo»

/** Un mensaje que no cabe en la conversación: se ve su inicio, con un degradado al final que avisa que hay más, y «Ver todo» lo despliega completo
 *  (con su formato y sus saltos de línea). Se mide por la altura real, así que también aplica a mensajes cortos con muchos renglones. */
function TextoLargo({ texto, ...resto }) {
  const [abierto, setAbierto] = useState(false);
  const [desborda, setDesborda] = useState(false);
  const caja = useRef(null);
  useLayoutEffect(() => {
    const el = caja.current;
    if (!el) return undefined;
    const medir = () => setDesborda(el.scrollHeight > ALTO_MAX + 24); // un margen: no se recorta por unas pocas líneas de más
    medir();
    const o = new ResizeObserver(medir);
    o.observe(el);
    return () => o.disconnect();
  }, [texto]);
  const recortado = desborda && !abierto;
  const degradado = "linear-gradient(to bottom, #000 70%, transparent)";
  return (
    <>
      <span ref={caja} className="block" style={recortado ? { maxHeight: ALTO_MAX, overflow: "hidden", WebkitMaskImage: degradado, maskImage: degradado } : undefined}>
        <Texto texto={texto} {...resto} />
      </span>
      {desborda && (
        <button type="button" onClick={() => setAbierto((a) => !a)} aria-expanded={abierto}
          className="mt-1 block text-xs font-semibold underline underline-offset-2 opacity-90 hover:opacity-100">{abierto ? "Ver menos" : "Ver todo"}</button>
      )}
    </>
  );
}

/** Un @usuario que el servidor reconoció como mención: se ve como «@Nombre» resaltado (más fuerte si te mencionaron a ti). */
function Mencion({ token, menciones, yo, mio }) {
  const limpio = token.slice(1).replace(/[.-]+$/, "");
  const sobra = token.slice(1 + limpio.length);
  const m = menciones.find((x) => x.username.toLowerCase() === limpio.toLowerCase());
  if (!m) return token;
  const soyYo = m.id === yo;
  return (
    <>
      <span title={`${m.nombre} (@${m.username})`}
        className={cx("rounded px-1 font-semibold", soyYo ? "bg-amarillo text-tinta" : mio ? "bg-white/20 text-white" : "bg-azul/10 text-azul")}>@{m.nombre.split(" ")[0]}</span>
      {sobra}
    </>
  );
}

/** Texto con enlaces clicables. Se construye con elementos de React (nunca HTML), así que no hay inyección. */
function Texto({ texto, menciones = [], yo = null, mio = false }) {
  return texto.split(URL_RE).map((parte, i) => (i % 2 === 1
    ? <a key={i} href={parte} target="_blank" rel="noopener noreferrer nofollow" className="underline underline-offset-2 break-all">{parte}</a>
    : <Fragment key={i}>{menciones.length
      ? parte.split(/((?<![\w.@])@[\w.-]+)/g).map((p, j) => (j % 2 === 1 ? <Mencion key={j} token={p} menciones={menciones} yo={yo} mio={mio} /> : p))
      : parte}</Fragment>));
}

const tamano = (b) => (b < 1024 * 1024 ? `${Math.max(1, Math.round(b / 1024))} KB` : `${(b / 1024 / 1024).toFixed(1)} MB`);

/** Un archivo adjunto: la imagen se ve en el mensaje (y se abre en grande); un documento sale como tarjeta con su nombre, tamaño y descarga. */
function Adjunto({ m, mio, galeria = [], meta = null }) {
  const a = m.archivo;
  const ver = useVisor();
  const abrir = urlArchivoChat(m.id), bajar = urlArchivoChat(m.id, true);
  // Abrir, reproducir o descargar el archivo queda como evidencia («quién lo abrió»)
  const abierto = () => { if (!mio) chatAbierto(m.id); };
  if (a.es_zip) {
    if (a.purgado) {
      return <span className={cx("mb-1 flex items-center gap-2 rounded-xl px-3 py-2 text-xs italic", mio ? "bg-azul-700 text-white/80" : "bg-fondo text-gris")}><FileArchive className="size-4 shrink-0" aria-hidden />El ZIP «{a.nombre}» se borró solo para liberar espacio</span>;
    }
    return (
      <a href={bajar} download onClick={abierto} className={cx("mb-1 flex min-w-56 items-center gap-3 rounded-xl px-3 py-2.5 transition-colors", mio ? "bg-azul-700 text-white hover:bg-azul-700/90" : "bg-fondo text-tinta hover:bg-linea-suave")}
        aria-label={`Descargar ${a.nombre}`}>
        <span className={cx("flex size-11 shrink-0 flex-col items-center justify-center rounded-lg", mio ? "bg-white/15" : "bg-amarillo-50 text-[#8a5a00]")}><FileArchive className="size-5" aria-hidden /><span className="text-[9px] font-bold leading-none">ZIP</span></span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium">{a.nombre}</span>
          <span className={cx("flex flex-wrap items-center gap-x-1.5 text-xs", mio ? "text-white/70" : "text-gris")}>
            {tamano(a.tamano)}{a.items != null && <> · {a.items} {a.items === 1 ? "archivo" : "archivos"}</>}
            {a.revisado && <span className="inline-flex items-center gap-0.5" title="Revisado con el antivirus"><ShieldCheck className="size-3" aria-hidden />Revisado</span>}
          </span>
        </span>
        <Download className="size-4 shrink-0 opacity-70" aria-hidden />
      </a>
    );
  }
  if (a.es_video) {
    if (a.purgado) {
      return <span className={cx("mb-1 flex items-center gap-2 rounded-xl px-3 py-2 text-xs italic", mio ? "bg-azul-700 text-white/80" : "bg-fondo text-gris")}><Film className="size-4 shrink-0" aria-hidden />El video se borró solo para liberar espacio</span>;
    }
    return (
      <span className="mb-1 block max-w-full overflow-hidden rounded-xl">
        <video controls preload="metadata" playsInline src={abrir} onPlay={abierto} className="max-h-[17rem] w-full min-w-[15.5rem] bg-black sm:min-w-[17rem]" aria-label={a.nombre}>
          <a href={bajar}>Descargar el video</a>
        </video>
        <a href={bajar} className={cx("flex items-center justify-between gap-2 px-2.5 py-1.5 text-xs", mio ? "bg-azul-700 text-white/90" : "bg-fondo text-gris")}><span className="truncate">{a.nombre} · {tamano(a.tamano)}</span><Download className="size-3.5 shrink-0" aria-hidden /></a>
      </span>
    );
  }
  if (a.es_imagen) {
    // Miniatura del tamaño de WhatsApp (no la foto entera): se abre en grande, dentro de la plataforma, con todas las fotos del chat
    const abrirFoto = () => {
      abierto();
      const i = galeria.findIndex((g) => g.id === m.id);
      if (i >= 0) ver(galeria, i); else ver({ src: abrir, nombre: a.nombre, descargar: bajar });
    };
    return (
      <span className={cx("relative block overflow-hidden rounded-xl bg-linea-suave", !meta && "mb-1")}>
        <button type="button" onClick={abrirFoto} aria-label={`Ver ${a.nombre}`} className="block w-full cursor-zoom-in">
          <img src={abrir} alt={a.nombre} loading="lazy" className={cx("max-h-[17rem] min-h-24 object-cover", meta ? "w-[15.5rem] sm:w-[17rem]" : "w-full")} />
        </button>
        {meta && <span className="pointer-events-none absolute inset-x-0 bottom-0 flex justify-end bg-gradient-to-t from-black/45 to-transparent px-2 pb-1.5 pt-6">{meta}</span>}
      </span>
    );
  }
  const Icono = /\.(xlsx?|csv|ods)$/i.test(a.nombre) ? FileSpreadsheet : FileText;
  return (
    <a href={bajar} onClick={abierto} className={cx("mb-1 flex min-w-48 items-center gap-3 rounded-xl px-3 py-2.5 transition-colors", mio ? "bg-azul-700 text-white hover:bg-azul-700/90" : "bg-fondo text-tinta hover:bg-linea-suave")}
      aria-label={`Descargar ${a.nombre}`}>
      <span className={cx("flex size-10 shrink-0 items-center justify-center rounded-lg", mio ? "bg-white/15" : "bg-azul/10 text-azul")}><Icono className="size-5" aria-hidden /></span>
      <span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium">{a.nombre}</span><span className={cx("block text-xs", mio ? "text-white/70" : "text-gris")}>{tamano(a.tamano)} · Descargar</span></span>
      <Download className="size-4 shrink-0 opacity-70" aria-hidden />
    </a>
  );
}

/** El «visto» de un mensaje tuyo: una palomita = enviado; dos de color = ya lo leyeron. En grupos, en cada mensaje, cuántos lo vieron
 *  (12/15); tocarlo abre quién lo vio y quién no, con fecha y hora. Dentro de la burbuja azul las palomitas leídas van en celeste. */
function Visto({ m, lectores, privado, detalle, onVer, enBurbuja, sobreFoto }) {
  const vistos = lectores.lista.filter((l) => l.hasta >= m.id);
  const total = lectores.total;
  const todos = total > 0 && vistos.length >= total;
  const algunos = vistos.length > 0;
  const texto = privado ? (algunos ? "Visto" : "Enviado") : algunos ? `Visto por ${todos ? "todos" : `${vistos.length} de ${total}`}` : "Enviado";
  const Icono = algunos ? CheckCheck : Check;
  const contenido = (
    <>
      <Icono className={enBurbuja || sobreFoto ? "size-3.5" : "size-3.5"} aria-hidden />
      {detalle ? <span className="font-medium">{texto}</span>
        : !privado && total > 0 ? <span className="num font-medium" aria-label={texto}>{vistos.length}/{total}</span>
          : <span className="sr-only">{texto}</span>}
    </>
  );
  const color = enBurbuja ? (algunos ? "text-[#8fd0ff]" : "text-white/75") : sobreFoto ? (algunos ? "text-[#8fd0ff]" : "text-white") : algunos ? "text-azul" : "text-gris";
  const clase = cx("inline-flex items-center gap-0.5", color);
  return onVer
    ? <button type="button" onClick={onVer} className={cx(clase, "pointer-events-auto rounded hover:underline")} title="Ver quién lo vio">{contenido}</button>
    : <span className={clase} title={texto}>{contenido}</span>;
}

/** ¿Todavía se puede editar? Se vuelve a calcular solo al vencer el plazo (el botón desaparece sin recargar). */
function useEditable(hasta) {
  const fin = hasta ? Date.parse(hasta) : 0;
  const [vigente, setVigente] = useState(() => fin > Date.now());
  useEffect(() => {
    if (!fin) { setVigente(false); return undefined; }
    const falta = fin - Date.now();
    setVigente(falta > 0);
    if (falta <= 0) return undefined;
    const t = setTimeout(() => setVigente(false), Math.min(falta, 2 ** 31 - 1));
    return () => clearTimeout(t);
  }, [fin]);
  return vigente;
}

/** Editar el texto en la misma burbuja: Enter guarda, Mayús+Enter salta de línea, Esc cancela. */
function EdicionEnLinea({ m, onGuardar, onCancelar }) {
  const [texto, setTexto] = useState(m.texto || "");
  const [guardando, setGuardando] = useState(false);
  const caja = useRef(null);
  useEffect(() => {
    const el = caja.current;
    if (!el) return;
    el.focus({ preventScroll: true });
    el.setSelectionRange(el.value.length, el.value.length);
    el.closest("div.rounded-2xl")?.scrollIntoView({ block: "nearest", behavior: "smooth" });   // que se vea entero, con sus botones
  }, []);
  const guardar = async () => {
    const limpio = texto.trim();
    if (limpio === (m.texto || "").trim()) { onCancelar(); return; }
    if (!limpio && !m.archivo) return;
    setGuardando(true);
    if (await onGuardar(m.id, limpio)) onCancelar();
    setGuardando(false);
  };
  return (
    <div className="w-full min-w-64 max-w-md rounded-2xl bg-white p-2 shadow-sm ring-2 ring-azul/40">
      <textarea ref={caja} value={texto} onChange={(e) => setTexto(e.target.value)} rows={Math.min(8, Math.max(2, texto.split("\n").length))}
        onKeyDown={(e) => { if (e.key === "Escape") onCancelar(); if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); guardar(); } }}
        aria-label="Editar mensaje" className="w-full resize-none rounded-lg border-0 p-1 text-[14px] leading-snug text-tinta focus:outline-none focus:ring-0" />
      <div className="flex items-center justify-end gap-2 pt-1">
        <span className="mr-auto text-[11px] text-gris">Esc para cancelar · Enter para guardar</span>
        <button type="button" onClick={onCancelar} className="rounded-lg px-2.5 py-1 text-xs font-medium text-gris hover:bg-fondo">Cancelar</button>
        <button type="button" onClick={guardar} disabled={guardando || (!texto.trim() && !m.archivo)} className="rounded-lg bg-azul px-3 py-1 text-xs font-semibold text-white hover:bg-azul-700 disabled:opacity-50">{guardando ? "Guardando…" : "Guardar"}</button>
      </div>
    </div>
  );
}

const UMBRAL_DESLIZAR = 60;
const PULSACION_LARGA = 450;   // ms: mantener pulsado abre el menú del mensaje (celular)

/** Deslizar el mensaje hacia un lado (en el celular) para responderlo, como en WhatsApp. El desplazamiento vertical sigue normal. */
function useDeslizar(alResponder, activo, alPulsarLargo) {
  const inicio = useRef(null);
  const reloj = useRef(0);
  const [dx, setDx] = useState(0);
  useEffect(() => () => clearTimeout(reloj.current), []);
  if (!activo) return { dx: 0, eventos: {} };
  const soltar = () => { clearTimeout(reloj.current); setDx(0); inicio.current = null; };
  return {
    dx,
    eventos: {
      onTouchStart: (e) => {
        if (e.touches.length > 1 || e.target.closest("a, video, textarea")) return;
        const t = e.touches[0];
        inicio.current = { x: t.clientX, y: t.clientY, eje: null };
        clearTimeout(reloj.current);
        // Mantener pulsado (sin moverse) abre el menú del mensaje, como en WhatsApp
        if (alPulsarLargo) reloj.current = setTimeout(() => { if (inicio.current && !inicio.current.eje) { inicio.current.largo = true; navigator.vibrate?.(20); alPulsarLargo(); } }, PULSACION_LARGA);
      },
      onTouchMove: (e) => {
        const s = inicio.current;
        if (!s || s.largo) return;
        const t = e.touches[0];
        const x = t.clientX - s.x, y = t.clientY - s.y;
        if (!s.eje) {
          if (Math.abs(x) < 8 && Math.abs(y) < 8) return;
          clearTimeout(reloj.current);
          s.eje = Math.abs(x) > Math.abs(y) * 1.2 ? "x" : "y";   // si empieza vertical, es desplazar la lista
        }
        if (s.eje === "x") setDx(Math.max(-90, Math.min(90, x)));
      },
      onTouchEnd: (e) => {
        if (inicio.current?.largo) e.preventDefault();   // que soltar después de la pulsación larga no haga clic
        else if (Math.abs(dx) >= UMBRAL_DESLIZAR) { navigator.vibrate?.(15); alResponder(); }
        soltar();
      },
      onTouchCancel: soltar,
    },
  };
}

/** La cita del mensaje al que se responde; al tocarla lleva al original. */
function Cita({ cita, mio, onIr }) {
  const texto = cita.eliminado ? "Mensaje eliminado" : cita.texto || (cita.archivo ? `📎 ${cita.archivo.es_imagen ? "Imagen" : cita.archivo.nombre}` : "");
  return (
    <button type="button" onClick={() => onIr?.(cita.id)} title="Ir al mensaje original"
      className={cx("mb-1 block w-full min-w-[10rem] rounded-lg border-l-4 px-2 py-1 text-left text-[12.5px] leading-snug",
        mio ? "border-white/70 bg-white/15 hover:bg-white/25" : "border-azul bg-fondo hover:bg-linea-suave")}>
      <span className={cx("block font-semibold", mio ? "text-white" : "text-azul")}>{cita.autor_nombre}</span>
      <span className={cx("line-clamp-2 whitespace-pre-wrap break-words", mio ? "text-white/85" : "text-gris", cita.eliminado && "italic")}>{texto}</span>
    </button>
  );
}

/** Hora, «Editado» y las palomitas, dentro de la burbuja (abajo a la derecha, como en WhatsApp). Sobre una foto van en blanco. */
function Meta({ m, mio, lectores, privado, onVer, sobreFoto }) {
  return (
    <span className={cx("flex items-center justify-end gap-1 text-[10.5px] leading-none", sobreFoto ? "text-white drop-shadow" : mio ? "text-white/75" : "text-gris")}>
      {m.editado_en && <span title={`Editado a las ${hora(m.editado_en)}`} className="italic">Editado ·</span>}
      <time dateTime={m.creado}>{hora(m.creado)}</time>
      {mio && <Visto m={m} lectores={lectores} privado={privado} detalle={false} enBurbuja={!sobreFoto} sobreFoto={sobreFoto} onVer={m.puede_ver_vistos ? () => onVer(m) : null} />}
    </span>
  );
}

function Burbuja({ m, mio, primero, privado, onBorrar, onEditar, onResponder, onReaccion, onReenviar, onIr, resaltado, lectores, ultimoMio, yo, onVer, galeria }) {
  const [editando, setEditando] = useState(false);
  const [menu, setMenu] = useState(null);   // {en:{x,y,derecha}} o {hoja:true}
  const editable = useEditable(mio && onEditar && !m.eliminado ? m.editable_hasta : null);
  const avisar = useAviso();
  const copiar = async () => {
    if (await copiarTexto(m.texto)) avisar("Mensaje copiado");
    else avisar("No se pudo copiar. Mantén pulsado el texto para seleccionarlo.", "rojo");
  };
  const { dx, eventos } = useDeslizar(() => onResponder?.(m), !!onResponder && !m.eliminado && !editando, () => setMenu({ hoja: true }));
  if (m.eliminado) {
    return <p data-mensaje={m.id} className={cx("my-0.5 flex", mio ? "justify-end" : privado ? "" : "pl-10")}><span className="rounded-xl bg-white/70 px-3 py-1.5 text-xs italic text-gris ring-1 ring-linea-suave">🚫 Mensaje eliminado</span></p>;
  }
  const mia = m.reacciones?.find((r) => r.mia)?.emoji;
  const soloFoto = m.archivo?.es_imagen && !m.texto && !m.responde_a;
  const acciones = {
    responder: onResponder && (() => onResponder(m)),
    copiar: m.texto && copiar,
    reenviar: onReenviar && !m.archivo?.purgado && (() => onReenviar(m)),
    editar: editable && (() => setEditando(true)),
    info: m.puede_ver_vistos && (() => onVer(m)),
    borrar: m.puede_borrar && (() => onBorrar(m.id)),
  };
  const abrirMenu = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    setMenu({ en: { x: mio ? r.right : r.left, y: r.bottom + 4, derecha: mio } });
  };
  const alClicDerecho = (e) => {
    if (editando || e.target.closest("a, video, textarea")) return;
    if (window.matchMedia("(pointer: coarse)").matches) { e.preventDefault(); return; }   // en el celular abre con la pulsación larga
    e.preventDefault();
    setMenu({ en: { x: e.clientX, y: e.clientY } });
  };
  const cola = primero && (mio ? "rounded-tr-[4px]" : "rounded-tl-[4px]");
  return (
    <div data-mensaje={m.id} {...eventos} onContextMenu={alClicDerecho} style={{ touchAction: "pan-y" }}
      className={cx("group relative flex items-end gap-2 rounded-xl transition-colors duration-700 [@media(pointer:coarse)]:select-none", mio ? "flex-row-reverse" : "", primero ? "mt-3" : "mt-0.5",
        resaltado && "bg-amarillo-50", m.reacciones?.length && "mb-1")}>
      {dx !== 0 && (
        <span aria-hidden className={cx("absolute top-1/2 flex size-8 -translate-y-1/2 items-center justify-center rounded-full bg-white text-azul shadow", dx > 0 ? "left-1" : "right-1")}
          style={{ opacity: Math.min(1, Math.abs(dx) / UMBRAL_DESLIZAR), transform: `translateY(-50%) scale(${Math.abs(dx) >= UMBRAL_DESLIZAR ? 1.1 : 0.8})` }}>
          <Reply className="size-4" />
        </span>
      )}
      <div className="flex w-full items-end gap-2" style={{ transform: dx ? `translateX(${dx}px)` : undefined, transition: dx ? "none" : "transform 150ms ease-out", flexDirection: mio ? "row-reverse" : undefined }}>
      {!mio && !privado && (primero ? <Avatar nombre={m.autor_nombre} tam="sm" /> : <span className="size-8 shrink-0" aria-hidden />)}
      <div className={cx("flex max-w-[85%] flex-col lg:max-w-[70%]", mio ? "items-end" : "items-start")}>
        {editando && editable ? <EdicionEnLinea m={m} onGuardar={onEditar} onCancelar={() => setEditando(false)} /> : (
          <div className={cx("relative min-w-0 rounded-2xl text-[14px] leading-snug", cola,
            soloFoto ? "p-1" : "px-2.5 pb-1.5 pt-1.5", m.archivo?.es_imagen && !soloFoto && "w-[16.75rem] !px-1 sm:w-[18rem] [&>*:not(span.relative):not(button)]:px-1.5",
            mio ? "bg-azul text-white" : "bg-white text-tinta shadow-sm ring-1 ring-linea")}>
            {primero && !mio && !privado && <span className="block px-0.5 pb-0.5 text-xs font-semibold text-azul">{m.autor_nombre}</span>}
            {m.reenviado && <span className={cx("flex items-center gap-1 px-0.5 pb-0.5 text-[11.5px] italic", mio ? "text-white/75" : "text-gris")}><Forward className="size-3" aria-hidden />Reenviado</span>}
            {m.responde_a && <Cita cita={m.responde_a} mio={mio} onIr={onIr} />}
            {m.archivo && <Adjunto m={m} mio={mio} galeria={galeria} meta={soloFoto ? <Meta m={m} mio={mio} lectores={lectores} privado={privado} onVer={onVer} sobreFoto /> : null} />}
            {m.texto && <div className="whitespace-pre-wrap break-words px-0.5"><TextoLargo texto={m.texto} menciones={m.menciones || []} yo={yo} mio={mio} /></div>}
            {!soloFoto && <div className="-mb-0.5 mt-0.5 pl-6"><Meta m={m} mio={mio} lectores={lectores} privado={privado} onVer={onVer} /></div>}
            {/* La flechita del menú, en la esquina de la burbuja (PC); en el celular se mantiene pulsado */}
            <button type="button" onClick={abrirMenu} aria-label="Opciones del mensaje" aria-haspopup="menu" title="Opciones"
              className={cx("absolute right-1 top-1 hidden rounded-full p-0.5 opacity-0 transition-opacity focus-visible:opacity-100 group-hover:opacity-100 sm:block",
                soloFoto ? "bg-black/40 text-white" : mio ? "bg-azul text-white/90 shadow-[-6px_0_8px_rgb(31_78_156)]" : "bg-white text-gris shadow-[-6px_0_8px_white]", menu && "opacity-100")}>
              <ChevronDown className="size-4" aria-hidden />
            </button>
          </div>
        )}
        <Reacciones lista={m.reacciones} mio={mio} onReaccion={onReaccion && ((e) => onReaccion(m.id, e))} />
        {mio && ultimoMio && !privado && lectores.total > 0 && (
          <div className="px-1 pt-0.5 text-[11px] text-gris"><Visto m={m} lectores={lectores} privado={privado} detalle onVer={m.puede_ver_vistos ? () => onVer(m) : null} /></div>
        )}
      </div>
      </div>
      {menu && <MenuMensaje {...menu} mia={mia} acciones={acciones} onReaccion={onReaccion && ((e) => onReaccion(m.id, e))} onCerrar={() => setMenu(null)} />}
    </div>
  );
}

/** Varias fotos seguidas de la misma persona (4 o más), como un álbum de WhatsApp: cuadrícula 2×2 y «+N» en la última. */
function Album({ grupo, mio, primero, privado, galeria, lectores, onVer, onResponder, onBorrar }) {
  const ver = useVisor();
  const [menu, setMenu] = useState(null);
  const ultimo = grupo[grupo.length - 1];
  const muestra = grupo.slice(0, 4);
  const abrir = (m) => {
    if (!mio) chatAbierto(m.id);
    const i = galeria.findIndex((g) => g.id === m.id);
    ver(galeria, Math.max(0, i));
  };
  const borrables = grupo.every((m) => m.puede_borrar);
  const acciones = {
    responder: onResponder && (() => onResponder(ultimo)),
    borrar: borrables && (() => grupo.forEach((m) => onBorrar(m.id))),
  };
  return (
    <div data-mensaje={ultimo.id} onContextMenu={(e) => { e.preventDefault(); setMenu(window.matchMedia("(pointer: coarse)").matches ? { hoja: true } : { en: { x: e.clientX, y: e.clientY } }); }}
      className={cx("group flex items-end gap-2", mio && "flex-row-reverse", primero ? "mt-3" : "mt-0.5")}>
      {!mio && !privado && (primero ? <Avatar nombre={ultimo.autor_nombre} tam="sm" /> : <span className="size-8 shrink-0" aria-hidden />)}
      <div className={cx("relative rounded-2xl p-1", mio ? "bg-azul" : "bg-white shadow-sm ring-1 ring-linea", primero && (mio ? "rounded-tr-[4px]" : "rounded-tl-[4px]"))}>
        {primero && !mio && !privado && <span className="block px-1.5 pb-1 text-xs font-semibold text-azul">{ultimo.autor_nombre}</span>}
        <div className="grid w-[15.5rem] grid-cols-2 gap-1 sm:w-[17rem]">
          {muestra.map((m, i) => (
            <button key={m.id} type="button" onClick={() => abrir(m)} aria-label={`Ver ${m.archivo.nombre}`} className="relative aspect-square cursor-zoom-in overflow-hidden rounded-xl bg-linea-suave">
              <img src={urlArchivoChat(m.id)} alt={m.archivo.nombre} loading="lazy" className="size-full object-cover" />
              {i === 3 && grupo.length > 4 && <span className="absolute inset-0 flex items-center justify-center bg-black/45 text-2xl font-semibold text-white num">+{grupo.length - 4}</span>}
            </button>
          ))}
        </div>
        <span className="pointer-events-none absolute bottom-2 right-2.5 rounded-full bg-black/35 px-1.5 py-0.5"><Meta m={ultimo} mio={mio} lectores={lectores} privado={privado} onVer={onVer} sobreFoto /></span>
        <button type="button" onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); setMenu({ en: { x: mio ? r.right : r.left, y: r.bottom + 4, derecha: mio } }); }}
          aria-label="Opciones del álbum" className="absolute right-2 top-2 hidden rounded-full bg-black/40 p-0.5 text-white opacity-0 transition-opacity focus-visible:opacity-100 group-hover:opacity-100 sm:block">
          <ChevronDown className="size-4" aria-hidden />
        </button>
      </div>
      {menu && <MenuMensaje {...menu} acciones={acciones} onCerrar={() => setMenu(null)} />}
    </div>
  );
}

/** Lista con desplazamiento inteligente: si estás al final sigue los mensajes nuevos; si lees arriba, no te mueve y te avisa. */
export default function ListaMensajes({ mensajes, lectores = { lista: [], total: 0 }, usuarioId, hayMas, cargando, privado = false, nombreOtro = "", conversacionId, onMas, onBorrar, onEditar, onResponder, onReaccion }) {
  const caja = useRef(null);
  const alFinal = useRef(true);
  const previo = useRef({ n: 0, primero: null, alto: 0 });
  const [nuevos, setNuevos] = useState(0);         // mensajes que llegaron mientras leías arriba
  const [abajo, setAbajo] = useState(true);        // ¿se está viendo el final? (si no, aparece la flecha para bajar)
  const [viendo, setViendo] = useState(null);   // mensaje del que se consulta quién lo vio
  const [reenviando, setReenviando] = useState(null);   // mensaje que se va a reenviar
  const [resaltado, setResaltado] = useState(null);   // el original al que se saltó desde una cita
  const avisarLista = useAviso();
  const irAMensaje = (id) => {
    const el = caja.current?.querySelector(`[data-mensaje="${id}"]`);
    if (!el) { avisarLista(hayMas ? "Ese mensaje es más antiguo: toca «Ver mensajes anteriores» arriba." : "Ese mensaje ya no está disponible.", "rojo"); return; }
    el.scrollIntoView({ block: "center", behavior: "smooth" });
    setResaltado(id);
    setTimeout(() => setResaltado((r) => (r === id ? null : r)), 1600);
  };

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
      else setNuevos((n) => n + mensajes.filter((x) => x.id > (p.ultimo || 0) && x.autor !== usuarioId).length);
    }
    previo.current = { n: mensajes.length, primero, alto: el.scrollHeight, ultimo: mensajes[mensajes.length - 1]?.id ?? 0 };
  }, [mensajes, usuarioId]);

  useEffect(() => { previo.current.alto = caja.current?.scrollHeight ?? 0; });

  const alDesplazar = () => {
    const el = caja.current;
    alFinal.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    setAbajo(el.scrollHeight - el.scrollTop - el.clientHeight < 240);
    if (alFinal.current) setNuevos(0);
  };

  const ultimoPropio = [...mensajes].reverse().find((x) => x.autor === usuarioId && !x.eliminado)?.id;
  // Todas las fotos de la conversación (las cargadas), para pasar de una a otra en el visor, con quién la envió y cuándo
  const galeria = useMemo(() => mensajes.filter((m) => !m.eliminado && m.archivo?.es_imagen).map((m) => ({
    id: m.id, src: urlArchivoChat(m.id), descargar: urlArchivoChat(m.id, true), nombre: m.archivo.nombre,
    detalle: `${m.autor === usuarioId ? "Tú" : m.autor_nombre} · ${new Date(m.creado).toLocaleString("es-DO", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })}`,
  })), [mensajes, usuarioId]);
  // Fotos seguidas de la misma persona (sin texto ni cita, en pocos minutos): de 4 en adelante se juntan en un álbum
  const bloques = useMemo(() => {
    const foto = (m) => !m.eliminado && m.archivo?.es_imagen && !m.texto && !m.responde_a && !m.reenviado && !m.reacciones?.length;
    const r = [];
    for (let i = 0; i < mensajes.length; i += 1) {
      const m = mensajes[i];
      if (foto(m)) {
        let j = i;
        while (j + 1 < mensajes.length && foto(mensajes[j + 1]) && mensajes[j + 1].autor === m.autor
          && etiquetaDia(mensajes[j + 1].creado) === etiquetaDia(m.creado)
          && (new Date(mensajes[j + 1].creado) - new Date(mensajes[j].creado)) / 60000 <= MINUTOS_AGRUPAR) j += 1;
        if (j - i + 1 >= 4) { r.push({ album: mensajes.slice(i, j + 1), i }); i = j; continue; }
      }
      r.push({ m, i });
    }
    return r;
  }, [mensajes]);
  const dias = [];
  bloques.forEach((x) => {
    const dia = etiquetaDia((x.m || x.album[0]).creado);
    if (dias[dias.length - 1]?.dia !== dia) dias.push({ dia, items: [] });
    dias[dias.length - 1].items.push(x);
  });
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
            <p className="mt-1 text-sm text-gris">{privado ? `Escribe el primero para saludar a ${nombreOtro}.` : "Escribe el primero para saludar al equipo."} También puedes adjuntar un documento, una imagen o un video con el clip.</p>
          </div>
        )}
        {/* Cada día es una sección: su fecha queda pegada arriba mientras se recorre y la del día siguiente la reemplaza (como en WhatsApp) */}
        {dias.map(({ dia, items }) => (
          <section key={`${dia}-${items[0].i}`} aria-label={dia}>
            <p className="pointer-events-none sticky top-0 z-[2] py-2 text-center"><span className="inline-block rounded-lg bg-white/95 px-2.5 py-1 text-[11.5px] font-medium first-letter:uppercase text-gris shadow-sm ring-1 ring-linea-suave">{dia}</span></p>
            {items.map(({ m: m0, album, i }, k) => {
              const m = m0 || album[0];
              const antes = mensajes[i - 1];
              const primero = k === 0 || !antes || antes.autor !== m.autor || antes.eliminado
                || (new Date(m.creado) - new Date(antes.creado)) / 60000 > MINUTOS_AGRUPAR;
              const mio = m.autor === usuarioId;
              return album
                ? <Album key={m.id} grupo={album} mio={mio} primero={primero} privado={privado} galeria={galeria} lectores={lectores} onVer={setViendo} onResponder={onResponder} onBorrar={onBorrar} />
                : <Burbuja key={m.id} m={m} mio={mio} primero={primero} privado={privado} onBorrar={onBorrar} onEditar={onEditar} onResponder={onResponder} onReaccion={onReaccion}
                  onReenviar={setReenviando} onIr={irAMensaje} resaltado={resaltado === m.id} lectores={lectores} ultimoMio={m.id === ultimoPropio} yo={usuarioId} onVer={setViendo} galeria={galeria} />;
            })}
          </section>
        ))}
      </div>
      <ModalVistos mensaje={viendo} onCerrar={() => setViendo(null)} />
      <ModalReenviar mensaje={reenviando} conversacionActual={conversacionId} onCerrar={() => setReenviando(null)} />
      {(!abajo || nuevos > 0) && (
        <button type="button" onClick={() => irAlFinal(true)} aria-label={nuevos ? `${nuevos} mensajes nuevos: ir al final` : "Ir al final"}
          className="absolute bottom-3 right-4 flex size-10 items-center justify-center rounded-full bg-white text-gris shadow-lg ring-1 ring-linea transition hover:text-azul">
          <ChevronDown className="size-5" aria-hidden />
          {nuevos > 0 && <span className="absolute -top-1.5 -right-1 min-w-5 rounded-full bg-azul px-1 text-center text-[11px] font-semibold leading-5 text-white num">{nuevos > 99 ? "99+" : nuevos}</span>}
        </button>
      )}
    </div>
  );
}
