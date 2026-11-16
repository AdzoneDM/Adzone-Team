// Colaboración y actividades adicionales (12.4): pedir y dar apoyo, registrar lo que hago por iniciativa
// propia y, para quien supervisa, validar ambas cosas. Todo cuenta como indicador, no solo las tareas.
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { BookOpen, Check, HandHeart, HeartHandshake, Lightbulb, Plus, Trash2, X } from "lucide-react";
import {
  borrarActividad, crearActividad, crearColaboracion, listarActividades, listarColaboraciones, miDisponibilidad,
  pasoColaboracion, personasColaborar, retirarColaboracion, revisarActividad,
} from "@/lib/api";
import { useSesion } from "@/lib/sesion";
import { refrescarAvisos } from "@/app/Estructura";
import { Alerta, Boton, Cabecera, Campo, Cargando, Insignia, Modal, Pestanas, Vacio, useAviso } from "@/components/ui";
import { useNovedades } from "@/lib/novedades";

const hoyISO = () => new Date().toLocaleDateString("sv-SE", { timeZone: "America/Santo_Domingo" });
const fecha = (d) => d ? new Date(d.length === 10 ? d + "T12:00:00" : d).toLocaleDateString("es-DO", { day: "numeric", month: "short" }) : "";
const horas = (m) => !m ? "" : m < 60 ? `${m} min` : `${Math.floor(m / 60)} h${m % 60 ? ` ${m % 60} min` : ""}`;
const TONO = { SOLICITADA: "amarillo", ACEPTADA: "azul", RECHAZADA: "neutro", REALIZADA: "amarillo", VALIDADA: "verde", NO_VALIDADA: "rojo",
  REGISTRADA: "amarillo" };

// ---------------------------------------------------------------- Actividades adicionales
function NuevaActividad({ abierto, onCerrar, onCreada, tipos }) {
  const avisar = useAviso();
  const [f, setF] = useState({ fecha: hoyISO(), tipo: "DOCUMENTACION", descripcion: "", resultado: "", minutos: 30 });
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const cambiar = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }));
  const guardar = async () => {
    setGuardando(true); setError("");
    try {
      const a = await crearActividad({ ...f, minutos: Number(f.minutos) || 0 });
      onCreada(a); avisar("Registrada. Tu supervisor la valida y cuenta en tus indicadores.");
      setF({ fecha: hoyISO(), tipo: f.tipo, descripcion: "", resultado: "", minutos: 30 });
    } catch (e) { setError(e.message); }
    setGuardando(false);
  };
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo="Registrar actividad adicional"
      descripcion="Lo que haces por iniciativa propia, sobre todo cuando terminaste tus tareas."
      pie={<><Boton variante="fantasma" onClick={onCerrar}>Cancelar</Boton><Boton onClick={guardar} cargando={guardando}>Registrar</Boton></>}>
      <div className="space-y-4">
        <Campo etiqueta="Tipo">
          {(id) => <select id={id} className="campo" value={f.tipo} onChange={cambiar("tipo")}>
            {tipos.map((t) => <option key={t.valor} value={t.valor}>{t.texto}</option>)}
          </select>}
        </Campo>
        <Campo etiqueta="¿Qué hiciste?">
          {(id) => <textarea id={id} className="campo" rows={3} value={f.descripcion} onChange={cambiar("descripcion")}
            placeholder="Ej.: Ordené la carpeta compartida de artes por cliente y año." />}
        </Campo>
        <Campo etiqueta="Resultado (opcional)" ayuda="Qué quedó: el documento, la mejora propuesta, lo que aprendiste.">
          {(id) => <textarea id={id} className="campo" rows={2} value={f.resultado} onChange={cambiar("resultado")} />}
        </Campo>
        <div className="grid grid-cols-2 gap-3">
          <Campo etiqueta="Día">{(id) => <input id={id} type="date" className="campo" max={hoyISO()} value={f.fecha} onChange={cambiar("fecha")} />}</Campo>
          <Campo etiqueta="Tiempo (minutos)">{(id) => <input id={id} type="number" min={0} max={720} step={5} className="campo" value={f.minutos} onChange={cambiar("minutos")} />}</Campo>
        </div>
        {error && <Alerta>{error}</Alerta>}
      </div>
    </Modal>
  );
}

function FilaActividad({ a, onBorrar, onRevisar, revisando }) {
  return (
    <li className="rounded-xl border border-linea bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-medium">{a.tipo_nombre}</p>
          <p className="text-sm text-gris">{onRevisar ? `${a.usuario_nombre}${a.departamento ? ` · ${a.departamento}` : ""} · ` : ""}{fecha(a.fecha)}{a.minutos ? ` · ${horas(a.minutos)}` : ""}</p>
        </div>
        <Insignia tono={TONO[a.estado]}>{a.estado === "REGISTRADA" ? "Por validar" : a.estado === "VALIDADA" ? "Validada" : "No validada"}</Insignia>
      </div>
      <p className="mt-2 whitespace-pre-line text-[15px]">{a.descripcion}</p>
      {a.resultado && <p className="mt-1 whitespace-pre-line text-sm text-gris"><span className="font-medium text-tinta">Resultado: </span>{a.resultado}</p>}
      {a.comentario_supervisor && <p className="mt-1 text-sm text-gris"><span className="font-medium text-tinta">{a.validada_por_nombre}: </span>{a.comentario_supervisor}</p>}
      {(onBorrar || onRevisar) && a.estado === "REGISTRADA" && (
        <div className="mt-3 flex flex-wrap gap-2">
          {onBorrar && <Boton variante="fantasma" tam="sm" icono={Trash2} onClick={() => onBorrar(a)}>Borrar</Boton>}
          {onRevisar && a.puedo_validar && <>
            <Boton tam="sm" icono={Check} onClick={() => onRevisar(a, true)} cargando={revisando === a.id}>Validar</Boton>
            <Boton variante="secundario" tam="sm" icono={X} onClick={() => onRevisar(a, false)}>No validar</Boton>
          </>}
        </div>
      )}
    </li>
  );
}

// ---------------------------------------------------------------- Colaboración
function PedirApoyo({ abierto, onCerrar, onCreada, yaRealizada }) {
  const avisar = useAviso();
  const [personas, setPersonas] = useState([]);
  const [f, setF] = useState({ persona: "", descripcion: "", resultado: "", minutos: 30 });
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { if (abierto) personasColaborar().then(setPersonas).catch(() => {}); }, [abierto]);
  const cambiar = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }));
  const guardar = async () => {
    setGuardando(true); setError("");
    try {
      const datos = yaRealizada
        ? { solicitante: f.persona, ya_realizada: true, descripcion: f.descripcion, resultado: f.resultado, minutos: Number(f.minutos) || 0 }
        : { ayudante: f.persona, descripcion: f.descripcion };
      onCreada(await crearColaboracion(datos));
      avisar(yaRealizada ? "Registrado. Su supervisor lo valida." : "Listo: le llegó tu pedido de apoyo.");
      setF({ persona: "", descripcion: "", resultado: "", minutos: 30 });
    } catch (e) { setError(e.message); }
    setGuardando(false);
  };
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={yaRealizada ? "Registrar un apoyo que diste" : "Pedir apoyo a un compañero"}
      descripcion={yaRealizada ? "Ayudaste a alguien con su trabajo: queda constancia y cuenta en tu evaluación." : "Le llega un aviso; puede aceptar o decir que ahora no puede."}
      pie={<><Boton variante="fantasma" onClick={onCerrar}>Cancelar</Boton><Boton onClick={guardar} cargando={guardando} disabled={!f.persona}>{yaRealizada ? "Registrar" : "Pedir apoyo"}</Boton></>}>
      <div className="space-y-4">
        <Campo etiqueta={yaRealizada ? "¿A quién apoyaste?" : "¿A quién le pides apoyo?"}
          ayuda="Aparecen las personas de tu departamento. Para otro departamento, pídeselo a tu supervisor.">
          {(id) => <select id={id} className="campo" value={f.persona} onChange={cambiar("persona")}>
            <option value="">Elegir…</option>
            {personas.map((p) => <option key={p.id} value={p.id}>{p.nombre}{p.departamento ? ` · ${p.departamento}` : ""}</option>)}
          </select>}
        </Campo>
        <Campo etiqueta={yaRealizada ? "¿En qué lo apoyaste?" : "¿En qué necesitas apoyo?"}>
          {(id) => <textarea id={id} className="campo" rows={3} value={f.descripcion} onChange={cambiar("descripcion")} />}
        </Campo>
        {yaRealizada && <>
          <Campo etiqueta="Resultado">{(id) => <textarea id={id} className="campo" rows={2} value={f.resultado} onChange={cambiar("resultado")} placeholder="Ej.: Terminó la campaña a tiempo." />}</Campo>
          <Campo etiqueta="Tiempo (minutos)">{(id) => <input id={id} type="number" min={0} max={720} step={5} className="campo" value={f.minutos} onChange={cambiar("minutos")} />}</Campo>
        </>}
        {error && <Alerta>{error}</Alerta>}
      </div>
    </Modal>
  );
}

const TEXTO_ACCION = { aceptar: "Aceptar", rechazar: "No puedo", realizar: "Terminé el apoyo", validar: "Validar", no_validar: "No validar", cancelar: "Retirar" };

function FilaColaboracion({ c, yo, onPaso }) {
  const [abierto, setAbierto] = useState(null);
  const [texto, setTexto] = useState("");
  const [minutos, setMinutos] = useState(30);
  const pideTexto = ["rechazar", "realizar", "no_validar"];
  const ejecutar = (accion) => {
    if (pideTexto.includes(accion) && abierto !== accion) { setAbierto(accion); return; }
    onPaso(c, accion, texto, minutos); setAbierto(null); setTexto("");
  };
  const quien = c.ayudante === yo ? `Apoyas a ${c.solicitante_nombre}` : c.solicitante === yo ? `${c.ayudante_nombre} te apoya` : `${c.ayudante_nombre} apoya a ${c.solicitante_nombre}`;
  return (
    <li className="rounded-xl border border-linea bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-medium">{quien}</p>
          <p className="text-sm text-gris">{fecha(c.fecha_creacion)}{c.tarea_titulo ? ` · Tarea: ${c.tarea_titulo}` : ""}{c.minutos ? ` · ${horas(c.minutos)}` : ""}
            {c.ayudante_departamento && c.solicitante_departamento && c.ayudante_departamento !== c.solicitante_departamento ? ` · ${c.ayudante_departamento} → ${c.solicitante_departamento}` : ""}</p>
        </div>
        <Insignia tono={TONO[c.estado]}>{c.estado_nombre}</Insignia>
      </div>
      <p className="mt-2 whitespace-pre-line text-[15px]">{c.descripcion}</p>
      {c.resultado && <p className="mt-1 whitespace-pre-line text-sm text-gris"><span className="font-medium text-tinta">Resultado: </span>{c.resultado}</p>}
      {c.motivo && <p className="mt-1 text-sm text-gris"><span className="font-medium text-tinta">{c.validada_por_nombre || "Motivo"}: </span>{c.motivo}</p>}
      {c.yo.length > 0 && (
        <div className="mt-3 space-y-2">
          {abierto && (
            <div className="flex flex-wrap gap-2">
              <input className="campo flex-1" value={texto} onChange={(e) => setTexto(e.target.value)} autoFocus
                placeholder={abierto === "realizar" ? "Resultado del apoyo" : "Motivo"} aria-label="Detalle" />
              {abierto === "realizar" && <input type="number" className="campo w-28" min={0} max={720} step={5} value={minutos}
                onChange={(e) => setMinutos(e.target.value)} aria-label="Minutos" />}
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            {c.yo.map((a) => (
              <Boton key={a} tam="sm" variante={["aceptar", "realizar", "validar"].includes(a) ? "primario" : "secundario"}
                onClick={() => (a === "cancelar" ? onPaso(c, a) : ejecutar(a))}>{abierto === a ? "Confirmar" : TEXTO_ACCION[a]}</Boton>
            ))}
            {abierto && <Boton tam="sm" variante="fantasma" onClick={() => setAbierto(null)}>Cancelar</Boton>}
          </div>
        </div>
      )}
    </li>
  );
}

// ---------------------------------------------------------------- Página
export default function Colaboracion() {
  const { usuario, puedeValidar } = useSesion();
  const avisar = useAviso();
  const [params, setParams] = useSearchParams();
  const ver = params.get("ver") || "apoyos";
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  const [modal, setModal] = useState(null);
  const [revisando, setRevisando] = useState(null);

  const cargar = useCallback(() => {
    const pedidos = [listarColaboraciones({ ambito: "mias" }), listarActividades({ ambito: "mias" }), miDisponibilidad()];
    if (puedeValidar) pedidos.push(listarColaboraciones({ ambito: "por_validar" }), listarActividades({ ambito: "por_validar" }));
    Promise.all(pedidos).then(([colab, act, disp, cv = [], av = []]) => { setDatos({ colab, act, disp, cv, av }); setError(""); })
      .catch((e) => setError(e.message));
  }, [puedeValidar]);
  useEffect(() => { cargar(); }, [cargar]);
  useNovedades(cargar);

  const cambiar = (v) => { params.set("ver", v); setParams(params, { replace: true }); };
  const paso = async (c, accion, texto, minutos) => {
    try {
      if (accion === "cancelar") await retirarColaboracion(c.id); else await pasoColaboracion(c.id, accion, texto, minutos);
      cargar(); refrescarAvisos();
    } catch (e) { avisar(e.message, "rojo"); }
  };
  const revisar = async (a, aprobar) => {
    let comentario = "";
    if (!aprobar) { comentario = window.prompt("¿Por qué no se valida?") || ""; if (!comentario) return; }
    setRevisando(a.id);
    try { await revisarActividad(a.id, aprobar, comentario); cargar(); } catch (e) { avisar(e.message, "rojo"); }
    setRevisando(null);
  };
  const borrar = async (a) => {
    try { await borrarActividad(a.id); cargar(); } catch (e) { avisar(e.message, "rojo"); }
  };

  if (error) return <Alerta>{error}</Alerta>;
  if (!datos) return <Cargando />;
  const pendientes = datos.colab.filter((c) => c.yo.length > 0).length;
  const porValidar = datos.cv.length + datos.av.length;

  return (
    <div className="space-y-6">
      <Cabecera titulo="Colaboración y actividades"
        descripcion="El trabajo en equipo y lo que haces por iniciativa propia también cuentan. Tu supervisor lo valida.">
        <div className="flex flex-wrap gap-2">
          <Boton variante="secundario" icono={HandHeart} onClick={() => setModal("pedir")}>Pedir apoyo</Boton>
          <Boton variante="secundario" icono={HeartHandshake} onClick={() => setModal("dado")}>Registrar apoyo dado</Boton>
          <Boton variante="acento" icono={Plus} onClick={() => setModal("actividad")}>Actividad adicional</Boton>
        </div>
      </Cabecera>

      {datos.disp.en_espera && (
        <Alerta tono="amarillo" className="border border-amarillo bg-amarillo-50 text-[#7a5000]">
          <span className="font-medium">Estás en espera de asignación</span> desde las {new Date(datos.disp.desde).toLocaleTimeString("es-DO", { hour: "numeric", minute: "2-digit" })}:
          {" "}mientras llega una tarea, registra lo que hagas: organizar archivos, estudiar procedimientos, capacitarte o apoyar a un compañero.
        </Alerta>
      )}

      <Pestanas valor={ver} onCambio={cambiar} className="md:max-w-2xl" opciones={[
        { valor: "apoyos", etiqueta: "Apoyos", cuenta: pendientes || undefined },
        { valor: "actividades", etiqueta: "Mis actividades", cuenta: datos.act.length || undefined },
        ...(puedeValidar ? [{ valor: "por_validar", etiqueta: "Por validar", cuenta: porValidar || undefined }] : []),
      ]} />

      {ver === "apoyos" && (datos.colab.length === 0
        ? <Vacio icono={HeartHandshake} titulo="Sin apoyos todavía">Pide ayuda cuando una tarea se complique, o registra cuando apoyes a un compañero.</Vacio>
        : <ul className="space-y-3">{datos.colab.map((c) => <FilaColaboracion key={c.id} c={c} yo={usuario.id} onPaso={paso} />)}</ul>)}

      {ver === "actividades" && (datos.act.length === 0
        ? <Vacio icono={Lightbulb} titulo="Sin actividades registradas"
            accion={<Boton variante="acento" icono={Plus} onClick={() => setModal("actividad")}>Registrar actividad</Boton>}>
            Documentación, estudio de políticas, capacitación, mejoras de procesos…: todo lo que aportas además de tus tareas.
          </Vacio>
        : <ul className="space-y-3">{datos.act.map((a) => <FilaActividad key={a.id} a={a} onBorrar={borrar} />)}</ul>)}

      {ver === "por_validar" && (porValidar === 0
        ? <Vacio icono={BookOpen} titulo="Nada por validar">Las actividades y apoyos de tu equipo aparecen aquí cuando los registran.</Vacio>
        : (
          <div className="space-y-6">
            {datos.cv.length > 0 && <section className="space-y-3"><h2 className="font-semibold">Apoyos entre compañeros</h2>
              <ul className="space-y-3">{datos.cv.map((c) => <FilaColaboracion key={c.id} c={c} yo={usuario.id} onPaso={paso} />)}</ul></section>}
            {datos.av.length > 0 && <section className="space-y-3"><h2 className="font-semibold">Actividades adicionales</h2>
              <ul className="space-y-3">{datos.av.map((a) => <FilaActividad key={a.id} a={a} onRevisar={revisar} revisando={revisando} />)}</ul></section>}
          </div>
        ))}

      <NuevaActividad abierto={modal === "actividad"} onCerrar={() => setModal(null)} tipos={datos.disp.tipos_actividad}
        onCreada={() => { setModal(null); cambiar("actividades"); cargar(); }} />
      <PedirApoyo abierto={modal === "pedir" || modal === "dado"} yaRealizada={modal === "dado"} onCerrar={() => setModal(null)}
        onCreada={() => { setModal(null); cambiar("apoyos"); cargar(); }} />
    </div>
  );
}

