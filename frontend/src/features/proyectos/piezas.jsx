import { useEffect, useState } from "react";
import { guardarProyecto } from "@/lib/api";
import { ESTADOS_PROYECTO, PRIORIDADES_OT } from "@/lib/formato";
import { useRecurso } from "@/lib/recursos";
import { useSesion } from "@/lib/sesion";
import { SelectorCliente, SelectorPersona, SelectorPersonas } from "@/components/Selectores";
import { Alerta, Boton, Campo, Modal, cx } from "@/components/ui";

const TONO = {
  PLANIFICADO: "bg-linea-suave text-tinta", EN_CURSO: "bg-azul/10 text-azul", EN_PAUSA: "bg-amarillo-50 text-[#7a5000]",
  TERMINADO: "bg-verde-50 text-verde", CANCELADO: "bg-linea-suave text-gris line-through",
};
export const EstadoProyecto = ({ estado }) => <span className={cx("whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium", TONO[estado])}>{ESTADOS_PROYECTO[estado]}</span>;

export function AvanceProyecto({ progreso, ancho = "w-24", className }) {
  const pct = progreso?.tareas ? Math.round((progreso.validadas / progreso.tareas) * 100) : 0;
  return (
    <span className={cx("inline-flex items-center gap-2 text-xs text-gris", className)}>
      <span className={cx("h-1.5 overflow-hidden rounded-full bg-linea", ancho)}><span className={cx("block h-full rounded-full", pct === 100 ? "bg-verde" : "bg-azul")} style={{ width: `${pct}%` }} /></span>
      <span className="num">{progreso?.tareas ? `${progreso.validadas}/${progreso.tareas}` : "Sin tareas"}</span>
    </span>
  );
}

export function FormProyecto({ abierto, onCerrar, inicial, onGuardado }) {
  const { usuario } = useSesion();
  const [deptos] = useRecurso("departamentos");
  const [f, setF] = useState({});
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const editando = !!inicial?.id;
  useEffect(() => {
    if (!abierto) return;
    setError("");
    setF(inicial?.id ? { ...inicial, cliente: String(inicial.cliente), departamento: inicial.departamento ? String(inicial.departamento) : "",
      responsable: inicial.responsable ? String(inicial.responsable) : "" }
      : { nombre: "", cliente: inicial?.cliente ? String(inicial.cliente) : "", departamento: usuario.departamento_id ? String(usuario.departamento_id) : "",
        responsable: String(usuario.id), miembros: [], estado: "PLANIFICADO", prioridad: "NORMAL", fecha_inicio: "", fecha_fin: "", presupuesto: "", descripcion: "" });
  }, [abierto, inicial, usuario]);
  const guardar = async (e) => {
    e.preventDefault();
    if (!f.nombre?.trim()) return setError("Ponle nombre al proyecto.");
    if (!f.cliente) return setError("Elige el cliente.");
    setGuardando(true); setError("");
    try {
      const p = await guardarProyecto({
        id: f.id, nombre: f.nombre.trim(), cliente: Number(f.cliente), departamento: f.departamento ? Number(f.departamento) : null,
        responsable: f.responsable ? Number(f.responsable) : null, miembros: (f.miembros || []).map(Number), estado: f.estado, prioridad: f.prioridad,
        fecha_inicio: f.fecha_inicio || null, fecha_fin: f.fecha_fin || null, descripcion: f.descripcion || "",
        ...(usuario.es_finanzas || usuario.gestiona ? { presupuesto: f.presupuesto === "" || f.presupuesto == null ? null : f.presupuesto } : {}),
      });
      onGuardado(p, editando);
    } catch (err) { setError(err.message); }
    setGuardando(false);
  };
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={editando ? `Editar ${inicial.codigo}` : "Nuevo proyecto"} ancho="md:max-w-2xl"
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton type="submit" form="form-proyecto" cargando={guardando}>{editando ? "Guardar" : "Crear proyecto"}</Boton></>}>
      <form id="form-proyecto" onSubmit={guardar} className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        <Campo etiqueta="Nombre del proyecto">{(id) => <input id={id} className="campo" value={f.nombre || ""} onChange={(e) => setF({ ...f, nombre: e.target.value })} maxLength={200} autoFocus />}</Campo>
        <div className="grid gap-4 sm:grid-cols-2">
          <SelectorCliente valor={f.cliente} onCambio={(v) => setF({ ...f, cliente: v })} />
          <Campo etiqueta="Departamento que lo lleva">
            {(id) => (
              <select id={id} className="campo" value={f.departamento || ""} onChange={(e) => setF({ ...f, departamento: e.target.value })}>
                <option value="">Varios departamentos</option>
                {(deptos || []).map((d) => <option key={d.id} value={d.id}>{d.nombre}</option>)}
              </select>
            )}
          </Campo>
          <SelectorPersona etiqueta="Responsable" valor={f.responsable} onCambio={(v) => setF({ ...f, responsable: v })} />
          <Campo etiqueta="Estado">
            {(id) => <select id={id} className="campo" value={f.estado} onChange={(e) => setF({ ...f, estado: e.target.value })}>
              {Object.entries(ESTADOS_PROYECTO).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>}
          </Campo>
          <Campo etiqueta="Inicio">{(id) => <input id={id} type="date" className="campo" value={f.fecha_inicio || ""} onChange={(e) => setF({ ...f, fecha_inicio: e.target.value })} />}</Campo>
          <Campo etiqueta="Entrega">{(id) => <input id={id} type="date" className="campo" min={f.fecha_inicio || undefined} value={f.fecha_fin || ""} onChange={(e) => setF({ ...f, fecha_fin: e.target.value })} />}</Campo>
          <Campo etiqueta="Prioridad">
            {(id) => <select id={id} className="campo" value={f.prioridad} onChange={(e) => setF({ ...f, prioridad: e.target.value })}>
              {Object.entries(PRIORIDADES_OT).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>}
          </Campo>
          {(usuario.es_finanzas || usuario.gestiona) && (
            <Campo etiqueta="Monto vendido (RD$, opcional)" ayuda="Solo lo ven Finanzas y quien gestiona.">
              {(id) => <input id={id} type="number" min={0} step="any" className="campo" value={f.presupuesto ?? ""} onChange={(e) => setF({ ...f, presupuesto: e.target.value })} />}
            </Campo>
          )}
        </div>
        <SelectorPersonas leyenda="Equipo del proyecto" ayuda="Lo ven en sus proyectos y reciben los comentarios." valor={f.miembros || []}
          onCambio={(v) => setF({ ...f, miembros: v })} excluir={[f.responsable]} />
        <Campo etiqueta="Descripción (opcional)">{(id) => <textarea id={id} rows={3} className="campo" value={f.descripcion || ""} onChange={(e) => setF({ ...f, descripcion: e.target.value })} />}</Campo>
      </form>
    </Modal>
  );
}
