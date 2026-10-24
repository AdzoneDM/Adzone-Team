import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Briefcase, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { departamentos as cargarDeptos, eliminarDepartamento, eliminarPuesto, guardarDepartamento, guardarPuesto, puestos as cargarPuestos } from "@/lib/api";
import { Alerta, Boton, Cabecera, Campo, Cargando, Modal, Panel, Vacio, cx, useAviso, useConfirmar } from "@/components/ui";

export function FormPuesto({ abierto, inicial, deptos, puestos, onCerrar, onGuardado }) {
  const [f, setF] = useState({});
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  useEffect(() => {
    if (abierto) { setError(""); setF(inicial?.id ? { ...inicial } : { nombre: "", departamento: inicial?.departamento || "", supervisor: "", funciones_principales: "" }); }
  }, [abierto, inicial]);
  const guardar = async (e) => {
    e.preventDefault();
    if (!f.nombre?.trim() || !f.departamento) return setError("Escribe el nombre y elige el departamento.");
    setGuardando(true);
    try {
      const p = await guardarPuesto({ id: f.id, nombre: f.nombre.trim(), departamento: Number(f.departamento), supervisor: f.supervisor ? Number(f.supervisor) : null, funciones_principales: f.funciones_principales || "" });
      onGuardado(p);
    } catch (err) { setError(err.message); }
    setGuardando(false);
  };
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={f.id ? "Editar puesto" : "Nuevo puesto"} ancho="md:max-w-2xl"
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton type="submit" form="form-puesto" cargando={guardando}>{f.id ? "Guardar cambios" : "Crear puesto"}</Boton></>}>
      <form id="form-puesto" onSubmit={guardar} className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        <Campo etiqueta="Nombre del puesto">{(id) => <input id={id} className="campo" value={f.nombre || ""} onChange={(e) => setF({ ...f, nombre: e.target.value })} autoFocus />}</Campo>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Departamento">{(id) => (
            <select id={id} className="campo" value={f.departamento || ""} onChange={(e) => setF({ ...f, departamento: e.target.value })}>
              <option value="">Elige…</option>{deptos.map((d) => <option key={d.id} value={d.id}>{d.nombre}</option>)}
            </select>)}</Campo>
          <Campo etiqueta="Reporta a" ayuda="Quien ocupe ese puesto asigna y valida sus tareas.">{(id) => (
            <select id={id} className="campo" value={f.supervisor || ""} onChange={(e) => setF({ ...f, supervisor: e.target.value })}>
              <option value="">Nadie (puesto superior)</option>
              {puestos.filter((p) => p.id !== f.id).map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
            </select>)}</Campo>
        </div>
        <Campo etiqueta="Funciones principales" ayuda="Una función por línea.">
          {(id) => <textarea id={id} className="campo" rows={7} value={f.funciones_principales || ""} onChange={(e) => setF({ ...f, funciones_principales: e.target.value })} />}
        </Campo>
      </form>
    </Modal>
  );
}

// Los colores de los 7 departamentos oficiales (texto, fondo). Elegir de aquí evita colores ilegibles.
const PALETAS = [
  ["#2f3a4f", "#eef1f6"], ["#1d4189", "#e6edfa"], ["#56298f", "#f0e9fb"], ["#a3170f", "#fde8e7"],
  ["#8a4300", "#fdeedd"], ["#7a5000", "#fff4d6"], ["#0d6455", "#e2f4f1"],
];

export default function Puestos() {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const [deptos, setDeptos] = useState(null);
  const [puestos, setPuestos] = useState(null);
  const [error, setError] = useState("");
  const [filtro, setFiltro] = useState("");
  const [buscar, setBuscar] = useState("");
  const [formDepto, setFormDepto] = useState(null);
  const [colorDepto, setColorDepto] = useState(PALETAS[0]);
  const [nombreDepto, setNombreDepto] = useState("");
  const [formPuesto, setFormPuesto] = useState(null);

  const cargar = useCallback(() => {
    Promise.all([cargarDeptos(), cargarPuestos()]).then(([d, p]) => { setDeptos(d); setPuestos(p); }).catch((e) => setError(e.message));
  }, []);
  useEffect(() => { cargar(); }, [cargar]);

  const lista = useMemo(() => (puestos || []).filter((p) => (!filtro || String(p.departamento) === filtro)
    && (!buscar || p.nombre.toLowerCase().includes(buscar.toLowerCase()))), [puestos, filtro, buscar]);

  const guardarDepto = async (e) => {
    e.preventDefault();
    try {
      await guardarDepartamento({ id: formDepto.id, nombre: nombreDepto, color: colorDepto[0], color_fondo: colorDepto[1] });
      avisar(formDepto.id ? "Departamento actualizado." : "Departamento creado.");
      setFormDepto(null);
      cargar();
    } catch (err) { avisar(err.message, "rojo"); }
  };
  const borrarDepto = async (d) => {
    if (!(await confirmar({ titulo: `¿Borrar «${d.nombre}»?`, mensaje: "Solo se puede si no tiene puestos.", boton: "Borrar", peligro: true }))) return;
    try { await eliminarDepartamento(d.id); avisar("Departamento borrado."); if (filtro === String(d.id)) setFiltro(""); cargar(); } catch (e) { avisar(e.message, "rojo"); }
  };
  const borrarPuesto = async (p) => {
    if (!(await confirmar({ titulo: `¿Borrar el puesto «${p.nombre}»?`, mensaje: "Se borran también sus KPIs asignados. Solo se puede si nadie ocupa el puesto.", boton: "Borrar", peligro: true }))) return;
    try { await eliminarPuesto(p.id); avisar("Puesto borrado."); cargar(); } catch (e) { avisar(e.message, "rojo"); }
  };

  if (error) return <Alerta>{error}</Alerta>;
  if (!deptos || !puestos) return <Cargando />;

  return (
    <div>
      <Cabecera titulo="Departamentos y puestos" descripcion="Cada puesto tiene un departamento, a quién reporta, sus funciones y sus KPIs.">
        <Boton variante="secundario" icono={Plus} onClick={() => { setFormDepto({}); setNombreDepto(""); setColorDepto(PALETAS[0]); }}>Departamento</Boton>
        <Boton icono={Plus} onClick={() => setFormPuesto({ departamento: filtro })}>Puesto</Boton>
      </Cabecera>

      <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <Panel titulo="Departamentos" cuerpo="p-2">
          <ul>
            <li><button type="button" onClick={() => setFiltro("")} className={cx("w-full rounded-lg px-3 py-2 text-left text-sm", !filtro ? "bg-azul/10 font-medium text-azul" : "hover:bg-fondo")}>Todos <span className="text-gris">({puestos.length} puestos)</span></button></li>
            {deptos.map((d) => (
              <li key={d.id} className="group flex items-center gap-1">
                <button type="button" onClick={() => setFiltro(String(d.id))} className={cx("min-w-0 flex-1 rounded-lg px-3 py-2 text-left text-sm", filtro === String(d.id) ? "bg-azul/10 font-medium text-azul" : "hover:bg-fondo")}>
                  <span className="flex items-center gap-2"><span className="size-2.5 shrink-0 rounded-full" style={{ backgroundColor: d.color }} aria-hidden="true" /><span className="truncate">{d.nombre}</span></span>
                  <span className="text-xs text-gris">{d.puestos} puestos, {d.personas} personas</span>
                </button>
                <Boton variante="fantasma" tam="sm" icono={Pencil} aria-label={`Editar ${d.nombre}`} className="px-2 opacity-60 group-hover:opacity-100" onClick={() => { setFormDepto(d); setNombreDepto(d.nombre); setColorDepto([d.color, d.color_fondo]); }} />
                <Boton variante="fantasma" tam="sm" icono={Trash2} aria-label={`Borrar ${d.nombre}`} className="px-2 text-rojo opacity-60 group-hover:opacity-100" onClick={() => borrarDepto(d)} />
              </li>
            ))}
          </ul>
        </Panel>

        <Panel cuerpo="p-0" titulo={filtro ? deptos.find((d) => String(d.id) === filtro)?.nombre : "Todos los puestos"}
          accion={<div className="relative"><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" /><input className="campo h-9 w-48 pl-9 text-sm" placeholder="Buscar puesto" value={buscar} onChange={(e) => setBuscar(e.target.value)} aria-label="Buscar puesto" /></div>}>
          {lista.length === 0 ? <div className="p-5"><Vacio icono={Briefcase} titulo="No hay puestos aquí" /></div> : (
            <div className="overflow-x-auto">
              <table className="tabla">
                <thead><tr><th>Puesto</th>{!filtro && <th>Departamento</th>}<th>Reporta a</th><th>Personas</th><th className="w-24"><span className="sr-only">Acciones</span></th></tr></thead>
                <tbody>
                  {lista.map((p) => (
                    <tr key={p.id}>
                      <td><Link to={`/puestos/${p.id}`} className="font-medium hover:text-azul">{p.nombre}</Link>{p.subordinados > 0 && <p className="text-xs text-gris">{p.subordinados} puestos le reportan</p>}</td>
                      {!filtro && <td className="text-sm text-gris">{p.departamento_nombre}</td>}
                      <td className="text-sm">{p.supervisor_nombre || <span className="text-gris">—</span>}</td>
                      <td className="text-sm">{p.personas.length ? p.personas.map((x) => x.nombre).join(", ") : <span className="text-gris">Vacante</span>}</td>
                      <td className="whitespace-nowrap text-right">
                        <Boton variante="fantasma" tam="sm" icono={Pencil} aria-label={`Editar ${p.nombre}`} onClick={() => setFormPuesto(p)} />
                        <Boton variante="fantasma" tam="sm" icono={Trash2} aria-label={`Borrar ${p.nombre}`} className="text-rojo" onClick={() => borrarPuesto(p)} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>

      <Modal abierto={!!formDepto} onCerrar={() => setFormDepto(null)} titulo={formDepto?.id ? "Editar departamento" : "Nuevo departamento"} ancho="max-w-md"
        pie={<><Boton variante="secundario" onClick={() => setFormDepto(null)}>Cancelar</Boton><Boton type="submit" form="form-depto">{formDepto?.id ? "Guardar" : "Crear"}</Boton></>}>
        <form id="form-depto" onSubmit={guardarDepto} className="space-y-4">
          <Campo etiqueta="Nombre">{(id) => <input id={id} className="campo" value={nombreDepto} onChange={(e) => setNombreDepto(e.target.value)} autoFocus />}</Campo>
          <fieldset>
            <legend className="etiqueta">Color</legend>
            <div className="flex flex-wrap gap-2">
              {PALETAS.map(([c, f]) => (
                <button key={c} type="button" onClick={() => setColorDepto([c, f])} aria-pressed={colorDepto[0] === c} aria-label={`Color ${c}`}
                  className={cx("rounded-full px-3 py-1 text-sm font-medium ring-offset-2", colorDepto[0] === c && "ring-2 ring-noche")} style={{ color: c, backgroundColor: f }}>
                  {nombreDepto || "Ejemplo"}
                </button>
              ))}
            </div>
          </fieldset>
        </form>
      </Modal>
      <FormPuesto abierto={!!formPuesto} inicial={formPuesto} deptos={deptos} puestos={puestos} onCerrar={() => setFormPuesto(null)}
        onGuardado={() => { avisar(formPuesto?.id ? "Puesto actualizado." : "Puesto creado."); setFormPuesto(null); cargar(); }} />
    </div>
  );
}
