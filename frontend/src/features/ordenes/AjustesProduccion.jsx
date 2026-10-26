// Quién supervisa cada área (recibe G1 y firma G3) y la tabla de tiempos estándar para calcular la fecha comprometida.
import { useCallback, useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { configAreas, eliminarTiempo, guardarConfigArea, guardarTiempo, tiemposEstandar } from "@/lib/api";
import { olvidarRecurso, useRecurso } from "@/lib/recursos";
import { useSesion } from "@/lib/sesion";
import { SelectorPersonas } from "@/components/Selectores";
import { Alerta, Boton, Cabecera, Cargando, Modal, Panel, useAviso } from "@/components/ui";
import { AreaChip } from "./piezas";

export default function AjustesProduccion() {
  const avisar = useAviso();
  const { esAdmin, esCoordinacion } = useSesion();
  const [catalogo] = useRecurso("catalogo");
  const [areas, setAreas] = useState(null);
  const [tiempos, setTiempos] = useState(null);
  const [editando, setEditando] = useState(null);
  const [nuevo, setNuevo] = useState({ area: "", trabajo: "", dias: "" });
  const [error, setError] = useState("");
  const cargar = useCallback(() => {
    configAreas().then(setAreas).catch((e) => setError(e.message));
    tiemposEstandar().then(setTiempos).catch(() => setTiempos([]));
  }, []);
  useEffect(() => { cargar(); }, [cargar]);
  if (!esAdmin && !esCoordinacion) return <Alerta>Esta página es de Coordinación de Producción y la dirección.</Alerta>;
  if (error) return <Alerta>{error}</Alerta>;
  if (!areas || !tiempos) return <Cargando />;
  const listo = (msg) => { olvidarRecurso("catalogo"); avisar(msg); cargar(); };

  return (
    <div className="space-y-5">
      <Cabecera titulo="Áreas y tiempos de producción" descripcion="Quién recibe cada Orden de Área (G1) y firma el control de calidad (G3), y cuántos días toma cada trabajo." />
      <Panel titulo="Supervisores por área" cuerpo="p-0">
        <ul className="divide-y divide-linea-suave">
          {areas.map((a) => (
            <li key={a.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
              <AreaChip area={a.codigo} nombre={a.nombre} />
              <span className="text-sm text-gris">{a.departamento_nombre || "Sin departamento"}</span>
              <span className="min-w-0 flex-1 text-[15px]">{a.supervisores_nombres.length ? a.supervisores_nombres.join(", ") : <span className="text-gris">El gerente del departamento</span>}</span>
              {esAdmin && <Boton variante="fantasma" tam="sm" onClick={() => setEditando({ ...a, supervisores: a.supervisores.map(String) })}>Cambiar</Boton>}
            </li>
          ))}
        </ul>
      </Panel>

      <Panel titulo="Tiempos estándar (días hábiles)" cuerpo="p-0">
        <div className="overflow-x-auto">
          <table className="tabla">
            <thead><tr><th>Área</th><th>Trabajo</th><th className="text-right">Días</th><th /></tr></thead>
            <tbody>
              {tiempos.map((t) => (
                <tr key={t.id}>
                  <td><AreaChip area={t.area} /></td>
                  <td>{t.trabajo}</td>
                  <td className="text-right"><input type="number" min={0} step="0.5" aria-label={`Días de ${t.trabajo}`} className="h-9 w-20 rounded-md border border-linea px-2 text-right" defaultValue={Number(t.dias)}
                    onBlur={async (e) => { if (Number(e.target.value) !== Number(t.dias)) { try { await guardarTiempo({ id: t.id, dias: e.target.value }); listo("Tiempo actualizado."); } catch (err) { avisar(err.message, "rojo"); } } }} /></td>
                  <td className="text-right"><button type="button" aria-label={`Quitar ${t.trabajo}`} className="rounded p-2 text-gris hover:text-rojo" onClick={async () => { await eliminarTiempo(t.id); listo("Quitado."); }}><Trash2 className="size-4" /></button></td>
                </tr>
              ))}
              <tr>
                <td><select aria-label="Área" className="h-10 rounded-md border border-linea px-2" value={nuevo.area} onChange={(e) => setNuevo({ ...nuevo, area: e.target.value })}>
                  <option value="">Área…</option>{(catalogo?.areas || []).map((a) => <option key={a.codigo} value={a.codigo}>{a.codigo} · {a.nombre}</option>)}</select></td>
                <td><input aria-label="Trabajo" className="h-10 w-full rounded-md border border-linea px-2" placeholder="Ej.: Lona hasta 10 m²" value={nuevo.trabajo} onChange={(e) => setNuevo({ ...nuevo, trabajo: e.target.value })} /></td>
                <td className="text-right"><input aria-label="Días" type="number" min={0} step="0.5" className="h-10 w-20 rounded-md border border-linea px-2 text-right" value={nuevo.dias} onChange={(e) => setNuevo({ ...nuevo, dias: e.target.value })} /></td>
                <td className="text-right"><Boton tam="sm" icono={Plus} disabled={!nuevo.area || !nuevo.trabajo.trim() || nuevo.dias === ""} onClick={async () => {
                  try { await guardarTiempo(nuevo); setNuevo({ area: "", trabajo: "", dias: "" }); listo("Agregado."); } catch (e) { avisar(e.message, "rojo"); }
                }}>Agregar</Boton></td>
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>

      <Modal abierto={!!editando} onCerrar={() => setEditando(null)} titulo={`Supervisores de ${editando?.nombre}`} ancho="max-w-lg"
        descripcion="Reciben las Órdenes de Área (G1), firman el control de calidad (G3) y los traspasos que llegan al área. Vacío = el gerente del departamento."
        pie={<><Boton variante="secundario" onClick={() => setEditando(null)}>Cancelar</Boton><Boton onClick={async () => {
          try { await guardarConfigArea(editando.id, { supervisores: editando.supervisores.map(Number) }); setEditando(null); listo("Supervisores guardados."); } catch (e) { avisar(e.message, "rojo"); }
        }}>Guardar</Boton></>}>
        {editando && <SelectorPersonas leyenda="Supervisores" valor={editando.supervisores} onCambio={(v) => setEditando({ ...editando, supervisores: v })} />}
      </Modal>
    </div>
  );
}
