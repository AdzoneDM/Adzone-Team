import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { BellRing, Ban, ClipboardList, Pencil, Plus, Repeat, RotateCcw, Search, Target, Trash2 } from "lucide-react";
import {
  cancelarTarea, eliminarRecurrente, eliminarTarea, equipo as cargarEquipo, guardarRecurrente,
  listarRecurrentes, listarTareas, obtenerTarea, reabrirTarea, recordarTarea,
} from "@/lib/api";
import { ESTADOS, fechaCorta, hoyISO, mesActual } from "@/lib/formato";
import {
  Alerta, Boton, Cabecera, Campo, Cargando, EstadoTarea, Estrellas, Insignia, Modal, Panel, Pestanas, PrioridadTarea,
  SelectorMes, Vacio, useAviso, useConfirmar,
} from "@/components/ui";
import { DetalleTarea, EquipoTarea, Progreso, Vencimiento } from "@/features/tareas/componentes";
import Ahora from "@/features/equipo/Ahora";
import FormTarea from "@/features/tareas/FormTarea";

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
          <thead><tr><th>Tarea</th><th>Responsable</th><th>Se repite</th><th>Prioridad</th><th>Estado</th><th className="w-28"><span className="sr-only">Acciones</span></th></tr></thead>
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

export default function Equipo() {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const [params, setParams] = useSearchParams();
  const [gente, setGente] = useState([]);
  const [tareas, setTareas] = useState(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState(null);
  const [detalle, setDetalle] = useState(null);
  const [version, setVersion] = useState(0);
  const [reabriendo, setReabriendo] = useState(false);
  const [motivo, setMotivo] = useState("");
  const vista = params.get("ver") || "ahora";
  const mes = params.get("mes") || mesActual();
  const colaborador = params.get("colaborador") || "";
  const estado = params.get("estado") || "";
  const vencidas = params.get("vencidas") === "1";
  const [buscar, setBuscar] = useState("");

  useEffect(() => { if (params.get("nueva") === "1") { setForm({}); params.delete("nueva"); setParams(params, { replace: true }); } }, [params, setParams]);
  const poner = (clave, valor) => { if (valor) params.set(clave, valor); else params.delete(clave); setParams(params, { replace: true }); };

  const cargar = useCallback(() => {
    setTareas(null);
    listarTareas({ ambito: "equipo", mes: vencidas ? "" : mes, colaborador, estado, vencidas: vencidas ? "1" : "" })
      .then(setTareas).catch((e) => setError(e.message));
  }, [mes, colaborador, estado, vencidas]);
  useEffect(() => { cargar(); }, [cargar, version]);
  useEffect(() => { cargarEquipo().then(setGente).catch(() => {}); }, []);

  const lista = useMemo(() => (tareas || []).filter((t) => !buscar || t.titulo.toLowerCase().includes(buscar.toLowerCase()))
    .sort((a, b) => a.fecha_limite.localeCompare(b.fecha_limite)), [tareas, buscar]);
  const cuenta = (fn) => (tareas || []).filter(fn).length;
  const hoy = hoyISO();

  const recargar = () => setVersion((v) => v + 1);
  const accionDetalle = async (accion) => {
    const t = detalle;
    try {
      if (accion === "reabrir") {
        await reabrirTarea(t.id, motivo.trim());
        setReabriendo(false);
        setMotivo("");
        avisar("Reabierta: volvió a «En revisión» y dejó de contar.");
      } else if (accion === "recordar") {
        const r = await recordarTarea(t.id, "");
        avisar(r.message);
        return;
      } else if (accion === "cancelar") {
        if (!(await confirmar({ titulo: "¿Cancelar esta tarea?", mensaje: "No contará para el puntaje de nadie. Queda en el historial.", boton: "Cancelar tarea", peligro: true }))) return;
        await cancelarTarea(t.id, "");
        avisar("Tarea cancelada.");
      } else if (accion === "eliminar") {
        if (!(await confirmar({ titulo: "¿Borrar esta tarea?", mensaje: "Se borra con su historial y sus archivos. Si solo ya no hace falta, mejor cancélala.", boton: "Borrar", peligro: true }))) return;
        await eliminarTarea(t.id);
        avisar("Tarea borrada.");
      }
      setDetalle(null);
      recargar();
    } catch (e) { avisar(e.message, "rojo"); }
  };

  if (error) return <Alerta>{error}</Alerta>;
  return (
    <div>
      <Cabecera titulo="Mi equipo" descripcion="En qué está cada quien, sus tareas y las que se repiten. Las tareas cuentan para el puntaje cuando las validas.">
        <Boton icono={Plus} onClick={() => setForm({ colaborador: colaborador || "" })}>Nueva tarea</Boton>
      </Cabecera>

      <Pestanas className="mb-5 max-w-md" valor={vista} onCambio={(v) => poner("ver", v === "ahora" ? "" : v)}
        opciones={[{ valor: "ahora", etiqueta: "Ahora" }, { valor: "tareas", etiqueta: "Tareas" }, { valor: "recurrentes", etiqueta: "Recurrentes" }]} />

      {vista === "ahora" ? (
        <Ahora version={version} onAbrirTarea={async (id) => { try { setDetalle(await obtenerTarea(id)); } catch (e) { avisar(e.message, "rojo"); } }}
          onAsignar={(persona) => setForm({ colaborador: String(persona.id) })} />
      ) : vista === "recurrentes" ? (
        <Recurrentes gente={gente} version={version} recargar={recargar} onEditar={setForm} />
      ) : (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-2">
            {!vencidas && <SelectorMes valor={mes} onCambio={(v) => poner("mes", v === mesActual() ? "" : v)} hastaActual={false} />}
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
            <div className="relative min-w-48 flex-1 md:max-w-xs">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" />
              <input className="campo h-11 pl-9" placeholder="Buscar tarea" value={buscar} onChange={(e) => setBuscar(e.target.value)} aria-label="Buscar tarea" />
            </div>
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
                    <thead><tr><th>Tarea</th><th>Responsable</th><th>Prioridad</th><th>Fecha límite</th><th>Estado</th><th>Calidad</th></tr></thead>
                    <tbody>
                      {lista.map((t) => (
                        <tr key={t.id} className="cursor-pointer" onClick={() => setDetalle(t)}>
                          <td className="max-w-md">
                            <button type="button" className="text-left font-medium hover:text-azul" onClick={(e) => { e.stopPropagation(); setDetalle(t); }}>{t.titulo}</button>
                            <div className="mt-0.5 flex flex-wrap gap-2 text-sm text-gris">
                              {t.kpi_nombre && <span className="flex items-center gap-1"><Target className="size-3.5" />{t.kpi_nombre}</span>}
                              {t.es_recurrente && <span className="flex items-center gap-1"><Repeat className="size-3.5" />Recurrente</span>}
                              {t.rondas_revision > 0 && <Insignia tono="rojo">Devuelta {t.rondas_revision}×</Insignia>}
                              <Progreso progreso={t.progreso} />
                            </div>
                            <EquipoTarea tarea={t} className="mt-0.5" />
                          </td>
                          <td className="whitespace-nowrap">{t.colaborador_nombre}{t.companeros_nombres?.length > 0 && <span className="block text-sm text-gris">+{t.companeros_nombres.length}</span>}</td>
                          <td><PrioridadTarea prioridad={t.prioridad} /></td>
                          <td className="whitespace-nowrap"><p className="num">{fechaCorta(t.fecha_limite)}</p><Vencimiento tarea={t} /></td>
                          <td><EstadoTarea estado={t.estado} /></td>
                          <td><Estrellas valor={t.calificacion_calidad} /></td>
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
                      <p className="text-sm text-gris">{t.colaborador_nombre}</p>
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
        pie={detalle && (
          <div className="flex w-full flex-wrap justify-end gap-2">
            {detalle.estado === "COMPLETADA" && detalle.puedo_revisar && <Boton variante="secundario" icono={RotateCcw} onClick={() => setReabriendo(true)}>Reabrir</Boton>}
            {!["COMPLETADA", "CANCELADA"].includes(detalle.estado) && detalle.puedo_gestionar && (<>
              <Boton variante="peligro" icono={Trash2} onClick={() => accionDetalle("eliminar")} className="mr-auto">Borrar</Boton>
              <Boton variante="secundario" icono={Ban} onClick={() => accionDetalle("cancelar")}>Cancelar tarea</Boton>
              {["PENDIENTE", "EN_PROGRESO"].includes(detalle.estado) && detalle.puedo_revisar && <Boton variante="secundario" icono={BellRing} onClick={() => accionDetalle("recordar")}>Recordar</Boton>}
              <Boton icono={Pencil} onClick={() => { setForm(detalle); setDetalle(null); }}>Editar</Boton>
            </>)}
          </div>
        )} />

      <FormTarea abierto={!!form} inicial={form} gente={gente} onCerrar={() => setForm(null)}
        onGuardada={(msg) => { setForm(null); avisar(msg); recargar(); }} />
      <Modal abierto={reabriendo} onCerrar={() => setReabriendo(false)} titulo="Reabrir tarea validada" ancho="max-w-md"
        descripcion="Vuelve a «En revisión» y deja de contar para el puntaje hasta que la valides otra vez."
        pie={<><Boton variante="secundario" onClick={() => setReabriendo(false)}>Volver</Boton><Boton icono={RotateCcw} onClick={() => accionDetalle("reabrir")} disabled={motivo.trim().length < 3}>Reabrir</Boton></>}>
        <Campo etiqueta="Motivo" ayuda="Le llega a la persona.">{(id) => <textarea id={id} className="campo" rows={3} value={motivo} onChange={(e) => setMotivo(e.target.value)} autoFocus />}</Campo>
      </Modal>
    </div>
  );
}
