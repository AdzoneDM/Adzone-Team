// Piezas de tareas que comparten Mis tareas, Por validar y Tareas del equipo.
import { useEffect, useRef, useState } from "react";
import { Briefcase, Camera, Check, ExternalLink, FileText, ImagePlus, Link2, Repeat, Target, Users, X } from "lucide-react";
import { entregarTarea, historialTarea, marcarPaso } from "@/lib/api";
import { fechaCorta, fechaHora, vencimiento } from "@/lib/formato";
import { Alerta, Boton, Campo, EstadoTarea, Estrellas, Insignia, Modal, PrioridadTarea, cx } from "@/components/ui";

const MAX_LADO = 1600;
const MAX_ARCHIVOS = 6;

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
      {mostrar.length > 0 && (
        <ul className="grid grid-cols-[repeat(auto-fill,minmax(96px,1fr))] gap-2">
          {mostrar.map((e) => (
            <li key={e.id}>
              {e.es_imagen ? (
                <button type="button" onClick={() => setGrande(e)} className="block w-full overflow-hidden rounded-lg border border-linea bg-fondo">
                  <img src={e.url} alt={e.nombre_original || "Evidencia"} loading="lazy" className="aspect-square w-full object-cover" />
                </button>
              ) : (
                <a href={e.url} target="_blank" rel="noopener noreferrer" className="flex aspect-square flex-col items-center justify-center gap-1 rounded-lg border border-linea bg-fondo p-2 text-center text-xs text-gris hover:text-azul">
                  <FileText className="size-6" /><span className="line-clamp-2 break-all">{e.nombre_original}</span>
                </a>
              )}
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

const ICONO_HISTORIAL = { DEVUELTA: "bg-rojo", VALIDADA: "bg-amarillo", REABIERTA: "bg-rojo", ENTREGADA: "bg-azul", CANCELADA: "bg-gris" };

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
          <p className="text-sm"><span className="font-medium">{h.accion_texto}</span> <span className="text-gris">por {h.usuario_nombre} · {fechaHora(h.fecha)}</span></p>
          {h.comentario && h.accion !== "EDITADA" && <p className="mt-0.5 whitespace-pre-line text-sm text-gris">{h.comentario}</p>}
        </li>
      ))}
    </ol>
  );
}

/** Datos de una tarea; las acciones las pone cada pantalla en `pie`. */
export function DetalleTarea({ tarea, abierto, onCerrar, pie, onCambio }) {
  if (!tarea) return null;
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={tarea.titulo} ancho="md:max-w-2xl" pie={pie}>
      <div className="space-y-5">
        <div className="flex flex-wrap items-center gap-2">
          <EstadoTarea estado={tarea.estado} />
          <PrioridadTarea prioridad={tarea.prioridad} />
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
          {tarea.kpi_nombre && <div className="col-span-2 sm:col-span-3"><dt className="text-gris">Suma al KPI</dt><dd className="flex items-center gap-1.5 font-medium"><Target className="size-4 text-azul" />{tarea.kpi_nombre}</dd></div>}
        </dl>
        {tarea.descripcion && <p className="whitespace-pre-line text-[15px]">{tarea.descripcion}</p>}

        <Pasos tarea={tarea} onCambio={onCambio} />

        {tarea.comentario_revision && tarea.estado !== "COMPLETADA" && (
          <Alerta tono="rojo"><p className="font-medium">Para corregir</p><p className="whitespace-pre-line">{tarea.comentario_revision}</p></Alerta>
        )}

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
  const galeria = useRef(null);

  useEffect(() => { if (abierto) { setNota(""); setEnlace(""); setArchivos([]); setError(""); } }, [abierto, tarea?.id]);

  const agregar = async (lista) => {
    const nuevos = Array.from(lista || []);
    if (archivos.length + nuevos.length > MAX_ARCHIVOS) setError(`Como máximo ${MAX_ARCHIVOS} archivos por entrega.`);
    const listos = await Promise.all(nuevos.slice(0, MAX_ARCHIVOS - archivos.length).map(achicarFoto));
    setArchivos((a) => [...a, ...listos.map((f) => ({ f, url: f.type.startsWith("image/") ? URL.createObjectURL(f) : null }))]);
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
        <Boton type="submit" form="form-entrega" variante="acento" cargando={enviando}>{archivos.length ? "Subir y entregar" : "Entregar"}</Boton>
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
          <p className="etiqueta">Fotos o PDF (opcional, hasta {MAX_ARCHIVOS})</p>
          <div className="grid grid-cols-2 gap-2 md:flex">
            <Boton variante="secundario" icono={Camera} onClick={() => camara.current?.click()} className="md:hidden">Tomar foto</Boton>
            <Boton variante="secundario" icono={ImagePlus} onClick={() => galeria.current?.click()}>Elegir archivos</Boton>
          </div>
          <input ref={camara} type="file" accept="image/*" capture="environment" className="sr-only" tabIndex={-1} onChange={(e) => { agregar(e.target.files); e.target.value = ""; }} />
          <input ref={galeria} type="file" accept="image/*,application/pdf" multiple className="sr-only" tabIndex={-1} onChange={(e) => { agregar(e.target.files); e.target.value = ""; }} />
          {archivos.length > 0 && (
            <ul className="mt-3 grid grid-cols-[repeat(auto-fill,minmax(84px,1fr))] gap-2">
              {archivos.map((a, i) => (
                <li key={i} className="relative">
                  {a.url ? <img src={a.url} alt={`Archivo ${i + 1}`} className="aspect-square w-full rounded-lg object-cover" />
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

