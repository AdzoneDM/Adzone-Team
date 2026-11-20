// KPIs del mes: la Dirección anota los resultados que vienen de fuera (ventas, seguidores, conversión…).
// Una tarjeta por persona con sus indicadores en filas, agrupadas por puesto, con el avance de lo anotado.
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { CircleCheckBig, Save, Search, SquarePen, X } from "lucide-react";
import { departamentos as cargarDeptos, guardarPlanilla, planillaKPI } from "@/lib/api";
import { mesActual, nombreMes, plural } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import { Alerta, Avatar, Barra, Boton, Cabecera, Cargando, Insignia, SelectorMes, Vacio, cx, useAviso, useConfirmar } from "@/components/ui";

const clave = (c, k) => `${c}-${k}`;
const COLUMNAS = "sm:grid-cols-[minmax(0,1fr)_7.5rem_7.5rem_8.5rem]";

/** Número con su unidad dentro del campo (por ejemplo «%»). Se pinta en ámbar mientras tiene cambios sin guardar. */
function CampoNumero({ etiqueta, rotulo, valor, onCambio, unidad, editado, desactivado }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-gris sm:sr-only" aria-hidden>{rotulo}</span>
      <span className="relative block">
        <input type="number" step="any" min={0} inputMode="decimal" value={valor} disabled={desactivado} aria-label={etiqueta}
          onChange={(e) => onCambio(e.target.value)} placeholder="—"
          className={cx("campo num h-10 w-full text-right", unidad && "!pr-8", editado && "!border-amarillo-600 !bg-amarillo-50", desactivado && "cursor-not-allowed")} />
        {unidad && <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-gris" aria-hidden>{unidad}</span>}
      </span>
    </label>
  );
}

function Cumplimiento({ k, editado }) {
  if (editado) return <p className="flex items-center gap-1.5 text-xs font-medium text-[#a86a00]"><span className="size-1.5 rounded-full bg-amarillo-600" aria-hidden />Sin guardar</p>;
  if (k.cumplimiento == null) return <p className="text-xs text-gris">Sin anotar</p>;
  return (
    <div className="flex items-center gap-2" title={`Cumplimiento: ${Math.round(k.cumplimiento)}%`}>
      <Barra valor={k.cumplimiento} className="flex-1" />
      <span className="num w-10 text-right text-xs font-semibold text-tinta">{Math.round(k.cumplimiento)}%</span>
    </div>
  );
}

export default function KpisDelMes() {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const { usuario } = useSesion();
  const [mes, setMes] = useState(mesActual());
  const [depto, setDepto] = useState("");
  const [deptos, setDeptos] = useState([]);
  const [datos, setDatos] = useState(null);
  const [cambios, setCambios] = useState({});
  const [errores, setErrores] = useState([]);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const [buscar, setBuscar] = useState("");
  const [soloPendientes, setSoloPendientes] = useState(false);

  const cargar = useCallback(() => {
    setDatos(null);
    setCambios({});
    planillaKPI(mes, depto).then(setDatos).catch((e) => setError(e.message));
  }, [mes, depto]);
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => { cargarDeptos().then(setDeptos).catch(() => {}); }, []);

  // Lo anotado en pantalla (sin guardar) manda sobre lo que viene del servidor
  const valor = (f, k, campo) => {
    const c = cambios[clave(f.colaborador, k.kpi_asignado)];
    if (c && campo in c) return c[campo];
    return k[campo] ?? "";
  };
  const poner = (f, k, campo, v) => setCambios((x) => {
    const id = clave(f.colaborador, k.kpi_asignado);
    return { ...x, [id]: { colaborador: f.colaborador, kpi_asignado: k.kpi_asignado, valor_meta: k.valor_meta ?? "", valor_real: k.valor_real ?? "", ...x[id], [campo]: v } };
  });
  const anotado = (f, k) => String(valor(f, k, "valor_real")) !== "";
  const pendientes = Object.values(cambios);

  // Personas del mismo puesto comparten KPIs: un grupo por puesto, una tarjeta por persona
  const grupos = useMemo(() => {
    const g = new Map();
    const t = buscar.trim().toLowerCase();
    (datos?.filas || []).forEach((f) => {
      if (t && !f.nombre.toLowerCase().includes(t)) return;
      if (soloPendientes && f.kpis.every((k) => anotado(f, k))) return;
      const id = `${f.departamento} · ${f.puesto}`;
      if (!g.has(id)) g.set(id, { id, titulo: f.puesto, departamento: f.departamento, filas: [] });
      g.get(id).filas.push(f);
    });
    return [...g.values()];
  }, [datos, buscar, soloPendientes, cambios]); // eslint-disable-line react-hooks/exhaustive-deps

  const total = useMemo(() => {
    const filas = datos?.filas || [];
    const celdas = filas.flatMap((f) => f.kpis.map((k) => anotado(f, k)));
    return { celdas: celdas.length, hechas: celdas.filter(Boolean).length, personas: filas.length };
  }, [datos, cambios]); // eslint-disable-line react-hooks/exhaustive-deps

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
  const sinResultados = datos && (datos.filas || []).length === 0;
  const avance = total.celdas ? Math.round((total.hechas / total.celdas) * 100) : 0;

  return (
    <div className="pb-24">
      <Cabecera titulo="KPIs del mes" descripcion="Anota los resultados que vienen de fuera (ventas, seguidores, conversión). Los KPIs automáticos se llenan solos con las tareas validadas.">
        <SelectorMes valor={mes} onCambio={async (m) => {
          if (!pendientes.length || await confirmar({ titulo: "Tienes cambios sin guardar", mensaje: "Si cambias de mes se pierden.", boton: "Cambiar de mes", peligro: true })) setMes(m);
        }} />
        <select className="campo h-11 w-auto py-0" value={depto} onChange={(e) => setDepto(e.target.value)} aria-label="Departamento">
          <option value="">Todos los departamentos</option>
          {deptos.map((d) => <option key={d.id} value={d.id}>{d.nombre}</option>)}
        </select>
      </Cabecera>

      {errores.length > 0 && <Alerta className="mb-4"><p className="font-medium">Algunos valores no se guardaron:</p><ul className="mt-1 list-disc pl-5">{errores.map((e, i) => <li key={i}>{e}</li>)}</ul></Alerta>}

      {!datos ? <Cargando /> : sinResultados ? (
        <Vacio icono={SquarePen} titulo="No hay KPIs manuales que anotar">
          Ningún puesto con personas tiene KPIs de entrada manual. Se asignan en <Link to="/puestos" className="font-medium text-azul hover:underline">Departamentos y puestos</Link>.
        </Vacio>
      ) : (
        <>
          {/* Resumen del mes + herramientas */}
          <div className="mb-5 rounded-xl border border-linea bg-white p-4">
            <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
              <div className="min-w-0 flex-1">
                <p className="text-sm text-gris">Avance de {nombreMes(mes)}</p>
                <p className="mt-0.5 flex flex-wrap items-baseline gap-x-2 font-display text-2xl font-semibold text-noche">
                  <span className="num">{total.hechas}</span><span className="text-base font-normal text-gris">de <span className="num">{total.celdas}</span> resultados anotados · {plural(total.personas, "persona", "personas")}</span>
                </p>
                <div className="mt-2 h-2 max-w-md overflow-hidden rounded-full bg-linea-suave" role="progressbar" aria-valuenow={avance} aria-valuemin={0} aria-valuemax={100} aria-label="Avance de resultados anotados"><div className="h-full rounded-full bg-azul transition-[width]" style={{ width: `${avance}%` }} /></div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <div className="relative min-w-52">
                  <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" aria-hidden />
                  <input className="campo h-10 !pl-9 !pr-9" placeholder="Buscar persona…" value={buscar} onChange={(e) => setBuscar(e.target.value)} aria-label="Buscar persona" />
                  {buscar && <button type="button" onClick={() => setBuscar("")} aria-label="Borrar la búsqueda" className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full p-1 text-gris hover:bg-linea"><X className="size-4" aria-hidden /></button>}
                </div>
                <button type="button" onClick={() => setSoloPendientes((v) => !v)} aria-pressed={soloPendientes}
                  className={cx("flex h-10 items-center gap-2 rounded-lg border px-3 text-sm font-medium transition-colors", soloPendientes ? "border-noche bg-noche text-white" : "border-linea bg-white text-tinta hover:bg-fondo")}>
                  <CircleCheckBig className="size-4" aria-hidden />Solo pendientes
                </button>
              </div>
            </div>
            {grupos.length > 1 && (
              <nav className="mt-3 flex flex-wrap gap-1.5 border-t border-linea-suave pt-3" aria-label="Ir a un puesto">
                {grupos.map((g) => (
                  <a key={g.id} href={`#puesto-${encodeURIComponent(g.id)}`} onClick={(e) => { e.preventDefault(); document.getElementById(`puesto-${g.id}`)?.scrollIntoView({ behavior: "smooth", block: "start" }); }}
                    className="rounded-full border border-linea bg-fondo px-3 py-1 text-xs font-medium text-tinta hover:border-azul/40 hover:bg-white">
                    {g.titulo} <span className="num text-gris">{g.filas.length}</span>
                  </a>
                ))}
              </nav>
            )}
          </div>

          {grupos.length === 0 ? (
            <Vacio icono={CircleCheckBig} titulo={soloPendientes ? "No queda nada pendiente" : "Nadie coincide con la búsqueda"}>
              {soloPendientes ? "Todos los resultados de este mes están anotados." : "Prueba con otro nombre."}
            </Vacio>
          ) : (
            <div className="space-y-8">
              {grupos.map((g) => {
                const celdas = g.filas.flatMap((f) => f.kpis.map((k) => anotado(f, k)));
                const hechas = celdas.filter(Boolean).length;
                return (
                  <section key={g.id} id={`puesto-${g.id}`} aria-label={g.titulo} className="scroll-mt-24">
                    <header className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1">
                      <h2 className="!text-lg font-semibold !text-noche">{g.titulo}</h2>
                      <Insignia tono="azul">{g.departamento}</Insignia>
                      <span className="ml-auto text-sm text-gris"><span className="num font-medium text-tinta">{hechas}</span> de <span className="num">{celdas.length}</span> anotados</span>
                    </header>
                    <div className="grid gap-4 2xl:grid-cols-2">
                      {g.filas.map((f) => {
                        const propio = f.colaborador === usuario?.id;
                        const hechosPersona = f.kpis.filter((k) => anotado(f, k)).length;
                        return (
                          <article key={f.colaborador} className="overflow-hidden rounded-xl border border-linea bg-white">
                            <header className="flex items-center gap-3 border-b border-linea-suave px-4 py-3">
                              <Avatar nombre={f.nombre} tam="sm" />
                              <div className="min-w-0 flex-1">
                                <h3 className="truncate !text-[15px] font-semibold !text-noche">{f.nombre}</h3>
                                {propio && <p className="text-xs text-gris">No puedes anotar tus propios resultados.</p>}
                              </div>
                              <Insignia tono={hechosPersona === f.kpis.length ? "verde" : "neutro"}>{hechosPersona}/{f.kpis.length}</Insignia>
                            </header>
                            <div className={cx("hidden gap-3 bg-fondo/70 px-4 py-1.5 text-xs font-medium text-gris sm:grid", COLUMNAS)} aria-hidden>
                              <span>Indicador</span><span className="text-right">Logrado</span><span className="text-right">Meta</span><span>Cumplimiento</span>
                            </div>
                            <ul className="divide-y divide-linea-suave">
                              {f.kpis.map((k) => {
                                const editado = !!cambios[clave(f.colaborador, k.kpi_asignado)];
                                const unidad = k.unidad_medida === "%" || k.unidad_medida === "" ? k.unidad_medida : null;
                                return (
                                  <li key={k.kpi_asignado} className={cx("grid items-center gap-x-3 gap-y-2 px-4 py-3", COLUMNAS)}>
                                    <div className="min-w-0 sm:pr-1">
                                      <p className="text-sm font-medium leading-snug text-tinta">{k.nombre}</p>
                                      <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-gris">
                                        <span>{unidad ? "" : `${k.unidad_medida || "valor"} · `}peso {k.ponderacion}%</span>
                                        {k.menor_es_mejor && <span className="rounded bg-fondo px-1.5 py-0.5 font-medium">Menor es mejor</span>}
                                      </p>
                                    </div>
                                    <div className="grid grid-cols-2 gap-3 sm:contents">
                                      <CampoNumero etiqueta={`Logrado: ${k.nombre} de ${f.nombre}`} rotulo="Logrado" unidad={unidad} valor={valor(f, k, "valor_real")} editado={editado} desactivado={propio}
                                        onCambio={(v) => poner(f, k, "valor_real", v)} />
                                      <CampoNumero etiqueta={`Meta: ${k.nombre} de ${f.nombre}`} rotulo="Meta" unidad={unidad} valor={valor(f, k, "valor_meta")} editado={editado} desactivado={propio}
                                        onCambio={(v) => poner(f, k, "valor_meta", v)} />
                                    </div>
                                    <Cumplimiento k={k} editado={editado} />
                                  </li>
                                );
                              })}
                            </ul>
                          </article>
                        );
                      })}
                    </div>
                  </section>
                );
              })}
            </div>
          )}
        </>
      )}

      {pendientes.length > 0 && (
        <div className="fixed inset-x-0 bottom-16 z-30 border-t border-linea bg-white/95 px-4 py-3 shadow-[0_-8px_24px_-12px_rgba(15,37,80,0.25)] backdrop-blur lg:bottom-0 lg:left-64">
          <div className="mx-auto flex max-w-[1320px] items-center justify-between gap-3 md:px-4">
            <p className="text-sm text-gris"><b className="num text-tinta">{pendientes.length}</b> cambio(s) sin guardar<span className="hidden sm:inline"> en {nombreMes(mes)}. Deja «Logrado» vacío para borrar un resultado</span>.</p>
            <div className="flex shrink-0 gap-2"><Boton variante="secundario" onClick={() => setCambios({})}>Descartar</Boton><Boton icono={Save} onClick={guardar} cargando={guardando}>Guardar</Boton></div>
          </div>
        </div>
      )}
    </div>
  );
}
