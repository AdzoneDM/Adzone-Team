// Un proyecto: avance, tareas (lista, tablero o cronograma), órdenes, conversación y números.
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, ClipboardList, ListChecks, Pencil, Plus, Trash2 } from "lucide-react";
import { comentarProyecto, comentariosProyecto, detalleProyecto, eliminarProyecto, equipo as cargarEquipo, obtenerProyecto } from "@/lib/api";
import { ESTADOS, dinero, fechaCorta, horas, hoyISO } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import Comentarios from "@/components/Comentarios";
import Cronograma from "@/components/Cronograma";
import { Alerta, Boton, Cargando, Panel, Pestanas, Vacio, cx, useAviso, useConfirmar } from "@/components/ui";
import FormOrden from "@/features/ordenes/FormOrden";
import { TarjetaOrden } from "@/features/ordenes/piezas";
import { DetalleTarea, Progreso, Vencimiento } from "@/features/tareas/componentes";
import FormTarea from "@/features/tareas/FormTarea";
import BotonCronometro from "@/features/tiempo/BotonCronometro";
import { AvanceProyecto, EstadoProyecto, FormProyecto } from "./piezas";

const COLOR_TAREA = {
  PENDIENTE: ["#5b6478", "#eef1f6"], EN_PROGRESO: ["#224b9a", "#e6edfa"], EN_REVISION: ["#7a5000", "#fff4d6"],
  COMPLETADA: ["#0d7a5f", "#e3f5ee"], CANCELADA: ["#8a94a8", "#f3f4f7"],
};

function Numero({ etiqueta, valor, tono }) {
  return <div className="rounded-xl border border-linea bg-white px-4 py-3"><p className="text-sm text-gris">{etiqueta}</p><p className={cx("font-display text-xl font-semibold num", tono)}>{valor}</p></div>;
}

export default function ProyectoDetalle() {
  const { id } = useParams();
  const { puedeValidar } = useSesion();
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [p, setP] = useState(null);
  const [d, setD] = useState(null);
  const [comentarios, setComentarios] = useState([]);
  const [gente, setGente] = useState([]);
  const [error, setError] = useState("");
  const [modal, setModal] = useState(null);
  const [tarea, setTarea] = useState(null);
  const vista = params.get("ver") || "tareas";

  const cargar = useCallback(() => {
    Promise.all([obtenerProyecto(id), detalleProyecto(id), comentariosProyecto(id)])
      .then(([a, b, c]) => { setP(a); setD(b); setComentarios(c); }).catch((e) => setError(e.message));
  }, [id]);
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => { if (puedeValidar) cargarEquipo().then(setGente).catch(() => {}); }, [puedeValidar]);

  if (error) return <Alerta>{error}</Alerta>;
  if (!p || !d) return <Cargando />;
  const tareas = d.tareas.filter((t) => t.estado !== "CANCELADA");
  const vencidas = tareas.filter((t) => ["PENDIENTE", "EN_PROGRESO"].includes(t.estado) && t.fecha_limite < hoyISO()).length;
  const fin = d.finanzas;

  return (
    <div>
      <Link to="/proyectos" className="mb-3 inline-flex items-center gap-1.5 text-sm font-medium text-azul hover:underline"><ArrowLeft className="size-4" />Proyectos</Link>
      <header className="mb-5 rounded-2xl border border-linea bg-white p-5">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="text-sm text-gris num">{p.codigo}</span>
          <EstadoProyecto estado={p.estado} />
          {p.departamento_nombre && <span className="rounded-full px-2.5 py-0.5 text-xs font-medium" style={{ color: p.color, backgroundColor: p.color_fondo }}>{p.departamento_nombre}</span>}
        </div>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold leading-tight md:text-[28px]">{p.nombre}</h1>
            <p className="mt-1 text-gris"><Link to={`/clientes/${p.cliente}`} className="font-medium text-tinta hover:text-azul">{p.cliente_nombre}</Link>
              {p.fecha_inicio && ` · ${fechaCorta(p.fecha_inicio)}`}{p.fecha_fin && ` → ${fechaCorta(p.fecha_fin)}`}</p>
            <p className="mt-1 text-sm text-gris">Responsable: <span className="text-tinta">{p.responsable_nombre || "—"}</span>{p.miembros_nombres.length > 0 && ` · Equipo: ${p.miembros_nombres.join(", ")}`}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {puedeValidar && <Boton icono={Plus} onClick={() => setModal("tarea")}>Tarea</Boton>}
            <Boton variante="secundario" icono={ClipboardList} onClick={() => setModal("orden")}>Orden</Boton>
            <BotonCronometro proyecto={p.id} />
            {p.puedo_gestionar && <Boton variante="secundario" icono={Pencil} onClick={() => setModal("editar")}>Editar</Boton>}
          </div>
        </div>
        {p.descripcion && <p className="mt-3 whitespace-pre-line text-[15px]">{p.descripcion}</p>}
        <AvanceProyecto progreso={p.progreso} ancho="h-2 flex-1" className="mt-4 flex w-full max-w-lg" />
      </header>

      <div className={cx("mb-5 grid grid-cols-2 gap-3", fin ? "md:grid-cols-4 xl:grid-cols-7" : "md:grid-cols-4")}>
        <Numero etiqueta="Tareas" valor={`${p.progreso.validadas}/${p.progreso.tareas}`} />
        <Numero etiqueta="Vencidas" valor={vencidas} tono={vencidas ? "text-rojo" : ""} />
        <Numero etiqueta="Órdenes abiertas" valor={p.progreso.ordenes_abiertas} />
        <Numero etiqueta="Horas trabajadas" valor={horas(d.horas * 60)} />
        {fin && <>
          <Numero etiqueta="Vendido" valor={dinero(fin.presupuesto)} />
          <Numero etiqueta="Facturado" valor={dinero(fin.facturado)} />
          <Numero etiqueta="Margen" valor={fin.facturado > 0 ? `${dinero(fin.margen)} · ${fin.margen_pct}%` : "—"} tono={fin.margen < 0 ? "text-rojo" : "text-verde"} />
        </>}
      </div>

      <Pestanas className="mb-4 max-w-xl" valor={vista} onCambio={(v) => { if (v === "tareas") params.delete("ver"); else params.set("ver", v); setParams(params, { replace: true }); }} opciones={[
        { valor: "tareas", etiqueta: "Tareas", cuenta: tareas.length },
        { valor: "cronograma", etiqueta: "Cronograma" },
        { valor: "ordenes", etiqueta: "Órdenes", cuenta: d.ordenes.length },
        { valor: "conversacion", etiqueta: "Conversación", cuenta: comentarios.length },
      ]} />

      {vista === "tareas" && (tareas.length === 0 ? (
        <Vacio icono={ListChecks} titulo="El proyecto no tiene tareas" accion={puedeValidar && <Boton icono={Plus} onClick={() => setModal("tarea")}>Primera tarea</Boton>}>
          Divide el proyecto en tareas con responsable, fechas y pasos. Cuentan para el puntaje cuando se validan.
        </Vacio>
      ) : (
        <div className="grid gap-3 lg:grid-cols-4">
          {["PENDIENTE", "EN_PROGRESO", "EN_REVISION", "COMPLETADA"].map((e) => (
            <section key={e} className="rounded-xl bg-linea-suave/70 p-2">
              <h2 className="flex items-center justify-between px-1.5 pb-2 text-sm font-semibold">{ESTADOS[e]}<span className="rounded-full bg-white px-2 text-xs text-gris num">{tareas.filter((t) => t.estado === e).length}</span></h2>
              <ul className="space-y-2">
                {tareas.filter((t) => t.estado === e).map((t) => (
                  <li key={t.id}>
                    <button type="button" onClick={() => setTarea(t)} className="block w-full rounded-xl border border-linea bg-white p-3 text-left hover:border-azul/40">
                      <p className="font-medium leading-snug">{t.titulo}</p>
                      <p className="mt-0.5 truncate text-sm text-gris">{[t.colaborador_nombre, ...(t.companeros_nombres || [])].join(", ")}</p>
                      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1"><Vencimiento tarea={t} /><Progreso progreso={t.progreso} />
                        {t.horas_estimadas && <span className="text-xs text-gris">{Number(t.horas_estimadas)} h</span>}</div>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      ))}

      {vista === "cronograma" && (
        <Cronograma filas={tareas.map((t) => ({
          id: t.id, etiqueta: t.titulo, sub: t.colaborador_nombre, inicio: t.fecha_inicio || t.fecha_creacion.slice(0, 10), fin: t.fecha_limite,
          color: COLOR_TAREA[t.estado][0], fondo: COLOR_TAREA[t.estado][1], onClick: () => setTarea(t),
          progreso: t.progreso ? (100 * t.progreso.hechos) / t.progreso.total : t.estado === "COMPLETADA" ? 100 : 0,
          alerta: ["PENDIENTE", "EN_PROGRESO"].includes(t.estado) && t.fecha_limite < hoyISO(),
        }))} />
      )}

      {vista === "ordenes" && (d.ordenes.length === 0 ? (
        <Vacio icono={ClipboardList} titulo="Sin órdenes de trabajo" accion={<Boton icono={Plus} onClick={() => setModal("orden")}>Nueva orden</Boton>}>
          Pide desde aquí la impresión, la grabación o el desarrollo de este proyecto y quedará conectada.
        </Vacio>
      ) : <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{d.ordenes.map((o) => <li key={o.id}><TarjetaOrden orden={o} onAbrir={() => navigate(`/ordenes/${o.id}`)} /></li>)}</ul>)}

      {vista === "conversacion" && (
        <Panel><Comentarios lista={comentarios} onEnviar={async (texto) => { await comentarProyecto(p.id, texto); setComentarios(await comentariosProyecto(p.id)); }} /></Panel>
      )}

      {p.puedo_gestionar && d.tareas.length === 0 && d.ordenes.length === 0 && (
        <Boton variante="fantasma" icono={Trash2} className="mt-6 text-rojo" onClick={async () => {
          if (!(await confirmar({ titulo: "¿Borrar este proyecto?", mensaje: "No tiene tareas ni órdenes.", boton: "Borrar", peligro: true }))) return;
          try { await eliminarProyecto(p.id); avisar("Proyecto borrado."); navigate("/proyectos"); } catch (e) { avisar(e.message, "rojo"); }
        }}>Borrar proyecto</Boton>
      )}

      <FormProyecto abierto={modal === "editar"} inicial={p} onCerrar={() => setModal(null)} onGuardado={() => { setModal(null); avisar("Proyecto actualizado."); cargar(); }} />
      <FormTarea abierto={modal === "tarea"} inicial={{ proyecto: p.id, cliente: p.cliente_nombre }} gente={gente} onCerrar={() => setModal(null)}
        onGuardada={(msg) => { setModal(null); avisar(msg); cargar(); }} />
      <FormOrden abierto={modal === "orden"} inicial={{ cliente: p.cliente, proyecto: p.id }} onCerrar={() => setModal(null)}
        onGuardada={(o) => { setModal(null); avisar(`${o.numero} pedida.`); cargar(); }} />
      <DetalleTarea tarea={tarea} abierto={!!tarea} onCerrar={() => setTarea(null)} onCambio={(t) => { setTarea(t); cargar(); }}
        pie={tarea && <div className="flex w-full flex-wrap justify-end gap-2">
          {tarea.soy_participante && ["PENDIENTE", "EN_PROGRESO"].includes(tarea.estado) && <>
            <BotonCronometro tarea={tarea.id} />
            <Link to={`/mis-tareas?tarea=${tarea.id}`} className="inline-flex h-11 items-center rounded-lg bg-amarillo px-4 text-[15px] font-medium">Entregar</Link>
          </>}
          {tarea.puedo_gestionar && !["COMPLETADA", "CANCELADA"].includes(tarea.estado) && <Boton variante="secundario" icono={Pencil} onClick={() => { setModal("editarTarea"); }}>Editar</Boton>}
        </div>} />
      <FormTarea abierto={modal === "editarTarea"} inicial={tarea} gente={gente} onCerrar={() => setModal(null)}
        onGuardada={(msg) => { setModal(null); setTarea(null); avisar(msg); cargar(); }} />
    </div>
  );
}
