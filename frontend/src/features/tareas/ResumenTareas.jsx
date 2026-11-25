// Panel de tareas: cuántas hay en cada estado, con filtros. Cada persona ve solo las estadísticas de lo que ya puede ver.
import { useCallback, useEffect, useMemo, useState } from "react";
import { ChartNoAxesColumn } from "lucide-react";
import { resumenTareas } from "@/lib/api";
import { useNovedades } from "@/lib/novedades";
import { useRecurso } from "@/lib/recursos";
import { Alerta, Cabecera, Cargando, Vacio, cx } from "@/components/ui";
import { Link } from "react-router-dom";

const mesDe = () => { const d = new Date(); return { desde: new Date(d.getFullYear(), d.getMonth(), 1).toLocaleDateString("sv-SE"), hasta: new Date(d.getFullYear(), d.getMonth() + 1, 0).toLocaleDateString("sv-SE") }; };

// [clave del servidor, texto, color, qué significa]
const TARJETAS = [
  ["pendientes", "Pendientes", "text-gris", "Asignadas que aún no empiezan."],
  ["en_proceso", "En proceso", "text-azul", "Ya empezadas."],
  ["devueltas", "Devueltas", "text-[#a86a00]", "El supervisor las devolvió para corregir."],
  ["por_validar", "Por validar", "text-[#a86a00]", "Entregadas, esperando que alguien las valide."],
  ["aprobadas", "Aprobadas", "text-verde", "Validadas: las que suman al puntaje."],
  ["vencidas", "Vencidas", "text-rojo", "Pasó su fecha límite sin entregarse (se cuentan además de su estado)."],
  ["bloqueadas", "Bloqueadas", "text-gris", "Detenidas por un problema."],
  ["canceladas", "Canceladas", "text-gris", "Ya no hacen falta."],
];
const PRIORIDADES = { URGENTE: "Urgente", ALTA: "Alta", MEDIA: "Media", BAJA: "Baja" };

export default function ResumenTareas() {
  const [gente] = useRecurso("directorio");
  const [deptos] = useRecurso("departamentos");
  const [f, setF] = useState({ departamento: "", persona: "", asignador: "", estado: "", prioridad: "", ...mesDe() });
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  const traer = useCallback(() => resumenTareas(Object.fromEntries(Object.entries(f).filter(([, v]) => v !== ""))).then((d) => { setDatos(d); setError(""); }).catch((e) => setError(e.message)), [f]);
  useEffect(() => { setDatos(null); traer(); }, [traer]);
  useNovedades(traer); // se actualiza solo cuando alguien valida, devuelve o entrega, sin parpadeo
  const poner = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }));
  const personas = useMemo(() => (gente || []).slice().sort((a, b) => a.nombre.localeCompare(b.nombre)), [gente]);
  const c = datos?.conteos;
  const conAlgo = c && c.total > 0;

  return (
    <div>
      <Cabecera titulo="Resumen de tareas" descripcion="Cuántas tareas hay en cada estado. Ves las estadísticas de lo tuyo, de tu equipo y de lo que asignaste (Dirección, de todo).">
        <Link to="/historial-tareas" className="text-sm font-medium text-azul hover:underline">Ver el historial →</Link>
      </Cabecera>
      <div className="mb-5 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <select className="campo h-11 py-0" value={f.departamento} onChange={poner("departamento")} aria-label="Departamento"><option value="">Todos los departamentos</option>{(deptos || []).map((d) => <option key={d.id} value={d.id}>{d.nombre}</option>)}</select>
        <select className="campo h-11 py-0" value={f.persona} onChange={poner("persona")} aria-label="Colaborador"><option value="">Colaborador: todos</option>{personas.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}</select>
        <select className="campo h-11 py-0" value={f.asignador} onChange={poner("asignador")} aria-label="Quién asigna"><option value="">Quién asigna: todos</option>{personas.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}</select>
        <select className="campo h-11 py-0" value={f.estado} onChange={poner("estado")} aria-label="Estado"><option value="">Todos los estados</option>{[...TARJETAS.map(([k, t]) => [k, t])].map(([k, t]) => <option key={k} value={k}>{t}</option>)}</select>
        <select className="campo h-11 py-0" value={f.prioridad} onChange={poner("prioridad")} aria-label="Prioridad"><option value="">Todas las prioridades</option>{Object.entries(PRIORIDADES).map(([k, t]) => <option key={k} value={k}>{t}</option>)}</select>
        <label className="flex items-center gap-2 text-sm text-gris">Fecha límite desde<input type="date" className="campo h-11 py-0" value={f.desde} onChange={poner("desde")} /></label>
        <label className="flex items-center gap-2 text-sm text-gris">hasta<input type="date" className="campo h-11 py-0" value={f.hasta} onChange={poner("hasta")} /></label>
        <button type="button" onClick={() => setF({ departamento: "", persona: "", asignador: "", estado: "", prioridad: "", desde: "", hasta: "" })} className="h-11 rounded-lg border border-linea bg-white px-3 text-sm font-medium text-azul hover:bg-fondo">Todo el tiempo</button>
      </div>

      {error ? <Alerta>{error}</Alerta> : !datos ? <Cargando /> : !conAlgo ? (
        <Vacio icono={ChartNoAxesColumn} titulo="No hay tareas con esos filtros">Prueba con otro mes o quita algún filtro.</Vacio>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
            <div className="rounded-xl border border-noche bg-noche p-4 text-white">
              <p className="text-sm text-white/70">Total de tareas</p>
              <p className="num mt-1 font-display text-3xl font-semibold">{c.total}</p>
              <p className="mt-1 text-xs text-white/70">A tiempo: {c.a_tiempo} · fuera de plazo: {c.fuera_de_plazo}</p>
            </div>
            {TARJETAS.map(([k, texto, color, ayuda]) => (
              <div key={k} className="rounded-xl border border-linea bg-white p-4" title={ayuda}>
                <p className="text-sm text-gris">{texto}</p>
                <p className={cx("num mt-1 font-display text-3xl font-semibold", c[k] > 0 ? color : "text-linea")}>{c[k]}</p>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-linea-suave"><div className="h-full rounded-full bg-current opacity-60" style={{ width: `${Math.round((c[k] / c.total) * 100)}%` }} /></div>
              </div>
            ))}
          </div>
          <p className="text-xs text-gris">Pasa el cursor por cada tarjeta para ver qué incluye. «Vencidas» se cuenta además del estado de cada tarea.</p>

          {datos.por_departamento.length > 0 && (
            <section aria-label="Por departamento" className="overflow-hidden rounded-xl border border-linea bg-white">
              <h2 className="border-b border-linea-suave bg-fondo/70 px-4 py-2.5 !text-[15px] font-semibold !text-noche">Por departamento</h2>
              <div className="overflow-x-auto">
                <table className="tabla">
                  <thead><tr><th>Departamento</th><th className="text-right">Total</th><th className="text-right">Abiertas</th><th className="text-right">Vencidas</th><th className="text-right">Por validar</th><th className="text-right">Aprobadas</th></tr></thead>
                  <tbody>{datos.por_departamento.map((d) => (
                    <tr key={d.departamento}><td className="font-medium">{d.departamento}</td><td className="num text-right">{d.total}</td><td className="num text-right">{d.abiertas}</td>
                      <td className={cx("num text-right", d.vencidas > 0 && "font-semibold text-rojo")}>{d.vencidas}</td><td className="num text-right">{d.por_validar}</td><td className="num text-right text-verde">{d.aprobadas}</td></tr>))}</tbody>
                </table>
              </div>
            </section>
          )}
          {Object.keys(datos.por_prioridad).length > 0 && (
            <p className="text-sm text-gris">Por prioridad: {Object.entries(PRIORIDADES).filter(([k]) => datos.por_prioridad[k]).map(([k, t]) => `${t} ${datos.por_prioridad[k]}`).join(" · ")}</p>
          )}
        </div>
      )}
    </div>
  );
}
