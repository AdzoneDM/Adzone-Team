// «Nueva tarea para mí»: la persona se asigna una tarea a sí misma y elige quién la valida (Dirección).
import { useEffect, useState } from "react";
import { guardarTarea, misRevisores, subirReferencias } from "@/lib/api";
import { hoyISO, sumarDias } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import { Alerta, Boton, Campo, Modal } from "@/components/ui";
import { SelectorArchivos } from "@/features/tareas/componentes";

const VACIA = () => ({ titulo: "", descripcion: "", prioridad: "MEDIA", fecha_limite: sumarDias(hoyISO(), 3), horas_estimadas: "", revisor: "" });

export default function FormTareaPropia({ abierto, onCerrar, onGuardada }) {
  const { usuario } = useSesion();
  const [f, setF] = useState(VACIA());
  const [revisores, setRevisores] = useState(null);
  const [referencias, setReferencias] = useState([]);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    if (!abierto) return;
    setF(VACIA());
    setReferencias([]);
    setError("");
    misRevisores().then((l) => { setRevisores(l); if (l.length === 1) setF((x) => ({ ...x, revisor: String(l[0].id) })); }).catch(() => setRevisores([]));
  }, [abierto]);

  const cambiar = (campo) => (e) => setF((x) => ({ ...x, [campo]: e.target.value }));

  const guardar = async (e) => {
    e.preventDefault();
    setError("");
    if (!f.titulo.trim()) return setError("Escribe qué vas a hacer.");
    if (!f.fecha_limite) return setError("Pon la fecha límite.");
    if (!f.revisor) return setError("Elige quién va a validar tu tarea.");
    setGuardando(true);
    try {
      const t = await guardarTarea({
        titulo: f.titulo.trim(), descripcion: f.descripcion.trim(), colaborador: usuario.id, revisor: Number(f.revisor),
        prioridad: f.prioridad, fecha_limite: f.fecha_limite, horas_estimadas: f.horas_estimadas === "" ? null : f.horas_estimadas,
        pasos_texto: [],
      });
      let aviso = "";
      if (referencias.length) {
        try { await subirReferencias(t.id, referencias); } catch (err) { aviso = ` Pero los archivos no se pudieron subir: ${err.message}`; }
      }
      const quien = revisores?.find((r) => String(r.id) === f.revisor)?.nombre;
      onGuardada(`Tarea creada. ${quien ? `${quien} la validará cuando la entregues.` : ""}${aviso}`.trim());
    } catch (err) { setError(err.message); }
    setGuardando(false);
  };

  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo="Nueva tarea para mí" descripcion="La haces tú; la valida la persona que elijas abajo." ancho="md:max-w-xl"
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton type="submit" form="form-tarea-propia" cargando={guardando}>Crear tarea</Boton></>}>
      <form id="form-tarea-propia" onSubmit={guardar} className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        <Campo etiqueta="Qué vas a hacer">{(id) => <input id={id} className="campo" value={f.titulo} onChange={cambiar("titulo")} maxLength={255} autoFocus />}</Campo>
        <Campo etiqueta="Detalles (opcional)">{(id) => <textarea id={id} className="campo" rows={3} value={f.descripcion} onChange={cambiar("descripcion")} />}</Campo>
        <div className="grid gap-4 sm:grid-cols-3">
          <Campo etiqueta="Fecha límite">{(id) => <input id={id} type="date" className="campo" value={f.fecha_limite} onChange={cambiar("fecha_limite")} />}</Campo>
          <Campo etiqueta="Prioridad">
            {(id) => <select id={id} className="campo" value={f.prioridad} onChange={cambiar("prioridad")}><option value="ALTA">Alta</option><option value="MEDIA">Media</option><option value="BAJA">Baja</option></select>}
          </Campo>
          <Campo etiqueta="Horas estimadas">
            {(id) => <input id={id} type="number" min={0} step="0.5" inputMode="decimal" className="campo" value={f.horas_estimadas} onChange={cambiar("horas_estimadas")} />}
          </Campo>
        </div>
        <Campo etiqueta="Quién la valida" ayuda="Le llegará el aviso cuando la entregues.">
          {(id) => (
            <select id={id} className="campo" value={f.revisor} onChange={cambiar("revisor")} disabled={!revisores}>
              <option value="">{revisores ? "Elige a quien la revisa…" : "Cargando…"}</option>
              {(revisores || []).map((r) => <option key={r.id} value={r.id}>{r.nombre}{r.puesto ? ` (${r.puesto})` : ""}</option>)}
            </select>
          )}
        </Campo>
        <SelectorArchivos archivos={referencias} onCambio={setReferencias} etiqueta="Adjuntar boceto, imagen o video (opcional)" disabled={guardando} />
      </form>
    </Modal>
  );
}
