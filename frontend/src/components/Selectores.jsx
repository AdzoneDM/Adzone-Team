// Selectores comunes: cliente (con alta rápida) y personas (chips).
import { useState } from "react";
import { Plus } from "lucide-react";
import { guardarCliente } from "@/lib/api";
import { useRecurso } from "@/lib/recursos";
import { Boton, Campo, cx, useAviso } from "@/components/ui";

export function SelectorCliente({ valor, onCambio, etiqueta = "Cliente", requerido = true }) {
  const [clientes, recargar] = useRecurso("clientes");
  const [nuevo, setNuevo] = useState(null);
  const [guardando, setGuardando] = useState(false);
  const avisar = useAviso();
  const crear = async () => {
    if (!nuevo?.trim()) return;
    setGuardando(true);
    try {
      const c = await guardarCliente({ nombre: nuevo.trim() });
      recargar();
      onCambio(String(c.id));
      setNuevo(null);
      avisar(`Cliente «${c.nombre}» registrado. Completa sus datos en Clientes.`);
    } catch (e) { avisar(e.message, "rojo"); }
    setGuardando(false);
  };
  if (nuevo !== null) {
    return (
      <Campo etiqueta="Nombre del cliente nuevo">
        {(id) => (
          <div className="flex gap-2">
            <input id={id} className="campo" value={nuevo} onChange={(e) => setNuevo(e.target.value)} autoFocus maxLength={200}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); crear(); } }} />
            <Boton onClick={crear} cargando={guardando}>Agregar</Boton>
            <Boton variante="secundario" onClick={() => setNuevo(null)}>Volver</Boton>
          </div>
        )}
      </Campo>
    );
  }
  return (
    <Campo etiqueta={etiqueta}>
      {(id) => (
        <div className="flex gap-2">
          <select id={id} className="campo" value={valor || ""} onChange={(e) => onCambio(e.target.value)} required={requerido}>
            <option value="">{clientes ? "Elige el cliente…" : "Cargando…"}</option>
            {(clientes || []).map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select>
          <Boton variante="secundario" icono={Plus} onClick={() => setNuevo("")} aria-label="Cliente nuevo" className="shrink-0 px-3" title="Cliente nuevo" />
        </div>
      )}
    </Campo>
  );
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
