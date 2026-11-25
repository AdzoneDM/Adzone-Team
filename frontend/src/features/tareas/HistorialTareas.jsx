// Historial de tareas: quién la hizo, quién la asignó y quién la validó, con fechas y calidad. Cada quien ve lo que ya veía (lo suyo, su equipo, lo que asignó).
import { useCallback, useEffect, useState } from "react";
import { useNovedades } from "@/lib/novedades";
import { ChevronLeft, ChevronRight, Download, History, Search } from "lucide-react";
import { historialTareas, obtenerTarea, urlHistorialCsv } from "@/lib/api";
import { fechaCorta } from "@/lib/formato";
import { useRecurso } from "@/lib/recursos";
import { DetalleTarea } from "@/features/tareas/componentes";
import { Alerta, Avatar, Boton, Cabecera, Cargando, Estrellas, Insignia, Vacio, useAviso } from "@/components/ui";

const fecha = (d) => (d ? fechaCorta(String(d).slice(0, 10)) : "—");

function Personas({ f }) {
  return (
    <div className="flex min-w-0 items-center gap-2">
      <Avatar nombre={f.hizo.nombre} tam="sm" />
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{f.hizo.nombre}</p>
        <p className="truncate text-xs text-gris">{f.hizo.departamento}{f.companeros.length > 0 && ` · con ${f.companeros.join(", ")}`}</p>
      </div>
    </div>
  );
}
const Validacion = ({ f }) => (f.estado === "CANCELADA" ? <Insignia>Cancelada</Insignia>
  : <span className="text-sm">{f.valido || "—"}{f.autovalidada && <Insignia tono="amarillo" className="ml-1.5">Autovalidada</Insignia>}</span>);

export default function HistorialTareas() {
  const avisar = useAviso();
  const [gente] = useRecurso("directorio");
  const [deptos] = useRecurso("departamentos");
  const [f, setF] = useState({ estado: "COMPLETADA", q: "", persona: "", validador: "", departamento: "", desde: "", hasta: "" });
  const [pagina, setPagina] = useState(1);
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  const [detalle, setDetalle] = useState(null);

  const params = useCallback(() => Object.fromEntries(Object.entries(f).filter(([, v]) => v !== "")), [f]);
  const [pulso, setPulso] = useState(0);
  useNovedades(() => setPulso((p) => p + 1)); // al llegar novedades se vuelve a pedir la página actual, sin mostrar «cargando»
  useEffect(() => { setPagina(1); }, [f]);
  useEffect(() => {
    const t = setTimeout(() => { // espera un instante al escribir para no consultar con cada letra
      historialTareas({ ...params(), pagina }).then((d) => { setDatos(d); setError(""); }).catch((e) => setError(e.message));
    }, f.q ? 300 : 0);
    return () => clearTimeout(t);
  }, [params, pagina, f.q, pulso]);
  const poner = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }));
  const abrir = async (id) => { try { setDetalle(await obtenerTarea(id)); } catch (e) { avisar(e.message, "rojo"); } };
  const personas = (gente || []).slice().sort((a, b) => a.nombre.localeCompare(b.nombre));

  if (error && !datos) return <Alerta>{error}</Alerta>;
  return (
    <div>
      <Cabecera titulo="Historial de tareas" descripcion="Quién hizo cada tarea, quién la asignó y quién la validó, con sus fechas y su calidad. Ves lo tuyo, lo de tu equipo y lo que tú asignaste.">
        <a href={urlHistorialCsv(params())} download><Boton variante="secundario" icono={Download}>Descargar (Excel)</Boton></a>
      </Cabecera>
      <div className="mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <div className="relative sm:col-span-2">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" aria-hidden />
          <input className="campo h-11 !pl-9" placeholder="Buscar por tarea o cliente…" value={f.q} onChange={poner("q")} aria-label="Buscar tarea o cliente" />
        </div>
        <select className="campo h-11 py-0 md:max-w-none" value={f.persona} onChange={poner("persona")} aria-label="Quién la hizo"><option value="">Quién la hizo: todos</option>{personas.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}</select>
        <select className="campo h-11 py-0" value={f.validador} onChange={poner("validador")} aria-label="Quién la validó"><option value="">Quién la validó: todos</option>{personas.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}</select>
        <select className="campo h-11 py-0" value={f.departamento} onChange={poner("departamento")} aria-label="Departamento"><option value="">Todos los departamentos</option>{(deptos || []).map((d) => <option key={d.id} value={d.id}>{d.nombre}</option>)}</select>
        <select className="campo h-11 py-0" value={f.estado} onChange={poner("estado")} aria-label="Estado"><option value="COMPLETADA">Validadas</option><option value="CANCELADA">Canceladas</option><option value="todas">Todas</option></select>
        <label className="flex items-center gap-2 text-sm text-gris">Desde<input type="date" className="campo h-11 py-0" value={f.desde} onChange={poner("desde")} /></label>
        <label className="flex items-center gap-2 text-sm text-gris">Hasta<input type="date" className="campo h-11 py-0" value={f.hasta} onChange={poner("hasta")} /></label>
      </div>

      {!datos ? <Cargando /> : datos.resultados.length === 0 ? (
        <Vacio icono={History} titulo="No hay tareas con esos filtros">Cambia los filtros o amplía las fechas.</Vacio>
      ) : (
        <>
          <p className="mb-2 text-sm text-gris" aria-live="polite"><b className="num text-tinta">{datos.count}</b> {datos.count === 1 ? "tarea" : "tareas"}</p>
          <div className="hidden overflow-x-auto rounded-xl border border-linea bg-white md:block">
            <table className="tabla">
              <thead><tr><th>Tarea</th><th>Quién la hizo</th><th>Asignada por</th><th>Validada por</th><th>Calidad</th><th className="text-right">Validada</th></tr></thead>
              <tbody>
                {datos.resultados.map((t) => (
                  <tr key={t.id} className="cursor-pointer" onClick={() => abrir(t.id)}>
                    <td className="max-w-xs"><button type="button" className="text-left font-medium hover:text-azul" onClick={(e) => { e.stopPropagation(); abrir(t.id); }}>{t.titulo}</button>
                      <p className="text-xs text-gris">{t.cliente || "Sin cliente"}{t.departamento_origen && t.departamento_origen !== t.hizo.departamento && ` · aporte de ${t.departamento_origen}`}</p></td>
                    <td><Personas f={t} /></td>
                    <td className="text-sm">{t.asigno || "—"}</td>
                    <td><Validacion f={t} /></td>
                    <td>{t.estado === "COMPLETADA" ? <Estrellas valor={t.calidad} /> : "—"}</td>
                    <td className="whitespace-nowrap text-right text-sm">{fecha(t.cierre)}{t.estado === "COMPLETADA" && t.a_tiempo === false && <p className="text-xs text-[#a86a00]">Tarde</p>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="space-y-3 md:hidden">
            {datos.resultados.map((t) => (
              <li key={t.id}>
                <button type="button" onClick={() => abrir(t.id)} className="w-full space-y-2 rounded-xl border border-linea bg-white p-4 text-left">
                  <p className="font-medium leading-snug">{t.titulo}</p>
                  <p className="text-xs text-gris">{t.cliente || "Sin cliente"} · {fecha(t.cierre)}</p>
                  <Personas f={t} />
                  <p className="text-sm text-gris">Asignó: <span className="text-tinta">{t.asigno || "—"}</span></p>
                  <p className="text-sm text-gris">Validó: <Validacion f={t} /> {t.estado === "COMPLETADA" && <Estrellas valor={t.calidad} />}</p>
                </button>
              </li>
            ))}
          </ul>
          {datos.paginas > 1 && (
            <nav className="mt-4 flex items-center justify-center gap-3" aria-label="Páginas">
              <Boton variante="secundario" tam="sm" icono={ChevronLeft} disabled={datos.pagina <= 1} onClick={() => setPagina((p) => p - 1)}>Anterior</Boton>
              <span className="text-sm text-gris">Página <b className="num text-tinta">{datos.pagina}</b> de <span className="num">{datos.paginas}</span></span>
              <Boton variante="secundario" tam="sm" disabled={datos.pagina >= datos.paginas} onClick={() => setPagina((p) => p + 1)}>Siguiente<ChevronRight className="size-4" aria-hidden /></Boton>
            </nav>
          )}
        </>
      )}
      <DetalleTarea tarea={detalle} abierto={!!detalle} onCerrar={() => setDetalle(null)} />
    </div>
  );
}
