import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Network, UserRound } from "lucide-react";
import { organigrama } from "@/lib/api";
import { plural } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import { Alerta, Cabecera, Cargando, Vacio, cx } from "@/components/ui";

function Personas({ lista }) {
  if (!lista.length) return <p className="text-xs text-gris">Vacante</p>;
  return (
    <ul className="flex flex-wrap gap-1">
      {lista.map((p) => <li key={p.id} className="flex items-center gap-1 rounded-full bg-azul/8 px-2 py-0.5 text-xs text-noche"><UserRound className="size-3" />{p.nombre}</li>)}
    </ul>
  );
}

function Nodo({ nodo, nivel, admin }) {
  const titulo = admin ? <Link to={`/puestos/${nodo.id}`} className="font-medium hover:text-azul">{nodo.nombre}</Link> : <span className="font-medium">{nodo.nombre}</span>;
  return (
    <li className={cx(nivel > 0 && "relative pl-4 before:absolute before:left-0 before:top-0 before:h-5 before:w-3 before:rounded-bl-md before:border-b before:border-l before:border-linea")}>
      <div className={cx("rounded-lg border bg-white px-3 py-2", nodo.personas.length ? "border-linea" : "border-dashed border-linea")}>
        <p className="text-sm leading-snug">{titulo}</p>
        <div className="mt-1.5"><Personas lista={nodo.personas} /></div>
      </div>
      {nodo.hijos.length > 0 && (
        <ul className="ml-3 mt-2 space-y-2 border-l border-linea pl-0">{nodo.hijos.map((h) => <Nodo key={h.id} nodo={h} nivel={nivel + 1} admin={admin} />)}</ul>
      )}
    </li>
  );
}

export default function Organigrama() {
  const { esAdmin } = useSesion();
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { organigrama().then(setDatos).catch((e) => setError(e.message)); }, []);

  if (error) return <Alerta>{error}</Alerta>;
  if (!datos) return <Cargando />;
  if (!datos.raices.length) return <Vacio icono={Network} titulo="Todavía no hay puestos">Los puestos y a quién reportan se crean en Departamentos y puestos.</Vacio>;

  // Cada raíz (normalmente la Dirección General) arriba; sus gerencias como columnas debajo.
  return (
    <div>
      <Cabecera titulo="Organigrama" descripcion="Quién reporta a quién. El supervisor de cada persona es quien ocupa el puesto del que depende; es quien asigna y valida sus tareas." />
      {datos.sin_puesto > 0 && esAdmin && (
        <Alerta tono="amarillo" className="mb-5">{plural(datos.sin_puesto, "persona activa no tiene", "personas activas no tienen")} puesto: no tienen supervisor ni KPIs. <Link to="/personas" className="font-medium underline">Asignar puestos</Link></Alerta>
      )}
      <div className="space-y-10">
        {datos.raices.map((raiz) => (
          <section key={raiz.id}>
            <div className="mx-auto max-w-sm rounded-xl bg-noche px-5 py-4 text-center text-white">
              {esAdmin ? <Link to={`/puestos/${raiz.id}`} className="font-display text-lg font-semibold hover:text-amarillo">{raiz.nombre}</Link> : <p className="font-display text-lg font-semibold">{raiz.nombre}</p>}
              <p className="text-sm text-white/60">{raiz.departamento}</p>
              <div className="mt-2 flex justify-center">{raiz.personas.length ? <p className="text-sm">{raiz.personas.map((p) => p.nombre).join(", ")}</p> : <p className="text-sm text-white/50">Vacante</p>}</div>
            </div>
            {raiz.hijos.length > 0 && (
              <>
                <div className="mx-auto h-6 w-px bg-linea" />
                <div className="grid gap-4 border-t border-linea pt-6 sm:grid-cols-2 xl:grid-cols-4">
                  {raiz.hijos.map((g) => (
                    <div key={g.id} className="rounded-xl border border-linea bg-fondo/60 p-3">
                      <div className="rounded-lg bg-white px-3 py-2.5 ring-1 ring-azul/25">
                        {esAdmin ? <Link to={`/puestos/${g.id}`} className="font-display font-semibold text-noche hover:text-azul">{g.nombre}</Link> : <p className="font-display font-semibold text-noche">{g.nombre}</p>}
                        <p className="text-xs text-gris">{g.departamento}</p>
                        <div className="mt-1.5"><Personas lista={g.personas} /></div>
                      </div>
                      {g.hijos.length > 0 && <ul className="mt-3 space-y-2">{g.hijos.map((h) => <Nodo key={h.id} nodo={h} nivel={1} admin={esAdmin} />)}</ul>}
                    </div>
                  ))}
                </div>
              </>
            )}
          </section>
        ))}
      </div>
    </div>
  );
}
