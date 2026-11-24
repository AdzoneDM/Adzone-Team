import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Ban, Hand, ListChecks, Paperclip, Play, Plus, Send, Target, Unlock } from "lucide-react";
import { bloquearTarea, desbloquearTarea, iniciarTarea, listarTareas, miDisponibilidad, miResumen, pedirTrabajo } from "@/lib/api";
import { mesActual } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import { refrescarAvisos } from "@/app/Estructura";
import { DetalleTarea, EntregarModal, EquipoTarea, Evidencias, Progreso, Vencimiento } from "@/features/tareas/componentes";
import FormTareaPropia from "@/features/tareas/FormTareaPropia";
import { Alerta, Boton, Campo, Cargando, EstadoTarea, Estrellas, Modal, Pestanas, PrioridadTarea, SelectorMes, Vacio, cx, useAviso } from "@/components/ui";
import { MiMes } from "@/features/inicio/Inicio";
import BotonCronometro from "@/features/tiempo/BotonCronometro";
import { useCronometro } from "@/features/tiempo/cronometro";
import { useNovedades } from "@/lib/novedades";

/** Bloquear: qué impide seguir. Le llega a su supervisor. */
function BloquearModal({ tarea, onCerrar, onHecho }) {
  const avisar = useAviso();
  const [motivo, setMotivo] = useState("");
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { setMotivo(""); setError(""); }, [tarea]);
  const guardar = async () => {
    setCargando(true); setError("");
    try { onHecho(await bloquearTarea(tarea.id, motivo)); avisar("Marcada como bloqueada. Tu supervisor ya lo sabe."); }
    catch (e) { setError(e.message); }
    setCargando(false);
  };
  return (
    <Modal abierto={!!tarea} onCerrar={onCerrar} titulo="¿Qué impide seguir?" descripcion={tarea?.titulo}
      pie={<><Boton variante="fantasma" onClick={onCerrar}>Cancelar</Boton><Boton variante="peligro" icono={Ban} onClick={guardar} cargando={cargando}>Marcar bloqueada</Boton></>}>
      <Campo etiqueta="Motivo" ayuda="Ej.: espero el logo del cliente, falta material, necesito una aprobación.">
        {(id) => <textarea id={id} className="campo" rows={3} value={motivo} onChange={(e) => setMotivo(e.target.value)} autoFocus />}
      </Campo>
      {error && <Alerta className="mt-3">{error}</Alerta>}
    </Modal>
  );
}

function FilaTarea({ tarea, onAbrir, onIniciar, onEntregar, onBloquear, onDesbloquear, iniciando }) {
  const devuelta = tarea.comentario_revision && tarea.estado === "EN_PROGRESO";
  const bloqueada = tarea.estado === "BLOQUEADA";
  return (
    <li data-guia="tarea" className={cx("rounded-xl border bg-white", devuelta || bloqueada ? "border-rojo/40" : "border-linea")}>
      <div className="grid gap-3 p-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-center md:gap-6 md:px-5">
        <button type="button" onClick={() => onAbrir(tarea)} className="min-w-0 text-left">
          <p className="font-medium leading-snug text-tinta hover:text-azul">{tarea.titulo}</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1.5">
            <Vencimiento tarea={tarea} />
            <PrioridadTarea prioridad={tarea.prioridad} />
            {tarea.estado !== "PENDIENTE" && <EstadoTarea estado={tarea.estado} />}
            {tarea.kpi_nombre && <span className="flex min-w-0 items-center gap-1 text-sm text-gris"><Target className="size-3.5 shrink-0" /><span className="truncate">{tarea.kpi_nombre}</span></span>}
            {tarea.estado === "COMPLETADA" && <Estrellas valor={tarea.calificacion_calidad} />}
            <Progreso progreso={tarea.progreso} />
            {tarea.referencias?.length > 0 && <span className="inline-flex items-center gap-1 text-sm font-medium text-azul"><Paperclip className="size-3.5" aria-hidden />{tarea.referencias.length} referencia{tarea.referencias.length > 1 ? "s" : ""}</span>}
          </div>
          <EquipoTarea tarea={tarea} className="mt-1.5" />
        </button>
        {(tarea.estado === "PENDIENTE" || tarea.estado === "EN_PROGRESO") && (
          <div className="grid grid-cols-2 gap-2 md:flex">
            {/* «Empezar» pone el cronómetro; ya empezada, el botón permite pausarlo y retomarlo */}
            {tarea.estado === "PENDIENTE"
              ? <Boton variante="secundario" icono={Play} onClick={() => onIniciar(tarea)} cargando={iniciando === tarea.id}>Empezar</Boton>
              : <BotonCronometro tarea={tarea.id} />}
            <Boton variante="acento" icono={Send} onClick={() => onEntregar(tarea)}>
              {devuelta ? "Entregar de nuevo" : "Entregar"}
            </Boton>
            <Boton variante="fantasma" icono={Ban} onClick={() => onBloquear(tarea)} className="col-span-2 md:col-span-1">Bloqueada</Boton>
          </div>
        )}
        {bloqueada && (
          <Boton variante="secundario" icono={Unlock} onClick={() => onDesbloquear(tarea)}>Ya puedo seguir</Boton>
        )}
      </div>
      {bloqueada && (
        <div className="border-t border-rojo/20 bg-rojo-50 px-4 py-3 text-sm text-[#7a1610] md:px-5">
          <span className="font-medium">Bloqueada: </span><span className="whitespace-pre-line">{tarea.motivo_bloqueo}</span>
        </div>
      )}
      {devuelta && (
        <div className="border-t border-rojo/20 bg-rojo-50 px-4 py-3 text-sm text-[#7a1610] md:px-5">
          <span className="font-medium">Para corregir: </span><span className="whitespace-pre-line">{tarea.comentario_revision}</span>
        </div>
      )}
      {tarea.estado === "EN_REVISION" && (tarea.evidencias?.length > 0) && (
        <div className="border-t border-linea-suave px-4 py-3 md:px-5"><Evidencias tarea={tarea} compacto /></div>
      )}
    </li>
  );
}

export default function MisTareas() {
  const { usuario } = useSesion();
  const avisar = useAviso();
  const crono = useCronometro();
  const [params, setParams] = useSearchParams();
  const [tareas, setTareas] = useState(null);
  const [resumen, setResumen] = useState(null);
  const [error, setError] = useState("");
  const [mesValidadas, setMesValidadas] = useState(mesActual());
  const [entregando, setEntregando] = useState(null);
  const [iniciando, setIniciando] = useState(null);
  const [pidiendo, setPidiendo] = useState(false);
  const [creando, setCreando] = useState(false); // nueva tarea para mí
  const [bloqueando, setBloqueando] = useState(null);
  const [disp, setDisp] = useState(null);
  const [filtroHacer, setFiltroHacer] = useState("todas"); // dentro de «Por hacer»: todas, vencidas o devueltas para corregir
  const ver = params.get("ver") || "hacer";
  const abierta = params.get("tarea");

  const cargar = useCallback(() => {
    Promise.all([listarTareas({ ambito: "mias" }), miResumen(mesActual()), miDisponibilidad().catch(() => null)])
      .then(([t, r, d]) => { setTareas(t); setResumen(r); setDisp(d); })
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => { cargar(); }, [cargar]);
  // Tareas nuevas, devueltas o validadas aparecen sin recargar la página.
  useNovedades(cargar);

  const grupos = useMemo(() => {
    const lista = tareas || [];
    const porFecha = (a, b) => a.fecha_limite.localeCompare(b.fecha_limite);
    return {
      hacer: lista.filter((t) => t.estado === "PENDIENTE" || t.estado === "EN_PROGRESO" || t.estado === "BLOQUEADA")
        .sort((a, b) => (a.estado === "BLOQUEADA" ? 1 : 0) - (b.estado === "BLOQUEADA" ? 1 : 0)
          || (b.comentario_revision ? 1 : 0) - (a.comentario_revision ? 1 : 0) || porFecha(a, b)),
      revision: lista.filter((t) => t.estado === "EN_REVISION").sort(porFecha),
      validadas: lista.filter((t) => t.estado === "COMPLETADA" && t.fecha_limite.startsWith(mesValidadas)).sort((a, b) => -porFecha(a, b)),
    };
  }, [tareas, mesValidadas]);

  const cambiarVista = (v) => { params.set("ver", v); params.delete("tarea"); setParams(params, { replace: true }); };
  const abrir = (t) => { params.set("tarea", t.id); setParams(params); };
  const cerrar = () => { params.delete("tarea"); setParams(params); };

  const iniciar = async (t) => {
    setIniciando(t.id);
    try {
      const nueva = await iniciarTarea(t.id);
      setTareas((l) => l.map((x) => (x.id === nueva.id ? nueva : x)));
      await crono?.refrescar();
      avisar("Tarea empezada. El cronómetro está corriendo.");
    } catch (e) { avisar(e.message, "rojo"); }
    setIniciando(null);
  };

  const pedir = async () => {
    setPidiendo(true);
    try { const r = await pedirTrabajo(); avisar(r.message); cargar(); } catch (e) { avisar(e.message, "rojo"); }
    setPidiendo(false);
  };
  const reemplazar = (t) => setTareas((l) => l.map((x) => (x.id === t.id ? t : x)));
  const desbloquear = async (t) => {
    try { reemplazar(await desbloquearTarea(t.id, "")); avisar("De vuelta en curso."); } catch (e) { avisar(e.message, "rojo"); }
  };

  if (error) return <Alerta>{error}</Alerta>;
  if (!tareas || !resumen) return <Cargando />;

  const hoyStr = new Date().toLocaleDateString("sv-SE", { timeZone: "America/Santo_Domingo" });
  const esVencida = (t) => t.estado !== "BLOQUEADA" && t.fecha_limite < hoyStr;   // pasó su fecha límite sin entregarse
  const esDevuelta = (t) => !!t.comentario_revision;                               // el supervisor la devolvió para corregir
  const nVencidas = grupos.hacer.filter(esVencida).length;
  const nDevueltas = grupos.hacer.filter(esDevuelta).length;
  const base = grupos[ver] || grupos.hacer;
  const lista = ver === "hacer" && filtroHacer === "vencidas" ? base.filter(esVencida) : ver === "hacer" && filtroHacer === "devueltas" ? base.filter(esDevuelta) : base;
  const soloBloqueadas = ver === "hacer" && lista.length > 0 && lista.every((t) => t.estado === "BLOQUEADA");
  const detalle = abierta ? tareas.find((t) => String(t.id) === abierta) : null;

  return (
    <div className="space-y-6">
      <MiMes resumen={resumen} nombre={usuario.nombre} />

      {disp?.en_espera && (
        <Alerta tono="amarillo" className="border border-amarillo bg-amarillo-50 text-[#7a5000]">
          <span className="font-medium">En espera de asignación</span> desde las {new Date(disp.desde).toLocaleTimeString("es-DO", { hour: "numeric", minute: "2-digit" })}: tu supervisor ya lo sabe.
          {" "}Mientras tanto, <Link to="/colaboracion?ver=actividades" className="font-medium underline">registra lo que hagas</Link> (archivos, estudio, capacitación, apoyo a compañeros).
        </Alerta>
      )}
      {soloBloqueadas && !disp?.en_espera && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amarillo bg-amarillo-50 px-4 py-3 text-[15px] text-[#7a5000]">
          <span>Solo te quedan tareas bloqueadas. Avisa a tu supervisor que puedes tomar otra cosa.</span>
          <Boton variante="acento" tam="sm" icono={Hand} onClick={pedir} cargando={pidiendo}>Pedir más trabajo</Boton>
        </div>
      )}

      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <Pestanas className="md:max-w-xl md:flex-1" valor={ver} onCambio={cambiarVista} opciones={[
          { valor: "hacer", etiqueta: "Por hacer", cuenta: grupos.hacer.length },
          { valor: "revision", etiqueta: "En revisión", cuenta: grupos.revision.length },
          { valor: "validadas", etiqueta: "Validadas" },
        ]} />
        {ver === "validadas" && <SelectorMes valor={mesValidadas} onCambio={setMesValidadas} />}
        {usuario.puede_autoasignar && <Boton icono={Plus} onClick={() => setCreando(true)} data-guia="tarea-propia" className="w-full md:w-auto">Nueva tarea para mí</Boton>}
      </div>

      {ver === "hacer" && (nVencidas > 0 || nDevueltas > 0) && (
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filtrar lo que tienes por hacer">
          {[["todas", "Todas", grupos.hacer.length, ""], ["vencidas", "Vencidas", nVencidas, "rojo"], ["devueltas", "Devueltas para corregir", nDevueltas, "amarillo"]].map(([k, texto, n, tono]) => (
            <button key={k} type="button" aria-pressed={filtroHacer === k} onClick={() => setFiltroHacer(k)}
              className={cx("flex h-9 items-center gap-2 rounded-full border px-3.5 text-sm font-medium transition-colors", filtroHacer === k ? "border-noche bg-noche text-white" : "border-linea bg-white text-tinta hover:bg-fondo")}>
              {texto}<span className={cx("num rounded-full px-1.5 text-xs", filtroHacer === k ? "bg-white/20" : tono === "rojo" && n > 0 ? "bg-rojo-50 text-rojo" : tono === "amarillo" && n > 0 ? "bg-amarillo-50 text-[#8a5a00]" : "bg-fondo text-gris")}>{n}</span>
            </button>
          ))}
        </div>
      )}

      {lista.length === 0 ? (
        <Vacio icono={ListChecks} accion={ver === "hacer" && <div className="flex flex-wrap justify-center gap-2">
          {usuario.puede_autoasignar && <Boton icono={Plus} onClick={() => setCreando(true)}>Nueva tarea para mí</Boton>}
          <Boton variante="acento" icono={Hand} onClick={pedir} cargando={pidiendo}>Pedir más trabajo</Boton></div>} titulo={
          ver === "hacer" ? (base.length > 0 ? "Nada con este filtro" : "No tienes tareas pendientes") : ver === "revision" ? "Nada esperando validación" : "Sin tareas validadas en ese mes"}>
          {ver === "hacer" ? (disp?.en_espera ? "Tu supervisor ya sabe que estás disponible. Mientras llega una tarea, registra tus actividades adicionales."
            : "Estás al día. Avísale a tu supervisor que puedes tomar más: quedas «en espera de asignación» hasta que te llegue una tarea.")
            : ver === "revision" ? "Lo que entregues queda aquí hasta que tu supervisor lo valide o te lo devuelva."
              : "Las tareas validadas son las que suman a tu puntaje."}
        </Vacio>
      ) : (
        <ul className="space-y-3">
          {lista.map((t) => <FilaTarea key={t.id} tarea={t} onAbrir={abrir} onIniciar={iniciar} onEntregar={setEntregando}
            onBloquear={setBloqueando} onDesbloquear={desbloquear} iniciando={iniciando} />)}
        </ul>
      )}

      <FormTareaPropia abierto={creando} onCerrar={() => setCreando(false)} onGuardada={(m) => { setCreando(false); avisar(m); setParams((p) => { p.set("ver", "hacer"); return p; }, { replace: true }); cargar(); }} />

      <DetalleTarea tarea={detalle} abierto={!!detalle} onCerrar={cerrar}
        onCambio={(t) => setTareas((l) => l.map((x) => (x.id === t.id ? t : x)))}
        pie={detalle && (detalle.estado === "PENDIENTE" || detalle.estado === "EN_PROGRESO") && (<>
          <BotonCronometro tarea={detalle.id} />
          <Boton variante="acento" icono={Send} onClick={() => { cerrar(); setEntregando(detalle); }}>Entregar</Boton>
        </>)} />

      <BloquearModal tarea={bloqueando} onCerrar={() => setBloqueando(null)} onHecho={(t) => { setBloqueando(null); reemplazar(t); }} />

      <EntregarModal tarea={entregando} abierto={!!entregando} onCerrar={() => setEntregando(null)}
        onEntregada={(t) => {
          setEntregando(null);
          setTareas((l) => l.map((x) => (x.id === t.id ? t : x)));
          miResumen(mesActual()).then(setResumen).catch(() => {});
          crono?.refrescar();
          refrescarAvisos();
          avisar("Entregada. Cuenta para tu avance cuando tu supervisor la valide.");
        }} />
    </div>
  );
}
