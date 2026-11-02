// Control de horario: mi asistencia, el equipo hoy y en el mes, permisos y vacaciones, horarios y feriados.
import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CalendarClock, Check, Download, Plus, Trash2, X } from "lucide-react";
import {
  asignacionesHorario, asignarHorario, asistenciaHoy, asistenciaMes, asistenciaReporte, ausencias, borrarFeriado, borrarHorario,
  borrarMarcaje, corregirMarcaje, feriados, guardarFeriado, guardarHorario, horarios, pedirAusencia, retirarAusencia, revisarAusencia,
  urlAsistenciaCsv,
} from "@/lib/api";
import { diaSemana, fechaCorta, mesActual, reloj } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import { Alerta, Boton, Cabecera, Campo, Cargando, Insignia, Modal, Panel, Pestanas, Puntaje, SelectorMes, cx, useAviso, useConfirmar } from "@/components/ui";

const hora = (iso) => (iso ? new Date(iso).toLocaleTimeString("es-DO", { hour: "numeric", minute: "2-digit" }) : "—");
const ESTADO = {
  TRABAJANDO: ["Trabajando", "verde"], EN_PAUSA: ["En pausa", "amarillo"], PRESENTE: ["Presente", "azul"], AUSENTE: ["Ausente", "rojo"],
  TARDE_SIN_MARCAR: ["No ha marcado", "rojo"], PENDIENTE: ["Aún no entra", "neutro"], PERMISO: ["Permiso", "azul"], LIBRE: ["Libre", "neutro"],
  SIN_CONTROL: ["Sin control", "neutro"], FUERA_DE_HORARIO: ["Fuera de horario", "neutro"], PROGRAMADO: ["Programado", "neutro"],
};
const Estado = ({ e }) => { const [t, tono] = ESTADO[e] || [e, "neutro"]; return <Insignia tono={tono}>{t}</Insignia>; };
const pct = (v) => (v == null ? "—" : `${Number(v).toLocaleString("es-DO", { maximumFractionDigits: 1 })} %`);

function Dato({ titulo, valor, detalle, alerta }) {
  return (
    <div className="rounded-xl border border-linea bg-white p-4">
      <p className="text-sm text-gris">{titulo}</p>
      <p className={cx("mt-1 font-display text-2xl font-semibold num", alerta && "text-rojo")}>{valor}</p>
      {detalle && <p className="mt-0.5 text-xs text-gris">{detalle}</p>}
    </div>
  );
}

export function ResumenAsistencia({ r, adherencia }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      <Dato titulo="Adherencia al horario" valor={<Puntaje valor={adherencia} />} detalle="Puntualidad, asistencia y horas" />
      <Dato titulo="Puntualidad" valor={pct(r.puntualidad)} detalle={`${r.tardanzas} tarde · ${r.minutos_tarde} min`} alerta={r.tardanzas >= 3} />
      <Dato titulo="Asistencia" valor={pct(r.asistencia)} detalle={`${r.dias_presentes} de ${r.dias_laborables} días · ${r.ausencias} ausencia(s)`} alerta={r.ausencias > 0} />
      <Dato titulo="Horas trabajadas" valor={reloj(r.minutos_trabajados)} detalle={`de ${reloj(r.minutos_programados)} programadas`} />
      <Dato titulo="Horas extra" valor={reloj(r.minutos_extra)} detalle={r.minutos_extra >= 600 ? "Riesgo de agotamiento" : "Sobre lo programado"} alerta={r.minutos_extra >= 600} />
      <Dato titulo="Salidas tempranas" valor={r.salidas_tempranas} detalle={`${r.sin_salida} día(s) sin marcar salida`} alerta={r.sin_salida > 0} />
    </div>
  );
}

/** El mes de una persona, día por día. Con `puedeCorregir`, su supervisor agrega o borra marcajes. */
export function MesPersona({ usuario, puedeCorregir }) {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const [mes, setMes] = useState(mesActual());
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [corrigiendo, setCorrigiendo] = useState(null);
  const cargar = useCallback(() => { setD(null); asistenciaMes({ mes, usuario }).then(setD).catch((e) => setError(e.message)); }, [mes, usuario]);
  useEffect(() => { cargar(); }, [cargar]);
  if (error) return <Alerta>{error}</Alerta>;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {d && <p className="text-gris">{d.persona.nombre}{d.persona.puesto ? ` · ${d.persona.puesto}` : ""}</p>}
        <SelectorMes valor={mes} onCambio={setMes} />
      </div>
      {!d ? <Cargando /> : (
        <>
          <ResumenAsistencia r={d.resumen} adherencia={d.adherencia} />
          <Panel titulo="Día por día" cuerpo="p-0">
            <div className="overflow-x-auto">
              <table className="tabla">
                <thead><tr><th>Día</th><th>Estado</th><th>Entrada</th><th>Salida</th><th className="text-right">Trabajado</th><th className="text-right">Tarde</th><th className="text-right">Extra</th><th>Marcajes</th></tr></thead>
                <tbody>
                  {[...d.dias].reverse().map((j) => (
                    <tr key={j.fecha} className={!j.laborable && !j.entrada ? "text-gris" : ""}>
                      <td className="whitespace-nowrap"><span className="capitalize">{diaSemana(j.fecha)}</span> {fechaCorta(j.fecha)}{j.feriado && <Insignia className="ml-1">Feriado</Insignia>}</td>
                      <td><Estado e={j.estado} />{j.ausencia && <span className="ml-1 text-xs text-gris">{j.ausencia}</span>}{j.sin_salida && <Insignia tono="amarillo" className="ml-1">Sin salida</Insignia>}</td>
                      <td className="num">{hora(j.entrada)}</td>
                      <td className="num">{hora(j.salida)}</td>
                      <td className="text-right num">{j.trabajados ? reloj(j.trabajados) : "—"}</td>
                      <td className={cx("text-right num", j.tardanza && "text-rojo")}>{j.tardanza ? `${j.tardanza} min` : "—"}</td>
                      <td className="text-right num">{j.extra ? reloj(j.extra) : "—"}</td>
                      <td>
                        <div className="flex flex-wrap items-center gap-1">
                          {j.marcajes.map((m) => (
                            <span key={m.id} className={cx("inline-flex items-center gap-1 rounded border px-1.5 text-xs num", m.corregido ? "border-amarillo bg-amarillo-50" : "border-linea")}
                              title={`${m.tipo}${m.motivo ? ` · ${m.motivo}` : ""}${m.corregido ? " · corregido" : ""} · ${m.origen}`}>
                              {{ ENTRADA: "E", PAUSA: "P", REGRESO: "R", SALIDA: "S" }[m.tipo]} {hora(m.momento)}
                              {puedeCorregir && <button type="button" aria-label="Borrar marcaje" className="text-gris hover:text-rojo" onClick={async () => {
                                if (await confirmar({ titulo: "¿Borrar este marcaje?", boton: "Borrar", peligro: true })) {
                                  try { await borrarMarcaje(m.id); cargar(); } catch (e) { avisar(e.message, "rojo"); }
                                }
                              }}><X className="size-3" /></button>}
                            </span>
                          ))}
                          {puedeCorregir && <button type="button" className="rounded px-1 text-xs text-azul hover:underline" onClick={() => setCorrigiendo({ fecha: j.fecha, tipo: "ENTRADA", hora: "08:00", nota: "" })}>+ marcaje</button>}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </>
      )}
      <Modal abierto={!!corrigiendo} onCerrar={() => setCorrigiendo(null)} titulo="Agregar marcaje" descripcion="Queda registrado que lo agregaste tú, con la nota."
        pie={<><Boton variante="secundario" onClick={() => setCorrigiendo(null)}>Cancelar</Boton><Boton onClick={async () => {
          try {
            await corregirMarcaje({ usuario, tipo: corrigiendo.tipo, momento: new Date(`${corrigiendo.fecha}T${corrigiendo.hora}`).toISOString(), nota: corrigiendo.nota });
            setCorrigiendo(null); avisar("Marcaje agregado."); cargar();
          } catch (e) { avisar(e.message, "rojo"); }
        }}>Agregar</Boton></>}>
        {corrigiendo && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Campo etiqueta="Tipo">{(id) => <select id={id} className="campo" value={corrigiendo.tipo} onChange={(e) => setCorrigiendo({ ...corrigiendo, tipo: e.target.value })}>
              <option value="ENTRADA">Entrada</option><option value="PAUSA">Inicio de pausa</option><option value="REGRESO">Fin de pausa</option><option value="SALIDA">Salida</option></select>}</Campo>
            <Campo etiqueta="Hora">{(id) => <input id={id} type="time" className="campo" value={corrigiendo.hora} onChange={(e) => setCorrigiendo({ ...corrigiendo, hora: e.target.value })} />}</Campo>
            <Campo etiqueta="Motivo de la corrección" className="sm:col-span-2">{(id) => <input id={id} className="campo" placeholder="Olvidó marcar la salida" value={corrigiendo.nota} onChange={(e) => setCorrigiendo({ ...corrigiendo, nota: e.target.value })} />}</Campo>
          </div>
        )}
      </Modal>
    </div>
  );
}

function Hoy({ onVer }) {
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const cargar = () => asistenciaHoy().then(setD).catch((e) => setError(e.message));
    cargar();
    const t = setInterval(cargar, 60000);
    return () => clearInterval(t);
  }, []);
  if (error) return <Alerta>{error}</Alerta>;
  if (!d) return <Cargando />;
  const c = d.conteo;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Dato titulo="Trabajando" valor={(c.TRABAJANDO || 0) + (c.PRESENTE || 0)} />
        <Dato titulo="En pausa" valor={c.EN_PAUSA || 0} />
        <Dato titulo="Llegaron tarde" valor={d.tardes} alerta={d.tardes > 0} />
        <Dato titulo="No han marcado" valor={(c.TARDE_SIN_MARCAR || 0) + (c.AUSENTE || 0)} alerta={(c.TARDE_SIN_MARCAR || 0) + (c.AUSENTE || 0) > 0} />
        <Dato titulo="Con permiso" valor={c.PERMISO || 0} />
      </div>
      <Panel titulo="Equipo hoy" cuerpo="p-0">
        <div className="overflow-x-auto">
          <table className="tabla">
            <thead><tr><th>Persona</th><th>Estado</th><th>Entrada</th><th className="text-right">Trabajado</th><th>Computadora</th></tr></thead>
            <tbody>
              {d.personas.map((p) => (
                <tr key={p.id} className="cursor-pointer hover:bg-fondo" onClick={() => onVer(p.id)}>
                  <td><p className="font-medium">{p.nombre}</p><p className="text-xs text-gris">{p.puesto || "Sin puesto"}</p></td>
                  <td><Estado e={p.estado} />{p.llegada === "TARDE" && <span className="ml-1 text-xs text-rojo">{p.tardanza} min tarde</span>}</td>
                  <td className="num">{hora(p.entrada)}{p.turno && <span className="block text-xs text-gris">turno {p.turno[0]}</span>}</td>
                  <td className="text-right num">{p.trabajados ? reloj(p.trabajados) : "—"}</td>
                  <td>{p.pc ? (
                    <span className="text-sm"><span className={cx("mr-1.5 inline-block size-2 rounded-full", p.pc.en_vivo ? (p.pc.activo ? "bg-verde" : "bg-amarillo-600") : "bg-gris")} />
                      {p.pc.en_vivo ? (p.pc.activo ? p.pc.app || "Activo" : "Inactivo") : `Visto ${hora(p.pc.minuto)}`}</span>
                  ) : <span className="text-sm text-gris">—</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

function MesEquipo({ onVer }) {
  const [mes, setMes] = useState(mesActual());
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { setD(null); asistenciaReporte(mes).then(setD).catch((e) => setError(e.message)); }, [mes]);
  if (error) return <Alerta>{error}</Alerta>;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SelectorMes valor={mes} onCambio={setMes} />
        <a href={urlAsistenciaCsv(mes)} className="inline-flex h-10 items-center gap-2 rounded-lg border border-linea bg-white px-3 text-sm font-medium hover:border-azul"><Download className="size-4" />Excel del mes</a>
      </div>
      {!d ? <Cargando /> : (
        <Panel cuerpo="p-0">
          <div className="overflow-x-auto">
            <table className="tabla">
              <thead><tr><th>Persona</th><th className="text-right">Adherencia</th><th className="text-right">Puntualidad</th><th className="text-right">Asistencia</th><th className="text-right">Tardanzas</th><th className="text-right">Ausencias</th><th className="text-right">Trabajadas</th><th className="text-right">Extra</th><th className="text-right">Sin salida</th></tr></thead>
              <tbody>
                {d.personas.map((p) => (
                  <tr key={p.id} className="cursor-pointer hover:bg-fondo" onClick={() => onVer(p.id)}>
                    <td><p className="font-medium">{p.nombre}</p><p className="text-xs text-gris">{p.departamento || ""}</p></td>
                    <td className="text-right"><Puntaje valor={p.adherencia} /></td>
                    <td className="text-right num">{pct(p.puntualidad)}</td>
                    <td className="text-right num">{pct(p.asistencia)}</td>
                    <td className={cx("text-right num", p.tardanzas >= 3 && "text-rojo")}>{p.tardanzas} <span className="text-xs text-gris">({p.minutos_tarde} min)</span></td>
                    <td className={cx("text-right num", p.ausencias && "text-rojo")}>{p.ausencias}</td>
                    <td className="text-right num">{reloj(p.minutos_trabajados)}</td>
                    <td className={cx("text-right num", p.minutos_extra >= 600 && "text-[#a86a00]")}>{reloj(p.minutos_extra)}</td>
                    <td className="text-right num">{p.sin_salida}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </div>
  );
}

const TIPOS_AUSENCIA = [["VACACIONES", "Vacaciones"], ["LICENCIA", "Licencia médica"], ["PERMISO", "Permiso"], ["TRABAJO_FUERA", "Trabajo fuera de la oficina"], ["OTRO", "Otro"]];

function Permisos({ gestiona }) {
  const avisar = useAviso();
  const [mias, setMias] = useState(null);
  const [equipo, setEquipo] = useState([]);
  const [form, setForm] = useState(null);
  const cargar = useCallback(() => {
    ausencias().then(setMias).catch(() => setMias([]));
    if (gestiona) ausencias("equipo").then(setEquipo).catch(() => {});
  }, [gestiona]);
  useEffect(() => { cargar(); }, [cargar]);
  if (!mias) return <Cargando />;
  const pendientes = equipo.filter((a) => a.puede_revisar);
  const Fila = ({ a, revisar }) => (
    <li className="flex flex-wrap items-center gap-3 px-5 py-3">
      <div className="min-w-0 flex-1">
        <p className="font-medium">{revisar ? `${a.persona} · ` : ""}{a.tipo_nombre} <span className="text-sm font-normal text-gris">{fechaCorta(a.desde)} → {fechaCorta(a.hasta)} ({a.dias} día{a.dias === 1 ? "" : "s"})</span></p>
        {a.motivo && <p className="text-sm text-gris">{a.motivo}</p>}
        {a.comentario_revision && <p className="text-sm text-gris">{a.revisada_por_nombre}: {a.comentario_revision}</p>}
      </div>
      <Insignia tono={{ PENDIENTE: "amarillo", APROBADA: "verde", RECHAZADA: "rojo" }[a.estado]}>{a.estado.charAt(0) + a.estado.slice(1).toLowerCase()}</Insignia>
      {revisar && a.puede_revisar && <>
        <Boton tam="sm" icono={Check} onClick={async () => { try { await revisarAusencia(a.id, true, ""); avisar("Aprobada."); cargar(); } catch (e) { avisar(e.message, "rojo"); } }}>Aprobar</Boton>
        <Boton tam="sm" variante="secundario" icono={X} onClick={async () => { const c = window.prompt("¿Por qué se rechaza?") ?? null; if (c === null) return; try { await revisarAusencia(a.id, false, c); avisar("Rechazada."); cargar(); } catch (e) { avisar(e.message, "rojo"); } }}>Rechazar</Boton>
      </>}
      {!revisar && a.estado === "PENDIENTE" && <Boton tam="sm" variante="fantasma" icono={Trash2} className="text-rojo" aria-label="Retirar solicitud" onClick={async () => { await retirarAusencia(a.id); cargar(); }} />}
    </li>
  );
  return (
    <div className="space-y-5">
      {gestiona && (
        <Panel titulo={`Solicitudes de mi equipo${pendientes.length ? ` · ${pendientes.length} por revisar` : ""}`} cuerpo="p-0">
          {equipo.length === 0 ? <p className="p-5 text-sm text-gris">Nadie de tu equipo ha pedido permisos.</p>
            : <ul className="divide-y divide-linea-suave">{equipo.map((a) => <Fila key={a.id} a={a} revisar />)}</ul>}
        </Panel>
      )}
      <Panel titulo="Mis solicitudes" accion={<Boton tam="sm" icono={Plus} onClick={() => setForm({ tipo: "PERMISO", desde: "", hasta: "", motivo: "" })}>Pedir permiso o vacaciones</Boton>} cuerpo="p-0">
        {mias.length === 0 ? <p className="p-5 text-sm text-gris">No has pedido permisos.</p> : <ul className="divide-y divide-linea-suave">{mias.map((a) => <Fila key={a.id} a={a} />)}</ul>}
      </Panel>
      <Modal abierto={!!form} onCerrar={() => setForm(null)} titulo="Pedir permiso o vacaciones" descripcion="Le llega a tu supervisor para aprobarlo. Los días aprobados no cuentan como ausencia."
        pie={<><Boton variante="secundario" onClick={() => setForm(null)}>Cancelar</Boton><Boton onClick={async () => {
          if (!form.desde) return avisar("Elige la fecha.", "rojo");
          try { await pedirAusencia({ ...form, hasta: form.hasta || form.desde }); setForm(null); avisar("Solicitud enviada."); cargar(); } catch (e) { avisar(e.message, "rojo"); }
        }}>Enviar</Boton></>}>
        {form && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Campo etiqueta="Tipo" className="sm:col-span-2">{(id) => <select id={id} className="campo" value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })}>{TIPOS_AUSENCIA.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select>}</Campo>
            <Campo etiqueta="Desde">{(id) => <input id={id} type="date" className="campo" value={form.desde} onChange={(e) => setForm({ ...form, desde: e.target.value })} />}</Campo>
            <Campo etiqueta="Hasta">{(id) => <input id={id} type="date" className="campo" value={form.hasta} min={form.desde} onChange={(e) => setForm({ ...form, hasta: e.target.value })} />}</Campo>
            <Campo etiqueta="Motivo" className="sm:col-span-2">{(id) => <textarea id={id} rows={3} className="campo" value={form.motivo} onChange={(e) => setForm({ ...form, motivo: e.target.value })} />}</Campo>
          </div>
        )}
      </Modal>
    </div>
  );
}

const DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

function Horarios() {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const [lista, setLista] = useState(null);
  const [personas, setPersonas] = useState([]);
  const [fer, setFer] = useState([]);
  const [editando, setEditando] = useState(null);
  const [nuevoFeriado, setNuevoFeriado] = useState({ fecha: "", nombre: "" });
  const cargar = useCallback(() => {
    horarios().then(setLista).catch(() => setLista([]));
    asignacionesHorario().then(setPersonas).catch(() => {});
    feriados().then(setFer).catch(() => {});
  }, []);
  useEffect(() => { cargar(); }, [cargar]);
  if (!lista) return <Cargando />;
  const resumen = (h) => Object.entries(h.dias).map(([d, [a, b]]) => `${DIAS[d].slice(0, 3)} ${a}-${b}`).join(" · ");
  return (
    <div className="space-y-5">
      <Panel titulo="Horarios" accion={<Boton tam="sm" icono={Plus} onClick={() => setEditando({ nombre: "", dias: { 0: ["08:00", "17:00"], 1: ["08:00", "17:00"], 2: ["08:00", "17:00"], 3: ["08:00", "17:00"], 4: ["08:00", "17:00"] }, almuerzo_minutos: 60, tolerancia_minutos: 10, por_defecto: false, activo: true })}>Horario</Boton>} cuerpo="p-0">
        <ul className="divide-y divide-linea-suave">
          {lista.map((h) => (
            <li key={h.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
              <div className="min-w-0 flex-1"><p className="font-medium">{h.nombre} {h.por_defecto && <Insignia tono="azul">Por defecto</Insignia>}</p>
                <p className="text-sm text-gris">{resumen(h)} · almuerzo {h.almuerzo_minutos} min · tolerancia {h.tolerancia_minutos} min · {h.personas} persona(s)</p></div>
              <Boton tam="sm" variante="secundario" onClick={() => setEditando({ ...h })}>Editar</Boton>
              <Boton tam="sm" variante="fantasma" icono={Trash2} className="text-rojo" aria-label={`Borrar ${h.nombre}`} onClick={async () => {
                if (await confirmar({ titulo: `¿Borrar «${h.nombre}»?`, boton: "Borrar", peligro: true })) { try { await borrarHorario(h.id); cargar(); } catch (e) { avisar(e.message, "rojo"); } }
              }} />
            </li>
          ))}
        </ul>
      </Panel>

      <Panel titulo="Horario de cada persona" cuerpo="p-0">
        <div className="overflow-x-auto">
          <table className="tabla">
            <thead><tr><th>Persona</th><th>Horario</th><th>Marca obligatoria</th></tr></thead>
            <tbody>
              {personas.map((p) => (
                <tr key={p.id}>
                  <td><p className="font-medium">{p.nombre}</p><p className="text-xs text-gris">{p.puesto || "Sin puesto"}</p></td>
                  <td><select aria-label={`Horario de ${p.nombre}`} className="campo h-10" value={p.horario || ""} onChange={async (e) => {
                    try { await asignarHorario({ usuarios: [p.id], horario: Number(e.target.value), marca_obligatoria: p.marca_obligatoria }); cargar(); } catch (er) { avisar(er.message, "rojo"); }
                  }}>{lista.map((h) => <option key={h.id} value={h.id}>{h.nombre}</option>)}</select>{!p.propio && <span className="ml-2 text-xs text-gris">(por defecto)</span>}</td>
                  <td><label className="flex min-h-10 items-center gap-2 text-sm"><input type="checkbox" className="accent-azul" checked={p.marca_obligatoria} onChange={async (e) => {
                    try { await asignarHorario({ usuarios: [p.id], horario: p.horario, marca_obligatoria: e.target.checked }); cargar(); } catch (er) { avisar(er.message, "rojo"); }
                  }} />{p.marca_obligatoria ? "Sí: si no marca, sale ausente" : "No (dirección, trabajo libre)"}</label></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel titulo="Feriados" cuerpo="p-0">
        <ul className="divide-y divide-linea-suave">
          {fer.map((f) => (
            <li key={f.id} className="flex items-center gap-3 px-5 py-2.5"><span className="w-28 num">{fechaCorta(f.fecha)}</span><span className="flex-1">{f.nombre}</span>
              <Boton tam="sm" variante="fantasma" icono={Trash2} className="text-rojo" aria-label={`Quitar ${f.nombre}`} onClick={async () => { await borrarFeriado(f.id); cargar(); }} /></li>
          ))}
          <li className="flex flex-wrap items-center gap-2 px-5 py-3">
            <input type="date" aria-label="Fecha del feriado" className="campo h-10 w-44" value={nuevoFeriado.fecha} onChange={(e) => setNuevoFeriado({ ...nuevoFeriado, fecha: e.target.value })} />
            <input aria-label="Nombre del feriado" className="campo h-10 min-w-0 flex-1" placeholder="Día de la Constitución" value={nuevoFeriado.nombre} onChange={(e) => setNuevoFeriado({ ...nuevoFeriado, nombre: e.target.value })} />
            <Boton tam="sm" icono={Plus} disabled={!nuevoFeriado.fecha || !nuevoFeriado.nombre.trim()} onClick={async () => {
              try { await guardarFeriado(nuevoFeriado); setNuevoFeriado({ fecha: "", nombre: "" }); cargar(); } catch (e) { avisar(e.message, "rojo"); }
            }}>Agregar</Boton>
          </li>
        </ul>
      </Panel>

      <Modal abierto={!!editando} onCerrar={() => setEditando(null)} titulo={editando?.id ? "Editar horario" : "Nuevo horario"} ancho="md:max-w-xl"
        pie={<><Boton variante="secundario" onClick={() => setEditando(null)}>Cancelar</Boton><Boton onClick={async () => {
          try { await guardarHorario(editando); setEditando(null); avisar("Horario guardado."); cargar(); } catch (e) { avisar(e.message, "rojo"); }
        }}>Guardar</Boton></>}>
        {editando && (
          <div className="space-y-4">
            <Campo etiqueta="Nombre">{(id) => <input id={id} className="campo" value={editando.nombre} onChange={(e) => setEditando({ ...editando, nombre: e.target.value })} placeholder="Call Center mañana" />}</Campo>
            <fieldset className="space-y-2">
              <legend className="etiqueta">Días y horas</legend>
              {DIAS.map((nombre, i) => {
                const turno = editando.dias[i];
                const poner = (v) => { const dias = { ...editando.dias }; if (v) dias[i] = v; else delete dias[i]; setEditando({ ...editando, dias }); };
                return (
                  <div key={i} className="flex flex-wrap items-center gap-2">
                    <label className="flex w-32 min-h-10 items-center gap-2"><input type="checkbox" className="accent-azul" checked={!!turno} onChange={(e) => poner(e.target.checked ? ["08:00", "17:00"] : null)} />{nombre}</label>
                    {turno && <>
                      <input type="time" aria-label={`Entrada ${nombre}`} className="campo h-10 w-32" value={turno[0]} onChange={(e) => poner([e.target.value, turno[1]])} />
                      <span className="text-gris">a</span>
                      <input type="time" aria-label={`Salida ${nombre}`} className="campo h-10 w-32" value={turno[1]} onChange={(e) => poner([turno[0], e.target.value])} />
                    </>}
                  </div>
                );
              })}
            </fieldset>
            <div className="grid gap-4 sm:grid-cols-2">
              <Campo etiqueta="Almuerzo (minutos)" ayuda="No cuenta como trabajado.">{(id) => <input id={id} type="number" min={0} className="campo" value={editando.almuerzo_minutos} onChange={(e) => setEditando({ ...editando, almuerzo_minutos: Number(e.target.value) })} />}</Campo>
              <Campo etiqueta="Tolerancia (minutos)" ayuda="Gracia antes de contar tardanza.">{(id) => <input id={id} type="number" min={0} className="campo" value={editando.tolerancia_minutos} onChange={(e) => setEditando({ ...editando, tolerancia_minutos: Number(e.target.value) })} />}</Campo>
            </div>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-azul" checked={editando.por_defecto} onChange={(e) => setEditando({ ...editando, por_defecto: e.target.checked })} />Usar para quien no tenga horario asignado</label>
          </div>
        )}
      </Modal>
    </div>
  );
}

export default function Asistencia() {
  const { esAdmin, veAsistenciaEquipo } = useSesion();
  const gestiona = veAsistenciaEquipo;
  const [params, setParams] = useSearchParams();
  const [persona, setPersona] = useState(null);
  const ver = params.get("ver") || (gestiona ? "hoy" : "mia");
  const opciones = [
    gestiona && { valor: "hoy", etiqueta: "Hoy" },
    gestiona && { valor: "equipo", etiqueta: "Equipo en el mes" },
    { valor: "mia", etiqueta: "Mi asistencia" },
    { valor: "permisos", etiqueta: "Permisos" },
    esAdmin && { valor: "horarios", etiqueta: "Horarios" },
  ].filter(Boolean);
  const verPersona = (id) => setPersona(id);
  return (
    <div className="space-y-5">
      <Cabecera titulo="Asistencia" descripcion="Entrada, pausas y salida de cada día; tardanzas, ausencias, horas extra, permisos y vacaciones." />
      <Pestanas opciones={opciones} valor={ver} onCambio={(v) => { setPersona(null); setParams({ ver: v }); }} />
      {persona ? (
        <div className="space-y-3">
          <button type="button" className="text-sm font-medium text-azul hover:underline" onClick={() => setPersona(null)}>← Volver</button>
          <MesPersona usuario={persona} puedeCorregir />
          <p className="text-sm text-gris"><Link to={`/ficha?usuario=${persona}`} className="text-azul hover:underline">Ver su ficha de productividad completa</Link></p>
        </div>
      ) : ver === "hoy" ? <Hoy onVer={verPersona} />
        : ver === "equipo" ? <MesEquipo onVer={verPersona} />
          : ver === "permisos" ? <Permisos gestiona={gestiona} />
            : ver === "horarios" ? <Horarios />
              : <MesPersona />}
      {ver === "mia" && !persona && <p className="flex items-center gap-2 text-sm text-gris"><CalendarClock className="size-4" />Marca tu jornada arriba, junto al buscador. Si olvidas marcar, tu supervisor lo corrige.</p>}
    </div>
  );
}
