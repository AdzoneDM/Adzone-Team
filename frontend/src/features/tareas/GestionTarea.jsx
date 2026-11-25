// Editar, reabrir y eliminar una tarea desde cualquier pantalla donde se abra (Mi equipo, Historial, Mis tareas, Por validar,
// Proyectos). Cada botón sale solo a quien tiene el permiso sobre esa tarea (Accesos y permisos → Editar / Reabrir / Eliminar tareas).
import { useEffect, useState } from "react";
import { Pencil, RotateCcw, Trash2 } from "lucide-react";
import { eliminarTarea, equipo as cargarEquipo, obtenerTarea, reabrirTarea } from "@/lib/api";
import { Boton, Campo, Modal, useAviso } from "@/components/ui";
import FormTarea from "@/features/tareas/FormTarea";

/** Reabrir en cualquier estado: motivo, a dónde vuelve (revisar otra vez o corregir) y, si hace falta, fecha e instrucciones nuevas. */
export function ModalReabrir({ tarea, onCerrar, onHecho }) {
  const avisar = useAviso();
  const [d, setD] = useState({});
  const [enviando, setEnviando] = useState(false);
  useEffect(() => { if (tarea) setD({ motivo: "", a: "CORREGIR", fecha_limite: tarea.fecha_limite || "", descripcion: tarea.descripcion || "" }); }, [tarea]);
  if (!tarea) return null;
  const entregada = ["EN_REVISION", "COMPLETADA"].includes(tarea.estado) || !!tarea.fecha_entrega_real;
  const elegirDestino = entregada && tarea.estado !== "EN_REVISION";
  const enviar = async () => {
    setEnviando(true);
    try {
      await reabrirTarea(tarea.id, {
        motivo: d.motivo.trim(), a: elegirDestino ? d.a : "CORREGIR",
        ...(d.fecha_limite && d.fecha_limite !== tarea.fecha_limite ? { fecha_limite: d.fecha_limite } : {}),
        ...(d.descripcion !== (tarea.descripcion || "") ? { descripcion: d.descripcion } : {}),
      });
      avisar(tarea.estado === "COMPLETADA" ? "Reabierta: dejó de contar como validada hasta que se valide otra vez. Le llegó el aviso." : "Reabierta. Le llegó el aviso.");
      onHecho();
    } catch (e) { avisar(e.message, "rojo"); }
    setEnviando(false);
  };
  return (
    <Modal abierto onCerrar={onCerrar} titulo="Reabrir tarea" ancho="md:max-w-lg"
      descripcion={tarea.estado === "COMPLETADA" ? "Deja de contar para el puntaje, el avance y los KPIs hasta que se valide otra vez. Las entregas y comentarios anteriores se conservan." : "Vuelve al flujo de entrega y validación. Las entregas y comentarios anteriores se conservan."}
      pie={<><Boton variante="secundario" onClick={onCerrar}>Volver</Boton><Boton icono={RotateCcw} cargando={enviando} onClick={enviar} disabled={(d.motivo || "").trim().length < 5}>Reabrir</Boton></>}>
      <div className="space-y-4">
        <Campo etiqueta="Motivo" ayuda="Mínimo 5 letras. Le llega a la persona y queda en el historial.">{(id) => <textarea id={id} className="campo" rows={3} value={d.motivo || ""} onChange={(e) => setD({ ...d, motivo: e.target.value })} autoFocus />}</Campo>
        {elegirDestino && (
          <fieldset>
            <legend className="mb-1.5 text-sm font-medium">¿Qué pasa ahora?</legend>
            <div className="space-y-1.5">
              <label className="flex items-start gap-2 text-sm"><input type="radio" name="destino" className="mt-1 accent-azul" checked={d.a === "CORREGIR"} onChange={() => setD({ ...d, a: "CORREGIR" })} /><span><b>Que la corrija</b> y la entregue de nuevo</span></label>
              <label className="flex items-start gap-2 text-sm"><input type="radio" name="destino" className="mt-1 accent-azul" checked={d.a === "REVISION"} onChange={() => setD({ ...d, a: "REVISION" })} /><span><b>Revisar otra vez</b> la misma entrega</span></label>
            </div>
          </fieldset>
        )}
        <Campo etiqueta="Nueva fecha de entrega" ayuda="Opcional.">{(id) => <input id={id} type="date" className="campo" value={d.fecha_limite || ""} onChange={(e) => setD({ ...d, fecha_limite: e.target.value })} />}</Campo>
        <Campo etiqueta="Instrucciones" ayuda="Opcional: actualízalas si cambió lo que hay que hacer.">{(id) => <textarea id={id} className="campo" rows={4} value={d.descripcion || ""} onChange={(e) => setD({ ...d, descripcion: e.target.value })} />}</Campo>
      </div>
    </Modal>
  );
}

/** Eliminar con confirmación y motivo obligatorio. Se conserva (auditoría) y se puede recuperar desde «Eliminadas». */
export function ModalEliminar({ tarea, onCerrar, onHecho }) {
  const avisar = useAviso();
  const [motivo, setMotivo] = useState("");
  const [enviando, setEnviando] = useState(false);
  useEffect(() => { setMotivo(""); }, [tarea]);
  if (!tarea) return null;
  const enviar = async () => {
    setEnviando(true);
    try { await eliminarTarea(tarea.id, motivo.trim()); avisar("Tarea eliminada. Puedes recuperarla en «Eliminadas»."); onHecho(); } catch (e) { avisar(e.message, "rojo"); }
    setEnviando(false);
  };
  return (
    <Modal abierto onCerrar={onCerrar} titulo="¿Eliminar esta tarea?" ancho="md:max-w-md"
      descripcion={`«${tarea.titulo}» deja de aparecer y de contar para el avance, el puntaje y los KPIs. Se conserva con su historial y se puede recuperar.`}
      pie={<><Boton variante="secundario" onClick={onCerrar}>Volver</Boton><Boton variante="peligro" icono={Trash2} cargando={enviando} onClick={enviar} disabled={motivo.trim().length < 5}>Eliminar</Boton></>}>
      <Campo etiqueta="Motivo" ayuda="Obligatorio (mínimo 5 letras): creada por error, duplicada, ya no hace falta…">{(id) => <textarea id={id} className="campo" rows={3} value={motivo} onChange={(e) => setMotivo(e.target.value)} autoFocus />}</Campo>
    </Modal>
  );
}

/** Botones Eliminar · Reabrir · Editar de una tarea, con sus ventanas. `onCambio(tarea)` tras editar o reabrir; `onEliminada()` tras eliminar. */
export function BotonesGestion({ tarea, onCambio, onEliminada, tam }) {
  const avisar = useAviso();
  const [reabriendo, setReabriendo] = useState(null);
  const [eliminando, setEliminando] = useState(null);
  const [editando, setEditando] = useState(null);
  const [gente, setGente] = useState([]);
  useEffect(() => { if (editando) cargarEquipo().then(setGente).catch(() => setGente([])); }, [editando]);
  if (!tarea || !(tarea.puedo_eliminar || tarea.puedo_reabrir || tarea.puedo_gestionar)) return null;
  const refrescar = async () => { try { onCambio?.(await obtenerTarea(tarea.id)); } catch { onEliminada?.(); } };
  return (
    <>
      {tarea.puedo_eliminar && <Boton variante="peligro" tam={tam} icono={Trash2} onClick={() => setEliminando(tarea)} className="mr-auto">Eliminar</Boton>}
      {tarea.puedo_reabrir && <Boton variante="secundario" tam={tam} icono={RotateCcw} onClick={() => setReabriendo(tarea)}>Reabrir</Boton>}
      {tarea.puedo_gestionar && <Boton variante="secundario" tam={tam} icono={Pencil} onClick={() => setEditando(tarea)}>Editar</Boton>}
      <ModalReabrir tarea={reabriendo} onCerrar={() => setReabriendo(null)} onHecho={() => { setReabriendo(null); refrescar(); }} />
      <ModalEliminar tarea={eliminando} onCerrar={() => setEliminando(null)} onHecho={() => { setEliminando(null); onEliminada?.(); }} />
      <FormTarea abierto={!!editando} inicial={editando} gente={gente} onCerrar={() => setEditando(null)}
        onGuardada={(msg) => { setEditando(null); avisar(msg); refrescar(); }} />
    </>
  );
}
