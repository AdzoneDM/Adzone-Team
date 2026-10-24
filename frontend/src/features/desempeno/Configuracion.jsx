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
        peso_tareas: Number(f.peso_tareas), nota_tarde: Number(f.nota_tarde), minimo_tareas_empleado_mes: Number(f.minimo_tareas_empleado_mes),
        tramos_bono: tramos.filter((t) => t.desde !== "" && t.porcentaje !== "").map((t) => ({ desde: Number(t.desde), porcentaje: Number(t.porcentaje) })),
      });
      setF(r);
      avisar("Reglas guardadas. El ranking ya se calcula con ellas.");
    } catch (err) { setError(err.message); }
    setGuardando(false);
  };

  const pesoTareas = Math.max(0, Math.min(100, Number(f.peso_tareas) || 0));
  return (
    <form onSubmit={guardar} className="max-w-3xl">
      <Cabecera titulo="Reglas del puntaje" descripcion="Cómo se calcula el puntaje mensual de cada persona y el bono sugerido. Los cambios aplican a todos los meses que se consulten.">
        <Boton type="submit" icono={Save} cargando={guardando}>Guardar reglas</Boton>
      </Cabecera>
      {error && <Alerta className="mb-4">{error}</Alerta>}
      <div className="space-y-6">
        <Panel titulo="Peso de cada parte">
          <Campo etiqueta={`Tareas validadas ${pesoTareas}% · KPIs del puesto ${100 - pesoTareas}%`} ayuda="Si alguien solo tiene una de las dos partes en el mes, esa vale el 100%.">
            {(id) => <input id={id} type="range" min={0} max={100} step={5} value={pesoTareas} onChange={(e) => setF({ ...f, peso_tareas: e.target.value })} className="w-full accent-azul" />}
          </Campo>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <Campo etiqueta="Puntualidad de una entrega tarde" ayuda="A tiempo vale 100; sin entregar y vencida, 0.">
              {(id) => <input id={id} type="number" min={0} max={100} className="campo" value={f.nota_tarde} onChange={(e) => setF({ ...f, nota_tarde: e.target.value })} />}
            </Campo>
            <Campo etiqueta="Tareas validadas para ser candidato" ayuda="Mínimo en el mes para optar a Empleado del Mes.">
              {(id) => <input id={id} type="number" min={0} max={100} className="campo" value={f.minimo_tareas_empleado_mes} onChange={(e) => setF({ ...f, minimo_tareas_empleado_mes: e.target.value })} />}
            </Campo>
          </div>
        </Panel>

        <Panel titulo="Bono sugerido" accion={<Boton variante="secundario" tam="sm" icono={Plus} onClick={() => setF({ ...f, tramos_bono: [...tramos, { desde: "", porcentaje: "" }] })}>Tramo</Boton>}>
          <p className="mb-4 text-sm text-gris">Según el puntaje del mes. Aparece en el ranking y en el Excel como guía; la dirección decide.</p>
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
                <Boton variante="fantasma" icono={Trash2} className="text-rojo" aria-label="Quitar tramo" onClick={() => setF({ ...f, tramos_bono: tramos.filter((_, j) => j !== i) })} />
              </li>
            ))}
          </ul>
        </Panel>

        <Panel titulo="Cómo se calcula la nota de cada tarea">
          <ul className="list-disc space-y-1.5 pl-5 text-[15px] text-gris">
            <li>Puntualidad: 100 si se entregó a tiempo, {f.nota_tarde} si se entregó tarde, 0 si venció sin entregar.</li>
            <li>Calidad: las estrellas del supervisor (1 = 0, 3 = 50, 5 = 100). La nota es el promedio de las dos.</li>
            <li>Prioridad alta pesa 3, media 2 y baja 1.</li>
            <li>No cuentan todavía las entregas sin validar ni las tareas que no han vencido.</li>
          </ul>
        </Panel>
      </div>
    </form>
  );
}
