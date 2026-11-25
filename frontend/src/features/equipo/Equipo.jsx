import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ArchiveRestore, BellRing, Ban, ClipboardList, History, Pencil, Plus, Repeat, RotateCcw, Search, Target, Trash2, X } from "lucide-react";
import {
  cancelarTarea, eliminarRecurrente, eliminarTarea, equipo as cargarEquipo, guardarRecurrente,
  listarRecurrentes, listarTareas, obtenerTarea, reabrirTarea, recordarTarea, restaurarTarea, tareasEliminadas,
} from "@/lib/api";
import { ESTADOS, fechaCorta, fechaHora, hoyISO, mesActual } from "@/lib/formato";
import {
  Alerta, Boton, Cabecera, Campo, Cargando, EstadoTarea, Estrellas, Insignia, Modal, Panel, Pestanas, PrioridadTarea,
  SelectorMes, Vacio, useAviso, useConfirmar,
} from "@/components/ui";
import { DetalleTarea, EquipoTarea, Progreso, Vencimiento } from "@/features/tareas/componentes";
import Ahora from "@/features/equipo/Ahora";
import BuscadorEquipo from "@/features/equipo/BuscadorEquipo";
import FormTarea from "@/features/tareas/FormTarea";
import { useNovedades } from "@/lib/novedades";
import { useSesion } from "@/lib/sesion";

function Recurrentes({ gente, onEditar, recargar, version }) {
  const [lista, setLista] = useState(null);
  const avisar = useAviso();
  const confirmar = useConfirmar();
  useEffect(() => { listarRecurrentes().then(setLista).catch((e) => avisar(e.message, "rojo")); }, [version, avisar]);
  if (!lista) return <Cargando />;
  if (!lista.length) return <Vacio icono={Repeat} titulo="No hay tareas recurrentes">Programa las tareas que se repiten (la parrilla semanal, el informe mensual) y se crearán solas.</Vacio>;
  const alternar = async (r) => { await guardarRecurrente({ id: r.id, activa: !r.activa }); recargar(); };
  return (
    <Panel cuerpo="p-0">
      <div className="overflow-x-auto">
        <table className="tabla">
          <thead><tr><th className="min-w-56">Tarea</th><th>Responsable</th><th>Se repite</th><th>Prioridad</th><th>Estado</th><th className="w-28"><span className="sr-only">Acciones</span></th></tr></thead>
          <tbody>
            {lista.map((r) => (
              <tr key={r.id}>
                <td><p className="font-medium">{r.titulo}</p>{r.kpi_nombre && <p className="flex items-center gap-1 text-sm text-gris"><Target className="size-3.5" />{r.kpi_nombre}</p>}</td>
                <td>{r.colaborador_nombre}</td>
                <td>{r.frecuencia_texto}</td>
                <td><PrioridadTarea prioridad={r.prioridad} /></td>
                <td><button type="button" onClick={() => alternar(r)} className="text-sm font-medium text-azul hover:underline">{r.activa ? "Activa · pausar" : "En pausa · activar"}</button></td>
                <td className="whitespace-nowrap text-right">
                  <Boton variante="fantasma" tam="sm" icono={Pencil} aria-label={`Editar ${r.titulo}`} onClick={() => onEditar({ ...r, tipo: "recurrente", repetir: true })} />
                  <Boton variante="fantasma" tam="sm" icono={Trash2} aria-label={`Borrar ${r.titulo}`} className="text-rojo" onClick={async () => {
                    if (await confirmar({ titulo: "¿Dejar de repetir esta tarea?", mensaje: "Las tareas que ya se crearon se quedan. Solo deja de crear nuevas.", boton: "Dejar de repetir", peligro: true })) {
                      await eliminarRecurrente(r.id); recargar(); avisar("Ya no se repite.");
                    }
                  }} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {gente.length === 0 && <p className="p-4 text-sm text-gris">No tienes personas a cargo.</p>}
    </Panel>
  );
}

/** Tareas eliminadas (auditoría): quién, cuándo, por qué, en qué estado estaban y su historial. Se pueden recuperar. */
function Eliminadas({ version, recargar }) {
  const [lista, setLista] = useState(null);
  const [abierta, setAbierta] = useState(null);
  const avisar = useAviso();
  const confirmar = useConfirmar();
  useEffect(() => { tareasEliminadas().then(setLista).catch((e) => { setLista([]); avisar(e.message, "rojo"); }); }, [version, avisar]);
  if (!lista) return <Cargando />;
  if (!lista.length) return <Vacio icono={Trash2} titulo="No hay tareas eliminadas">Las tareas que se eliminen quedan aquí con su motivo y su historial, y se pueden recuperar.</Vacio>;
  const recuperar = async (t) => {
    if (!(await confirmar({ titulo: "¿Recuperar esta tarea?", mensaje: `«${t.titulo}» vuelve tal como estaba (${ESTADOS[t.estado] || t.estado}), con su historial y sus archivos, y vuelve a contar.`, boton: "Recuperar" }))) return;
    try { await restaurarTarea(t.id); avisar("Tarea recuperada."); recargar(); } catch (e) { avisar(e.message, "rojo"); }
  };
  return (
    <ul className="space-y-2">
      {lista.map((t) => (
        <li key={t.id} className="rounded-xl border border-linea bg-white p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
            <div className="min-w-0 flex-1">
              <p className="font-medium">{t.titulo}</p>
              <p className="text-sm text-gris">{t.colaborador_nombre} · estaba <EstadoTarea estado={t.estado} /> · entrega {fechaCorta(t.fecha_limite)}</p>
              <p className="mt-1 text-sm"><span className="font-medium">Eliminada por {t.eliminada_por_nombre || "—"}</span> <span className="text-gris">· {fechaHora(t.eliminada_en)}</span></p>
              {t.motivo_eliminacion && <p className="mt-0.5 whitespace-pre-line text-sm text-gris">Motivo: {t.motivo_eliminacion}</p>}
            </div>
            <div className="flex shrink-0 gap-2">
              <Boton variante="secundario" tam="sm" icono={History} onClick={() => setAbierta(abierta === t.id ? null : t.id)} aria-expanded={abierta === t.id}>Historial</Boton>
              {t.puedo_restaurar && <Boton tam="sm" icono={ArchiveRestore} onClick={() => recuperar(t)}>Recuperar</Boton>}
            </div>
          </div>
          {abierta === t.id && (
            <ol className="mt-3 space-y-2 border-l border-linea pl-4">
              {t.historial.map((h) => (
                <li key={h.id} className="text-sm">
                  <span className="font-medium">{h.accion_texto}</span> <span className="text-gris">por {h.usuario_nombre} · {fechaHora(h.fecha)}</span>
                  {h.estado_antes && h.estado_despues && h.estado_antes !== h.estado_despues && <span className="text-gris"> · {ESTADOS[h.estado_antes] || h.estado_antes} → {ESTADOS[h.estado_despues] || h.estado_despues}</span>}
                  {h.comentario && !h.comentario.startsWith("Cambió:") && <p className="whitespace-pre-line text-gris">{h.comentario}</p>}
                </li>
              ))}
            </ol>
          )}
        </li>
      ))}
    </ul>
  );
}

/** Reabrir en cualquier estado: motivo, a dónde vuelve (revisar otra vez o corregir) y, si hace falta, fecha e instrucciones nuevas. */
function ModalReabrir({ tarea, onCerrar, onHecho }) {
  const avisar = useAviso();
  const [d, setD] = useState({});
  const [enviando, setEnviando] = useState(false);
  useEffect(() => { if (tarea) setD({ motivo: "", a: "CORREGIR", fecha_limite: tarea.fecha_limite || "", descripcion: tarea.descripcion || "" }); }, [tarea]);
  if (!tarea) return null;
  const entregada = ["EN_REVISION", "COMPLETADA"].includes(tarea.estado) || !!tarea.fecha_entrega_real;
  const elegirDestino = entregada && tarea.estado !== "EN_REVISION";
  const enviar = async () => {
    setEnviando(true);
    try {
      await reabrirTarea(tarea.id, {
        motivo: d.motivo.trim(), a: elegirDestino ? d.a : "CORREGIR",
        ...(d.fecha_limite && d.fecha_limite !== tarea.fecha_limite ? { fecha_limite: d.fecha_limite } : {}),
        ...(d.descripcion !== (tarea.descripcion || "") ? { descripcion: d.descripcion } : {}),
      });
      avisar(tarea.estado === "COMPLETADA" ? "Reabierta: dejó de contar como validada hasta que se valide otra vez. Le llegó el aviso." : "Reabierta. Le llegó el aviso.");
      onHecho();
    } catch (e) { avisar(e.message, "rojo"); }
    setEnviando(false);
  };
  return (
    <Modal abierto onCerrar={onCerrar} titulo="Reabrir tarea" ancho="md:max-w-lg"
      descripcion={tarea.estado === "COMPLETADA" ? "Deja de contar para el puntaje, el avance y los KPIs hasta que se valide otra vez. Las entregas y comentarios anteriores se conservan." : "Vuelve al flujo de entrega y validación. Las entregas y comentarios anteriores se conservan."}
      pie={<><Boton variante="secundario" onClick={onCerrar}>Volver</Boton><Boton icono={RotateCcw} cargando={enviando} onClick={enviar} disabled={(d.motivo || "").trim().length < 5}>Reabrir</Boton></>}>
      <div className="space-y-4">
        <Campo etiqueta="Motivo" ayuda="Mínimo 5 letras. Le llega a la persona y queda en el historial.">{(id) => <textarea id={id} className="campo" rows={3} value={d.motivo || ""} onChange={(e) => setD({ ...d, motivo: e.target.value })} autoFocus />}</Campo>
        {elegirDestino && (
          <fieldset>
            <legend className="mb-1.5 text-sm font-medium">¿Qué pasa ahora?</legend>
            <div className="space-y-1.5">
              <label className="flex items-start gap-2 text-sm"><input type="radio" name="destino" className="mt-1 accent-azul" checked={d.a === "CORREGIR"} onChange={() => setD({ ...d, a: "CORREGIR" })} /><span><b>Que la corrija</b> y la entregue de nuevo</span></label>
              <label className="flex items-start gap-2 text-sm"><input type="radio" name="destino" className="mt-1 accent-azul" checked={d.a === "REVISION"} onChange={() => setD({ ...d, a: "REVISION" })} /><span><b>Revisar otra vez</b> la misma entrega</span></label>
            </div>
          </fieldset>
        )}
        <Campo etiqueta="Nueva fecha de entrega" ayuda="Opcional.">{(id) => <input id={id} type="date" className="campo" value={d.fecha_limite || ""} onChange={(e) => setD({ ...d, fecha_limite: e.target.value })} />}</Campo>
        <Campo etiqueta="Instrucciones" ayuda="Opcional: actualízalas si cambió lo que hay que hacer.">{(id) => <textarea id={id} className="campo" rows={4} value={d.descripcion || ""} onChange={(e) => setD({ ...d, descripcion: e.target.value })} />}</Campo>
      </div>
    </Modal>
  );
}

/** Eliminar con confirmación y motivo obligatorio. Se conserva (auditoría) y se puede recuperar desde «Eliminadas». */
function ModalEliminar({ tarea, onCerrar, onHecho }) {
  const avisar = useAviso();
  const [motivo, setMotivo] = useState("");
  const [enviando, setEnviando] = useState(false);
  useEffect(() => { setMotivo(""); }, [tarea]);
  if (!tarea) return null;
  const enviar = async () => {
    setEnviando(true);
    try { await eliminarTarea(tarea.id, motivo.trim()); avisar("Tarea eliminada. Puedes recuperarla en «Eliminadas»."); onHecho(); } catch (e) { avisar(e.message, "rojo"); }
    setEnviando(false);
  };
  return (
    <Modal abierto onCerrar={onCerrar} titulo="¿Eliminar esta tarea?" ancho="md:max-w-md"
      descripcion={`«${tarea.titulo}» deja de aparecer y de contar para el avance, el puntaje y los KPIs. Se conserva con su historial y se puede recuperar.`}
      pie={<><Boton variante="secundario" onClick={onCerrar}>Volver</Boton><Boton variante="peligro" icono={Trash2} cargando={enviando} onClick={enviar} disabled={motivo.trim().length < 5}>Eliminar</Boton></>}>
      <Campo etiqueta="Motivo" ayuda="Obligatorio (mínimo 5 letras): creada por error, duplicada, ya no hace falta…">{(id) => <textarea id={id} className="campo" rows={3} value={motivo} onChange={(e) => setMotivo(e.target.value)} autoFocus />}</Campo>
    </Modal>
  );
}

export default function Equipo() {
  const { usuario } = useSesion();
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const [params, setParams] = useSearchParams();
  const [gente, setGente] = useState([]);
  const [tareas, setTareas] = useState(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState(null);
  const [detalle, setDetalle] = useState(null);
  const [version, setVersion] = useState(0);
  const [reabriendo, setReabriendo] = useState(null);
  const [eliminando, setEliminando] = useState(null);
  const vista = params.get("ver") || "ahora";
  const mes = params.get("mes") || mesActual();
  const colaborador = params.get("colaborador") || "";
  const estado = params.get("estado") || "";
  const vencidas = params.get("vencidas") === "1";
  const asignadas = params.get("asignadas") === "1"; // solo las que yo asigné a otras personas
  const buscar = params.get("buscar") || "";

  useEffect(() => { if (params.get("nueva") === "1") { setForm({}); params.delete("nueva"); setParams(params, { replace: true }); } }, [params, setParams]);
  const poner = (clave, valor) => { if (valor) params.set(clave, valor); else params.delete(clave); setParams(params, { replace: true }); };

  const cargar = useCallback((silencioso) => {
    if (silencioso !== true) setTareas(null);
    // Con una búsqueda de texto se mira en todas las tareas, de cualquier mes
    listarTareas({ ambito: "equipo", mes: vencidas || buscar ? "" : mes, colaborador, estado, vencidas: vencidas ? "1" : "", buscar, asignadas: asignadas ? "1" : "" })
      .then(setTareas).catch((e) => setError(e.message));
  }, [mes, colaborador, estado, vencidas, buscar, asignadas]);
  useEffect(() => { cargar(); }, [cargar, version]);
  useNovedades(useCallback(() => cargar(true), [cargar]));
  useEffect(() => { cargarEquipo().then(setGente).catch(() => {}); }, []);

  const lista = useMemo(() => [...(tareas || [])].sort((a, b) => a.fecha_limite.localeCompare(b.fecha_limite)), [tareas]);
  const cuenta = (fn) => (tareas || []).filter(fn).length;
  const hoy = hoyISO();

  const recargar = () => setVersion((v) => v + 1);
  // Desde el buscador: una persona muestra sus tareas; un texto busca en todas; una tarea se abre
  const verPersona = (p) => { const n = new URLSearchParams(params); n.set("ver", "tareas"); n.set("colaborador", String(p.id)); n.delete("buscar"); n.delete("vencidas"); setParams(n); };
  const buscarTexto = (texto) => { const n = new URLSearchParams(params); n.set("ver", "tareas"); n.set("buscar", texto); n.delete("colaborador"); n.delete("vencidas"); setParams(n); };
  // Un aviso de comentario lleva aquí con ?tarea=ID: se abre esa tarea
  useEffect(() => {
    const id = params.get("tarea");
    if (!id) return;
    obtenerTarea(id).then(setDetalle).catch((e) => avisar(e.message, "rojo"));
    params.delete("tarea");
    setParams(params, { replace: true });
  }, [params, setParams]); // eslint-disable-line react-hooks/exhaustive-deps
  const abrirTarea = async (t) => { try { setDetalle(await obtenerTarea(t.id)); } catch (e) { avisar(e.message, "rojo"); } };
  const accionDetalle = async (accion) => {
    const t = detalle;
    try {
      if (accion === "recordar") {
        const r = await recordarTarea(t.id, "");
        avisar(r.message);
        return;
      } else if (accion === "cancelar") {
        if (!(await confirmar({ titulo: "¿Cancelar esta tarea?", mensaje: "No contará para el puntaje de nadie. Queda en el historial.", boton: "Cancelar tarea", peligro: true }))) return;
        await cancelarTarea(t.id, "");
        avisar("Tarea cancelada.");
      }
      setDetalle(null);
      recargar();
    } catch (e) { avisar(e.message, "rojo"); }
  };

  if (error) return <Alerta>{error}</Alerta>;
  return (
    <div>
      <Cabecera titulo="Mi equipo" descripcion="En qué está cada quien: tus tareas y las de toda tu gente, y las que se repiten. Las tareas de tu equipo cuentan para su puntaje cuando las validas.">
        <Boton icono={Plus} onClick={() => setForm({ colaborador: colaborador || "" })} data-guia="nueva-tarea">Nueva tarea</Boton>
      </Cabecera>

      <BuscadorEquipo gente={gente} onPersona={verPersona} onTarea={abrirTarea} onBuscar={buscarTexto} className="mb-4 max-w-2xl" />

      <Pestanas className="mb-5 max-w-xl" valor={vista} onCambio={(v) => poner("ver", v === "ahora" ? "" : v)}
        opciones={[{ valor: "ahora", etiqueta: "Ahora" }, { valor: "tareas", etiqueta: "Tareas" }, { valor: "recurrentes", etiqueta: "Recurrentes" }, { valor: "eliminadas", etiqueta: "Eliminadas" }]} />

      {vista === "ahora" ? (
        <Ahora version={version} onAbrirTarea={async (id) => { try { setDetalle(await obtenerTarea(id)); } catch (e) { avisar(e.message, "rojo"); } }}
          onAsignar={(persona) => setForm({ colaborador: String(persona.id) })} />
      ) : vista === "recurrentes" ? (
        <Recurrentes gente={gente} version={version} recargar={recargar} onEditar={setForm} />
      ) : vista === "eliminadas" ? (
        <Eliminadas version={version} recargar={recargar} />
      ) : (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-2">
            {!vencidas && !buscar && <SelectorMes valor={mes} onCambio={(v) => poner("mes", v === mesActual() ? "" : v)} hastaActual={false} />}
            <select className="campo h-11 w-auto py-0" value={colaborador} onChange={(e) => poner("colaborador", e.target.value)} aria-label="Persona">
              <option value="">Todo el equipo</option>
              {gente.filter((g) => !g.es_yo).map((g) => <option key={g.id} value={g.id}>{g.nombre}</option>)}
            </select>
            <select className="campo h-11 w-auto py-0" value={estado} onChange={(e) => poner("estado", e.target.value)} aria-label="Estado" disabled={vencidas}>
              <option value="">Todos los estados</option>
              {Object.entries(ESTADOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <label className="flex h-11 items-center gap-2 rounded-lg border border-linea bg-white px-3 text-sm">
              <input type="checkbox" checked={vencidas} onChange={(e) => poner("vencidas", e.target.checked ? "1" : "")} className="accent-rojo" /> Solo vencidas
            </label>
            <label className="flex h-11 items-center gap-2 rounded-lg border border-linea bg-white px-3 text-sm" title="Las tareas que tú creaste y enviaste a otras personas, para darles seguimiento">
              <input type="checkbox" checked={asignadas} onChange={(e) => poner("asignadas", e.target.checked ? "1" : "")} className="accent-azul" /> Las que yo asigné
            </label>
            {buscar && (
              <button type="button" onClick={() => poner("buscar", "")} className="flex h-11 items-center gap-2 rounded-full border border-azul/30 bg-azul/10 pl-4 pr-3 text-sm font-medium text-azul hover:bg-azul/15" aria-label={`Quitar la búsqueda «${buscar}»`}>
                <Search className="size-4" aria-hidden />Búsqueda: «{buscar}»<X className="size-4" aria-hidden />
              </button>
            )}
          </div>

          {tareas && !vencidas && (
            <p className="mb-4 text-sm text-gris">
              {tareas.length} tareas · <span className="text-verde">{cuenta((t) => t.estado === "COMPLETADA")} validadas</span> ·{" "}
              <span className="text-[#a86a00]">{cuenta((t) => t.estado === "EN_REVISION")} por validar</span> ·{" "}
              <span className="text-rojo">{cuenta((t) => ["PENDIENTE", "EN_PROGRESO"].includes(t.estado) && t.fecha_limite < hoy)} vencidas</span>
            </p>
          )}

          {!tareas ? <Cargando /> : lista.length === 0 ? (
            <Vacio icono={ClipboardList} titulo="No hay tareas con esos filtros" accion={<Boton icono={Plus} onClick={() => setForm({})}>Nueva tarea</Boton>} />
          ) : (
            <>
              {/* PC: tabla */}
              <Panel cuerpo="p-0" className="hidden md:block">
                <div className="overflow-x-auto">
                  <table className="tabla">
                    <thead><tr><th className="min-w-56">Tarea</th><th>Responsable</th><th className="hidden xl:table-cell">Prioridad</th><th>Fecha límite</th><th>Estado</th><th className="hidden xl:table-cell">Calidad</th></tr></thead>
                    <tbody>
                      {lista.map((t) => (
                        <tr key={t.id} className="cursor-pointer" onClick={() => setDetalle(t)}>
                          <td className="max-w-md">
                            <button type="button" className="text-left font-medium hover:text-azul" onClick={(e) => { e.stopPropagation(); setDetalle(t); }}>{t.titulo}</button>
                            <div className="mt-0.5 flex flex-wrap gap-2 text-sm text-gris">
                              {/* En pantallas medianas la prioridad va aquí: su columna se oculta para no apretar el título */}
                              <span className="xl:hidden"><PrioridadTarea prioridad={t.prioridad} /></span>
                              {t.kpi_nombre && <span className="flex items-center gap-1"><Target className="size-3.5" />{t.kpi_nombre}</span>}
                              {t.es_recurrente && <span className="flex items-center gap-1"><Repeat className="size-3.5" />Recurrente</span>}
                              {t.rondas_revision > 0 && <Insignia tono="rojo">Devuelta {t.rondas_revision}×</Insignia>}
                              <Progreso progreso={t.progreso} />
                            </div>
                            <EquipoTarea tarea={t} className="mt-0.5" />
                          </td>
                          <td className="whitespace-nowrap">{t.colaborador_nombre}{t.colaborador === usuario?.id && <span className="ml-1 rounded bg-azul/10 px-1.5 py-0.5 text-[11px] font-semibold text-azul">Tú</span>}{t.companeros_nombres?.length > 0 && <span className="block text-sm text-gris">+{t.companeros_nombres.length}</span>}</td>
                          <td className="hidden xl:table-cell"><PrioridadTarea prioridad={t.prioridad} /></td>
                          <td className="whitespace-nowrap"><p className="num">{fechaCorta(t.fecha_limite)}</p><Vencimiento tarea={t} /></td>
                          <td className="whitespace-nowrap"><EstadoTarea estado={t.estado} /></td>
                          <td className="hidden xl:table-cell"><Estrellas valor={t.calificacion_calidad} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Panel>
              {/* Celular: tarjetas */}
              <ul className="space-y-2 md:hidden">
                {lista.map((t) => (
                  <li key={t.id}>
                    <button type="button" onClick={() => setDetalle(t)} className="w-full rounded-xl border border-linea bg-white p-4 text-left">
                      <p className="text-sm text-gris">{t.colaborador_nombre}{t.colaborador === usuario?.id && <span className="ml-1 rounded bg-azul/10 px-1.5 py-0.5 text-[11px] font-semibold text-azul">Tú</span>}</p>
                      <p className="font-medium">{t.titulo}</p>
                      <div className="mt-2 flex flex-wrap items-center gap-2"><EstadoTarea estado={t.estado} /><PrioridadTarea prioridad={t.prioridad} /><Vencimiento tarea={t} /><Progreso progreso={t.progreso} /></div>
                      <EquipoTarea tarea={t} className="mt-1.5" />
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}

      <DetalleTarea tarea={detalle} abierto={!!detalle} onCerrar={() => setDetalle(null)}
        onCambio={(t) => { setDetalle(t); cargar(true); }}  // al enviar una referencia (foto, video o PDF) o marcar un paso, la ventana se actualiza al instante
        pie={detalle && (
          <div className="flex w-full flex-wrap justify-end gap-2">
            {detalle.puedo_eliminar && <Boton variante="peligro" icono={Trash2} onClick={() => setEliminando(detalle)} className="mr-auto">Eliminar</Boton>}
            {!["COMPLETADA", "CANCELADA"].includes(detalle.estado) && detalle.puedo_gestionar && <Boton variante="secundario" icono={Ban} onClick={() => accionDetalle("cancelar")}>Cancelar tarea</Boton>}
            {["PENDIENTE", "EN_PROGRESO"].includes(detalle.estado) && detalle.puedo_revisar && <Boton variante="secundario" icono={BellRing} onClick={() => accionDetalle("recordar")}>Recordar</Boton>}
            {detalle.puedo_reabrir && <Boton variante="secundario" icono={RotateCcw} onClick={() => setReabriendo(detalle)}>Reabrir</Boton>}
            {detalle.puedo_gestionar && <Boton icono={Pencil} onClick={() => { setForm(detalle); setDetalle(null); }}>Editar</Boton>}
          </div>
        )} />

      <FormTarea abierto={!!form} inicial={form} gente={gente} onCerrar={() => setForm(null)}
        onGuardada={(msg) => { setForm(null); avisar(msg); recargar(); }} />
      <ModalReabrir tarea={reabriendo} onCerrar={() => setReabriendo(null)} onHecho={() => { setReabriendo(null); setDetalle(null); recargar(); }} />
      <ModalEliminar tarea={eliminando} onCerrar={() => setEliminando(null)} onHecho={() => { setEliminando(null); setDetalle(null); recargar(); }} />
    </div>
  );
}
