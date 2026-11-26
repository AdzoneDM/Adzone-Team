// Asignar o editar una tarea (también recurrente). Se usa en Mi equipo y en los proyectos.
import { useEffect, useState } from "react";
import { ArrowRight, Repeat, Sparkles } from "lucide-react";
import { guardarRecurrente, guardarTarea, subirReferencias, sugerirAsignacion } from "@/lib/api";
import { SelectorCliente, SelectorProyecto } from "@/components/Selectores";
import { useSesion } from "@/lib/sesion";
import { SelectorArchivos } from "@/features/tareas/componentes";
import { diasHasta, hoyISO, sumarDias } from "@/lib/formato";
import { Alerta, Boton, Campo, Modal, cx } from "@/components/ui";

const DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
const masDias = (n) => sumarDias(hoyISO(), n);

export default function FormTarea({ abierto, onCerrar, inicial, gente, onGuardada }) {
  const [f, setF] = useState({});
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const { usuario } = useSesion();
  const [sugeridos, setSugeridos] = useState([]);
  const [referencias, setReferencias] = useState([]); // bocetos o imágenes para que la persona tenga de guía
  const editando = !!inicial?.id;
  const esRecurrente = inicial?.tipo === "recurrente";
  const validada = editando && !esRecurrente && inicial?.estado === "COMPLETADA";

  useEffect(() => {
    if (!abierto) return;
    setError("");
    setReferencias([]);
    setF(inicial?.id ? {
      ...inicial, repetir: esRecurrente, companeros: inicial.companeros || [],
      pasosTexto: (inicial.pasos || []).map((p) => p.texto).join("\n"),
      proyecto: inicial.proyecto ? String(inicial.proyecto) : "", fecha_inicio: inicial.fecha_inicio || "",
      cliente_ref: inicial.cliente_ref ? String(inicial.cliente_ref) : "",
      horas_estimadas: inicial.horas_estimadas ?? "",
    } : {
      titulo: "", descripcion: "", cliente: inicial?.cliente || "", cliente_ref: inicial?.cliente_ref ? String(inicial.cliente_ref) : "", colaborador: inicial?.colaborador || "", companeros: [], pasosTexto: "",
      prioridad: "MEDIA", fecha_limite: masDias(3), kpi_asignado: "", repetir: false, frecuencia: "SEMANAL", dia_semana: 4, dia_mes: 28,
      proyecto: inicial?.proyecto ? String(inicial.proyecto) : "", fecha_inicio: "", horas_estimadas: "",
    });
  }, [abierto, inicial, esRecurrente]);

  const persona = gente.find((g) => String(g.id) === String(f.colaborador));
  const kpis = persona?.kpis_por_tareas || [];
  const cambiar = (campo) => (e) => setF((x) => ({ ...x, [campo]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));

  // Cambiar fechas, prioridad o responsable de una tarea ya creada exige decir por qué (queda en el historial y le llega a quien participa)
  const cambiosCriticos = editando && !esRecurrente && !f.repetir ? [
    String(f.fecha_limite || "") !== String(inicial.fecha_limite || "") && "la fecha de entrega",
    String(f.fecha_inicio || "") !== String(inicial.fecha_inicio || "") && "la fecha de inicio",
    f.prioridad !== inicial.prioridad && "la prioridad",
    String(f.colaborador || "") !== String(inicial.colaborador || "") && "el responsable",
  ].filter(Boolean) : [];
  const pideMotivo = cambiosCriticos.length > 0;

  const guardar = async (e) => {
    e.preventDefault();
    setError("");
    if (!f.titulo?.trim()) return setError("Escribe qué hay que hacer.");
    if (!f.colaborador) return setError("Elige a quién se la asignas.");
    if (!f.repetir && !f.fecha_limite) return setError("Pon la fecha límite.");
    if (pideMotivo && (f.motivo || "").trim().length < 5) return setError("Cuéntanos por qué cambias " + cambiosCriticos.join(", ") + " (mínimo 5 letras).");
    setGuardando(true);
    try {
      if (f.repetir) {
        await guardarRecurrente({
          id: esRecurrente ? f.id : undefined, titulo: f.titulo.trim(), descripcion: f.descripcion || "",
          colaborador: Number(f.colaborador), prioridad: f.prioridad, kpi_asignado: f.kpi_asignado || null,
          frecuencia: f.frecuencia, dia_semana: Number(f.dia_semana), dia_mes: Number(f.dia_mes),
          inicio: f.inicio || hoyISO(), activa: f.activa ?? true,
        });
        onGuardada(esRecurrente ? "Tarea recurrente actualizada." : "Tarea recurrente creada. Las próximas ya aparecen en la lista.");
      } else {
        const guardada = await guardarTarea({
          id: f.id, titulo: f.titulo.trim(), descripcion: f.descripcion || "",
          // El cliente registrado (expediente); si no se eligió, se conserva el texto que ya tenía la tarea
          cliente_ref: f.cliente_ref ? Number(f.cliente_ref) : null, cliente: f.cliente_ref ? undefined : (f.cliente || "").trim(),
          colaborador: Number(f.colaborador), companeros: (f.companeros || []).map(Number).filter((c) => c !== Number(f.colaborador)),
          pasos_texto: (f.pasosTexto || "").split("\n").map((t) => t.trim()).filter(Boolean),
          prioridad: f.prioridad, fecha_limite: f.fecha_limite, kpi_asignado: f.kpi_asignado || null,
          proyecto: f.proyecto ? Number(f.proyecto) : null, fecha_inicio: f.fecha_inicio || null,
          horas_estimadas: f.horas_estimadas === "" || f.horas_estimadas == null ? null : f.horas_estimadas,
          ...(pideMotivo ? { motivo: f.motivo.trim() } : {}),
          // Tarea ya validada: se puede ajustar la evaluación (recalcula el puntaje)
          ...(validada && (Number(f.calificacion_calidad) !== Number(inicial.calificacion_calidad) || (f.comentario_evaluacion || "") !== (inicial.comentario_evaluacion || ""))
            ? { calificacion_calidad: Number(f.calificacion_calidad), comentario_evaluacion: f.comentario_evaluacion || "" } : {}),
        });
        let sinReferencias = "";
        if (referencias.length) {
          try { await subirReferencias(guardada.id, referencias, { momento: guardada.rondas_revision > 0 ? "CORRECCION" : "ASIGNACION" }); } catch (err) { sinReferencias = ` Pero los archivos no se pudieron subir: ${err.message} Agrégalos desde la tarea.`; }
        }
        const otros = (f.companeros || []).length;
        onGuardada(sinReferencias ? (editando ? "Cambios guardados." : `Tarea asignada a ${persona?.nombre}.`) + sinReferencias : editando ? "Cambios guardados." : `Tarea asignada a ${persona?.nombre}${otros ? ` y ${otros} más` : ""}. Les llegó el aviso${referencias.length ? " con tus archivos de referencia" : ""}.`);
      }
    } catch (err) { setError(err.message); }
    setGuardando(false);
  };

  const pasada = !f.repetir && f.fecha_limite && diasHasta(f.fecha_limite) < 0;
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} ancho="md:max-w-2xl"
      titulo={esRecurrente ? "Editar tarea recurrente" : editando ? "Editar tarea" : "Nueva tarea"}
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton type="submit" form="form-tarea" cargando={guardando}>{editando ? "Guardar cambios" : f.repetir ? "Programar" : "Asignar tarea"}</Boton></>}>
      <form id="form-tarea" onSubmit={guardar} className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        {validada && (
          <div className="rounded-lg border border-amarillo/40 bg-amarillo/10 p-3">
            <p className="text-sm">Esta tarea ya está <b>validada</b>. Los cambios quedan en el historial con el antes y el después, y el puntaje se recalcula.</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-[auto_1fr]">
              <Campo etiqueta="Calidad">{(id) => (
                <select id={id} className="campo" value={f.calificacion_calidad ?? ""} onChange={cambiar("calificacion_calidad")}>
                  {[5, 4, 3, 2, 1].map((n) => <option key={n} value={n}>{"★".repeat(n)} {n}/5</option>)}
                </select>
              )}</Campo>
              <Campo etiqueta="Comentario de la evaluación">{(id) => <input id={id} className="campo" value={f.comentario_evaluacion || ""} onChange={cambiar("comentario_evaluacion")} maxLength={2000} />}</Campo>
            </div>
          </div>
        )}
        <Campo etiqueta="Qué hay que hacer">{(id) => <input id={id} className="campo" value={f.titulo || ""} onChange={cambiar("titulo")} maxLength={255} autoFocus />}</Campo>
        <Campo etiqueta="Detalles (opcional)">{(id) => <textarea id={id} className="campo" rows={3} value={f.descripcion || ""} onChange={cambiar("descripcion")} />}</Campo>
        {!f.repetir && (
          <SelectorArchivos archivos={referencias} onCambio={setReferencias} etiqueta="Adjuntar boceto, imagen o video de referencia" ayuda="Para que la persona tenga una guía visual." disabled={guardando} />
        )}
        {!f.repetir && (
          <div className="grid gap-4 sm:grid-cols-2">
            <SelectorCliente etiqueta="Cliente (opcional)" requerido={false} valor={f.cliente_ref}
              ayuda={!f.cliente_ref && f.cliente ? `Antes decía «${f.cliente}»: elígelo de la lista para que quede en su expediente.` : "Queda en el expediente del cliente."}
              onCambio={(id) => setF((x) => ({ ...x, cliente_ref: id, proyecto: id && x.proyecto && x.proyectoCliente && String(x.proyectoCliente) !== String(id) ? "" : x.proyecto }))} />
            <SelectorProyecto cliente={f.cliente_ref || undefined} valor={f.proyecto}
              onCambio={(id, o) => setF((x) => ({ ...x, proyecto: id, proyectoCliente: o?.cliente || "", cliente_ref: o?.cliente ? String(o.cliente) : x.cliente_ref }))} />
          </div>
        )}
        {!editando && !esRecurrente && <Sugerencias titulo={f.titulo} descripcion={f.descripcion} lista={sugeridos} setLista={setSugeridos}
          elegido={f.colaborador} onElegir={(id) => setF((x) => ({ ...x, colaborador: String(id), kpi_asignado: "" }))} />}
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Responsable">
            {(id) => (
              <select id={id} className="campo" value={f.colaborador || ""} onChange={(e) => setF((x) => ({ ...x, colaborador: e.target.value, kpi_asignado: "" }))} disabled={esRecurrente}>
                <option value="">Elige una persona…</option>
                {/* Con varias áreas (aporte entre áreas), la lista se agrupa por departamento; con una sola queda plana */}
                {(() => {
                  const opcion = (g) => <option key={g.id} value={g.id}>{g.nombre}{g.puesto ? ` (${g.puesto})` : ""}</option>;
                  const areas = [...new Set(gente.map((g) => g.departamento || "Sin área"))];
                  if (areas.length < 2) return gente.map(opcion);
                  return areas.map((a) => <optgroup key={a} label={a}>{gente.filter((g) => (g.departamento || "Sin área") === a).map(opcion)}</optgroup>);
                })()}
              </select>
            )}
          </Campo>
          <Campo etiqueta="Prioridad" ayuda="Urgente pesa 4 veces en el puntaje; alta 3; media 2; baja 1.">
            {(id) => <select id={id} className="campo" value={f.prioridad} onChange={cambiar("prioridad")}><option value="URGENTE">Urgente</option><option value="ALTA">Alta</option><option value="MEDIA">Media</option><option value="BAJA">Baja</option></select>}
          </Campo>
        </div>
        {persona && (
          <p className="flex flex-wrap items-center gap-2 rounded-lg bg-fondo px-3 py-2 text-sm">
            <span className="text-gris">Asigna</span><b className="font-semibold">{editando && inicial?.asignada_por_nombre ? inicial.asignada_por_nombre : `${usuario?.nombre || "Tú"} (tú)`}</b>
            <ArrowRight className="size-4 text-gris" aria-hidden /><span className="text-gris">Recibe</span><b className="font-semibold text-azul">{persona.nombre}</b>
            {(f.companeros || []).length > 0 && <span className="text-gris">y {(f.companeros || []).length} más</span>}
          </p>
        )}
        {pideMotivo && (
          <Campo etiqueta="Motivo del cambio" ayuda={`Cambias ${cambiosCriticos.join(", ")}. Le llega a quienes participan y queda en el historial.`}>
            {(id) => <textarea id={id} rows={2} className="campo" required minLength={5} maxLength={300} value={f.motivo || ""} onChange={cambiar("motivo")} placeholder="Ej.: el cliente movió el evento" />}
          </Campo>
        )}
        {!f.repetir && gente.length > 1 && (
          <fieldset>
            <legend className="etiqueta">Trabaja con (opcional)</legend>
            <p className="-mt-1 mb-2 text-sm text-gris">Cada quien la ve en sus tareas y le suma a todos cuando la validas.</p>
            <div className="flex flex-wrap gap-2">
              {gente.filter((g) => String(g.id) !== String(f.colaborador)).map((g) => {
                const activo = (f.companeros || []).map(String).includes(String(g.id));
                return (
                  <button key={g.id} type="button" aria-pressed={activo}
                    onClick={() => setF((x) => ({ ...x, companeros: activo ? x.companeros.filter((c) => String(c) !== String(g.id)) : [...(x.companeros || []), g.id] }))}
                    className={cx("min-h-10 rounded-full border px-3.5 text-sm font-medium transition-colors",
                      activo ? "border-azul bg-azul text-white" : "border-linea bg-white text-tinta hover:border-azul")}>
                    {g.nombre}
                  </button>
                );
              })}
            </div>
          </fieldset>
        )}
        {!f.repetir && (
          <Campo etiqueta="Pasos (opcional)" ayuda="Uno por línea. La persona los marca a medida que avanza y tú ves el progreso.">
            {(id) => <textarea id={id} className="campo" rows={3} value={f.pasosTexto || ""} onChange={cambiar("pasosTexto")} placeholder={"Boceto\nDiseño final\nPublicar"} />}
          </Campo>
        )}
        <Campo etiqueta="Suma al KPI (opcional)" ayuda={persona && !kpis.length ? "El puesto de esta persona no tiene KPIs automáticos." : "Cada tarea validada suma 1 a ese KPI del puesto."}>
          {(id) => (
            <select id={id} className="campo" value={f.kpi_asignado || ""} onChange={cambiar("kpi_asignado")} disabled={!kpis.length}>
              <option value="">Ninguno</option>
              {kpis.map((k) => <option key={k.id} value={k.id}>{k.nombre}</option>)}
            </select>
          )}
        </Campo>

        {!editando && (
          <label className="flex items-center gap-2.5 rounded-lg border border-linea px-3 py-3 text-[15px]">
            <input type="checkbox" checked={!!f.repetir} onChange={cambiar("repetir")} className="size-4 accent-azul" />
            <Repeat className="size-4 text-azul" /> Se repite (crear una cada semana o cada mes)
          </label>
        )}
        {f.repetir ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <Campo etiqueta="Cada cuánto">{(id) => <select id={id} className="campo" value={f.frecuencia} onChange={cambiar("frecuencia")}><option value="SEMANAL">Cada semana</option><option value="MENSUAL">Cada mes</option></select>}</Campo>
            {f.frecuencia === "SEMANAL" ? (
              <Campo etiqueta="Día de entrega">{(id) => <select id={id} className="campo" value={f.dia_semana} onChange={cambiar("dia_semana")}>{DIAS.map((d, i) => <option key={d} value={i}>{d}</option>)}</select>}</Campo>
            ) : (
              <Campo etiqueta="Día del mes" ayuda="Del 1 al 28, para que exista en todos los meses.">{(id) => <input id={id} type="number" min={1} max={28} className="campo" value={f.dia_mes} onChange={cambiar("dia_mes")} />}</Campo>
            )}
            <p className="text-sm text-gris sm:col-span-2">Cada tarea se crea una semana antes de su entrega y le llega el aviso a la persona.</p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-3">
            <Campo etiqueta="Empieza (opcional)" ayuda="Para el cronograma.">
              {(id) => <input id={id} type="date" className="campo" value={f.fecha_inicio || ""} max={f.fecha_limite || undefined} onChange={cambiar("fecha_inicio")} />}
            </Campo>
            <Campo etiqueta="Fecha límite" error={pasada ? "Esa fecha ya pasó: contará como vencida si no se entrega." : ""}>
              {(id) => <input id={id} type="date" className="campo" value={f.fecha_limite || ""} onChange={cambiar("fecha_limite")} />}
            </Campo>
            <Campo etiqueta="Horas estimadas" ayuda="Para medir la carga.">
              {(id) => <input id={id} type="number" min={0} step="0.5" inputMode="decimal" className="campo" value={f.horas_estimadas ?? ""} onChange={cambiar("horas_estimadas")} />}
            </Campo>
          </div>
        )}
      </form>
    </Modal>
  );
}


/** A quién conviene asignarla: menos carga, buen cumplimiento y calidad, y experiencia en tareas parecidas. */
function Sugerencias({ titulo, descripcion, lista, setLista, elegido, onElegir }) {
  useEffect(() => {
    if (!titulo || titulo.trim().length < 4) { setLista([]); return undefined; }
    const t = setTimeout(() => sugerirAsignacion(titulo, descripcion).then((l) => setLista(l.slice(0, 3))).catch(() => setLista([])), 600);
    return () => clearTimeout(t);
  }, [titulo, descripcion, setLista]);
  if (!lista.length) return null;
  return (
    <div className="rounded-lg border border-azul/20 bg-azul/5 p-3">
      <p className="mb-2 flex items-center gap-1.5 text-sm font-medium text-azul"><Sparkles className="size-4" />Sugerencia para asignar</p>
      <div className="space-y-1.5">
        {lista.map((p) => (
          <button key={p.id} type="button" onClick={() => onElegir(p.id)} aria-pressed={String(elegido) === String(p.id)}
            className={cx("flex w-full items-start gap-2 rounded-md border px-2.5 py-1.5 text-left text-sm",
              String(elegido) === String(p.id) ? "border-azul bg-white" : "border-transparent hover:border-linea hover:bg-white")}>
            <span className="font-medium">{p.nombre}</span><span className="min-w-0 flex-1 truncate text-gris">{p.razon}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
