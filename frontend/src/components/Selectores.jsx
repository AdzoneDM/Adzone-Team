// Selectores comunes: cliente y proyecto (con autocompletado) y personas (chips).
import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { guardarCliente, listarProyectos } from "@/lib/api";
import Autocompletar from "@/components/Autocompletar";
import { useRecurso } from "@/lib/recursos";
import { Boton, Campo, cx, useAviso } from "@/components/ui";

/** Cliente con autocompletado (clientes reales de la plataforma). Si no existe, se registra ahí mismo (el servidor evita duplicados). */
export function SelectorCliente({ valor, onCambio, etiqueta = "Cliente", requerido = true, ayuda, permitirNuevo = true }) {
  const [clientes, recargar] = useRecurso("clientes");
  const avisar = useAviso();
  const opciones = (clientes || []).map((c) => ({ id: c.id, texto: c.nombre, sub: c.activo === false ? "inactivo" : c.tipo_nombre || "" }));
  const crear = async (nombre) => {
    try {
      const c = await guardarCliente({ nombre });
      recargar();
      avisar(`Cliente «${c.nombre}» registrado. Completa sus datos en Clientes.`);
      return { id: c.id, texto: c.nombre };
    } catch (e) { avisar(e.message, "rojo"); return null; }
  };
  return <Autocompletar etiqueta={etiqueta} ayuda={ayuda} opciones={opciones} valor={valor} onCambio={(id) => onCambio(id)} cargando={!clientes}
    onCrear={permitirNuevo ? crear : undefined} textoCrear="Registrar cliente" placeholder="Busca el cliente por su nombre…" requerido={requerido && !valor} />;
}

/** Proyecto con autocompletado; con `cliente`, solo los proyectos de ese cliente. */
export function SelectorProyecto({ cliente, valor, onCambio, etiqueta = "Proyecto (opcional)", ayuda }) {
  const [proyectos, setProyectos] = useState(null);
  useEffect(() => {
    let vivo = true;
    setProyectos(null);
    listarProyectos({ activos: 1, ...(cliente ? { cliente } : {}) }).then((l) => vivo && setProyectos(Array.isArray(l) ? l : l?.results || [])).catch(() => vivo && setProyectos([]));
    return () => { vivo = false; };
  }, [cliente]);
  const opciones = (proyectos || []).filter((p) => !cliente || String(p.cliente) === String(cliente))
    .map((p) => ({ id: p.id, texto: `${p.codigo} · ${p.nombre}`, sub: cliente ? p.estado_nombre || "" : p.cliente_nombre, cliente: p.cliente }));
  return <Autocompletar etiqueta={etiqueta} ayuda={ayuda} opciones={opciones} valor={valor} onCambio={onCambio} cargando={!proyectos}
    placeholder={cliente ? "Busca entre los proyectos de este cliente…" : "Busca el proyecto…"} vacio={cliente ? "Este cliente no tiene proyectos activos" : "Sin proyectos"} />;
}

/** Elegir varias personas con botones. `excluir`: ids que no se muestran. */
export function SelectorPersonas({ valor = [], onCambio, excluir = [], filtro, leyenda, ayuda }) {
  const [gente] = useRecurso("directorio");
  const lista = (gente || []).filter((g) => !excluir.map(String).includes(String(g.id)) && (!filtro || filtro(g)));
  const activos = valor.map(String);
  return (
    <fieldset>
      {leyenda && <legend className="etiqueta">{leyenda}</legend>}
      {ayuda && <p className="-mt-1 mb-2 text-sm text-gris">{ayuda}</p>}
      <div className="flex max-h-44 flex-wrap gap-2 overflow-y-auto">
        {lista.map((g) => {
          const on = activos.includes(String(g.id));
          return (
            <button key={g.id} type="button" aria-pressed={on} title={g.puesto || ""}
              onClick={() => onCambio(on ? valor.filter((v) => String(v) !== String(g.id)) : [...valor, g.id])}
              className={cx("min-h-10 rounded-full border px-3.5 text-sm font-medium", on ? "border-azul bg-azul text-white" : "border-linea bg-white hover:border-azul")}>
              {g.nombre}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

export function SelectorPersona({ valor, onCambio, etiqueta, filtro, vacio = "Elige una persona…", ayuda }) {
  const [gente] = useRecurso("directorio");
  return (
    <Campo etiqueta={etiqueta} ayuda={ayuda}>
      {(id) => (
        <select id={id} className="campo" value={valor || ""} onChange={(e) => onCambio(e.target.value)}>
          <option value="">{vacio}</option>
          {(gente || []).filter((g) => !filtro || filtro(g)).map((g) => <option key={g.id} value={g.id}>{g.nombre}{g.puesto ? ` · ${g.puesto}` : ""}</option>)}
        </select>
      )}
    </Campo>
  );
}
