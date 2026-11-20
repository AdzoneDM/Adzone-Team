// Lista de personas: filtros con conteos, grupos por departamento, tabla en pantallas grandes y tarjetas en el celular.

import { Pencil, Search, UserRound, X } from "lucide-react";
import { hace } from "@/lib/formato";
import { Avatar, Boton, Insignia, Vacio, cx } from "@/components/ui";

const SIN_DEPTO = "Sin departamento";
const DIAS_ACTIVA = 7;

/** Perfiles de acceso como etiquetas: Dirección destacada y, si hay muchos, «+n». */
function Perfiles({ roles = [] }) {
  const lista = roles.filter((r) => r !== "Colaborador");
  if (!lista.length) return <Insignia>Colaborador</Insignia>;
  const [primero, ...resto] = lista;
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      <Insignia tono={lista.includes("Administrador") ? "noche" : "neutro"}>{lista.includes("Administrador") ? "Administrador" : primero}</Insignia>
      {(lista.includes("Administrador") ? lista.length - 1 : resto.length) > 0 && (
        <span className="text-xs font-medium text-gris" title={lista.join(", ")}>+{lista.includes("Administrador") ? lista.length - 1 : resto.length}</span>
      )}
    </span>
  );
}

/** Último acceso: «hace 2 h» con un punto verde si entró esta semana; «Nunca» destacado en ámbar suave. */
function Acceso({ fecha }) {
  if (!fecha) return <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-sm text-[#8a5a00]"><span className="size-1.5 rounded-full bg-amarillo-600" aria-hidden />Nunca ha entrado</span>;
  const reciente = (Date.now() - new Date(fecha).getTime()) / 86400000 < DIAS_ACTIVA;
  return <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-sm text-gris"><span className={cx("size-1.5 rounded-full", reciente ? "bg-verde" : "bg-linea")} aria-hidden />{hace(fecha)}</span>;
}

function Nombre({ u, yo }) {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <Avatar nombre={u.nombre} tam="sm" />
      <div className="min-w-0">
        <p className="truncate font-medium leading-tight text-tinta">{u.nombre}{u.id === yo && <span className="ml-1.5 rounded bg-azul/10 px-1.5 py-0.5 text-[11px] font-semibold text-azul">Tú</span>}</p>
        <p className="truncate text-[13px] text-gris">{u.username}{u.email && <span className="hidden xl:inline"> · {u.email}</span>}</p>
      </div>
    </div>
  );
}

function Puesto({ u }) {
  if (!u.puesto) return <Insignia tono="amarillo">Sin puesto</Insignia>;
  return (
    <div className="min-w-0">
      <p className="truncate text-sm text-tinta">{u.puesto}</p>
      {u.puestos_adicionales?.length > 0 && <p className="truncate text-xs text-azul">+ {u.puestos_adicionales.map((p) => p.nombre).join(", ")}</p>}
    </div>
  );
}

function BotonEditar({ u, onEditar }) {
  return <Boton variante="fantasma" tam="sm" icono={Pencil} aria-label={`Editar a ${u.nombre}`} title="Editar" onClick={() => onEditar(u)} />;
}

/** Agrupa por departamento (ordenados) y dentro, por nombre. */
function agrupar(lista) {
  const grupos = new Map();
  [...lista].sort((a, b) => a.nombre.localeCompare(b.nombre, "es")).forEach((u) => {
    const clave = u.departamento || SIN_DEPTO;
    if (!grupos.has(clave)) grupos.set(clave, []);
    grupos.get(clave).push(u);
  });
  return [...grupos.entries()].sort(([a], [b]) => (a === SIN_DEPTO) - (b === SIN_DEPTO) || a.localeCompare(b, "es"));
}

/** Filtros como botones con su conteo (una sola fila, se desplaza en el celular). */
export function FiltrosPersonas({ filtro, onFiltro, conteos }) {
  const opciones = [
    ["activos", "Activas"], ["sin_acceso", "Aún no entran"], ["sin_puesto", "Sin puesto"], ["inactivos", "Desactivadas"], ["todos", "Todas"],
  ];
  return (
    <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 md:mx-0 md:px-0 [scrollbar-width:none]" role="tablist" aria-label="Mostrar personas">
      {opciones.map(([clave, texto]) => (
        <button key={clave} type="button" role="tab" aria-selected={filtro === clave} onClick={() => onFiltro(clave)}
          className={cx("flex h-10 shrink-0 items-center gap-2 rounded-full border px-4 text-sm font-medium transition-colors",
            filtro === clave ? "border-noche bg-noche text-white" : "border-linea bg-white text-tinta hover:border-azul/40 hover:bg-fondo")}>
          {texto}
          <span className={cx("num rounded-full px-1.5 text-xs", filtro === clave ? "bg-white/20" : "bg-fondo text-gris", clave === "sin_puesto" && conteos[clave] > 0 && filtro !== clave && "bg-amarillo-50 text-[#8a5a00]")}>{conteos[clave]}</span>
        </button>
      ))}
    </div>
  );
}

export function BuscadorPersonas({ valor, onCambio, depto, onDepto, deptos }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="relative min-w-56 flex-1 md:max-w-md">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" aria-hidden />
        <input className="campo h-11 !pl-9 !pr-9" placeholder="Buscar persona…" value={valor} onChange={(e) => onCambio(e.target.value)} aria-label="Buscar persona" />
        {valor && <button type="button" onClick={() => onCambio("")} aria-label="Borrar la búsqueda" className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full p-1 text-gris hover:bg-linea"><X className="size-4" aria-hidden /></button>}
      </div>
      <select className="campo h-11 w-auto py-0" value={depto} onChange={(e) => onDepto(e.target.value)} aria-label="Departamento">
        <option value="">Todos los departamentos</option>
        {deptos.map((d) => <option key={d} value={d}>{d}</option>)}
      </select>
    </div>
  );
}

export default function ListaPersonas({ personas, yo, veSalarios, onEditar, onLimpiar }) {
  if (!personas.length) {
    return <Vacio icono={UserRound} titulo="Nadie coincide con lo que buscas" accion={<Boton variante="secundario" onClick={onLimpiar}>Ver a todas las personas</Boton>} />;
  }
  const grupos = agrupar(personas);
  return (
    <div className="space-y-5">
      {grupos.map(([depto, gente]) => (
        <section key={depto} aria-label={depto} className="overflow-hidden rounded-xl border border-linea bg-white">
          <header className="flex items-center justify-between border-b border-linea-suave bg-fondo/70 px-4 py-2.5">
            <h2 className="!text-[15px] font-semibold !text-noche">{depto}</h2>
            <span className="num text-xs font-medium text-gris">{gente.length} {gente.length === 1 ? "persona" : "personas"}</span>
          </header>

          {/* Pantallas grandes: tabla */}
          <table className="hidden w-full text-left md:table">
            <caption className="sr-only">Personas de {depto}</caption>
            <colgroup><col className="w-[30%]" /><col className="w-[24%]" /><col className="w-[16%]" />{veSalarios && <col className="w-[10%]" />}<col /><col className="w-14" /></colgroup>
            <thead className="text-xs font-medium text-gris">
              <tr className="border-b border-linea-suave"><th className="px-4 py-2 font-medium">Persona</th><th className="py-2 font-medium">Puesto</th><th className="py-2 font-medium">Perfil</th>{veSalarios && <th className="py-2 text-right font-medium">Salario</th>}<th className="py-2 pl-4 font-medium">Último acceso</th><th className="py-2 pr-3"><span className="sr-only">Acciones</span></th></tr>
            </thead>
            <tbody className="divide-y divide-linea-suave">
              {gente.map((u) => (
                <tr key={u.id} className={cx("transition-colors hover:bg-fondo/60", !u.is_active && "opacity-60")}>
                  <td className="px-4 py-3"><Nombre u={u} yo={yo} /></td>
                  <td className="py-3 pr-3"><Puesto u={u} /></td>
                  <td className="py-3"><Perfiles roles={u.roles} />{!u.is_active && <Insignia className="ml-1">Desactivada</Insignia>}</td>
                  {veSalarios && <td className="whitespace-nowrap py-3 text-right text-sm">{u.salario_mensual != null ? <span className="num">{Number(u.salario_mensual).toLocaleString("es-DO", { maximumFractionDigits: 0 })}</span> : <span className="text-gris">—</span>}</td>}
                  <td className="py-3 pl-4"><Acceso fecha={u.last_login} /></td>
                  <td className="py-2 pr-3 text-right"><BotonEditar u={u} onEditar={onEditar} /></td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Celular: tarjetas */}
          <ul className="divide-y divide-linea-suave md:hidden">
            {gente.map((u) => (
              <li key={u.id} className={cx("flex items-start gap-2 px-4 py-3", !u.is_active && "opacity-60")}>
                <div className="min-w-0 flex-1 space-y-2">
                  <Nombre u={u} yo={yo} />
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 pl-[44px]">
                    <Puesto u={u} />
                    <Perfiles roles={u.roles} />
                    {!u.is_active && <Insignia>Desactivada</Insignia>}
                  </div>
                  <div className="pl-[44px]"><Acceso fecha={u.last_login} /></div>
                </div>
                <BotonEditar u={u} onEditar={onEditar} />
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

