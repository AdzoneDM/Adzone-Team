// Asignar o editar una tarea (también recurrente). Se usa en Mi equipo y en los proyectos.
import { useEffect, useState } from "react";
import { Repeat } from "lucide-react";
import { guardarRecurrente, guardarTarea, listarProyectos } from "@/lib/api";
import { diasHasta, hoyISO, sumarDias } from "@/lib/formato";
import { Alerta, Boton, Campo, Modal, cx } from "@/components/ui";

const DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
const masDias = (n) => sumarDias(hoyISO(), n);

export default function FormTarea({ abierto, onCerrar, inicial, gente, onGuardada }) {
  const [f, setF] = useState({});
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [proyectos, setProyectos] = useState([]);
  const editando = !!inicial?.id;
  const esRecurrente = inicial?.tipo === "recurrente";

  useEffect(() => {
    if (!abierto) return;
    setError("");
    setF(inicial?.id ? {
      ...inicial, repetir: esRecurrente, companeros: inicial.companeros || [],
      pasosTexto: (inicial.pasos || []).map((p) => p.texto).join("\n"),
      proyecto: inicial.proyecto ? String(inicial.proyecto) : "", fecha_inicio: inicial.fecha_inicio || "",
      horas_estimadas: inicial.horas_estimadas ?? "",
    } : {
      titulo: "", descripcion: "", cliente: inicial?.cliente || "", colaborador: inicial?.colaborador || "", companeros: [], pasosTexto: "",
      prioridad: "MEDIA", fecha_limite: masDias(3), kpi_asignado: "", repetir: false, frecuencia: "SEMANAL", dia_semana: 4, dia_mes: 28,
      proyecto: inicial?.proyecto ? String(inicial.proyecto) : "", fecha_inicio: "", horas_estimadas: "",
    });
    listarProyectos({ activos: 1 }).then(setProyectos).catch(() => setProyectos([]));
  }, [abierto, inicial, esRecurrente]);

  const persona = gente.find((g) => String(g.id) === String(f.colaborador));
  const kpis = persona?.kpis_por_tareas || [];
  const cambiar = (campo) => (e) => setF((x) => ({ ...x, [campo]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));

  const guardar = async (e) => {
    e.preventDefault();
    setError("");
    if (!f.titulo?.trim()) return setError("Escribe qué hay que hacer.");
    if (!f.colaborador) return setError("Elige a quién se la asignas.");
    if (!f.repetir && !f.fecha_limite) return setError("Pon la fecha límite.");
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
        await guardarTarea({
          id: f.id, titulo: f.titulo.trim(), descripcion: f.descripcion || "", cliente: (f.cliente || "").trim(),
          colaborador: Number(f.colaborador), companeros: (f.companeros || []).map(Number).filter((c) => c !== Number(f.colaborador)),
          pasos_texto: (f.pasosTexto || "").split("\n").map((t) => t.trim()).filter(Boolean),
          prioridad: f.prioridad, fecha_limite: f.fecha_limite, kpi_asignado: f.kpi_asignado || null,
          proyecto: f.proyecto ? Number(f.proyecto) : null, fecha_inicio: f.fecha_inicio || null,
          horas_estimadas: f.horas_estimadas === "" || f.horas_estimadas == null ? null : f.horas_estimadas,
        });
        const otros = (f.companeros || []).length;
        onGuardada(editando ? "Cambios guardados." : `Tarea asignada a ${persona?.nombre}${otros ? ` y ${otros} más` : ""}. Les llegó el aviso.`);
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
        <Campo etiqueta="Qué hay que hacer">{(id) => <input id={id} className="campo" value={f.titulo || ""} onChange={cambiar("titulo")} maxLength={255} autoFocus />}</Campo>
        <Campo etiqueta="Detalles (opcional)">{(id) => <textarea id={id} className="campo" rows={3} value={f.descripcion || ""} onChange={cambiar("descripcion")} />}</Campo>
        <Campo etiqueta="Cliente (opcional)">{(id) => <input id={id} className="campo" value={f.cliente || ""} onChange={cambiar("cliente")} maxLength={150} placeholder="Ej.: Plaza Bonao" />}</Campo>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Responsable">
            {(id) => (
              <select id={id} className="campo" value={f.colaborador || ""} onChange={(e) => setF((x) => ({ ...x, colaborador: e.target.value, kpi_asignado: "" }))} disabled={esRecurrente}>
                <option value="">Elige una persona…</option>
                {gente.map((g) => <option key={g.id} value={g.id}>{g.nombre}{g.puesto ? ` (${g.puesto})` : ""}</option>)}
              </select>
            )}
          </Campo>
          <Campo etiqueta="Prioridad" ayuda="Alta pesa 3 veces en el puntaje; media 2; baja 1.">
            {(id) => <select id={id} className="campo" value={f.prioridad} onChange={cambiar("prioridad")}><option value="ALTA">Alta</option><option value="MEDIA">Media</option><option value="BAJA">Baja</option></select>}
          </Campo>
        </div>
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
        {!f.repetir && (
          <Campo etiqueta="Proyecto (opcional)">
            {(id) => (
              <select id={id} className="campo" value={f.proyecto || ""} onChange={cambiar("proyecto")}>
                <option value="">Ninguno</option>
                {proyectos.map((p) => <option key={p.id} value={p.id}>{p.codigo} · {p.nombre} ({p.cliente_nombre})</option>)}
              </select>
            )}
          </Campo>
        )}
      </form>
    </Modal>
  );
}
