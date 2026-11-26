// Piezas de tareas que comparten Mis tareas, Por validar y Tareas del equipo.
import { useCallback, useEffect, useRef, useState } from "react";
import { Briefcase, Camera, Check, Copy, ExternalLink, FileText, Film, ImagePlus, Link2, Paperclip, Repeat, Target, Trash2, Users, Video, X } from "lucide-react";
import { comentarTarea, comentariosTarea, entregarTarea, historialTarea, marcarPaso, obtenerTarea, quitarReferencia, subirReferencias } from "@/lib/api";
import Comentarios from "@/components/Comentarios";
import { BotonesGestion } from "@/features/tareas/GestionTarea";
import { useNovedades } from "@/lib/novedades";
import { MAX_FOTO_MB, limites } from "@/lib/archivos";
import { ESTADOS, fechaCorta, fechaHora, vencimiento } from "@/lib/formato";
import { Alerta, Boton, Campo, EstadoTarea, Estrellas, Insignia, Modal, PrioridadTarea, cx, useAviso } from "@/components/ui";

const MAX_LADO = 1600;

async function copiarTexto(texto) {
  try { await navigator.clipboard.writeText(texto); return true; } catch { /* sin permiso: se intenta a la antigua */ }
  const area = document.createElement("textarea");
  area.value = texto; area.setAttribute("readonly", ""); area.style.position = "fixed"; area.style.opacity = "0";
  document.body.appendChild(area); area.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch { ok = false; }
  area.remove();
  return ok;
}

// Texto de la tarea (los detalles que escribió quien la asignó) con un botón para copiarlo tal cual.
export function TextoCopiable({ texto, className }) {
  const avisar = useAviso();
  const [copiado, setCopiado] = useState(false);
  const copiar = async () => {
    if (await copiarTexto(texto)) { setCopiado(true); avisar("Texto copiado"); setTimeout(() => setCopiado(false), 2000); }
    else avisar("No se pudo copiar. Mantén pulsado el texto para seleccionarlo.", "rojo");
  };
  return (
    <div className={cx("relative rounded-xl bg-fondo px-4 py-3 pr-24", className)}>
      <p className="whitespace-pre-line select-text leading-relaxed">{texto}</p>
      <button type="button" onClick={copiar} aria-label="Copiar el texto de la tarea"
        className="absolute right-2 top-2 inline-flex items-center gap-1 rounded-lg border border-linea bg-white px-2 py-1 text-xs font-medium text-gris hover:text-tinta">
        {copiado ? <Check className="size-3.5 text-verde" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
        {copiado ? "Copiado" : "Copiar"}
      </button>
    </div>
  );
}
const MAX_ARCHIVOS = 10;
const EXT_PERMITIDAS = /\.(jpe?g|png|webp|heic|heif|gif|pdf|mp4|mov|m4v|webm|avi|mkv|3gp|mpe?g|doc|docx|xls|xlsx|ppt|pptx|odt|ods|csv|txt|zip)$/i;
const esDocumento = (f) => /\.(doc|docx|xls|xlsx|ppt|pptx|odt|ods|csv|txt|zip)$/i.test(f.name || "");
const ACEPTA = "image/*,video/*,application/pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.odt,.ods,.csv,.txt,.zip";
export const esVideo = (f) => (f.type || "").startsWith("video/") || /\.(mp4|mov|m4v|webm|avi|mkv|3gp|mpe?g)$/i.test(f.name || "");
const tamanoMB = (b) => (b < 1024 * 1024 ? `${Math.max(1, Math.round(b / 1024))} KB` : b >= 10 * 1024 * 1024 ? `${Math.round(b / 1024 / 1024)} MB` : `${(b / 1024 / 1024).toFixed(1)} MB`);

/** Qué le pasa a un archivo antes de subirlo (null = está bien): tipo permitido y peso (el video tiene su propio límite). */
export function problemaDeArchivo(f) {
  if (!EXT_PERMITIDAS.test(f.name || "")) return `«${f.name}»: solo se aceptan fotos, videos, PDF o documentos (Word, Excel, PowerPoint, CSV, texto o ZIP).`;
  const tope = esVideo(f) ? limites.videoMB : /\.zip$/i.test(f.name) ? limites.zipMB : esDocumento(f) ? 15 : MAX_FOTO_MB;
  if (f.size > tope * 1024 * 1024) return `«${f.name}» pesa ${tamanoMB(f.size)} y el máximo es ${tope} MB${esVideo(f) ? ". Para un video largo, súbelo a Drive y pega el enlace" : ""}.`;
  return null;
}

/** Un video de una entrega o una referencia: se reproduce en la página; si ya se borró solo, lo dice. */
export function VideoArchivo({ a }) {
  if (a.purgado) {
    return (
      <div className="flex items-center gap-3 rounded-lg border border-dashed border-linea bg-fondo px-3 py-2.5 text-sm text-gris">
        <Film className="size-5 shrink-0" aria-hidden />
        <span className="min-w-0"><span className="block truncate font-medium text-tinta">{a.nombre_original || "Video"}</span>Se borró solo para liberar espacio (pasaron los días de conservación después de validada la tarea).</span>
      </div>
    );
  }
  return (
    <figure>
      <video controls preload="metadata" playsInline src={a.url} className="aspect-video w-full rounded-lg bg-black" aria-label={a.nombre_original || "Video"}>
        <a href={`${a.url}?descargar=1`}>Descargar el video</a>
      </video>
      <figcaption className="mt-1 flex items-center justify-between gap-2 text-xs text-gris">
        <span className="min-w-0 truncate">{a.nombre_original}{a.tamano ? ` · ${tamanoMB(a.tamano)}` : ""}</span>
        <a href={`${a.url}?descargar=1`} className="shrink-0 font-medium text-azul hover:underline">Descargar</a>
      </figcaption>
    </figure>
  );
}

/** Achica una foto en el navegador (máx. 1600 px, JPG): sube rápido con datos móviles. */
export function achicarFoto(archivo) {
  return new Promise((resolver) => {
    if (!/^image\/(jpeg|png|webp)$/i.test(archivo.type)) return resolver(archivo);
    const url = URL.createObjectURL(archivo);
    const img = new Image();
    img.onload = () => {
      const escala = Math.min(1, MAX_LADO / Math.max(img.naturalWidth, img.naturalHeight));
      if (escala === 1 && archivo.size < 900 * 1024) { URL.revokeObjectURL(url); return resolver(archivo); }
      const c = document.createElement("canvas");
      c.width = Math.round(img.naturalWidth * escala);
      c.height = Math.round(img.naturalHeight * escala);
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(url);
      c.toBlob((blob) => {
        if (!blob) return resolver(archivo);
        resolver(new File([blob], archivo.name.replace(/\.[^.]+$/, "") + ".jpg", { type: "image/jpeg" }));
      }, "image/jpeg", 0.82);
    };
    img.onerror = () => { URL.revokeObjectURL(url); resolver(archivo); };
    img.src = url;
  });
}

/** Elegir bocetos, imágenes o PDF para adjuntar (las fotos se achican antes de subir). */
export function SelectorArchivos({ archivos, onCambio, etiqueta = "Adjuntar boceto, imagen o video", ayuda, max = MAX_ARCHIVOS, disabled }) {
  const entrada = useRef(null);
  const [procesando, setProcesando] = useState(false);
  const [aviso, setAviso] = useState("");
  const elegir = async (e) => {
    const elegidos = Array.from(e.target.files || []);
    e.target.value = "";
    if (!elegidos.length) return;
    const falla = elegidos.map(problemaDeArchivo).find(Boolean);
    setAviso(falla || "");
    const nuevos = elegidos.filter((f) => !problemaDeArchivo(f));
    if (!nuevos.length) return;
    setProcesando(true);
    const listos = await Promise.all(nuevos.map(achicarFoto));
    onCambio([...archivos, ...listos].slice(0, max));
    setProcesando(false);
  };
  return (
    <div>
      <input ref={entrada} type="file" multiple accept={ACEPTA} className="sr-only" onChange={elegir} tabIndex={-1} aria-hidden="true" />
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={() => entrada.current?.click()} disabled={disabled || procesando || archivos.length >= max}
          className="inline-flex h-10 items-center gap-2 rounded-lg border border-dashed border-azul/50 bg-azul/5 px-3 text-sm font-medium text-azul hover:bg-azul/10 disabled:cursor-not-allowed disabled:opacity-50">
          <Paperclip className="size-4" aria-hidden />{procesando ? "Preparando…" : etiqueta}
        </button>
        {archivos.length === 0 && <span className="text-xs text-gris">{ayuda ? `${ayuda} ` : ""}Imágenes, PDF, documentos o videos (hasta {limites.videoMB} MB).</span>}
      </div>
      {aviso && <p role="alert" className="mt-1.5 text-xs text-rojo">{aviso}</p>}
      {archivos.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-2">
          {archivos.map((a, i) => (
            <li key={`${a.name}-${i}`} className="flex max-w-full items-center gap-2 rounded-lg border border-linea bg-white py-1 pl-2.5 pr-1 text-sm">
              {a.type.startsWith("image/") ? <ImagePlus className="size-4 shrink-0 text-gris" aria-hidden /> : esVideo(a) ? <Film className="size-4 shrink-0 text-gris" aria-hidden /> : <FileText className="size-4 shrink-0 text-gris" aria-hidden />}
              <span className="max-w-40 truncate">{a.name}</span>
              <button type="button" onClick={() => onCambio(archivos.filter((_, j) => j !== i))} aria-label={`Quitar ${a.name}`} className="rounded p-1 text-gris hover:bg-rojo-50 hover:text-rojo"><X className="size-4" aria-hidden /></button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Bocetos e imágenes de referencia que dejó quien supervisa: al asignar y en cada corrección. */
export function Referencias({ tarea, onCambio, avisar }) {
  const [grande, setGrande] = useState(null);
  const [nuevos, setNuevos] = useState([]);
  const [subiendo, setSubiendo] = useState(false);
  const lista = tarea.referencias || [];
  // Quien puede editar la tarea agrega o quita referencias en cualquier estado (también validada)
  const puedeAgregar = !!tarea.puedo_gestionar;
  if (!lista.length && !puedeAgregar) return null;

  // Agrupadas: lo de la asignación primero, luego cada corrección
  const grupos = [];
  lista.forEach((r) => {
    const clave = r.momento === "CORRECCION" ? `c${r.ronda}` : "a";
    let g = grupos.find((x) => x.clave === clave);
    if (!g) { g = { clave, titulo: r.momento === "CORRECCION" ? `Para corregir${r.ronda > 1 || tarea.rondas_revision > 1 ? ` · devolución ${r.ronda}` : ""}` : "Al asignar la tarea", items: [] }; grupos.push(g); }
    g.items.push(r);
  });
  grupos.sort((a, b) => (a.clave === "a" ? -1 : b.clave === "a" ? 1 : a.clave.localeCompare(b.clave, undefined, { numeric: true })));

  const subir = async () => {
    setSubiendo(true);
    try {
      const actualizada = await subirReferencias(tarea.id, nuevos, { momento: tarea.rondas_revision > 0 ? "CORRECCION" : "ASIGNACION" });
      setNuevos([]);
      avisar?.("Referencia enviada. Le llegó el aviso.");
      onCambio?.(actualizada);
    } catch (e) { avisar?.(e.message, "rojo"); }
    setSubiendo(false);
  };
  const quitar = async (r) => {
    try { await quitarReferencia(r.url); onCambio?.(await obtenerTarea(tarea.id)); } catch (e) { avisar?.(e.message, "rojo"); }
  };

  return (
    <section aria-label="Referencias">
      <h3 className="mb-2 flex items-center gap-2 text-base font-semibold"><Paperclip className="size-4 text-azul" aria-hidden />Referencias</h3>
      <div className="space-y-4">
        {grupos.map((g) => (
          <div key={g.clave}>
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gris">{g.titulo}</p>
            {g.items.some((r) => r.es_video) && (
              <ul className="mb-2 grid gap-3 sm:grid-cols-2">
                {g.items.filter((r) => r.es_video).map((r) => (
                  <li key={r.id} className="group relative">
                    <VideoArchivo a={r} />
                    {r.puede_borrar && <button type="button" onClick={() => quitar(r)} aria-label={`Quitar ${r.nombre_original || "video"}`} className="absolute right-1 top-1 rounded-md bg-white/90 p-1 text-gris shadow hover:text-rojo"><Trash2 className="size-3.5" aria-hidden /></button>}
                    {r.nota && <p className="mt-0.5 line-clamp-2 text-[11px] text-gris">{r.nota}</p>}
                  </li>
                ))}
              </ul>
            )}
            <ul className="grid grid-cols-[repeat(auto-fill,minmax(112px,1fr))] gap-2">
              {g.items.filter((r) => !r.es_video).map((r) => (
                <li key={r.id} className="group relative">
                  {r.es_imagen ? (
                    <button type="button" onClick={() => setGrande(r)} className="block w-full overflow-hidden rounded-lg border border-linea bg-fondo" aria-label={`Ver ${r.nombre_original || "imagen"} en grande`}>
                      <img src={r.url} alt={r.nombre_original || "Referencia"} loading="lazy" className="aspect-square w-full object-cover" />
                    </button>
                  ) : (
                    <a href={r.url} target="_blank" rel="noopener noreferrer" className="flex aspect-square flex-col items-center justify-center gap-1 rounded-lg border border-linea bg-fondo p-2 text-center text-xs text-gris hover:text-azul">
                      <FileText className="size-6" aria-hidden /><span className="line-clamp-2 break-all">{r.nombre_original}</span>
                    </a>
                  )}
                  {r.puede_borrar && (
                    <button type="button" onClick={() => quitar(r)} aria-label={`Quitar ${r.nombre_original || "referencia"}`}
                      className="absolute right-1 top-1 rounded-md bg-white/90 p-1 text-gris shadow hover:text-rojo sm:opacity-0 sm:group-hover:opacity-100 sm:focus-visible:opacity-100"><Trash2 className="size-3.5" aria-hidden /></button>
                  )}
                  {r.nota && <p className="mt-0.5 line-clamp-2 text-[11px] text-gris">{r.nota}</p>}
                </li>
              ))}
            </ul>
            {g.items[0]?.subido_por_nombre && <p className="mt-1 text-xs text-gris">De {g.items[0].subido_por_nombre} · {fechaHora(g.items[0].fecha)}</p>}
          </div>
        ))}
        {puedeAgregar && (
          <div className="space-y-2">
            <SelectorArchivos archivos={nuevos} onCambio={setNuevos} etiqueta="Agregar boceto, imagen o video" disabled={subiendo} />
            {nuevos.length > 0 && <Boton tam="sm" onClick={subir} cargando={subiendo}>Enviar {nuevos.length === 1 ? "el archivo" : `los ${nuevos.length} archivos`}</Boton>}
          </div>
        )}
      </div>
      {grande && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-noche-900/90 p-4" role="dialog" aria-modal="true" aria-label="Referencia" onClick={() => setGrande(null)}>
          <button type="button" className="absolute right-4 top-4 rounded-lg bg-white/10 p-2 text-white" aria-label="Cerrar"><X className="size-6" /></button>
          <img src={grande.url} alt={grande.nombre_original || "Referencia"} className="max-h-full max-w-full rounded-lg object-contain" />
        </div>
      )}
    </section>
  );
}

export function Vencimiento({ tarea }) {
  if (tarea.estado === "COMPLETADA") {
    return <span className={cx("text-sm", tarea.a_tiempo ? "text-verde" : "text-[#a86a00]")}>{tarea.a_tiempo ? "Entregada a tiempo" : "Entregada tarde"}</span>;
  }
  if (tarea.estado === "EN_REVISION") return <span className="text-sm text-gris">Entregada {fechaCorta(tarea.fecha_completada)}</span>;
  if (tarea.estado === "CANCELADA") return <span className="text-sm text-gris">Cancelada</span>;
  const v = vencimiento(tarea.fecha_limite);
  return <span className={cx("text-sm", v.tono === "rojo" ? "font-medium text-rojo" : v.tono === "amarillo" ? "font-medium text-[#a86a00]" : "text-gris")}>{v.texto}</span>;
}

/** Barra de avance de los pasos: «2 de 5». */
export function Progreso({ progreso, className }) {
  if (!progreso?.total) return null;
  const pct = Math.round((progreso.hechos / progreso.total) * 100);
  return (
    <span className={cx("inline-flex items-center gap-2 text-sm text-gris", className)} title={`${progreso.hechos} de ${progreso.total} pasos`}>
      <span className="h-1.5 w-16 overflow-hidden rounded-full bg-linea" aria-hidden="true">
        <span className={cx("block h-full rounded-full", pct === 100 ? "bg-verde" : "bg-azul")} style={{ width: `${pct}%` }} />
      </span>
      <span className="num">{progreso.hechos}/{progreso.total}</span>
    </span>
  );
}

/** Quién más trabaja la tarea y para qué cliente: una línea corta. */
export function EquipoTarea({ tarea, className }) {
  const otros = tarea.companeros_nombres || [];
  if (!otros.length && !tarea.cliente) return null;
  return (
    <span className={cx("flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-sm text-gris", className)}>
      {tarea.cliente && <span className="flex min-w-0 items-center gap-1"><Briefcase className="size-3.5 shrink-0" /><span className="truncate">{tarea.cliente}</span></span>}
      {otros.length > 0 && <span className="flex min-w-0 items-center gap-1"><Users className="size-3.5 shrink-0" /><span className="truncate">con {otros.join(", ")}</span></span>}
    </span>
  );
}

/**
 * Checklist de la tarea. Quien la trabaja marca los pasos mientras está por hacer;
 * los demás lo ven como lectura. Marcar el primer paso la pasa a «En progreso».
 */
export function Pasos({ tarea, onCambio }) {
  const [marcando, setMarcando] = useState(null);
  const [error, setError] = useState("");
  const pasos = tarea.pasos || [];
  if (!pasos.length) return null;
  const puede = tarea.soy_participante && ["PENDIENTE", "EN_PROGRESO"].includes(tarea.estado);
  const marcar = async (p) => {
    setMarcando(p.id); setError("");
    try { onCambio?.(await marcarPaso(tarea.id, p.id, !p.hecho)); } catch (e) { setError(e.message); }
    setMarcando(null);
  };
  return (
    <section>
      <div className="mb-2 flex items-center justify-between gap-3">
        <h3 className="text-base font-semibold">Pasos</h3>
        <Progreso progreso={tarea.progreso} />
      </div>
      {error && <Alerta className="mb-2">{error}</Alerta>}
      <ul className="divide-y divide-linea-suave rounded-lg border border-linea">
        {pasos.map((p) => {
          const contenido = (<>
            <span className={cx("flex size-6 shrink-0 items-center justify-center rounded-md border-2",
              p.hecho ? "border-verde bg-verde text-white" : "border-linea bg-white", marcando === p.id && "animate-pulse")}>
              {p.hecho && <Check className="size-4" strokeWidth={3} />}
            </span>
            <span className="min-w-0 flex-1">
              <span className={cx("block text-[15px]", p.hecho && "text-gris line-through")}>{p.texto}</span>
              {p.hecho && p.hecho_por_nombre && <span className="block text-xs text-gris">{p.hecho_por_nombre}</span>}
            </span>
          </>);
          return (
            <li key={p.id}>
              {puede ? (
                <button type="button" onClick={() => marcar(p)} disabled={marcando !== null} aria-pressed={p.hecho}
                  className="flex min-h-12 w-full items-center gap-3 px-3 py-2 text-left hover:bg-fondo">{contenido}</button>
              ) : <div className="flex min-h-12 items-center gap-3 px-3 py-2">{contenido}</div>}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** Fotos y PDF de una entrega. Las fotos abren en grande. */
export function Evidencias({ tarea, compacto }) {
  const [grande, setGrande] = useState(null);
  const lista = tarea.evidencias || [];
  const rondas = [...new Set(lista.map((e) => e.ronda))];
  const ultima = rondas.length ? Math.max(...rondas) : 0;
  const mostrar = compacto ? lista.filter((e) => e.ronda === ultima) : lista;
  if (!mostrar.length && !tarea.evidencia_nota && !tarea.evidencia_enlace) return null;
  return (
    <div className="space-y-3">
      {tarea.evidencia_nota && <p className="whitespace-pre-line rounded-lg bg-fondo px-3.5 py-2.5 text-[15px]">{tarea.evidencia_nota}</p>}
      {tarea.evidencia_enlace && (
        <a href={tarea.evidencia_enlace} target="_blank" rel="noopener noreferrer" className="inline-flex max-w-full items-center gap-2 text-sm font-medium text-azul hover:underline">
          <Link2 className="size-4 shrink-0" /><span className="truncate">{tarea.evidencia_enlace}</span><ExternalLink className="size-3.5 shrink-0" />
        </a>
      )}
      {mostrar.some((e) => e.es_video) && (
        <ul className="grid gap-3 sm:grid-cols-2">
          {mostrar.filter((e) => e.es_video).map((e) => <li key={e.id}><VideoArchivo a={e} />{!compacto && rondas.length > 1 && <p className="mt-0.5 text-[11px] text-gris">Entrega {e.ronda + 1}</p>}</li>)}
        </ul>
      )}
      {mostrar.some((e) => !e.es_video) && (
        <ul className="grid grid-cols-[repeat(auto-fill,minmax(96px,1fr))] gap-2">
          {mostrar.filter((e) => !e.es_video).map((e) => (
            <li key={e.id}>
              {e.es_imagen ? (
                <button type="button" onClick={() => setGrande(e)} className="block w-full overflow-hidden rounded-lg border border-linea bg-fondo">
                  <img src={e.url} alt={e.nombre_original || "Evidencia"} loading="lazy" className="aspect-square w-full object-cover" />
                </button>
              ) : (
                <a href={e.url} target="_blank" rel="noopener noreferrer" title={`${e.nombre_original}${e.subido_por_nombre ? ` · lo adjuntó ${e.subido_por_nombre}` : ""}`} className="flex aspect-square flex-col items-center justify-center gap-1 rounded-lg border border-linea bg-fondo p-2 text-center text-xs text-gris hover:text-azul">
                  <FileText className="size-6" /><span className="rounded bg-azul/10 px-1 text-[10px] font-bold uppercase text-azul">{(e.nombre_original || "").split(".").pop().slice(0, 5)}</span><span className="line-clamp-2 break-all">{e.nombre_original}</span>
                </a>
              )}
              {!compacto && e.subido_por_nombre && <p className="mt-0.5 truncate text-[11px] text-gris" title={e.fecha}>{e.subido_por_nombre} · {new Date(e.fecha).toLocaleDateString("es-DO", { day: "numeric", month: "short" })}</p>}
              {!compacto && rondas.length > 1 && <p className="mt-0.5 text-[11px] text-gris">Entrega {e.ronda + 1}</p>}
            </li>
          ))}
        </ul>
      )}
      {grande && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-noche-900/90 p-4" role="dialog" aria-modal="true" aria-label="Evidencia" onClick={() => setGrande(null)}>
          <button type="button" className="absolute right-4 top-4 rounded-lg bg-white/10 p-2 text-white" aria-label="Cerrar"><X className="size-6" /></button>
          <img src={grande.url} alt={grande.nombre_original || "Evidencia"} className="max-h-full max-w-full rounded-lg object-contain" />
        </div>
      )}
    </div>
  );
}

const ICONO_HISTORIAL = { DEVUELTA: "bg-rojo", VALIDADA: "bg-amarillo", REABIERTA: "bg-rojo", ENTREGADA: "bg-azul", CANCELADA: "bg-gris", ELIMINADA: "bg-rojo", RESTAURADA: "bg-verde" };

export function Historial({ tareaId }) {
  const [lista, setLista] = useState(null);
  useEffect(() => { historialTarea(tareaId).then(setLista).catch(() => setLista([])); }, [tareaId]);
  if (!lista) return <p className="text-sm text-gris">Cargando historial…</p>;
  if (!lista.length) return <p className="text-sm text-gris">Sin movimientos registrados.</p>;
  return (
    <ol className="relative space-y-3 border-l border-linea pl-5">
      {lista.map((h) => (
        <li key={h.id} className="relative">
          <span className={cx("absolute -left-[25px] top-1.5 size-2.5 rounded-full ring-4 ring-white", ICONO_HISTORIAL[h.accion] || "bg-linea")} />
          <p className="text-sm"><span className="font-medium">{h.accion_texto}</span> <span className="text-gris">por {h.usuario_nombre} · {fechaHora(h.fecha)}</span>
            {h.estado_antes && h.estado_despues && h.estado_antes !== h.estado_despues && <span className="text-gris"> · {ESTADOS[h.estado_antes] || h.estado_antes} → {ESTADOS[h.estado_despues] || h.estado_despues}</span>}</p>
          {h.comentario && !(h.accion === "EDITADA" && h.comentario.startsWith("Cambió:")) && <p className="mt-0.5 whitespace-pre-line text-sm text-gris">{h.comentario}</p>}
        </li>
      ))}
    </ol>
  );
}

/** Conversación de la tarea: la ven y escriben solo quienes ven la tarea; se puede responder y mencionar con @; no se edita ni se borra. */
function ConversacionTarea({ tareaId }) {
  const [lista, setLista] = useState(null);
  const [error, setError] = useState("");
  const cargar = useCallback(() => comentariosTarea(tareaId).then((l) => { setLista(l); setError(""); }).catch((e) => setError(e.message)), [tareaId]);
  useEffect(() => { setLista(null); cargar(); }, [cargar]);
  useNovedades(cargar); // los comentarios nuevos aparecen sin recargar
  return (
    <section aria-label="Comentarios de la tarea">
      <h3 className="mb-3 text-base font-semibold">Comentarios{lista?.length ? ` (${lista.length})` : ""}</h3>
      {error ? <Alerta>{error}</Alerta> : !lista ? <p className="text-sm text-gris">Cargando…</p>
        : <Comentarios lista={lista.map((c) => ({ ...c, fecha: c.creado }))} permiteResponder
          onEnviar={async (texto, respondeA) => { await comentarTarea(tareaId, texto, respondeA); await cargar(); }} />}
    </section>
  );
}

/** Datos de una tarea; las acciones las pone cada pantalla en `pie`. */
export function DetalleTarea({ tarea: recibida, abierto, onCerrar, pie, onCambio, onEliminada }) {
  const avisar = useAviso();
  const [actual, setActual] = useState(recibida);
  useEffect(() => { setActual(recibida); }, [recibida]);
  // Tras editar o reabrir desde aquí se muestra la versión nueva aunque la pantalla de origen no la actualice
  const tarea = actual && recibida && actual.id === recibida.id ? actual : recibida;
  if (!tarea) return null;
  // Editar, reabrir y eliminar salen aquí en todas las pantallas, a quien tenga el permiso sobre esta tarea
  const gestiona = tarea.puedo_eliminar || tarea.puedo_reabrir || tarea.puedo_gestionar;
  const pieCompleto = gestiona ? (
    <div className="flex w-full flex-wrap justify-end gap-2">
      <BotonesGestion tarea={tarea} onCambio={(t) => { setActual(t); onCambio?.(t); }} onEliminada={() => { onCerrar?.(); onEliminada?.(); }} />
      {pie}
    </div>
  ) : pie;
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={tarea.titulo} ancho="md:max-w-2xl" pie={pieCompleto}>
      <div className="space-y-5">
        <div className="flex flex-wrap items-center gap-2">
          <EstadoTarea estado={tarea.estado} />
          <PrioridadTarea prioridad={tarea.prioridad} />
          {tarea.entre_areas && <Insignia tono="azul">Aporte: de {tarea.departamento_origen_nombre} → {tarea.colaborador_departamento}</Insignia>}
          {tarea.autovalidada && <Insignia tono="amarillo">Autovalidada</Insignia>}
          {tarea.es_recurrente && <Insignia><Repeat className="size-3" />Recurrente</Insignia>}
          {tarea.rondas_revision > 0 && <Insignia tono="rojo">{tarea.rondas_revision === 1 ? "Devuelta 1 vez" : `Devuelta ${tarea.rondas_revision} veces`}</Insignia>}
        </div>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
          <div><dt className="text-gris">Responsable</dt><dd className="font-medium">{tarea.colaborador_nombre}</dd></div>
          {tarea.companeros_nombres?.length > 0 && <div><dt className="text-gris">Con</dt><dd className="font-medium">{tarea.companeros_nombres.join(", ")}</dd></div>}
          {tarea.cliente && <div><dt className="text-gris">Cliente</dt><dd className="font-medium">{tarea.cliente}</dd></div>}
          {tarea.orden && <div><dt className="text-gris">Orden de trabajo</dt><dd className="font-medium"><a href={`/ordenes/${tarea.orden}`} className="text-azul hover:underline">{tarea.orden_numero}</a></dd></div>}
          {tarea.proyecto && <div><dt className="text-gris">Proyecto</dt><dd className="font-medium"><a href={`/proyectos/${tarea.proyecto}`} className="text-azul hover:underline">{tarea.proyecto_nombre}</a></dd></div>}
          {tarea.horas_estimadas && <div><dt className="text-gris">Estimado</dt><dd className="font-medium">{Number(tarea.horas_estimadas)} h</dd></div>}
          <div><dt className="text-gris">Fecha límite</dt><dd className="font-medium">{fechaCorta(tarea.fecha_limite)}</dd></div>
          <div><dt className="text-gris">Asignada por</dt><dd className="font-medium">{tarea.asignada_por_nombre || "—"}</dd></div>
          {tarea.revisor_nombre && <div><dt className="text-gris">La valida</dt><dd className="font-medium">{tarea.revisor_nombre}</dd></div>}
          {tarea.kpi_nombre && <div className="col-span-2 sm:col-span-3"><dt className="text-gris">Suma al KPI</dt><dd className="flex items-center gap-1.5 font-medium"><Target className="size-4 text-azul" />{tarea.kpi_nombre}</dd></div>}
        </dl>
        {tarea.descripcion && <TextoCopiable texto={tarea.descripcion} className="text-[15px]" />}

        <Pasos tarea={tarea} onCambio={onCambio} />

        {tarea.comentario_revision && tarea.estado !== "COMPLETADA" && (
          <Alerta tono="rojo"><p className="font-medium">Para corregir</p><p className="whitespace-pre-line">{tarea.comentario_revision}</p></Alerta>
        )}

        <Referencias tarea={tarea} onCambio={onCambio} avisar={avisar} />

        {(tarea.evidencias?.length > 0 || tarea.evidencia_nota || tarea.evidencia_enlace) && (
          <section>
            <h3 className="mb-2 text-base font-semibold">Evidencia</h3>
            <Evidencias tarea={tarea} />
          </section>
        )}

        {tarea.estado === "COMPLETADA" && (
          <section className="rounded-lg border border-amarillo/50 bg-amarillo-50 px-4 py-3">
            <p className="flex items-center gap-2 text-sm font-medium">Validada por {tarea.validada_por_nombre} <Estrellas valor={tarea.calificacion_calidad} /></p>
            {tarea.comentario_evaluacion && <p className="mt-1 text-sm text-gris">{tarea.comentario_evaluacion}</p>}
          </section>
        )}

        <ConversacionTarea tareaId={tarea.id} />

        <section>
          <h3 className="mb-3 text-base font-semibold">Historial</h3>
          <Historial tareaId={tarea.id} />
        </section>
      </div>
    </Modal>
  );
}

/** Entregar con nota, enlace y fotos (cámara o galería). Al menos una de las tres. */
export function EntregarModal({ tarea, abierto, onCerrar, onEntregada }) {
  const [nota, setNota] = useState("");
  const [enlace, setEnlace] = useState("");
  const [archivos, setArchivos] = useState([]);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const camara = useRef(null);
  const camaraVideo = useRef(null);
  const galeria = useRef(null);

  useEffect(() => { if (abierto) { setNota(""); setEnlace(""); setArchivos([]); setError(""); } }, [abierto, tarea?.id]);

  const agregar = async (lista) => {
    const elegidos = Array.from(lista || []);
    const falla = elegidos.map(problemaDeArchivo).find(Boolean);
    const nuevos = elegidos.filter((f) => !problemaDeArchivo(f));
    if (falla) setError(falla);
    else if (archivos.length + nuevos.length > MAX_ARCHIVOS) setError(`Como máximo ${MAX_ARCHIVOS} archivos por entrega.`);
    else setError("");
    const listos = await Promise.all(nuevos.slice(0, MAX_ARCHIVOS - archivos.length).map(achicarFoto));
    setArchivos((a) => [...a, ...listos.map((f) => ({ f, url: f.type.startsWith("image/") || esVideo(f) ? URL.createObjectURL(f) : null, video: esVideo(f) }))]);
  };

  const enviar = async (e) => {
    e.preventDefault();
    setError("");
    if (!nota.trim() && !enlace.trim() && !archivos.length) {
      setError("Agrega una nota, un enlace o una foto como evidencia.");
      return;
    }
    if (enlace.trim() && !/^https?:\/\//i.test(enlace.trim())) {
      setError("El enlace debe empezar con https:// (cópialo desde el navegador).");
      return;
    }
    setEnviando(true);
    try {
      const t = await entregarTarea(tarea.id, { nota: nota.trim(), enlace: enlace.trim(), archivos: archivos.map((a) => a.f) });
      onEntregada(t);
    } catch (err) {
      setError(err.message + (archivos.length ? " Tus fotos siguen aquí." : ""));
    } finally {
      setEnviando(false);
    }
  };

  if (!tarea) return null;
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo="Entregar tarea" descripcion={tarea.titulo}
      pie={<>
        <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
        <Boton type="submit" form="form-entrega" variante="acento" cargando={enviando}>{archivos.some((x) => x.video) ? (enviando ? "Subiendo el video…" : "Subir y entregar") : archivos.length ? "Subir y entregar" : "Entregar"}</Boton>
      </>}>
      <form id="form-entrega" onSubmit={enviar} className="space-y-4">
        {tarea.comentario_revision && <Alerta tono="rojo"><p className="font-medium">Lo que pidieron corregir</p><p className="whitespace-pre-line">{tarea.comentario_revision}</p></Alerta>}
        {error && <Alerta>{error}</Alerta>}
        <Campo etiqueta="¿Qué hiciste?">
          {(id) => <textarea id={id} className="campo" rows={4} value={nota} onChange={(e) => setNota(e.target.value)}
            placeholder="Ej.: Programé las 5 publicaciones de la semana en Meta Business." />}
        </Campo>
        <Campo etiqueta="Enlace (opcional)" ayuda="A la publicación, al documento o al video.">
          {(id) => <input id={id} className="campo" type="url" inputMode="url" value={enlace} onChange={(e) => setEnlace(e.target.value)} placeholder="https://" />}
        </Campo>
        <div>
          <p className="etiqueta">Fotos, videos, PDF o documentos (opcional, hasta {MAX_ARCHIVOS})</p>
          <div className="grid grid-cols-2 gap-2 md:flex">
            <Boton variante="secundario" icono={Camera} onClick={() => camara.current?.click()} className="md:hidden">Tomar foto</Boton>
            <Boton variante="secundario" icono={Video} onClick={() => camaraVideo.current?.click()} className="md:hidden">Grabar video</Boton>
            <Boton variante="secundario" icono={ImagePlus} onClick={() => galeria.current?.click()}>Elegir archivos</Boton>
          </div>
          <p className="mt-1.5 text-xs text-gris">Videos de hasta {limites.videoMB} MB (MP4, MOV o WEBM); para uno más largo, súbelo a Drive y pega el enlace. Se borran solos unos días después de que se valide la tarea; las fotos y los PDF se quedan.</p>
          <input ref={camara} type="file" accept="image/*" capture="environment" className="sr-only" tabIndex={-1} onChange={(e) => { agregar(e.target.files); e.target.value = ""; }} />
          <input ref={camaraVideo} type="file" accept="video/*" capture="environment" className="sr-only" tabIndex={-1} onChange={(e) => { agregar(e.target.files); e.target.value = ""; }} />
          <input ref={galeria} type="file" accept={ACEPTA} multiple className="sr-only" tabIndex={-1} onChange={(e) => { agregar(e.target.files); e.target.value = ""; }} />
          {archivos.length > 0 && (
            <ul className="mt-3 grid grid-cols-[repeat(auto-fill,minmax(84px,1fr))] gap-2">
              {archivos.map((a, i) => (
                <li key={i} className="relative">
                  {a.video ? <video src={a.url} muted playsInline preload="metadata" className="aspect-square w-full rounded-lg bg-black object-cover" aria-label={a.f.name} />
                    : a.url ? <img src={a.url} alt={`Archivo ${i + 1}`} className="aspect-square w-full rounded-lg object-cover" />
                    : <div className="flex aspect-square items-center justify-center rounded-lg bg-fondo p-2 text-center text-xs text-gris"><FileText className="mb-1 size-5" />{a.f.name}</div>}
                  <button type="button" onClick={() => setArchivos((l) => l.filter((_, j) => j !== i))}
                    className="absolute -right-1.5 -top-1.5 flex size-7 items-center justify-center rounded-full border-2 border-white bg-tinta text-white" aria-label={`Quitar archivo ${i + 1}`}>
                    <X className="size-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <p className="text-sm text-gris">Cuenta para tu avance cuando tu supervisor la valide.</p>
      </form>
    </Modal>
  );
}

