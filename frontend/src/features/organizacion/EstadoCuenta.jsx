import { useEffect, useState } from "react";
import { AlertTriangle, Ban, PauseCircle, RotateCcw, Trash2, UserX } from "lucide-react";
import { usuarioEstado, usuarioPendientes } from "@/lib/api";
import { fechaCorta } from "@/lib/formato";
import { Alerta, Boton, Campo, Cargando, Insignia, Modal, cx, useAviso } from "@/components/ui";

const ESTADOS = {
  ACTIVA: { nombre: "Activa", tono: "verde" },
  SUSPENDIDA: { nombre: "Suspendida", tono: "amarillo" },
  INACTIVA: { nombre: "Baja", tono: "neutro" },
  ELIMINADA: { nombre: "Eliminada", tono: "rojo" },
};

/** Insignia del estado de una cuenta (no sale para las activas). */
export function InsigniaEstado({ u }) {
  const e = ESTADOS[u.estado_cuenta];
  if (!e || u.estado_cuenta === "ACTIVA") return null;
  return <Insignia tono={e.tono}>{e.nombre}{u.estado_cuenta === "SUSPENDIDA" && u.suspendida_hasta ? ` hasta ${fechaCorta(u.suspendida_hasta)}` : ""}</Insignia>;
}

const ACCIONES = {
  SUSPENDIDA: { titulo: "Suspender temporalmente", icono: PauseCircle, texto: "No puede entrar mientras dure. Conserva todo y se reactiva con un clic (o sola en la fecha que elijas).", boton: "Suspender" },
  INACTIVA: { titulo: "Dar de baja (desactivar)", icono: UserX, texto: "Ya no trabaja aquí: no puede entrar y sale del ranking y del organigrama. Su historial se conserva.", boton: "Dar de baja" },
  ELIMINADA: { titulo: "Eliminar", icono: Trash2, texto: "Se oculta de las listas normales. No se borra nada: su historial queda y se puede restaurar. El borrado definitivo es solo de la Dirección.", boton: "Eliminar" },
  ACTIVA: { titulo: "Reactivar", icono: RotateCcw, texto: "Vuelve a poder entrar con su misma contraseña y permisos.", boton: "Reactivar" },
};

/** Cambiar el estado de una cuenta con confirmación: motivo, fecha de fin (suspensión) y qué pasa con sus pendientes. */
export default function EstadoCuenta({ persona, gente, puedeEliminar, onCerrar, onHecho }) {
  const avisar = useAviso();
  const estado = persona?.estado_cuenta || "ACTIVA";
  const opciones = estado === "ACTIVA" ? ["SUSPENDIDA", "INACTIVA", ...(puedeEliminar ? ["ELIMINADA"] : [])] : ["ACTIVA", ...(estado !== "INACTIVA" ? ["INACTIVA"] : []), ...(estado !== "ELIMINADA" && puedeEliminar ? ["ELIMINADA"] : [])];
  const [accion, setAccion] = useState(opciones[0]);
  const [motivo, setMotivo] = useState("");
  const [hasta, setHasta] = useState("");
  const [pend, setPend] = useState(null);
  const [destino, setDestino] = useState("");
  const [dejar, setDejar] = useState(false);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (!persona) return;
    setAccion(opciones[0]); setMotivo(""); setHasta(""); setDestino(""); setDejar(false); setError(""); setPend(null);
    if (persona.estado_cuenta === "ACTIVA") usuarioPendientes(persona.id).then(setPend).catch(() => setPend({ tareas: 0, lista: [] }));
  }, [persona?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!persona) return null;

  const apartando = accion !== "ACTIVA";
  const hayPend = pend && (pend.tareas || pend.como_companero || pend.por_revisar || pend.recurrentes);
  const candidatos = (gente || []).filter((g) => g.id !== persona.id && g.is_active);
  const A = ACCIONES[accion];

  const confirmar = async () => {
    setError("");
    if (apartando && motivo.trim().length < 3) return setError("Escribe el motivo: queda en el historial de la cuenta.");
    if (apartando && estado === "ACTIVA" && hayPend && !destino && !dejar) return setError("Esta persona tiene pendientes: pásalos a alguien o marca que se queden como están.");
    setEnviando(true);
    try {
      const r = await usuarioEstado(persona.id, { estado: accion, motivo: motivo.trim(), hasta: accion === "SUSPENDIDA" && hasta ? hasta : undefined, reasignar_a: destino ? Number(destino) : undefined, dejar_pendientes: dejar || undefined });
      avisar(`${persona.nombre}: ${ESTADOS[accion].nombre.toLowerCase()}${r.reasignado?.tareas ? ` · ${r.reasignado.tareas} tarea(s) pasaron a otra persona` : ""}.`);
      onHecho(r);
    } catch (e) { setError(e.message); }
    setEnviando(false);
  };

  return (
    <Modal abierto onCerrar={onCerrar} titulo={`Estado de la cuenta · ${persona.nombre}`} ancho="max-w-xl"
      descripcion={`Hoy: ${ESTADOS[estado].nombre}${persona.estado_motivo ? ` · ${persona.estado_motivo}` : ""}${persona.estado_por_nombre ? ` (por ${persona.estado_por_nombre}${persona.estado_desde ? `, ${fechaCorta(persona.estado_desde)}` : ""})` : ""}`}
      pie={<>
        <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
        <Boton variante={apartando ? "peligro" : "primario"} cargando={enviando} onClick={confirmar}>Confirmar: {A.boton.toLowerCase()} a {persona.first_name || persona.nombre}</Boton>
      </>}>
      <div className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        <fieldset className="grid gap-2">
          <legend className="sr-only">¿Qué quieres hacer?</legend>
          {opciones.map((k) => {
            const I = ACCIONES[k].icono;
            return (
              <label key={k} className={cx("flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors", accion === k ? "border-azul bg-azul/5 ring-2 ring-azul/15" : "border-linea hover:border-azul/40")}>
                <input type="radio" name="accion-cuenta" className="mt-1 accent-azul" checked={accion === k} onChange={() => { setAccion(k); setError(""); }} />
                <I className="mt-0.5 size-5 shrink-0 text-azul" aria-hidden />
                <span><b className="block text-[15px] text-tinta">{ACCIONES[k].titulo}</b><span className="text-sm text-gris">{ACCIONES[k].texto}</span></span>
              </label>
            );
          })}
        </fieldset>
        {apartando && (
          <Campo etiqueta="Motivo" ayuda="Obligatorio. Queda en el historial con tu nombre y la fecha.">
            {(id) => <textarea id={id} className="campo" rows={2} maxLength={300} value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Ej.: Licencia médica / Terminó su contrato" />}
          </Campo>
        )}
        {accion === "SUSPENDIDA" && (
          <Campo etiqueta="Termina el (opcional)" ayuda="Si pones una fecha, la cuenta se reactiva sola ese día. Vacío: sigue suspendida hasta que la reactives.">
            {(id) => <input id={id} type="date" className="campo" min={new Date(Date.now() + 86400000).toISOString().slice(0, 10)} value={hasta} onChange={(e) => setHasta(e.target.value)} />}
          </Campo>
        )}
        {apartando && estado === "ACTIVA" && (
          pend === null ? <Cargando /> : hayPend ? (
            <div className="space-y-3 rounded-xl border border-amarillo/60 bg-amarillo-50 p-3 text-sm">
              <p className="flex items-center gap-2 font-semibold text-[#7a5000]"><AlertTriangle className="size-4" aria-hidden />Tiene pendientes</p>
              <ul className="list-inside list-disc text-[#7a5000]">
                {pend.tareas > 0 && <li>{pend.tareas} tarea(s) abierta(s) a su nombre</li>}
                {pend.como_companero > 0 && <li>{pend.como_companero} tarea(s) donde colabora</li>}
                {pend.por_revisar > 0 && <li>{pend.por_revisar} entrega(s) que debía validar</li>}
                {pend.recurrentes > 0 && <li>{pend.recurrentes} tarea(s) recurrente(s)</li>}
                {pend.activos > 0 && <li>{pend.activos} equipo(s) o activo(s) a su cargo (se reasignan en Activos)</li>}
              </ul>
              {pend.lista?.length > 0 && <ul className="max-h-28 space-y-0.5 overflow-y-auto rounded-lg bg-white/70 p-2 text-tinta">{pend.lista.map((t) => <li key={t.id} className="truncate">• {t.titulo} <span className="text-gris">· vence {fechaCorta(t.fecha_limite)}</span></li>)}</ul>}
              <Campo etiqueta="Pasar sus pendientes a" ayuda="Las tareas conservan su historial y quién las asignó; la persona recibe un aviso.">
                {(id) => (
                  <select id={id} className="campo bg-white" value={destino} disabled={dejar} onChange={(e) => setDestino(e.target.value)}>
                    <option value="">Elige a una persona…</option>
                    {candidatos.map((g) => <option key={g.id} value={g.id}>{g.nombre}{g.puesto ? ` (${g.puesto})` : ""}</option>)}
                  </select>
                )}
              </Campo>
              <label className="flex items-start gap-2"><input type="checkbox" className="mt-1 accent-azul" checked={dejar} onChange={(e) => { setDejar(e.target.checked); if (e.target.checked) setDestino(""); }} />
                <span>Dejar los pendientes como están (siguen a su nombre y se reasignan después a mano).</span></label>
            </div>
          ) : <p className="rounded-lg bg-verde-50 p-3 text-sm text-verde">No tiene pendientes: se puede apartar sin reasignar nada.</p>
        )}
        {apartando && <p className="flex items-start gap-2 text-xs text-gris"><Ban className="mt-0.5 size-3.5 shrink-0" aria-hidden />Se cierran sus sesiones abiertas y no puede volver a entrar. Sus tareas, chats, comentarios y evidencias se conservan.</p>}
      </div>
    </Modal>
  );
}
