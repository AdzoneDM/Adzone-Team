import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Pencil, Plus, Target, Trash2 } from "lucide-react";
import {
  departamentos as cargarDeptos, eliminarKpiAsignado, guardarKpiAsignado, kpisAsignados, plantillas as cargarPlantillas,
  puesto as cargarPuesto, puestos as cargarPuestos,
} from "@/lib/api";
import { Alerta, Boton, Campo, Cargando, Insignia, Modal, Panel, Vacio, useAviso, useConfirmar } from "@/components/ui";
import { FormPuesto } from "@/features/organizacion/Puestos";

function FormKpi({ abierto, inicial, puestoId, plantillas, asignadas, onCerrar, onGuardado }) {
  const [f, setF] = useState({});
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  useEffect(() => {
    if (!abierto) return;
    setError("");
    setF(inicial?.id ? { ...inicial, plantilla_kpi: inicial.plantilla_kpi_detalle?.id }
      : { plantilla_kpi: "", ponderacion: "", es_entrada_manual: false, meta_numerica: "", objetivo_meta: "", periodicidad_objetivo: "MENSUAL", activo: true });
  }, [abierto, inicial]);
  const plantilla = plantillas.find((p) => String(p.id) === String(f.plantilla_kpi));
  const guardar = async (e) => {
    e.preventDefault();
    setError("");
    if (!f.plantilla_kpi) return setError("Elige qué KPI vas a medir.");
    if (f.ponderacion === "" || Number(f.ponderacion) < 0 || Number(f.ponderacion) > 100) return setError("El peso va de 0 a 100.");
    if (!f.es_entrada_manual && !f.meta_numerica) return setError("Un KPI automático necesita la meta mensual.");
    setGuardando(true);
    try {
      await guardarKpiAsignado({
        id: f.id, puesto_trabajo: Number(puestoId), plantilla_kpi: Number(f.plantilla_kpi), ponderacion: Number(f.ponderacion),
        es_entrada_manual: !!f.es_entrada_manual, meta_numerica: f.meta_numerica === "" ? null : Number(f.meta_numerica),
        objetivo_meta: f.objetivo_meta || "", periodicidad_objetivo: f.periodicidad_objetivo || "MENSUAL", activo: !!f.activo,
      });
      onGuardado();
    } catch (err) { setError(err.message); }
    setGuardando(false);
  };
  const disponibles = plantillas.filter((p) => !asignadas.includes(p.id) || p.id === inicial?.plantilla_kpi_detalle?.id);
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={f.id ? "Editar KPI del puesto" : "Asignar KPI"} ancho="md:max-w-xl"
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton type="submit" form="form-kpi" cargando={guardando}>{f.id ? "Guardar" : "Asignar"}</Boton></>}>
      <form id="form-kpi" onSubmit={guardar} className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        <Campo etiqueta="KPI" ayuda={<>¿No está en la lista? Créalo en <Link to="/plantillas-kpi" className="text-azul hover:underline">Plantillas de KPI</Link>.</>}>
          {(id) => (
            <select id={id} className="campo" value={f.plantilla_kpi || ""} onChange={(e) => setF({ ...f, plantilla_kpi: e.target.value })} disabled={!!f.id}>
              <option value="">Elige…</option>
              {disponibles.map((p) => <option key={p.id} value={p.id}>{p.nombre}{p.unidad_medida ? ` (${p.unidad_medida})` : ""}</option>)}
            </select>
          )}
        </Campo>
        {plantilla?.menor_es_mejor && <Alerta tono="azul">En este KPI un número más bajo es mejor.</Alerta>}
        <fieldset>
          <legend className="etiqueta">Cómo se mide</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {[[false, "Automático", plantilla?.menor_es_mejor ? "Promedio de rondas de entrega de las tareas validadas vinculadas." : "Cada tarea validada vinculada a este KPI suma 1."], [true, "Manual", "La administración anota el resultado cada mes (ventas, seguidores…)."]].map(([valor, titulo, texto]) => (
              <label key={titulo} className={`cursor-pointer rounded-lg border p-3 ${!!f.es_entrada_manual === valor ? "border-azul bg-azul/5" : "border-linea"}`}>
                <span className="flex items-center gap-2 font-medium"><input type="radio" name="modo" checked={!!f.es_entrada_manual === valor} onChange={() => setF({ ...f, es_entrada_manual: valor })} className="accent-azul" />{titulo}</span>
                <span className="mt-1 block text-sm text-gris">{texto}</span>
              </label>
            ))}
          </div>
        </fieldset>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Peso en el puesto (%)" ayuda="Los pesos del puesto deberían sumar 100.">
            {(id) => <input id={id} type="number" min={0} max={100} step="any" className="campo" value={f.ponderacion ?? ""} onChange={(e) => setF({ ...f, ponderacion: e.target.value })} />}
          </Campo>
          <Campo etiqueta={f.es_entrada_manual ? "Meta mensual de referencia" : "Meta mensual"} ayuda={f.es_entrada_manual ? "Opcional: se propone al anotar el mes." : "Ej.: 20 publicaciones validadas."}>
            {(id) => <input id={id} type="number" min={0} step="any" className="campo" value={f.meta_numerica ?? ""} onChange={(e) => setF({ ...f, meta_numerica: e.target.value })} />}
          </Campo>
        </div>
        <Campo etiqueta="Descripción de la meta (opcional)">{(id) => <input id={id} className="campo" value={f.objetivo_meta || ""} onChange={(e) => setF({ ...f, objetivo_meta: e.target.value })} placeholder="Ej.: menos de 3 rondas por proyecto" />}</Campo>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!f.activo} onChange={(e) => setF({ ...f, activo: e.target.checked })} className="accent-azul" />Activo (cuenta para el puntaje)</label>
      </form>
    </Modal>
  );
}

export default function PuestoDetalle() {
  const { id } = useParams();
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const [p, setP] = useState(null);
  const [kpis, setKpis] = useState([]);
  const [plantillas, setPlantillas] = useState([]);
  const [deptos, setDeptos] = useState([]);
  const [puestos, setPuestos] = useState([]);
  const [error, setError] = useState("");
  const [formKpi, setFormKpi] = useState(null);
  const [editando, setEditando] = useState(false);

  const cargar = useCallback(() => {
    Promise.all([cargarPuesto(id), kpisAsignados({ puesto_trabajo: id })]).then(([a, b]) => { setP(a); setKpis(b); }).catch((e) => setError(e.message));
  }, [id]);
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => { Promise.all([cargarPlantillas(), cargarDeptos(), cargarPuestos()]).then(([a, b, c]) => { setPlantillas(a); setDeptos(b); setPuestos(c); }).catch(() => {}); }, []);

  if (error) return <Alerta>{error}</Alerta>;
  if (!p) return <Cargando />;
  const funciones = (p.funciones_principales || "").split("\n").map((x) => x.trim()).filter(Boolean);
  const suma = kpis.filter((k) => k.activo).reduce((s, k) => s + Number(k.ponderacion), 0);

  return (
    <div>
      <Link to="/puestos" className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-azul hover:underline"><ArrowLeft className="size-4" />Departamentos y puestos</Link>
      <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-gris">{p.departamento_nombre}</p>
          <h1 className="text-3xl font-semibold">{p.nombre}</h1>
          <p className="mt-1 text-gris">{p.supervisor_nombre ? `Reporta a ${p.supervisor_nombre}` : "No reporta a nadie (puesto superior)"} · {p.personas.length ? p.personas.map((x) => x.nombre).join(", ") : "Vacante"}</p>
        </div>
        <Boton variante="secundario" icono={Pencil} onClick={() => setEditando(true)}>Editar puesto</Boton>
      </header>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <Panel titulo="Funciones principales">
          {funciones.length === 0 ? <p className="text-sm text-gris">Sin funciones registradas.</p> : (
            <ol className="list-decimal space-y-2.5 pl-5 text-[15px] leading-relaxed marker:text-gris">{funciones.map((x, i) => <li key={i}>{x}</li>)}</ol>
          )}
        </Panel>

        <Panel titulo="KPIs del puesto" accion={<Boton tam="sm" icono={Plus} onClick={() => setFormKpi({})}>Asignar KPI</Boton>} cuerpo="p-0">
          {kpis.length === 0 ? <div className="p-5"><Vacio icono={Target} titulo="Este puesto no tiene KPIs">Sin KPIs, el puntaje de estas personas sale solo de sus tareas.</Vacio></div> : (
            <>
              <div className="overflow-x-auto">
                <table className="tabla">
                  <thead><tr><th>KPI</th><th>Cómo se mide</th><th className="text-right">Meta</th><th className="text-right">Peso</th><th className="w-24"><span className="sr-only">Acciones</span></th></tr></thead>
                  <tbody>
                    {kpis.map((k) => (
                      <tr key={k.id} className={k.activo ? "" : "opacity-55"}>
                        <td><p className="font-medium">{k.nombre}</p>{k.objetivo_meta && <p className="text-sm text-gris">{k.objetivo_meta}</p>}{!k.activo && <Insignia>Inactivo</Insignia>}</td>
                        <td>{k.es_entrada_manual ? <Insignia>Manual</Insignia> : <Insignia tono="azul">Automático</Insignia>}</td>
                        <td className="text-right num">{k.meta_numerica ?? "—"} <span className="text-sm text-gris">{k.plantilla_kpi_detalle?.unidad_medida}</span></td>
                        <td className="text-right num">{Number(k.ponderacion)}%</td>
                        <td className="whitespace-nowrap text-right">
                          <Boton variante="fantasma" tam="sm" icono={Pencil} aria-label={`Editar ${k.nombre}`} onClick={() => setFormKpi(k)} />
                          <Boton variante="fantasma" tam="sm" icono={Trash2} aria-label={`Quitar ${k.nombre}`} className="text-rojo" onClick={async () => {
                            if (await confirmar({ titulo: "¿Quitar este KPI del puesto?", mensaje: "Se borran también sus resultados anotados. Si solo quieres dejar de medirlo, desactívalo.", boton: "Quitar", peligro: true })) {
                              try { await eliminarKpiAsignado(k.id); avisar("KPI quitado del puesto."); cargar(); } catch (e) { avisar(e.message, "rojo"); }
                            }
                          }} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className={`border-t border-linea-suave px-5 py-3 text-sm ${Math.round(suma) === 100 ? "text-verde" : "text-[#a86a00]"}`}>
                Los pesos activos suman {suma}%{Math.round(suma) === 100 ? "." : ". Deberían sumar 100% para que cada uno pese lo que dice."}
              </p>
            </>
          )}
        </Panel>
      </div>

      <FormKpi abierto={!!formKpi} inicial={formKpi} puestoId={id} plantillas={plantillas} asignadas={kpis.map((k) => k.plantilla_kpi_detalle?.id)}
        onCerrar={() => setFormKpi(null)} onGuardado={() => { avisar("KPI guardado."); setFormKpi(null); cargar(); }} />
      <FormPuesto abierto={editando} inicial={p} deptos={deptos} puestos={puestos} onCerrar={() => setEditando(false)}
        onGuardado={() => { avisar("Puesto actualizado."); setEditando(false); cargar(); }} />
    </div>
  );
}
