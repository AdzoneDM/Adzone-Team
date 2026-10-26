// Pedir o editar una orden de trabajo. Primero se elige el área; el formulario cambia según el área.
import { useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { guardarOrden, listarProyectos } from "@/lib/api";
import { PRIORIDADES_OT, hoyISO, sumarDias } from "@/lib/formato";
import { useRecurso } from "@/lib/recursos";
import { useSesion } from "@/lib/sesion";
import { SelectorCliente } from "@/components/Selectores";
import { Alerta, Boton, Campo, Cargando, Modal, cx } from "@/components/ui";
import { ICONOS } from "./piezas";

function CampoDinamico({ campo, valor, onCambio, error }) {
  const props = { className: "campo", value: valor ?? "", onChange: (e) => onCambio(e.target.value) };
  const ancho = campo.ancho === "completo" || ["largo", "multiple"].includes(campo.tipo) ? "sm:col-span-2" : "";
  const etiqueta = campo.etiqueta + (campo.requerido ? "" : " (opcional)");
  if (campo.tipo === "multiple") {
    const lista = Array.isArray(valor) ? valor : [];
    return (
      <fieldset className={ancho}>
        <legend className="etiqueta">{etiqueta}</legend>
        <div className="flex flex-wrap gap-2">
          {campo.opciones.map((o) => {
            const on = lista.includes(o);
            return (
              <button key={o} type="button" aria-pressed={on} onClick={() => onCambio(on ? lista.filter((x) => x !== o) : [...lista, o])}
                className={cx("min-h-10 rounded-full border px-3.5 text-sm font-medium", on ? "border-azul bg-azul text-white" : "border-linea bg-white hover:border-azul")}>{o}</button>
            );
          })}
        </div>
        {error && <p className="mt-1 text-[13px] text-rojo">{error}</p>}
      </fieldset>
    );
  }
  if (campo.tipo === "sino") {
    return (
      <label className={cx("flex min-h-11 items-center gap-2.5 self-end rounded-lg border border-linea px-3 text-[15px]", ancho)}>
        <input type="checkbox" checked={!!valor} onChange={(e) => onCambio(e.target.checked)} className="size-4 accent-azul" /> {campo.etiqueta}
      </label>
    );
  }
  return (
    <Campo etiqueta={etiqueta} ayuda={campo.ayuda} error={error} className={ancho}>
      {(id) => campo.tipo === "opcion" ? (
        <select id={id} {...props}><option value="">Elige…</option>{campo.opciones.map((o) => <option key={o}>{o}</option>)}</select>
      ) : campo.tipo === "largo" ? <textarea id={id} rows={3} {...props} />
        : campo.tipo === "fecha" ? <input id={id} type="date" {...props} />
          : campo.tipo === "fechahora" ? <input id={id} type="datetime-local" {...props} />
            : ["numero", "dinero"].includes(campo.tipo) ? <input id={id} type="number" inputMode="decimal" min={0} step="any" {...props} />
              : <input id={id} {...props} maxLength={200} />}
    </Campo>
  );
}

export function ElegirArea({ catalogo, onElegir }) {
  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {catalogo.map((t) => {
        const Icono = ICONOS[t.icono];
        return (
          <li key={t.tipo}>
            <button type="button" onClick={() => onElegir(t)} className="flex h-full w-full items-start gap-3 rounded-xl border border-linea bg-white p-4 text-left hover:border-azul hover:bg-azul/[0.03]">
              <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-azul/10 text-azul"><Icono className="size-5" /></span>
              <span><span className="block font-semibold">{t.nombre}</span><span className="mt-0.5 block text-sm text-gris">{t.descripcion}</span></span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export default function FormOrden({ abierto, onCerrar, inicial, onGuardada }) {
  const { usuario } = useSesion();
  const [catalogo] = useRecurso("catalogo");
  const [tipo, setTipo] = useState(null);
  const [f, setF] = useState({});
  const [proyectos, setProyectos] = useState([]);
  const [errores, setErrores] = useState({});
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const editando = !!inicial?.id;
  const veMontos = usuario?.es_finanzas || usuario?.gestiona;

  useEffect(() => {
    if (!abierto) return;
    setError(""); setErrores({});
    if (inicial?.id) {
      setF({ ...inicial, cliente: String(inicial.cliente), proyecto: inicial.proyecto ? String(inicial.proyecto) : "", detalles: { ...inicial.detalles } });
    } else {
      setF({ titulo: "", descripcion: "", cliente: inicial?.cliente ? String(inicial.cliente) : "", proyecto: inicial?.proyecto ? String(inicial.proyecto) : "",
        prioridad: "NORMAL", fecha_requerida: sumarDias(hoyISO(), 5), monto: "", detalles: {} });
    }
    setTipo(null);
  }, [abierto, inicial]);

  useEffect(() => {
    if (!catalogo || !abierto) return;
    const t = inicial?.tipo ? catalogo.find((c) => c.tipo === inicial.tipo) : null;
    if (t) setTipo(t);
  }, [catalogo, abierto, inicial]);

  useEffect(() => {
    if (!f.cliente) { setProyectos([]); return; }
    listarProyectos({ cliente: f.cliente, activos: 1 }).then(setProyectos).catch(() => setProyectos([]));
  }, [f.cliente]);

  const det = (clave) => (v) => setF((x) => ({ ...x, detalles: { ...x.detalles, [clave]: v } }));

  const guardar = async (e) => {
    e.preventDefault();
    setError(""); setErrores({});
    if (!f.titulo?.trim()) return setError("Escribe un título corto: qué se va a hacer.");
    if (!f.cliente) return setError("Elige el cliente (para trabajos internos, «ADZONE Digital Marketing»).");
    const faltan = tipo.campos.filter((c) => c.requerido && [undefined, "", null].includes(f.detalles[c.clave]) || (c.requerido && c.tipo === "multiple" && !(f.detalles[c.clave] || []).length));
    if (faltan.length) {
      setErrores(Object.fromEntries(faltan.map((c) => [c.clave, `Falta «${c.etiqueta}».`])));
      return setError(`Completa: ${faltan.map((c) => c.etiqueta).join(", ")}.`);
    }
    setGuardando(true);
    try {
      const datos = {
        id: f.id, tipo: tipo.tipo, titulo: f.titulo.trim(), descripcion: f.descripcion || "", cliente: Number(f.cliente),
        proyecto: f.proyecto ? Number(f.proyecto) : null, prioridad: f.prioridad, fecha_requerida: f.fecha_requerida || null,
        detalles: f.detalles,
      };
      if (veMontos) datos.monto = f.monto === "" || f.monto == null ? null : f.monto;
      const o = await guardarOrden(datos);
      onGuardada(o, editando);
    } catch (err) {
      setError(err.message);
      if (err.data?.detalles) setErrores(err.data.detalles);
    }
    setGuardando(false);
  };

  const titulo = editando ? `Editar ${inicial.numero}` : tipo ? `Nueva orden · ${tipo.nombre}` : "Nueva orden de trabajo";
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} ancho="md:max-w-3xl" titulo={titulo}
      descripcion={!tipo ? "¿Qué área hará el trabajo?" : editando ? null : `La recibe ${tipo.departamento} para aprobarla.`}
      pie={tipo && <>
        {!editando && <Boton variante="fantasma" icono={ArrowLeft} onClick={() => setTipo(null)} className="mr-auto">Cambiar área</Boton>}
        <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
        <Boton type="submit" form="form-orden" cargando={guardando}>{editando ? "Guardar cambios" : "Pedir orden"}</Boton>
      </>}>
      {!catalogo ? <Cargando /> : !tipo ? <ElegirArea catalogo={catalogo} onElegir={setTipo} /> : (
        <form id="form-orden" onSubmit={guardar} className="space-y-5">
          {error && <Alerta>{error}</Alerta>}
          <div className="grid gap-4 sm:grid-cols-2">
            <Campo etiqueta="Título" className="sm:col-span-2" ayuda="Ej.: Lona 3x2 del Torneo Superior">
              {(id) => <input id={id} className="campo" value={f.titulo || ""} onChange={(e) => setF({ ...f, titulo: e.target.value })} maxLength={200} autoFocus={!editando} />}
            </Campo>
            <SelectorCliente valor={f.cliente} onCambio={(v) => setF({ ...f, cliente: v, proyecto: "" })} />
            <Campo etiqueta="Proyecto (opcional)">
              {(id) => (
                <select id={id} className="campo" value={f.proyecto || ""} onChange={(e) => setF({ ...f, proyecto: e.target.value })} disabled={!proyectos.length}>
                  <option value="">{f.cliente && !proyectos.length ? "Este cliente no tiene proyectos activos" : "Ninguno"}</option>
                  {proyectos.map((p) => <option key={p.id} value={p.id}>{p.codigo} · {p.nombre}</option>)}
                </select>
              )}
            </Campo>
            <Campo etiqueta="Para cuándo la pide el cliente">
              {(id) => <input id={id} type="date" className="campo" value={f.fecha_requerida || ""} onChange={(e) => setF({ ...f, fecha_requerida: e.target.value })} />}
            </Campo>
            <Campo etiqueta="Prioridad">
              {(id) => (
                <select id={id} className="campo" value={f.prioridad} onChange={(e) => setF({ ...f, prioridad: e.target.value })}>
                  {Object.entries(PRIORIDADES_OT).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              )}
            </Campo>
          </div>

          <section className="rounded-xl border border-linea bg-fondo/50 p-4">
            <h3 className="mb-3 text-base font-semibold">Datos de {tipo.nombre.toLowerCase()}</h3>
            <div className="grid gap-4 sm:grid-cols-2">
              {tipo.campos.map((c) => <CampoDinamico key={c.clave} campo={c} valor={f.detalles?.[c.clave]} onCambio={det(c.clave)} error={errores[c.clave]} />)}
            </div>
          </section>

          <Campo etiqueta="Indicaciones (opcional)" ayuda="Lo que el equipo debe saber: referencias, colores, contacto en sitio…">
            {(id) => <textarea id={id} className="campo" rows={3} value={f.descripcion || ""} onChange={(e) => setF({ ...f, descripcion: e.target.value })} />}
          </Campo>
          {veMontos && (
            <Campo etiqueta="Monto acordado con el cliente (opcional)" ayuda="Sin ITBIS. Solo lo ven Finanzas y quien gestiona.">
              {(id) => <input id={id} type="number" min={0} step="any" inputMode="decimal" className="campo sm:max-w-xs" value={f.monto ?? ""} onChange={(e) => setF({ ...f, monto: e.target.value })} />}
            </Campo>
          )}
        </form>
      )}
    </Modal>
  );
}
