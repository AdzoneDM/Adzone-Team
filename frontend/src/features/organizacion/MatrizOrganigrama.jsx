// Matriz de reporte y coordinación (¿a quién le reporto?, ¿con quién coordino?, ¿por dónde escalo?) y registro de cambios y versiones.
import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Download, Printer, Search } from "lucide-react";
import { matrizOrganigrama, urlMatrizExcel, versionesOrganigrama } from "@/lib/api";
import { fechaCorta, fechaHora } from "@/lib/formato";
import { Alerta, Cargando, cx } from "@/components/ui";

const SITUACION = { VACANTE: ["Vacante", "border border-dashed border-gris/50 text-gris"], COMPARTIDO: ["Compartido", "bg-[#f0ebfb] text-[#6d4ac8]"], OCUPADO: ["Ocupado", "bg-verde-50 text-verde"] };
const normal = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export function Matriz() {
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [buscar, setBuscar] = useState("");
  useEffect(() => { matrizOrganigrama().then(setD).catch((e) => setError(e.message)); }, []);
  const t = normal(buscar.trim());
  const filas = useMemo(() => (d?.filas || []).filter((f) => !t || normal([f.puesto, f.unidad, f.departamento, ...f.personas, ...f.cubre].join(" ")).includes(t)), [d, t]);
  if (error) return <Alerta>{error}</Alerta>;
  if (!d) return <Cargando />;
  return (
    <div className="space-y-4">
      {d.revision.length ? (
        <div className="rounded-xl border border-amarillo-600/40 bg-amarillo-50 p-4 no-imprimir">
          <p className="flex items-center gap-2 font-semibold text-[#5c3d00]"><AlertTriangle className="size-4" aria-hidden />Revisión de coherencia</p>
          <ul className="mt-2 space-y-1.5 text-sm text-[#5c3d00]">{d.revision.map((a) => (
            <li key={a.tipo}>{a.texto} <span className="text-[#8a5a00]">{a.puestos.slice(0, 8).join(" · ")}{a.puestos.length > 8 ? ` y ${a.puestos.length - 8} más` : ""}</span></li>
          ))}</ul>
        </div>
      ) : <Alerta tono="verde" className="no-imprimir">Cada puesto tiene su superior directo y su unidad; las dependencias coinciden.</Alerta>}
      <div className="flex flex-wrap items-center gap-2 no-imprimir">
        <div className="relative min-w-56 flex-1 md:max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" aria-hidden />
          <input className="campo h-10 !pl-9" placeholder="Buscar cargo, unidad o persona" value={buscar} onChange={(e) => setBuscar(e.target.value)} aria-label="Buscar en la matriz" />
        </div>
        <a href={urlMatrizExcel} className="ml-auto inline-flex h-10 items-center gap-2 rounded-lg border border-linea bg-white px-4 text-sm font-semibold text-azul hover:bg-fondo"><Download className="size-4" aria-hidden />Excel (editable)</a>
        <button type="button" onClick={() => window.print()} className="inline-flex h-10 items-center gap-2 rounded-lg border border-linea bg-white px-4 text-sm font-semibold text-azul hover:bg-fondo"><Printer className="size-4" aria-hidden />PDF / imprimir</button>
      </div>
      <div className="overflow-x-auto rounded-xl bg-white shadow-sm ring-1 ring-linea print:overflow-visible print:shadow-none">
        <table className="w-full min-w-[60rem] text-sm">
          <thead className="bg-azul text-left text-xs text-white">
            <tr>{["Unidad", "Cargo", "Superior directo", "Coordinación operativa", "Personas", "Situación", "Vía de escalamiento"].map((h) => <th key={h} className="px-3 py-2.5 font-semibold">{h}</th>)}</tr>
          </thead>
          <tbody>
            {filas.map((f) => {
              const [st, cl] = SITUACION[f.situacion];
              return (
                <tr key={f.id} className="border-t border-linea-suave align-top">
                  <td className="px-3 py-2.5 font-semibold text-azul">{f.unidad || <span className="font-normal italic text-gris">Sin unidad</span>}</td>
                  <td className="px-3 py-2.5"><span className="font-medium text-tinta">{f.puesto}</span><span className="block text-xs text-gris">{f.departamento}</span></td>
                  <td className="px-3 py-2.5">{f.superior || <span className="text-gris">— máximo nivel</span>}</td>
                  <td className="px-3 py-2.5 text-xs">{f.coordina_con.length || f.coordinado_por.length ? <>
                    {f.coordina_con.map((x) => <span key={x} className="block">↔ {x}</span>)}
                    {f.coordinado_por.filter((x) => !f.coordina_con.includes(x)).map((x) => <span key={x} className="block text-gris">↔ {x}</span>)}
                  </> : <span className="text-gris">—</span>}</td>
                  <td className="px-3 py-2.5 text-xs">{f.personas.join(", ") || "—"}{f.cubre.length > 0 && <span className="block text-[#6d4ac8]">Cubre: {f.cubre.join(", ")}</span>}</td>
                  <td className="px-3 py-2.5"><span className={cx("inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold", cl)}>{st}</span></td>
                  <td className="px-3 py-2.5 text-xs text-gris">{f.escalamiento.length ? f.escalamiento.join(" → ") : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function Cambios() {
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { versionesOrganigrama().then(setD).catch((e) => setError(e.message)); }, []);
  if (error) return <Alerta>{error}</Alerta>;
  if (!d) return <Cargando />;
  return (
    <div className="grid gap-5 lg:grid-cols-[18rem_minmax(0,1fr)]">
      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-noche">Versiones aprobadas</h2>
        {d.versiones.length ? d.versiones.map((v) => (
          <div key={v.numero} className="rounded-xl bg-white p-3.5 shadow-sm ring-1 ring-linea">
            <p className="flex items-center gap-1.5 font-semibold"><CheckCircle2 className="size-4 text-verde" aria-hidden />Versión {v.numero}</p>
            <p className="text-sm text-gris">Vigente desde {fechaCorta(v.vigente_desde)} · {v.cambios} cambio(s)</p>
            <p className="text-xs text-gris">Aprobada por {v.aprobada_por} · {fechaHora(v.aprobada_en)}</p>
            {v.notas && <p className="mt-1 text-sm">{v.notas}</p>}
          </div>
        )) : <p className="text-sm text-gris">Todavía no hay versiones aprobadas por Dirección General.</p>}
      </section>
      <section>
        <h2 className="mb-2 text-sm font-semibold text-noche">Registro de cambios</h2>
        {d.cambios.length ? (
          <div className="overflow-x-auto rounded-xl bg-white shadow-sm ring-1 ring-linea">
            <table className="w-full min-w-[44rem] text-sm">
              <thead className="text-left text-xs text-gris"><tr>{["Fecha", "Puesto", "Qué cambió", "Antes → después", "Versión"].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr></thead>
              <tbody>{d.cambios.map((c) => (
                <tr key={c.id} className="border-t border-linea-suave align-top">
                  <td className="whitespace-nowrap px-3 py-2 text-xs text-gris">{fechaHora(c.fecha)}<span className="block">{c.usuario}</span></td>
                  <td className="px-3 py-2 font-medium">{c.puesto}</td>
                  <td className="px-3 py-2">{c.campo}</td>
                  <td className="px-3 py-2 text-xs"><span className="text-gris line-through decoration-gris/40">{c.antes || "—"}</span> → <b className="font-medium">{c.despues || "—"}</b></td>
                  <td className="px-3 py-2">{c.version ? `v${c.version}` : <span className="rounded-full bg-amarillo-50 px-2 py-0.5 text-[11px] font-semibold text-[#8a5a00]">Pendiente</span>}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : <p className="text-sm text-gris">No hay cambios registrados todavía: se anotan solos al editar nombre, unidad, departamento, superior o coordinación de un puesto.</p>}
      </section>
    </div>
  );
}
