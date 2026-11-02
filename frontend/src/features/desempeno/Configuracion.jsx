import { useEffect, useState } from "react";
import { Plus, Save, Trash2 } from "lucide-react";
import { configuracion, guardarConfiguracion } from "@/lib/api";
import { Alerta, Boton, Cabecera, Campo, Cargando, Panel, useAviso } from "@/components/ui";

export default function Configuracion() {
  const avisar = useAviso();
  const [f, setF] = useState(null);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  useEffect(() => { configuracion().then(setF).catch((e) => setError(e.message)); }, []);

  if (!f) return error ? <Alerta>{error}</Alerta> : <Cargando />;
  const tramos = f.tramos_bono || [];
  const ponerTramo = (i, campo, v) => setF({ ...f, tramos_bono: tramos.map((t, j) => (j === i ? { ...t, [campo]: v } : t)) });

  const guardar = async (e) => {
    e.preventDefault();
    setError("");
    setGuardando(true);
    try {
      const r = await guardarConfiguracion({
        peso_tareas: pesoTareas, peso_calidad: pesoCalidad, peso_jornada: pesoJornada, nota_tarde: Number(f.nota_tarde), minimo_tareas_empleado_mes: Number(f.minimo_tareas_empleado_mes),
        puntaje_minimo: Number(f.puntaje_minimo), minimo_tareas_evaluacion: Number(f.minimo_tareas_evaluacion),
        tramos_bono: tramos.filter((t) => t.desde !== "" && t.porcentaje !== "").map((t) => ({ desde: Number(t.desde), porcentaje: Number(t.porcentaje), ...(t.proporcional ? { proporcional: true } : {}) })),
      });
      setF(r);
      avisar("Reglas guardadas. El ranking ya se calcula con ellas.");
    } catch (err) { setError(err.message); }
    setGuardando(false);
  };

  const pesoTareas = Math.max(0, Math.min(100, Number(f.peso_tareas) || 0));
  const pesoCalidad = Math.max(0, Math.min(100 - pesoTareas, Number(f.peso_calidad) || 0));
  const pesoJornada = Math.max(0, Math.min(100 - pesoTareas - pesoCalidad, Number(f.peso_jornada) || 0));
  const pesoKpis = 100 - pesoTareas - pesoCalidad - pesoJornada;
  const mover = (campo, v) => {
    const n = { ...f, [campo]: Number(v) };
    const t = Math.min(100, Number(n.peso_tareas) || 0);
    const c = Math.min(100 - t, Number(n.peso_calidad) || 0);
    setF({ ...n, peso_tareas: t, peso_calidad: c, peso_jornada: Math.min(100 - t - c, Number(n.peso_jornada) || 0) });
  };
  return (
    <form onSubmit={guardar} className="max-w-3xl">
      <Cabecera titulo="Reglas del puntaje" descripcion="Cómo se calcula el puntaje mensual de cada persona y el bono sugerido. Los cambios aplican a todos los meses que se consulten.">
        <Boton type="submit" icono={Save} cargando={guardando}>Guardar reglas</Boton>
      </Cabecera>
      {error && <Alerta className="mb-4">{error}</Alerta>}
      <div className="space-y-6">
        <Panel titulo="Peso de cada parte">
          <p className="mb-4 rounded-lg bg-fondo px-4 py-3 text-[15px]">Tareas <strong className="num">{pesoTareas} %</strong> · KPIs del puesto <strong className="num">{pesoKpis} %</strong> · Calidad y satisfacción <strong className="num">{pesoCalidad} %</strong> · Asistencia y puntualidad <strong className="num">{pesoJornada} %</strong></p>
          <Campo etiqueta={`Cumplimiento de tareas: ${pesoTareas} %`} ayuda="Tareas validadas a tiempo, ponderadas por prioridad. Si a alguien le falta alguna parte en el mes, las que tiene se reparten el 100 %.">
            {(id) => <input id={id} type="range" min={0} max={100} step={1} value={pesoTareas} onChange={(e) => mover("peso_tareas", e.target.value)} className="w-full accent-azul" />}
          </Campo>
          <Campo etiqueta={`Calidad y satisfacción: ${pesoCalidad} %`} className="mt-4" ayuda="Estrellas de las tareas, % aprobado a la primera y la evaluación del supervisor del ciclo. En 0, la calidad vuelve a ir dentro de la nota de cada tarea.">
            {(id) => <input id={id} type="range" min={0} max={100 - pesoTareas} step={1} value={pesoCalidad} onChange={(e) => mover("peso_calidad", e.target.value)} className="w-full accent-azul" />}
          </Campo>
          <Campo etiqueta={`Asistencia y puntualidad: ${pesoJornada} %`} className="mt-4" ayuda="Adherencia al horario: puntualidad, días asistidos y horas cumplidas. Solo cuenta para quien marca su jornada.">
            {(id) => <input id={id} type="range" min={0} max={100 - pesoTareas - pesoCalidad} step={1} value={pesoJornada} onChange={(e) => mover("peso_jornada", e.target.value)} className="w-full accent-azul" />}
          </Campo>
          <p className="mt-4 text-sm text-gris">Los KPIs del puesto se quedan con el resto ({pesoKpis} %). La actividad de la computadora no da puntos: se muestra en la ficha y genera alertas.</p>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <Campo etiqueta="Puntualidad de una entrega tarde" ayuda="A tiempo vale 100; sin entregar y vencida, 0.">
              {(id) => <input id={id} type="number" min={0} max={100} className="campo" value={f.nota_tarde} onChange={(e) => setF({ ...f, nota_tarde: e.target.value })} />}
            </Campo>
            <Campo etiqueta="Tareas validadas para ser candidato" ayuda="Mínimo en el mes para optar a Empleado del Mes.">
              {(id) => <input id={id} type="number" min={0} max={100} className="campo" value={f.minimo_tareas_empleado_mes} onChange={(e) => setF({ ...f, minimo_tareas_empleado_mes: e.target.value })} />}
            </Campo>
          </div>
        </Panel>

        <Panel titulo="Desempeño mínimo">
          <p className="mb-4 text-sm text-gris">Quien quede por debajo sale marcado en Desempeño y en el Excel, con lo que le bajó el puntaje. Con muy pocas tareas el puntaje no es justo: esas personas salen como «pocos datos».</p>
          <div className="grid gap-4 sm:grid-cols-2">
            <Campo etiqueta="Puntaje mínimo del mes" ayuda="De 0 a 100. Por ejemplo, 70.">
              {(id) => <input id={id} type="number" min={0} max={100} className="campo" value={f.puntaje_minimo} onChange={(e) => setF({ ...f, puntaje_minimo: e.target.value })} />}
            </Campo>
            <Campo etiqueta="Tareas necesarias para juzgar" ayuda="Tareas que ya cuentan en el mes (validadas o vencidas). Si la persona tiene KPIs medidos, también se juzga.">
              {(id) => <input id={id} type="number" min={1} max={100} className="campo" value={f.minimo_tareas_evaluacion} onChange={(e) => setF({ ...f, minimo_tareas_evaluacion: e.target.value })} />}
            </Campo>
          </div>
        </Panel>

        <Panel titulo="Bono sugerido" accion={<Boton variante="secundario" tam="sm" icono={Plus} onClick={() => setF({ ...f, tramos_bono: [...tramos, { desde: "", porcentaje: "" }] })}>Tramo</Boton>}>
          <p className="mb-4 text-sm text-gris">Según el puntaje del mes. Aparece en el ranking y en el Excel como guía; la dirección decide.
            Política de las descripciones de puesto: 100 % → 10 % del salario; de 80 % a 99 % → proporcional; menos de 80 % → no aplica.</p>
          {tramos.length === 0 && <p className="text-sm text-gris">Sin tramos: no se sugiere bono.</p>}
          <ul className="space-y-3">
            {tramos.map((t, i) => (
              <li key={i} className="flex flex-wrap items-end gap-3">
                <label className="text-sm text-gris">Desde puntaje
                  <input type="number" min={0} max={100} className="campo mt-1 w-28" value={t.desde} onChange={(e) => ponerTramo(i, "desde", e.target.value)} />
                </label>
                <label className="text-sm text-gris">Bono (% del salario)
                  <input type="number" min={0} max={100} step="any" className="campo mt-1 w-36" value={t.porcentaje} onChange={(e) => ponerTramo(i, "porcentaje", e.target.value)} />
                </label>
                <label className="flex min-h-11 items-center gap-2 text-sm">
                  <input type="checkbox" className="accent-azul" checked={!!t.proporcional} onChange={(e) => ponerTramo(i, "proporcional", e.target.checked)} />
                  Proporcional al puntaje
                </label>
                <Boton variante="fantasma" icono={Trash2} className="text-rojo" aria-label="Quitar tramo" onClick={() => setF({ ...f, tramos_bono: tramos.filter((_, j) => j !== i) })} />
              </li>
            ))}
          </ul>
        </Panel>

        <Panel titulo="Cómo se calcula la nota de cada tarea">
          <ul className="list-disc space-y-1.5 pl-5 text-[15px] text-gris">
            <li>Puntualidad: 100 si se entregó a tiempo, {f.nota_tarde} si se entregó tarde, 0 si venció sin entregar.</li>
            <li>Con «Calidad y satisfacción» en más de 0, la nota de la tarea es solo la puntualidad y las estrellas (1 = 0, 3 = 50, 5 = 100) van a ese componente. En 0, la nota es el promedio de puntualidad y estrellas.</li>
            <li>Prioridad alta pesa 3, media 2 y baja 1.</li>
            <li>No cuentan todavía las entregas sin validar ni las tareas que no han vencido.</li>
          </ul>
        </Panel>
      </div>
    </form>
  );
}
