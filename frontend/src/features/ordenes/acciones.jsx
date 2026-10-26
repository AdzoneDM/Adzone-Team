// Ventanas de las acciones de una orden: aprobar, entregar y cancelar.
import { useEffect, useState } from "react";
import { CircleCheckBig, PackageCheck, X } from "lucide-react";
import { aprobarOrden, cancelarOrden, entregarOrden } from "@/lib/api";
import { hoyISO, sumarDias } from "@/lib/formato";
import { useRecurso } from "@/lib/recursos";
import { SelectorPersona, SelectorPersonas } from "@/components/Selectores";
import { Alerta, Boton, Campo, Modal } from "@/components/ui";

export function AprobarModal({ orden, abierto, onCerrar, onHecho }) {
  const [catalogo] = useRecurso("catalogo");
  const [f, setF] = useState({});
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const tipo = catalogo?.find((t) => t.tipo === orden?.tipo);

  useEffect(() => {
    if (!abierto || !orden) return;
    setError("");
    const pedida = orden.fecha_requerida && orden.fecha_requerida >= hoyISO() ? orden.fecha_requerida : sumarDias(hoyISO(), 3);
    setF({ responsable: "", equipo: [], fecha_compromiso: pedida, pasos: (tipo?.pasos || []).join("\n"), crear_tarea: true });
  }, [abierto, orden, tipo]);

  const enviar = async (e) => {
    e.preventDefault();
    if (!f.responsable) return setError("Elige quién tendrá la orden a cargo.");
    if (!f.fecha_compromiso) return setError("Pon la fecha que le comprometes al cliente.");
    setEnviando(true); setError("");
    try {
      const o = await aprobarOrden(orden.id, {
        responsable: Number(f.responsable), equipo: f.equipo.map(Number), fecha_compromiso: f.fecha_compromiso,
        crear_tarea: f.crear_tarea, pasos: f.pasos.split("\n").map((p) => p.trim()).filter(Boolean),
      });
      onHecho(o, "Orden aprobada. El responsable ya tiene su tarea con los pasos.");
    } catch (err) { setError(err.message); }
    setEnviando(false);
  };

  if (!orden) return null;
  const delDepto = (g) => g.departamento_id === orden.departamento;
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={`Aprobar ${orden.numero}`} descripcion={orden.titulo} ancho="md:max-w-2xl"
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton type="submit" form="form-aprobar" icono={CircleCheckBig} cargando={enviando}>Aprobar y asignar</Boton></>}>
      <form id="form-aprobar" onSubmit={enviar} className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        <div className="grid gap-4 sm:grid-cols-2">
          <SelectorPersona etiqueta="Responsable" valor={f.responsable} onCambio={(v) => setF({ ...f, responsable: v, equipo: f.equipo.filter((x) => String(x) !== v) })}
            filtro={delDepto} ayuda={`Personas de ${orden.departamento_nombre}.`} />
          <Campo etiqueta="Fecha comprometida" ayuda={orden.fecha_requerida ? `El cliente la pidió para el ${orden.fecha_requerida.split("-").reverse().join("/")}.` : ""}>
            {(id) => <input id={id} type="date" min={hoyISO()} className="campo" value={f.fecha_compromiso || ""} onChange={(e) => setF({ ...f, fecha_compromiso: e.target.value })} />}
          </Campo>
        </div>
        <SelectorPersonas leyenda="Equipo (opcional)" ayuda="Trabajan con el responsable y les cuenta cuando se valida."
          valor={f.equipo || []} onCambio={(v) => setF({ ...f, equipo: v })} excluir={[f.responsable]} filtro={delDepto} />
        <label className="flex items-center gap-2.5 text-[15px]">
          <input type="checkbox" checked={!!f.crear_tarea} onChange={(e) => setF({ ...f, crear_tarea: e.target.checked })} className="size-4 accent-azul" />
          Crear la tarea de producción con estos pasos
        </label>
        {f.crear_tarea && (
          <Campo etiqueta="Pasos" ayuda="Uno por línea. Puedes quitarlos o agregar los que hagan falta.">
            {(id) => <textarea id={id} rows={6} className="campo" value={f.pasos || ""} onChange={(e) => setF({ ...f, pasos: e.target.value })} />}
          </Campo>
        )}
      </form>
    </Modal>
  );
}

export function EntregarOrdenModal({ orden, abierto, onCerrar, onHecho }) {
  const [recibe, setRecibe] = useState("");
  const [nota, setNota] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  useEffect(() => { if (abierto) { setRecibe(""); setNota(""); setError(""); } }, [abierto]);
  const enviar = async (e) => {
    e.preventDefault();
    if (recibe.trim().length < 2) return setError("Anota el nombre de quien recibe.");
    setEnviando(true);
    try { onHecho(await entregarOrden(orden.id, recibe.trim(), nota.trim()), "Entregada. Finanzas recibió el aviso para facturar."); } catch (err) { setError(err.message); }
    setEnviando(false);
  };
  if (!orden) return null;
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={`Entregar ${orden.numero}`} descripcion={`${orden.titulo} · ${orden.cliente_nombre}`} ancho="max-w-md"
      pie={<><Boton variante="secundario" onClick={onCerrar}>Volver</Boton><Boton type="submit" form="form-entregar-ot" variante="acento" icono={PackageCheck} cargando={enviando}>Confirmar entrega</Boton></>}>
      <form id="form-entregar-ot" onSubmit={enviar} className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        <Campo etiqueta="Quién recibe">{(id) => <input id={id} className="campo" value={recibe} onChange={(e) => setRecibe(e.target.value)} placeholder="Nombre y empresa" autoFocus />}</Campo>
        <Campo etiqueta="Nota (opcional)">{(id) => <textarea id={id} rows={2} className="campo" value={nota} onChange={(e) => setNota(e.target.value)} placeholder="Ej.: instalada en la entrada principal" />}</Campo>
      </form>
    </Modal>
  );
}

export function CancelarOrdenModal({ orden, abierto, onCerrar, onHecho }) {
  const [motivo, setMotivo] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { if (abierto) { setMotivo(""); setError(""); } }, [abierto]);
  if (!orden) return null;
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={`Cancelar ${orden.numero}`} ancho="max-w-md"
      descripcion="Sus tareas abiertas también se cancelan. Queda en el historial."
      pie={<><Boton variante="secundario" onClick={onCerrar}>Volver</Boton>
        <Boton variante="peligro" icono={X} cargando={enviando} disabled={motivo.trim().length < 3} onClick={async () => {
          setEnviando(true);
          try { onHecho(await cancelarOrden(orden.id, motivo.trim()), "Orden cancelada."); } catch (e) { setError(e.message); }
          setEnviando(false);
        }}>Cancelar orden</Boton></>}>
      {error && <Alerta className="mb-3">{error}</Alerta>}
      <Campo etiqueta="Motivo">{(id) => <textarea id={id} rows={3} className="campo" value={motivo} onChange={(e) => setMotivo(e.target.value)} autoFocus />}</Campo>
    </Modal>
  );
}
