import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Hand, ListChecks, Play, Send, Target } from "lucide-react";
import { iniciarTarea, listarTareas, miResumen, pedirTrabajo } from "@/lib/api";
import { mesActual } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import { refrescarAvisos } from "@/app/Estructura";
import { DetalleTarea, EntregarModal, EquipoTarea, Evidencias, Progreso, Vencimiento } from "@/features/tareas/componentes";
import { Alerta, Boton, Cargando, EstadoTarea, Estrellas, Pestanas, PrioridadTarea, SelectorMes, Vacio, cx, useAviso } from "@/components/ui";
import { MiMes } from "@/features/inicio/Inicio";

function FilaTarea({ tarea, onAbrir, onIniciar, onEntregar, iniciando }) {
  const devuelta = tarea.comentario_revision && tarea.estado === "EN_PROGRESO";
  return (
    <li className={cx("rounded-xl border bg-white", devuelta ? "border-rojo/40" : "border-linea")}>
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
          </div>
          <EquipoTarea tarea={tarea} className="mt-1.5" />
        </button>
        {(tarea.estado === "PENDIENTE" || tarea.estado === "EN_PROGRESO") && (
          <div className="grid grid-cols-2 gap-2 md:flex">
            {tarea.estado === "PENDIENTE" && <Boton variante="secundario" icono={Play} onClick={() => onIniciar(tarea)} cargando={iniciando === tarea.id}>Empezar</Boton>}
            <Boton variante="acento" icono={Send} onClick={() => onEntregar(tarea)} className={tarea.estado === "EN_PROGRESO" ? "col-span-2" : ""}>
              {devuelta ? "Entregar de nuevo" : "Entregar"}
            </Boton>
          </div>
        )}
      </div>
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
  const [params, setParams] = useSearchParams();
  const [tareas, setTareas] = useState(null);
  const [resumen, setResumen] = useState(null);
  const [error, setError] = useState("");
  const [mesValidadas, setMesValidadas] = useState(mesActual());
  const [entregando, setEntregando] = useState(null);
  const [iniciando, setIniciando] = useState(null);
  const [pidiendo, setPidiendo] = useState(false);
  const ver = params.get("ver") || "hacer";
  const abierta = params.get("tarea");

  const cargar = useCallback(() => {
    Promise.all([listarTareas({ ambito: "mias" }), miResumen(mesActual())])
      .then(([t, r]) => { setTareas(t); setResumen(r); })
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => { cargar(); }, [cargar]);

  const grupos = useMemo(() => {
    const lista = tareas || [];
    const porFecha = (a, b) => a.fecha_limite.localeCompare(b.fecha_limite);
    return {
      hacer: lista.filter((t) => t.estado === "PENDIENTE" || t.estado === "EN_PROGRESO")
        .sort((a, b) => (b.comentario_revision ? 1 : 0) - (a.comentario_revision ? 1 : 0) || porFecha(a, b)),
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
    } catch (e) { avisar(e.message, "rojo"); }
    setIniciando(null);
  };

  const pedir = async () => {
    setPidiendo(true);
    try { const r = await pedirTrabajo(); avisar(r.message); } catch (e) { avisar(e.message, "rojo"); }
    setPidiendo(false);
  };

  if (error) return <Alerta>{error}</Alerta>;
  if (!tareas || !resumen) return <Cargando />;

  const lista = grupos[ver] || grupos.hacer;
  const detalle = abierta ? tareas.find((t) => String(t.id) === abierta) : null;

  return (
    <div className="space-y-6">
      <MiMes resumen={resumen} nombre={usuario.nombre} />

      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <Pestanas className="md:max-w-xl md:flex-1" valor={ver} onCambio={cambiarVista} opciones={[
          { valor: "hacer", etiqueta: "Por hacer", cuenta: grupos.hacer.length },
          { valor: "revision", etiqueta: "En revisión", cuenta: grupos.revision.length },
          { valor: "validadas", etiqueta: "Validadas" },
        ]} />
        {ver === "validadas" && <SelectorMes valor={mesValidadas} onCambio={setMesValidadas} />}
      </div>

      {lista.length === 0 ? (
        <Vacio icono={ListChecks} accion={ver === "hacer" && <Boton variante="acento" icono={Hand} onClick={pedir} cargando={pidiendo}>Pedir más trabajo</Boton>} titulo={
          ver === "hacer" ? "No tienes tareas pendientes" : ver === "revision" ? "Nada esperando validación" : "Sin tareas validadas en ese mes"}>
          {ver === "hacer" ? "Estás al día. Avísale a tu supervisor que puedes tomar más, o espera: cuando te asignen una, te llega el aviso."
            : ver === "revision" ? "Lo que entregues queda aquí hasta que tu supervisor lo valide o te lo devuelva."
              : "Las tareas validadas son las que suman a tu puntaje."}
        </Vacio>
      ) : (
        <ul className="space-y-3">
          {lista.map((t) => <FilaTarea key={t.id} tarea={t} onAbrir={abrir} onIniciar={iniciar} onEntregar={setEntregando} iniciando={iniciando} />)}
        </ul>
      )}

      <DetalleTarea tarea={detalle} abierto={!!detalle} onCerrar={cerrar}
        onCambio={(t) => setTareas((l) => l.map((x) => (x.id === t.id ? t : x)))}
        pie={detalle && (detalle.estado === "PENDIENTE" || detalle.estado === "EN_PROGRESO") && (
          <Boton variante="acento" icono={Send} onClick={() => { cerrar(); setEntregando(detalle); }}>Entregar</Boton>
        )} />

      <EntregarModal tarea={entregando} abierto={!!entregando} onCerrar={() => setEntregando(null)}
        onEntregada={(t) => {
          setEntregando(null);
          setTareas((l) => l.map((x) => (x.id === t.id ? t : x)));
          miResumen(mesActual()).then(setResumen).catch(() => {});
          refrescarAvisos();
          avisar("Entregada. Cuenta para tu avance cuando tu supervisor la valide.");
        }} />
    </div>
  );
}
