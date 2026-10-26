import { useCallback, useEffect, useState } from "react";
import { CircleCheckBig, RotateCcw } from "lucide-react";
import { devolverTarea, listarTareas, validarTarea } from "@/lib/api";
import { fechaCorta, hace } from "@/lib/formato";
import { refrescarAvisos } from "@/app/Estructura";
import { EquipoTarea, Evidencias, Historial, Pasos } from "@/features/tareas/componentes";
import { Alerta, Avatar, Boton, Cabecera, Campo, Cargando, EntradaEstrellas, Insignia, Modal, PrioridadTarea, Vacio, cx, useAviso } from "@/components/ui";
import { useRecurso } from "@/lib/recursos";
import { Checklist } from "@/features/ordenes/piezas";

const aTiempo = (t) => t.fecha_completada <= t.fecha_limite;

function Revision({ tarea, onListo }) {
  const avisar = useAviso();
  const [calidad, setCalidad] = useState(0);
  const [comentario, setComentario] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(null);
  const [verHistorial, setVerHistorial] = useState(false);
  const [g3, setG3] = useState({});
  const [causa, setCausa] = useState("");
  const [catalogo] = useRecurso("catalogo");
  const oa = tarea.oa_info;

  useEffect(() => { setCalidad(0); setComentario(""); setError(""); setVerHistorial(false); setG3(tarea.oa_info?.g3_marcados || {}); setCausa(""); }, [tarea.id, tarea.oa_info]);

  const validar = async () => {
    if (!calidad) { setError("Califica la calidad (1 a 5 estrellas) para validarla."); return; }
    setEnviando("validar");
    try {
      await validarTarea(tarea.id, calidad, comentario.trim(), oa ? { g3 } : {});
      avisar(`Validada. Ya cuenta para el puntaje de ${[tarea.colaborador_nombre, ...(tarea.companeros_nombres || [])].join(" y ")}.`);
      onListo(tarea.id);
    } catch (e) { setError(e.message); setEnviando(null); }
  };
  const devolver = async () => {
    if (comentario.trim().length < 5) { setError("Para devolverla, escribe qué debe corregir."); return; }
    setEnviando("devolver");
    try {
      await devolverTarea(tarea.id, comentario.trim(), oa ? { g3, causa_retrabajo: causa || null } : {});
      avisar(`Devuelta a ${tarea.colaborador_nombre} con tu comentario.`);
      onListo(tarea.id);
    } catch (e) { setError(e.message); setEnviando(null); }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-start gap-3">
        <Avatar nombre={tarea.colaborador_nombre} />
        <div className="min-w-0 flex-1">
          <p className="font-medium">{tarea.colaborador_nombre}</p>
          <p className="text-sm text-gris">{tarea.colaborador_puesto}</p>
        </div>
        <Insignia tono={aTiempo(tarea) ? "verde" : "amarillo"}>{aTiempo(tarea) ? "A tiempo" : "Tarde"}</Insignia>
      </div>
      <div>
        <h2 className="text-xl font-semibold leading-snug">{tarea.titulo}</h2>
        <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-gris">
          <PrioridadTarea prioridad={tarea.prioridad} />
          Entregada {fechaCorta(tarea.fecha_completada)}, límite {fechaCorta(tarea.fecha_limite)}
          {tarea.rondas_revision > 0 && <Insignia tono="rojo">Entrega n.º {tarea.rondas_revision + 1}</Insignia>}
        </p>
        <EquipoTarea tarea={tarea} className="mt-1.5" />
        {tarea.descripcion && <p className="mt-3 whitespace-pre-line text-[15px] text-gris">{tarea.descripcion}</p>}
      </div>
      <Pasos tarea={tarea} />
      <Evidencias tarea={tarea} compacto />

      <div className="space-y-4 rounded-xl border border-linea bg-fondo/60 p-4">
        {error && <Alerta>{error}</Alerta>}
        {oa && (
          <div className="rounded-lg border border-linea bg-white p-3">
            <Checklist items={oa.g3} valor={g3} onCambio={setG3} titulo={`G3 · Control de calidad de ${oa.numero}`}
              ayuda="Validar es firmar el control de calidad interno: el trabajo no sale del área sin todas las casillas." />
            {oa.requiere_g4 && !oa.g4_aprobado && <Alerta tono="amarillo" className="mt-2">Falta la aprobación escrita del cliente (G4) en la Orden de Área.</Alerta>}
            <Campo etiqueta="Si la devuelves: causa del retrabajo (opcional)" className="mt-3">
              {(id) => <select id={id} className="campo" value={causa} onChange={(e) => setCausa(e.target.value)}>
                <option value="">Solo corrección, sin registrar retrabajo</option>{(catalogo?.causas_retrabajo || []).map((c) => <option key={c}>{c}</option>)}</select>}
            </Campo>
          </div>
        )}
        <EntradaEstrellas valor={calidad} onCambio={(v) => { setCalidad(v); setError(""); }} nombre={`calidad-${tarea.id}`} />
        <Campo etiqueta="Comentario" ayuda="Opcional al validar. Si la devuelves, di exactamente qué corregir.">
          {(id) => <textarea id={id} className="campo bg-white" rows={3} value={comentario} onChange={(e) => setComentario(e.target.value)} />}
        </Campo>
        <div className="grid grid-cols-2 gap-2 sm:flex sm:justify-end">
          <Boton variante="secundario" icono={RotateCcw} onClick={devolver} cargando={enviando === "devolver"} disabled={!!enviando}>Devolver</Boton>
          <Boton icono={CircleCheckBig} onClick={validar} cargando={enviando === "validar"} disabled={!!enviando}>Validar</Boton>
        </div>
      </div>

      <div>
        <button type="button" className="text-sm font-medium text-azul hover:underline" onClick={() => setVerHistorial((v) => !v)}>
          {verHistorial ? "Ocultar historial" : "Ver historial de la tarea"}
        </button>
        {verHistorial && <div className="mt-3"><Historial tareaId={tarea.id} /></div>}
      </div>
    </div>
  );
}

export default function Validar() {
  const [lista, setLista] = useState(null);
  const [error, setError] = useState("");
  const [elegida, setElegida] = useState(null);
  const [esPC, setEsPC] = useState(() => window.matchMedia("(min-width: 1024px)").matches);

  useEffect(() => {
    const m = window.matchMedia("(min-width: 1024px)");
    const f = () => setEsPC(m.matches);
    m.addEventListener("change", f);
    return () => m.removeEventListener("change", f);
  }, []);

  const cargar = useCallback(() => {
    listarTareas({ ambito: "por_validar" })
      .then((t) => {
        const orden = [...t].sort((a, b) => a.fecha_modificacion.localeCompare(b.fecha_modificacion));
        setLista(orden);
        setElegida((e) => (e && orden.some((x) => x.id === e) ? e : esPC ? orden[0]?.id ?? null : null));
      })
      .catch((e) => setError(e.message));
  }, [esPC]);
  useEffect(() => { cargar(); }, [cargar]);

  const listo = (id) => {
    const resto = lista.filter((t) => t.id !== id);
    setLista(resto);
    setElegida(esPC ? resto[0]?.id ?? null : null);
    refrescarAvisos();
  };

  if (error) return <Alerta>{error}</Alerta>;
  if (!lista) return <Cargando />;
  const tarea = lista.find((t) => t.id === elegida);

  return (
    <div>
      <Cabecera titulo="Por validar" descripcion="Una tarea solo suma al avance, al puntaje y al KPI de la persona cuando la validas. Nadie valida su propio trabajo." />
      {lista.length === 0 ? (
        <Vacio icono={CircleCheckBig} titulo="Estás al día">No hay entregas de tu equipo esperando validación.</Vacio>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(280px,380px)_minmax(0,1fr)]">
          <ul className="space-y-2" aria-label="Entregas">
            {lista.map((t) => (
              <li key={t.id}>
                <button type="button" onClick={() => setElegida(t.id)} aria-current={t.id === elegida}
                  className={cx("flex w-full items-start gap-3 rounded-xl border bg-white p-4 text-left transition-colors",
                    t.id === elegida && esPC ? "border-azul ring-2 ring-azul/15" : "border-linea hover:border-azul/40")}>
                  <Avatar nombre={t.colaborador_nombre} tam="sm" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm text-gris">{t.colaborador_nombre}</span>
                    <span className="block font-medium leading-snug">{t.titulo}</span>
                    <span className="mt-1 flex flex-wrap items-center gap-2 text-xs text-gris">
                      Entregó {hace(t.fecha_modificacion)}
                      {!aTiempo(t) && <Insignia tono="amarillo">Tarde</Insignia>}
                      {t.rondas_revision > 0 && <Insignia tono="rojo">Corregida</Insignia>}
                      {t.evidencias.length > 0 && <span>{t.evidencias.length} archivo{t.evidencias.length > 1 ? "s" : ""}</span>}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {esPC && tarea && (
            <section className="sticky top-24 self-start rounded-xl border border-linea bg-white p-6" aria-label="Revisión">
              <Revision tarea={tarea} onListo={listo} />
            </section>
          )}
        </div>
      )}
      {!esPC && (
        <Modal abierto={!!tarea} onCerrar={() => setElegida(null)} titulo="Revisar entrega" ancho="md:max-w-2xl">
          {tarea && <Revision tarea={tarea} onListo={listo} />}
        </Modal>
      )}
    </div>
  );
}
