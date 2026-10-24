import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Save, SquarePen } from "lucide-react";
import { departamentos as cargarDeptos, guardarPlanilla, planillaKPI } from "@/lib/api";
import { mesActual, nombreMes } from "@/lib/formato";
import { Alerta, Barra, Boton, Cabecera, Cargando, Panel, SelectorMes, Vacio, useAviso, useConfirmar } from "@/components/ui";

const clave = (c, k) => `${c}-${k}`;

export default function KpisDelMes() {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const [mes, setMes] = useState(mesActual());
  const [depto, setDepto] = useState("");
  const [deptos, setDeptos] = useState([]);
  const [datos, setDatos] = useState(null);
  const [cambios, setCambios] = useState({});
  const [errores, setErrores] = useState([]);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  const cargar = useCallback(() => {
    setDatos(null);
    setCambios({});
    planillaKPI(mes, depto).then(setDatos).catch((e) => setError(e.message));
  }, [mes, depto]);
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => { cargarDeptos().then(setDeptos).catch(() => {}); }, []);

  // Personas del mismo puesto comparten KPIs: una tabla por puesto, una columna por KPI.
  const porPuesto = useMemo(() => {
    const g = new Map();
    (datos?.filas || []).forEach((f) => {
      const k = `${f.departamento} · ${f.puesto}`;
      if (!g.has(k)) g.set(k, { titulo: f.puesto, departamento: f.departamento, kpis: f.kpis, filas: [] });
      g.get(k).filas.push(f);
    });
    return [...g.values()];
  }, [datos]);

  const valor = (f, k, campo) => {
    const c = cambios[clave(f.colaborador, k.kpi_asignado)];
    if (c && campo in c) return c[campo];
    return k[campo] ?? "";
  };
  const poner = (f, k, campo, v) => setCambios((x) => {
    const id = clave(f.colaborador, k.kpi_asignado);
    return { ...x, [id]: { colaborador: f.colaborador, kpi_asignado: k.kpi_asignado, valor_meta: k.valor_meta ?? "", valor_real: k.valor_real ?? "", ...x[id], [campo]: v } };
  });
  const pendientes = Object.values(cambios);

  const guardar = async () => {
    setGuardando(true);
    setErrores([]);
    try {
      const r = await guardarPlanilla(mes, pendientes.map((c) => ({ ...c, valor_meta: c.valor_meta === "" ? 0 : c.valor_meta })));
      setErrores(r.errores);
      avisar(`${r.guardados} resultado(s) guardado(s)${r.borrados ? `, ${r.borrados} borrado(s)` : ""}.`);
      if (!r.errores.length) cargar();
    } catch (e) {
      setErrores(e.data?.errores || [e.message]);
    }
    setGuardando(false);
  };

  useEffect(() => {
    const salir = (e) => { if (pendientes.length) { e.preventDefault(); e.returnValue = ""; } };
    window.addEventListener("beforeunload", salir);
    return () => window.removeEventListener("beforeunload", salir);
  }, [pendientes.length]);

  if (error) return <Alerta>{error}</Alerta>;
  return (
    <div>
      <Cabecera titulo="KPIs del mes" descripcion="Anota los KPIs que vienen de fuera (ventas, seguidores, conversión). Los KPIs automáticos se llenan solos con las tareas validadas.">
        <SelectorMes valor={mes} onCambio={async (m) => {
          if (!pendientes.length || await confirmar({ titulo: "Tienes cambios sin guardar", mensaje: "Si cambias de mes se pierden.", boton: "Cambiar de mes", peligro: true })) setMes(m);
        }} />
        <select className="campo h-11 w-auto py-0" value={depto} onChange={(e) => setDepto(e.target.value)} aria-label="Departamento">
          <option value="">Todos los departamentos</option>
          {deptos.map((d) => <option key={d.id} value={d.id}>{d.nombre}</option>)}
        </select>
      </Cabecera>

      {errores.length > 0 && <Alerta className="mb-4"><p className="font-medium">Algunos valores no se guardaron:</p><ul className="mt-1 list-disc pl-5">{errores.map((e, i) => <li key={i}>{e}</li>)}</ul></Alerta>}

      {!datos ? <Cargando /> : porPuesto.length === 0 ? (
        <Vacio icono={SquarePen} titulo="No hay KPIs manuales que anotar">
          Ningún puesto con personas tiene KPIs de entrada manual. Se asignan en <Link to="/puestos" className="font-medium text-azul hover:underline">Departamentos y puestos</Link>.
        </Vacio>
      ) : (
        <div className="space-y-6 pb-20">
          {porPuesto.map((g) => (
            <Panel key={g.departamento + g.titulo} titulo={<>{g.titulo} <span className="text-sm font-normal text-gris">· {g.departamento}</span></>} cuerpo="p-0">
              <div className="overflow-x-auto">
                <table className="tabla">
                  <thead>
                    <tr>
                      <th>Persona</th>
                      {g.kpis.map((k) => (
                        <th key={k.kpi_asignado} className="min-w-56 whitespace-normal">
                          <span className="block text-tinta">{k.nombre}</span>
                          <span className="font-normal">{k.unidad_medida}{k.menor_es_mejor ? ", más bajo es mejor" : ""} · peso {k.ponderacion}%</span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {g.filas.map((f) => (
                      <tr key={f.colaborador}>
                        <td className="whitespace-nowrap font-medium">{f.nombre}</td>
                        {f.kpis.map((k) => {
                          const editado = !!cambios[clave(f.colaborador, k.kpi_asignado)];
                          return (
                            <td key={k.kpi_asignado}>
                              <div className="flex items-end gap-2">
                                <label className="text-xs text-gris">Logrado
                                  <input type="number" step="any" min={0} inputMode="decimal" className="campo mt-0.5 h-10 w-24 text-right num" value={valor(f, k, "valor_real")}
                                    onChange={(e) => poner(f, k, "valor_real", e.target.value)} />
                                </label>
                                <label className="text-xs text-gris">Meta
                                  <input type="number" step="any" min={0} inputMode="decimal" className="campo mt-0.5 h-10 w-24 text-right num" value={valor(f, k, "valor_meta")}
                                    onChange={(e) => poner(f, k, "valor_meta", e.target.value)} />
                                </label>
                              </div>
                              {!editado && k.cumplimiento != null && <div className="mt-1.5 flex items-center gap-2"><Barra valor={k.cumplimiento} className="w-24" /><span className="text-xs num">{Math.round(k.cumplimiento)}%</span></div>}
                              {editado && <p className="mt-1.5 text-xs text-[#a86a00]">Sin guardar</p>}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          ))}
        </div>
      )}

      {pendientes.length > 0 && (
        <div className="fixed inset-x-0 bottom-16 z-30 border-t border-linea bg-white/95 px-4 py-3 backdrop-blur md:bottom-0 md:left-64">
          <div className="mx-auto flex max-w-[1320px] items-center justify-between gap-3 md:px-4">
            <p className="text-sm text-gris">{pendientes.length} cambio(s) sin guardar en {nombreMes(mes)}. Deja «Logrado» vacío para borrar un resultado.</p>
            <div className="flex gap-2"><Boton variante="secundario" onClick={() => setCambios({})}>Descartar</Boton><Boton icono={Save} onClick={guardar} cargando={guardando}>Guardar</Boton></div>
          </div>
        </div>
      )}
    </div>
  );
}
