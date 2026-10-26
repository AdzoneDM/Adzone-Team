// Tiempo: mi semana (cronómetro y horas anotadas), la carga del equipo y el reporte de horas.
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ChevronLeft, ChevronRight, Clock, Pencil, Play, Plus, Square, Trash2 } from "lucide-react";
import { cargaSemanal, eliminarRegistro, guardarRegistro, listarTareas, miSemana, reporteTiempo } from "@/lib/api";
import { diaSemana, fechaCorta, horas, hoyISO, lunesDe, reloj, sumarDias } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import { Alerta, Avatar, Boton, Cabecera, Campo, Cargando, Modal, Panel, Pestanas, Vacio, cx, useAviso, useConfirmar } from "@/components/ui";
import { nombreRegistro, useCronometro } from "./cronometro";

function SelectorSemana({ fecha, onCambio }) {
  const lunes = lunesDe(fecha);
  const esta = lunes === lunesDe(hoyISO());
  return (
    <div className="inline-flex h-11 items-center rounded-lg border border-linea bg-white">
      <button type="button" onClick={() => onCambio(sumarDias(lunes, -7))} className="flex h-full items-center px-2.5 text-gris hover:text-azul" aria-label="Semana anterior"><ChevronLeft className="size-4" /></button>
      <span className="min-w-[10rem] text-center text-sm font-medium">{esta ? "Esta semana" : `${fechaCorta(lunes)} – ${fechaCorta(sumarDias(lunes, 6))}`}</span>
      <button type="button" onClick={() => onCambio(sumarDias(lunes, 7))} disabled={esta} className="flex h-full items-center px-2.5 text-gris hover:text-azul disabled:opacity-30" aria-label="Semana siguiente"><ChevronRight className="size-4" /></button>
    </div>
  );
}

function FormRegistro({ abierto, inicial, onCerrar, onGuardado }) {
  const [tareas, setTareas] = useState([]);
  const [f, setF] = useState({});
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  useEffect(() => {
    if (!abierto) return;
    setError("");
    setF(inicial?.id ? { ...inicial, horas: Math.floor(inicial.minutos / 60), mins: inicial.minutos % 60, tarea: inicial.tarea ? String(inicial.tarea) : "" }
      : { fecha: hoyISO(), horas: 1, mins: 0, tarea: "", descripcion: "", facturable: true });
    listarTareas({ ambito: "mias", estado: "" }).then((l) => setTareas(l.filter((t) => t.estado !== "CANCELADA" && (t.estado !== "COMPLETADA" || t.fecha_limite >= sumarDias(hoyISO(), -31))))).catch(() => {});
  }, [abierto, inicial]);
  const guardar = async (e) => {
    e.preventDefault();
    const minutos = Number(f.horas || 0) * 60 + Number(f.mins || 0);
    if (minutos < 1) return setError("Anota cuánto tiempo trabajaste.");
    if (minutos > 720) return setError("Como máximo 12 horas por registro.");
    if (!f.tarea && !f.descripcion?.trim()) return setError("Elige la tarea o escribe en qué trabajaste.");
    setGuardando(true); setError("");
    try {
      await guardarRegistro({ id: f.id, minutos, tarea: f.tarea ? Number(f.tarea) : null, descripcion: (f.descripcion || "").trim(), facturable: !!f.facturable, ...(f.id ? {} : { fecha: f.fecha }) });
      onGuardado();
    } catch (err) { setError(err.message); }
    setGuardando(false);
  };
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={inicial?.id ? "Editar tiempo" : "Anotar tiempo"} ancho="max-w-lg"
      descripcion="Para lo que hiciste sin cronómetro: una reunión, una visita, una grabación."
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton type="submit" form="form-registro" cargando={guardando}>Guardar</Boton></>}>
      <form id="form-registro" onSubmit={guardar} className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        <Campo etiqueta="Tarea">
          {(id) => <select id={id} className="campo" value={f.tarea || ""} onChange={(e) => setF({ ...f, tarea: e.target.value })}>
            <option value="">Sin tarea (escribe abajo qué hiciste)</option>
            {tareas.map((t) => <option key={t.id} value={t.id}>{t.titulo}{t.cliente ? ` · ${t.cliente}` : ""}</option>)}</select>}
        </Campo>
        <Campo etiqueta="Qué hiciste">{(id) => <input id={id} className="campo" value={f.descripcion || ""} onChange={(e) => setF({ ...f, descripcion: e.target.value })} maxLength={255} placeholder="Ej.: Reunión con el cliente" />}</Campo>
        <div className="grid grid-cols-3 gap-3">
          {!inicial?.id && <Campo etiqueta="Día">{(id) => <input id={id} type="date" className="campo" max={hoyISO()} min={sumarDias(hoyISO(), -31)} value={f.fecha || ""} onChange={(e) => setF({ ...f, fecha: e.target.value })} />}</Campo>}
          <Campo etiqueta="Horas">{(id) => <input id={id} type="number" min={0} max={12} className="campo" value={f.horas ?? 0} onChange={(e) => setF({ ...f, horas: e.target.value })} />}</Campo>
          <Campo etiqueta="Minutos">{(id) => <select id={id} className="campo" value={f.mins ?? 0} onChange={(e) => setF({ ...f, mins: e.target.value })}>{[0, 15, 30, 45].map((m) => <option key={m}>{m}</option>)}</select>}</Campo>
        </div>
        <label className="flex items-center gap-2 text-[15px]"><input type="checkbox" checked={!!f.facturable} onChange={(e) => setF({ ...f, facturable: e.target.checked })} className="size-4 accent-azul" /> Trabajo para un cliente (facturable)</label>
      </form>
    </Modal>
  );
}

function MiSemana() {
  const { activo, minutos, iniciar, detener } = useCronometro();
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const [fecha, setFecha] = useState(hoyISO());
  const [d, setD] = useState(null);
  const [form, setForm] = useState(null);
  const [que, setQue] = useState("");
  const cargar = useCallback(() => miSemana(fecha).then(setD).catch((e) => avisar(e.message, "rojo")), [fecha, avisar]);
  useEffect(() => { cargar(); }, [cargar, activo?.id]);
  useEffect(() => { window.addEventListener("adzone:tiempo", cargar); return () => window.removeEventListener("adzone:tiempo", cargar); }, [cargar]);
  if (!d) return <Cargando />;
  const maxDia = Math.max(480, ...d.dias.map((x) => x.minutos));
  const pct = Math.round((100 * d.total) / d.capacidad);
  const porDia = d.dias.map((dia) => ({ ...dia, registros: d.registros.filter((r) => r.dia === dia.fecha) })).filter((x) => x.registros.length).reverse();
  return (
    <div className="space-y-5">
      <Panel>
        {activo ? (
          <div className="flex flex-wrap items-center gap-4">
            <span className="relative flex size-3"><span className="absolute inline-flex size-full animate-ping rounded-full bg-rojo opacity-60" /><span className="relative inline-flex size-3 rounded-full bg-rojo" /></span>
            <div className="min-w-0 flex-1"><p className="text-sm text-gris">Trabajando en</p><p className="truncate font-medium">{nombreRegistro(activo)}</p></div>
            <p className="font-display text-3xl font-semibold num">{reloj(minutos)}</p>
            <Boton variante="peligro" icono={Square} onClick={detener}>Detener</Boton>
          </div>
        ) : (
          <form onSubmit={(e) => { e.preventDefault(); if (que.trim()) { iniciar({ descripcion: que.trim() }); setQue(""); } }} className="flex flex-col gap-2 sm:flex-row">
            <input className="campo" value={que} onChange={(e) => setQue(e.target.value)} placeholder="¿En qué estás trabajando? (o empieza el cronómetro desde una tarea)" aria-label="En qué trabajas" />
            <Boton type="submit" icono={Play} disabled={!que.trim()}>Empezar</Boton>
          </form>
        )}
      </Panel>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <SelectorSemana fecha={fecha} onCambio={setFecha} />
        <Boton variante="secundario" icono={Plus} onClick={() => setForm({})}>Anotar tiempo</Boton>
      </div>

      <Panel>
        <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
          <div><p className="text-sm text-gris">Total de la semana</p><p className="font-display text-3xl font-semibold num">{horas(d.total)}</p></div>
          <p className="text-sm text-gris">{pct}% de tus {d.capacidad / 60} h semanales</p>
        </div>
        <div className="grid grid-cols-7 items-end gap-2" style={{ height: 140 }}>
          {d.dias.map((x) => (
            <div key={x.fecha} className="flex h-full flex-col items-center justify-end gap-1">
              <span className="text-xs text-gris num">{x.minutos ? reloj(x.minutos) : ""}</span>
              <span className={cx("w-full max-w-12 rounded-t-md", x.fecha === hoyISO() ? "bg-amarillo" : "bg-azul/70")} style={{ height: `${Math.max(2, (x.minutos / maxDia) * 100)}%` }} />
              <span className={cx("text-xs capitalize", x.fecha === hoyISO() ? "font-semibold text-tinta" : "text-gris")}>{diaSemana(x.fecha)}</span>
            </div>
          ))}
        </div>
      </Panel>

      {porDia.length === 0 ? <Vacio icono={Clock} titulo="Sin tiempo anotado esta semana">Inicia el cronómetro desde una tarea o una orden, o anota el tiempo a mano.</Vacio> : porDia.map((dia) => (
        <Panel key={dia.fecha} titulo={<span className="capitalize">{diaSemana(dia.fecha, true)} {fechaCorta(dia.fecha)} · <span className="num text-gris">{horas(dia.minutos)}</span></span>} cuerpo="p-0">
          <ul className="divide-y divide-linea-suave">
            {dia.registros.map((r) => (
              <li key={r.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-5 py-3">
                <div className="min-w-0 basis-full sm:basis-auto sm:flex-1">
                  <p className="truncate font-medium">{nombreRegistro(r)}</p>
                  <p className="truncate text-sm text-gris">{[r.cliente, r.tarea_titulo && r.descripcion].filter(Boolean).join(" · ") || (r.facturable ? "Facturable" : "Interno")}</p>
                </div>
                <span className={cx("mr-auto font-medium num sm:mr-0", r.corriendo && "text-rojo")}>{r.corriendo ? "corriendo" : reloj(r.minutos)}</span>
                {!r.corriendo && <>
                  <Boton variante="fantasma" tam="sm" icono={Play} aria-label="Seguir con esto" title="Seguir con esto" onClick={() => iniciar({ tarea: r.tarea, orden: r.tarea ? null : r.orden, proyecto: r.tarea || r.orden ? null : r.proyecto, descripcion: r.descripcion })} />
                  <Boton variante="fantasma" tam="sm" icono={Pencil} aria-label="Editar" onClick={() => setForm(r)} />
                  <Boton variante="fantasma" tam="sm" icono={Trash2} aria-label="Borrar" className="text-rojo" onClick={async () => {
                    if (await confirmar({ titulo: "¿Borrar este registro?", mensaje: `${nombreRegistro(r)} · ${horas(r.minutos)}`, boton: "Borrar", peligro: true })) { await eliminarRegistro(r.id); cargar(); }
                  }} />
                </>}
              </li>
            ))}
          </ul>
        </Panel>
      ))}
      <FormRegistro abierto={!!form} inicial={form} onCerrar={() => setForm(null)} onGuardado={() => { setForm(null); avisar("Tiempo guardado."); cargar(); }} />
    </div>
  );
}

function CargaEquipo() {
  const [fecha, setFecha] = useState(hoyISO());
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { cargaSemanal(fecha).then(setD).catch((e) => setError(e.message)); }, [fecha]);
  if (error) return <Alerta>{error}</Alerta>;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SelectorSemana fecha={fecha} onCambio={setFecha} />
        <p className="text-sm text-gris"><span className="mr-1 inline-block size-2.5 rounded-sm bg-azul" />Anotado <span className="ml-3 mr-1 inline-block size-2.5 rounded-sm bg-azul/30" />Pendiente estimado</p>
      </div>
      {!d ? <Cargando /> : (
        <Panel cuerpo="p-0">
          <ul className="divide-y divide-linea-suave">
            {d.personas.map((p) => {
              const reg = (100 * p.registrado) / p.capacidad;
              const pen = (100 * p.pendiente) / p.capacidad;
              const alto = p.carga_pct > 100;
              return (
                <li key={p.id} className="grid gap-2 px-5 py-3.5 md:grid-cols-[260px_minmax(0,1fr)_140px] md:items-center md:gap-6">
                  <div className="flex items-center gap-3">
                    <Avatar nombre={p.nombre} tam="sm" />
                    <div className="min-w-0"><p className="truncate font-medium">{p.nombre}</p><p className="truncate text-xs text-gris">{p.puesto || "Sin puesto"}</p></div>
                  </div>
                  <div className="relative h-3 overflow-hidden rounded-full bg-linea-suave" role="img" aria-label={`${p.carga_pct}% de su capacidad`}>
                    <span className="absolute inset-y-0 left-0 bg-azul" style={{ width: `${Math.min(reg, 100)}%` }} />
                    <span className="absolute inset-y-0 bg-azul/30" style={{ left: `${Math.min(reg, 100)}%`, width: `${Math.max(0, Math.min(pen, 100 - Math.min(reg, 100)))}%` }} />
                  </div>
                  <p className="text-sm md:text-right">
                    <span className={cx("font-semibold num", alto ? "text-rojo" : p.carga_pct >= 85 ? "text-[#a86a00]" : "text-tinta")}>{p.carga_pct}%</span>
                    <span className="text-gris"> · {reloj(p.registrado)} + {reloj(p.pendiente)} / {p.capacidad / 60} h</span>
                    {alto && <span className="block text-xs font-medium text-rojo">Sobrecargado: reparte o mueve fechas</span>}
                  </p>
                </li>
              );
            })}
          </ul>
        </Panel>
      )}
      <p className="text-sm text-gris">El pendiente sale de las horas estimadas de sus tareas abiertas que vencen hasta el domingo. Pon horas estimadas al asignar para que esta vista sea precisa.</p>
    </div>
  );
}

function Reporte() {
  const [agrupar, setAgrupar] = useState("proyecto");
  const [desde, setDesde] = useState(hoyISO().slice(0, 8) + "01");
  const [hasta, setHasta] = useState(hoyISO());
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { reporteTiempo({ agrupar, desde, hasta }).then(setD).catch((e) => setError(e.message)); }, [agrupar, desde, hasta]);
  const max = useMemo(() => Math.max(1, ...(d?.filas || []).map((f) => f.minutos)), [d]);
  if (error) return <Alerta>{error}</Alerta>;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <Campo etiqueta="Agrupar por">{(id) => <select id={id} className="campo h-11 w-auto" value={agrupar} onChange={(e) => setAgrupar(e.target.value)}>
          <option value="proyecto">Proyecto</option><option value="cliente">Cliente</option><option value="orden">Orden de trabajo</option><option value="persona">Persona</option><option value="departamento">Departamento</option></select>}</Campo>
        <Campo etiqueta="Desde">{(id) => <input id={id} type="date" className="campo h-11" value={desde} onChange={(e) => setDesde(e.target.value)} />}</Campo>
        <Campo etiqueta="Hasta">{(id) => <input id={id} type="date" className="campo h-11" value={hasta} onChange={(e) => setHasta(e.target.value)} />}</Campo>
        {d && <p className="ml-auto text-sm text-gris">Total: <span className="font-semibold text-tinta">{horas(d.total)}</span></p>}
      </div>
      {!d ? <Cargando /> : d.filas.length === 0 ? <Vacio icono={Clock} titulo="Sin horas en ese periodo" /> : (
        <Panel cuerpo="p-0">
          <table className="tabla">
            <thead><tr><th>Nombre</th><th className="w-1/3">Horas</th><th className="text-right">Facturable</th><th className="hidden text-right md:table-cell">Personas</th></tr></thead>
            <tbody>
              {d.filas.map((f) => (
                <tr key={f.clave}>
                  <td className="font-medium">{f.nombre}</td>
                  <td><div className="flex items-center gap-2"><span className="h-2 rounded-full bg-azul" style={{ width: `${(70 * f.minutos) / max}%` }} /><span className="text-sm num">{reloj(f.minutos)}</span></div></td>
                  <td className="text-right text-sm num">{f.minutos ? Math.round((100 * f.facturable) / f.minutos) : 0}%</td>
                  <td className="hidden text-right text-sm num md:table-cell">{f.personas}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}
    </div>
  );
}

export default function MiTiempo() {
  const { puedeValidar, esFinanzas } = useSesion();
  const [params, setParams] = useSearchParams();
  const ver = params.get("ver") || "semana";
  const opciones = [{ valor: "semana", etiqueta: "Mi semana" }];
  if (puedeValidar) opciones.push({ valor: "carga", etiqueta: "Carga del equipo" });
  if (puedeValidar || esFinanzas) opciones.push({ valor: "reporte", etiqueta: "Reporte de horas" });
  return (
    <div className="max-w-5xl">
      <Cabecera titulo="Tiempo" descripcion="Cuánto toma cada trabajo. Sirve para repartir mejor la carga y saber qué proyectos dejan ganancia." />
      {opciones.length > 1 && <Pestanas className="mb-5 max-w-lg" valor={ver} onCambio={(v) => { if (v === "semana") params.delete("ver"); else params.set("ver", v); setParams(params, { replace: true }); }} opciones={opciones} />}
      {ver === "carga" && puedeValidar ? <CargaEquipo /> : ver === "reporte" && (puedeValidar || esFinanzas) ? <Reporte /> : <MiSemana />}
    </div>
  );
}
