// Panel de revisión de una entrega: información, evidencias (con vista previa y descarga), calidad del 1 al 5, comentarios y las acciones
// validar / devolver / ver historial, cada una con su confirmación. Sigue las reglas de siempre: nadie valida lo ajeno a su equipo, la calidad es
// obligatoria para validar y toda devolución explica qué corregir.
import { useEffect, useState } from "react";
import { CalendarClock, CircleCheckBig, ClipboardList, Clock, Download, Eye, FileText, Film, History, ImageIcon, Link2, MessageSquareText, RotateCcw, Star, TriangleAlert } from "lucide-react";
import { devolverTarea, validarTarea } from "@/lib/api";
import { fechaCorta, fechaHora } from "@/lib/formato";
import { anunciarNovedades } from "@/lib/novedades";
import { useRecurso } from "@/lib/recursos";
import { useSesion } from "@/lib/sesion";
import { Checklist } from "@/features/ordenes/piezas";
import { EquipoTarea, Historial, Pasos, SelectorArchivos, TextoCopiable } from "@/features/tareas/componentes";
import { Alerta, Avatar, Boton, Campo, Insignia, Modal, PrioridadTarea, cx, useAviso, useConfirmar } from "@/components/ui";
import { BotonesGestion } from "./GestionTarea";
import { ESCALA_CALIDAD, diasTarde, entregaDe, evidenciaActual, tamanoLegible, textoEspera, tipoDeArchivo } from "./validarUtil";

function Seccion({ icono: Icono, titulo, derecha, children }) {
  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="flex size-7 items-center justify-center rounded-lg bg-azul/10 text-azul">{Icono && <Icono className="size-4" aria-hidden />}</span>
        <h3 className="text-[15px] font-semibold">{titulo}</h3>
        {derecha && <span className="ml-auto text-xs text-gris">{derecha}</span>}
      </div>
      {children}
    </section>
  );
}

const Dato = ({ etiqueta, children, className }) => (
  <div className={className}><dt className="text-xs text-gris">{etiqueta}</dt><dd className="mt-0.5 text-sm font-medium">{children}</dd></div>
);

const ICONO_TIPO = { imagen: ImageIcon, video: Film, pdf: FileText, documento: FileText };
const COLOR_TIPO = { imagen: "bg-azul/10 text-azul", video: "bg-[#f4ebff] text-[#6941c6]", pdf: "bg-[#fef3f2] text-[#b42318]", documento: "bg-[#ecfdf3] text-[#067647]" };

/** Un archivo de evidencia: miniatura, nombre y tipo claros, y botones para verlo (imagen, PDF, video) y descargarlo. */
function ArchivoEvidencia({ e, onVer, etiquetaEntrega }) {
  const tipo = tipoDeArchivo(e);
  const Icono = ICONO_TIPO[tipo.clave];
  const verlo = tipo.clave !== "documento" && !e.purgado;
  return (
    <li className="flex gap-3 rounded-xl border border-linea bg-white p-2.5">
      <button type="button" disabled={!verlo} onClick={() => onVer(e)} aria-label={verlo ? `Ver ${e.nombre_original}` : e.nombre_original}
        className={cx("flex size-16 shrink-0 items-center justify-center overflow-hidden rounded-lg", COLOR_TIPO[tipo.clave], verlo && "hover:opacity-80")}>
        {tipo.clave === "imagen" && !e.purgado ? <img src={e.url} alt="" loading="lazy" className="size-full object-cover" />
          : <span className="flex flex-col items-center gap-0.5"><Icono className="size-6" aria-hidden /><span className="text-[10px] font-bold uppercase">{tipo.ext.slice(0, 5)}</span></span>}
      </button>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium" title={e.nombre_original}>{e.nombre_original || "Archivo"}</p>
        <p className="text-xs text-gris">{tipo.nombre}{tipo.ext && tipo.ext.toUpperCase() !== tipo.nombre.toUpperCase() ? ` · ${tipo.ext.toUpperCase()}` : ""}{e.tamano ? ` · ${tamanoLegible(e.tamano)}` : ""}</p>
        {(e.subido_por_nombre || etiquetaEntrega) && <p className="truncate text-[11px] text-gris">{[etiquetaEntrega, e.subido_por_nombre && `lo adjuntó ${e.subido_por_nombre}`].filter(Boolean).join(" · ")}</p>}
        {e.purgado ? <p className="mt-1 text-xs text-[#a86a00]">Se borró para liberar espacio.</p> : (
          <div className="mt-1.5 flex gap-1.5">
            {verlo && <button type="button" onClick={() => onVer(e)} className="inline-flex h-7 items-center gap-1 rounded-md border border-linea px-2 text-xs font-medium text-tinta hover:border-azul hover:text-azul"><Eye className="size-3.5" aria-hidden />Ver</button>}
            <a href={e.url} download={e.nombre_original} className="inline-flex h-7 items-center gap-1 rounded-md border border-linea px-2 text-xs font-medium text-tinta hover:border-azul hover:text-azul"><Download className="size-3.5" aria-hidden />Descargar</a>
          </div>
        )}
      </div>
    </li>
  );
}

function EvidenciasRevision({ tarea }) {
  const [ver, setVer] = useState(null);
  const actuales = evidenciaActual(tarea);
  const previas = (tarea.evidencias || []).filter((e) => !actuales.includes(e));
  const nada = !actuales.length && !tarea.evidencia_nota?.trim() && !tarea.evidencia_enlace;
  return (
    <>
      {nada && <p className="rounded-lg bg-fondo px-3.5 py-3 text-sm text-gris">Esta entrega no trae archivos, nota ni enlace.</p>}
      {tarea.evidencia_nota?.trim() && (
        <figure className="rounded-xl border-l-4 border-azul bg-fondo px-4 py-3">
          <figcaption className="mb-1 text-xs font-medium text-gris">Nota de {tarea.colaborador_nombre}</figcaption>
          <blockquote className="whitespace-pre-line text-[15px]">{tarea.evidencia_nota}</blockquote>
        </figure>
      )}
      {tarea.evidencia_enlace && (
        <a href={tarea.evidencia_enlace} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 rounded-xl border border-linea bg-white px-3.5 py-2.5 text-sm font-medium text-azul hover:border-azul">
          <Link2 className="size-4 shrink-0" aria-hidden /><span className="truncate">{tarea.evidencia_enlace}</span>
        </a>
      )}
      {actuales.length > 0 && <ul className="grid gap-2 sm:grid-cols-2">{actuales.map((e) => <ArchivoEvidencia key={e.id} e={e} onVer={setVer} />)}</ul>}
      {previas.length > 0 && (
        <details className="rounded-xl border border-linea-suave">
          <summary className="cursor-pointer px-3.5 py-2.5 text-sm font-medium text-gris hover:text-tinta">Entregas anteriores ({previas.length} {previas.length === 1 ? "archivo" : "archivos"})</summary>
          <ul className="grid gap-2 p-2.5 pt-0 sm:grid-cols-2">{previas.map((e) => <ArchivoEvidencia key={e.id} e={e} onVer={setVer} etiquetaEntrega={`Entrega ${e.ronda + 1}`} />)}</ul>
        </details>
      )}
      <Modal abierto={!!ver} onCerrar={() => setVer(null)} titulo={ver?.nombre_original || "Evidencia"} descripcion={ver ? `${tipoDeArchivo(ver).nombre}${ver.tamano ? ` · ${tamanoLegible(ver.tamano)}` : ""}` : undefined} ancho="md:max-w-4xl"
        pie={ver && <><a href={ver.url} download={ver.nombre_original} className="mr-auto inline-flex items-center gap-2 text-sm font-medium text-azul hover:underline"><Download className="size-4" aria-hidden />Descargar</a><Boton variante="secundario" onClick={() => setVer(null)}>Cerrar</Boton></>}>
        {ver && (tipoDeArchivo(ver).clave === "imagen" ? <img src={ver.url} alt={ver.nombre_original || "Evidencia"} className="mx-auto max-h-[70vh] max-w-full rounded-lg object-contain" />
          : tipoDeArchivo(ver).clave === "video" ? <video src={ver.url} controls preload="metadata" className="mx-auto max-h-[70vh] w-full rounded-lg bg-black" />
          : <iframe src={ver.url} title={ver.nombre_original} className="h-[70vh] w-full rounded-lg border border-linea" />)}
      </Modal>
    </>
  );
}

export default function RevisionTarea({ tarea, onListo, onFallo }) {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const { usuario } = useSesion();
  const [catalogo] = useRecurso("catalogo");
  const [calidad, setCalidad] = useState(0);
  const [comentario, setComentario] = useState("");
  const [archivos, setArchivos] = useState([]);   // bocetos o imágenes para la corrección, si la devuelve
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(null);
  const [historial, setHistorial] = useState(false);
  const [g3, setG3] = useState({});
  const [causa, setCausa] = useState("");
  const oa = tarea.oa_info;
  const propia = tarea.colaborador === usuario?.id;   // validar lo propio: solo validar (queda como autovalidación)

  // Lo que la persona escribe se conserva cuando la pantalla se actualiza sola: solo se reinicia al cambiar de tarea.
  useEffect(() => {
    setCalidad(0); setComentario(""); setArchivos([]); setError(""); setHistorial(false); setCausa("");
    setG3(tarea.oa_info?.g3_marcados || {});
  }, [tarea.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const tarde = diasTarde(tarea);
  const equipo = [tarea.colaborador_nombre, ...(tarea.companeros_nombres || [])].join(" y ");
  const esc = ESCALA_CALIDAD[calidad - 1];

  const validar = async () => {
    if (!calidad) { setError("Elige la calidad del trabajo (1 a 5) para poder validarla."); return; }
    const ok = await confirmar({
      titulo: "¿Validar esta tarea?", boton: "Sí, validar",
      mensaje: `Vas a validar «${tarea.titulo}» con calidad ${calidad} · ${esc.etiqueta}. Desde ese momento suma al avance, al puntaje y al KPI de ${equipo}. Queda registrado en el historial.`,
    });
    if (!ok) return;
    setEnviando("validar"); setError("");
    try {
      await validarTarea(tarea.id, calidad, comentario.trim(), oa ? { g3 } : {});
      avisar(`Validada. Ya cuenta para el puntaje de ${equipo}.`);
      anunciarNovedades();
      onListo(tarea.id);
    } catch (e) { setError(e.message); setEnviando(null); onFallo?.(); }
  };
  const devolver = async () => {
    if (comentario.trim().length < 5) { setError("Para devolverla, escribe exactamente qué debe corregir en «Comentarios del supervisor»."); return; }
    const ok = await confirmar({
      titulo: `¿Devolver la tarea a ${tarea.colaborador_nombre}?`, boton: "Sí, devolver", peligro: true,
      mensaje: `${tarea.colaborador_nombre} recibirá tu comentario${archivos.length ? " y tus archivos de referencia" : ""} y tendrá que volver a entregarla. Mientras tanto no suma al avance, al puntaje ni al KPI. Queda registrado en el historial.`,
    });
    if (!ok) return;
    setEnviando("devolver"); setError("");
    try {
      await devolverTarea(tarea.id, comentario.trim(), oa ? { g3, causa_retrabajo: causa || null } : {}, archivos);
      avisar(`Devuelta a ${tarea.colaborador_nombre} con tu comentario${archivos.length ? " y tus archivos de referencia" : ""}.`);
      anunciarNovedades();
      onListo(tarea.id);
    } catch (e) { setError(e.message); setEnviando(null); onFallo?.(); }
  };
  const verHistorial = () => {
    setHistorial(true);
    setTimeout(() => document.getElementById(`historial-${tarea.id}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" }), 50);
  };

  return (
    <div className="space-y-6">
      <header className="flex items-start gap-3">
        <Avatar nombre={tarea.colaborador_nombre} tam="lg" />
        <div className="min-w-0 flex-1">
          <p className="text-base font-semibold leading-tight">{tarea.colaborador_nombre}</p>
          <p className="text-sm text-gris">{[tarea.colaborador_puesto, tarea.colaborador_departamento].filter(Boolean).join(" · ")}</p>
        </div>
        <Insignia tono={tarde === 0 ? "verde" : "amarillo"}>{tarde === 0 ? "A tiempo" : "Atrasada"}</Insignia>
      </header>
      {(tarea.puedo_eliminar || tarea.puedo_reabrir || tarea.puedo_gestionar) && (
        <div className="flex flex-wrap justify-end gap-2">
          <BotonesGestion tarea={tarea} tam="sm" onCambio={(t) => (t.estado === "EN_REVISION" ? onFallo() : onListo(tarea.id))} onEliminada={() => onListo(tarea.id)} />
        </div>
      )}

      <Seccion icono={ClipboardList} titulo="Información de la tarea">
        <h2 className="text-xl font-semibold leading-snug">{tarea.titulo}</h2>
        <p className="flex flex-wrap items-center gap-2 text-sm text-gris">
          <PrioridadTarea prioridad={tarea.prioridad} />
          {tarea.rondas_revision > 0 && <Insignia tono="rojo"><RotateCcw className="size-3" aria-hidden />Entrega n.º {tarea.rondas_revision + 1}</Insignia>}
          <EquipoTarea tarea={tarea} />
        </p>
        {tarea.descripcion && <TextoCopiable texto={tarea.descripcion} className="text-[15px]" />}
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 rounded-xl border border-linea p-4 sm:grid-cols-3">
          <Dato etiqueta="Asignada">{fechaCorta(tarea.fecha_creacion)}{tarea.asignada_por_nombre ? <span className="block text-xs font-normal text-gris">por {tarea.asignada_por_nombre}</span> : null}</Dato>
          <Dato etiqueta="Entregada">{fechaHora(entregaDe(tarea))}<span className="block text-xs font-normal text-gris">{textoEspera(tarea)}</span></Dato>
          <Dato etiqueta="Fecha límite">{fechaCorta(tarea.fecha_limite)}</Dato>
          <Dato etiqueta="Cumplimiento" className="col-span-2 sm:col-span-3">
            {tarde === 0 ? <span className="text-verde">Entregada a tiempo</span> : <span className="text-[#a86a00]">Entregada con {tarde} {tarde === 1 ? "día" : "días"} de atraso</span>}
          </Dato>
        </dl>
        <Pasos tarea={tarea} />
      </Seccion>

      <Seccion icono={Film} titulo="Evidencias entregadas" derecha={evidenciaActual(tarea).length ? `${evidenciaActual(tarea).length} ${evidenciaActual(tarea).length === 1 ? "archivo" : "archivos"}` : undefined}>
        <EvidenciasRevision tarea={tarea} />
      </Seccion>

      <div className="space-y-6 rounded-2xl border border-linea bg-fondo/60 p-4 sm:p-5">
        {error && <Alerta>{error}</Alerta>}
        {oa && (
          <div className="rounded-xl border border-linea bg-white p-3">
            <Checklist items={oa.g3} valor={g3} onCambio={setG3} titulo={`G3 · Control de calidad de ${oa.numero}`}
              ayuda="Validar es firmar el control de calidad interno: el trabajo no sale del área sin todas las casillas." />
            {oa.requiere_g4 && !oa.g4_aprobado && <Alerta tono="amarillo" className="mt-2">Falta la aprobación escrita del cliente (G4) en la Orden de Área.</Alerta>}
            <Campo etiqueta="Si la devuelves: causa del retrabajo (opcional)" className="mt-3">
              {(id) => <select id={id} className="campo" value={causa} onChange={(e) => setCausa(e.target.value)}>
                <option value="">Solo corrección, sin registrar retrabajo</option>{(catalogo?.causas_retrabajo || []).map((c) => <option key={c}>{c}</option>)}</select>}
            </Campo>
          </div>
        )}

        <Seccion icono={Star} titulo="Evaluación de calidad" derecha={calidad ? esc.etiqueta : "Obligatoria para validar"}>
          <div role="radiogroup" aria-label="Calidad del trabajo" className="grid grid-cols-5 gap-1.5 sm:gap-2">
            {ESCALA_CALIDAD.map((n) => {
              const activa = calidad === n.valor;
              return (
                <button key={n.valor} type="button" role="radio" aria-checked={activa} onClick={() => { setCalidad(n.valor); setError(""); }}
                  className={cx("flex flex-col items-center gap-0.5 rounded-xl border-2 px-1 py-2.5 text-center transition-all focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-azul/25",
                    activa ? `${n.tono} shadow-sm` : "border-linea bg-white text-tinta hover:border-azul/40")}>
                  <span className="font-display text-xl font-bold leading-none">{n.valor}</span>
                  <span className="text-[11px] font-semibold leading-tight sm:text-xs">{n.etiqueta}</span>
                  <span className="hidden text-[10px] leading-tight opacity-80 lg:block">{n.detalle}</span>
                </button>
              );
            })}
          </div>
        </Seccion>

        <Seccion icono={MessageSquareText} titulo="Comentarios del supervisor">
          <Campo etiqueta="Observaciones" ayuda="Opcional al validar. Si la devuelves es obligatorio: di exactamente qué corregir.">
            {(id) => <textarea id={id} className="campo bg-white" rows={3} value={comentario} maxLength={2000} onChange={(e) => { setComentario(e.target.value); setError(""); }} placeholder="Ej.: El logo está muy pequeño; sube el contraste del texto." />}
          </Campo>
          {!propia && <SelectorArchivos archivos={archivos} onCambio={setArchivos} etiqueta="Adjuntar boceto, imagen, documento o video para la corrección" ayuda="Se envían solo si la devuelves." disabled={!!enviando} />}
        </Seccion>

        {propia && <Alerta tono="amarillo">Esta tarea la creaste para ti: puedes validarla tú mismo. Quedará registrada en el historial como <b>autovalidación</b>. (Devolverla o reabrirla no aplica a tu propio trabajo.)</Alerta>}

        <div className="flex flex-wrap items-center gap-2 border-t border-linea pt-4">
          <button type="button" onClick={verHistorial} className="inline-flex h-11 items-center gap-2 rounded-lg px-3 text-sm font-medium text-gris hover:bg-white hover:text-azul"><History className="size-4" aria-hidden />Ver historial</button>
          <div className="ml-auto flex flex-wrap items-center justify-end gap-2">
            {!calidad && <span className="flex items-center gap-1 text-xs text-[#a86a00]"><TriangleAlert className="size-3.5" aria-hidden />Elige la calidad para validar</span>}
            {!propia && <Boton variante="secundario" icono={RotateCcw} onClick={devolver} cargando={enviando === "devolver"} disabled={!!enviando} className="!border-rojo/40 !text-rojo hover:!bg-rojo-50">Devolver tarea</Boton>}
            <Boton icono={CircleCheckBig} onClick={validar} cargando={enviando === "validar"} disabled={!!enviando || !calidad}>Validar tarea</Boton>
          </div>
        </div>
      </div>

      <Seccion icono={CalendarClock} titulo="Historial y trazabilidad" derecha={tarea.rondas_revision > 0 ? `Devuelta ${tarea.rondas_revision} ${tarea.rondas_revision === 1 ? "vez" : "veces"}` : "Sin devoluciones"}>
        <div id={`historial-${tarea.id}`}>
          {historial ? <Historial tareaId={tarea.id} />
            : <button type="button" onClick={() => setHistorial(true)} className="inline-flex items-center gap-1.5 text-sm font-medium text-azul hover:underline"><Clock className="size-4" aria-hidden />Mostrar entregas, devoluciones, comentarios y validaciones anteriores</button>}
        </div>
      </Seccion>
    </div>
  );
}
