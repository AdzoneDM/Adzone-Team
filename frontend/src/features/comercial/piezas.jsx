// Piezas del módulo comercial: estados, formularios y ventanas de oportunidad y de solicitud de servicio, e historial.
// Las reglas (quién ve y quién cambia) las aplica el servidor; aquí solo se reflejan con `puedo_cambiar` y los datos de sesión.
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRightLeft, FolderKanban, History, MessageSquareText, Pencil, Plus, Send } from "lucide-react";
import {
  comentarOportunidad, comentarSolicitud, convertirSolicitud, guardarOportunidad, guardarSolicitud, listarOrdenes, obtenerOportunidad,
  obtenerSolicitud,
} from "@/lib/api";
import { fechaCorta, fechaHora, hoyISO } from "@/lib/formato";
import { useRecurso } from "@/lib/recursos";
import { useSesion } from "@/lib/sesion";
import { SelectorCliente, SelectorPersona } from "@/components/Selectores";
import { Alerta, Boton, Campo, Cargando, Insignia, Modal, cx, useAviso } from "@/components/ui";

export const ESTADOS_OP = {
  NUEVO: ["Nuevo contacto", "neutro"], CONTACTADO: ["Contactado", "azul"], EVALUACION: ["Evaluación de necesidades", "azul"],
  COTIZADA: ["Cotización enviada", "amarillo"], NEGOCIACION: ["En negociación", "amarillo"], APROBADA: ["Aprobado", "verde"],
  NO_CONCRETADA: ["No concretado", "rojo"],
};
export const ESTADOS_SOL = {
  RECIBIDA: ["Recibida", "neutro"], EVALUACION: ["En evaluación", "azul"], COTIZADA: ["Cotización enviada", "amarillo"],
  APROBADA: ["Aprobada por el cliente", "verde"], EN_EJECUCION: ["En proyecto / orden", "noche"], NO_CONCRETADA: ["No concretada", "rojo"],
};
export const SERVICIOS = [
  ["REDES", "Gestión de redes sociales", "Marketing"], ["PUBLICIDAD", "Publicidad digital", "Marketing"], ["ESTRATEGIA", "Estrategia digital", "Marketing"],
  ["FOTOGRAFIA", "Fotografía", "Audiovisual"], ["VIDEO", "Producción de video", "Audiovisual"], ["GRABACION", "Grabación / cobertura", "Audiovisual"],
  ["WEB", "Página web", "Tecnología"], ["SISTEMA", "Sistema o aplicación", "Tecnología"], ["TV", "Pauta en AdZone TV", "Adzone TV"],
  ["IMPRESION", "Impresión", "Impresión"], ["OTRO", "Otro servicio", null],
];

export const EstadoOp = ({ estado }) => <Insignia tono={ESTADOS_OP[estado]?.[1]}>{ESTADOS_OP[estado]?.[0] || estado}</Insignia>;
export const EstadoSol = ({ estado }) => <Insignia tono={ESTADOS_SOL[estado]?.[1]}>{ESTADOS_SOL[estado]?.[0] || estado}</Insignia>;

const deptoSugerido = (deptos, servicio) => {
  const nombre = SERVICIOS.find((s) => s[0] === servicio)?.[2];
  return nombre ? (deptos || []).find((d) => d.nombre.toLowerCase() === nombre.toLowerCase())?.id : undefined;
};

function SelectorDepto({ valor, onCambio, etiqueta = "Departamento responsable", vacio }) {
  const [deptos] = useRecurso("departamentos");
  return (
    <Campo etiqueta={etiqueta}>{(id) => (
      <select id={id} className="campo" value={valor || ""} onChange={(e) => onCambio(e.target.value)}>
        <option value="">{vacio || "Elige…"}</option>
        {(deptos || []).map((d) => <option key={d.id} value={d.id}>{d.nombre}</option>)}
      </select>
    )}</Campo>
  );
}

// ---------------------------------------------------------------- Historial
function Historial({ items, onComentar, estados = ESTADOS_OP }) {
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const avisar = useAviso();
  const enviar = async (e) => {
    e.preventDefault();
    if (!texto.trim()) return;
    setEnviando(true);
    try { await onComentar(texto.trim()); setTexto(""); } catch (err) { avisar(err.message, "rojo"); }
    setEnviando(false);
  };
  const describir = (m) => {
    if (m.tipo === "ESTADO") return <>cambió el estado: <b>{estados[m.estado_antes]?.[0] || m.estado_antes}</b> → <b>{estados[m.estado_despues]?.[0] || m.estado_despues}</b></>;
    if (m.tipo === "CAMBIO" && m.cambios && Object.keys(m.cambios).length) {
      return <>cambió {Object.entries(m.cambios).map(([k, v], i) => <span key={k}>{i ? ", " : ""}<b>{CAMPOS[k] || k}</b> ({v.antes || "—"} → {v.despues || "—"})</span>)}</>;
    }
    if (m.tipo === "CREADA") return "la registró";
    if (m.tipo === "CONVERSION") return "la convirtió";
    return null;
  };
  return (
    <section className="space-y-3">
      <h3 className="flex items-center gap-2 font-semibold"><History className="size-4 text-azul" aria-hidden />Historial y comentarios</h3>
      {onComentar && (
        <form onSubmit={enviar} className="flex gap-2">
          <input className="campo" value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Agregar una observación o un avance…" maxLength={4000} aria-label="Comentario" />
          <Boton type="submit" icono={Send} cargando={enviando} aria-label="Enviar comentario">Agregar</Boton>
        </form>
      )}
      <ol className="space-y-2">
        {items.map((m) => (
          <li key={m.id} className={cx("rounded-xl px-3 py-2 text-sm", m.tipo === "COMENTARIO" ? "bg-fondo" : "border border-linea")}>
            <p className="text-gris"><span className="font-medium text-tinta">{m.usuario_nombre || "Sistema"}</span> {describir(m)} · <span className="whitespace-nowrap">{fechaHora(m.fecha)}</span></p>
            {m.texto && <p className="mt-0.5 whitespace-pre-line">{m.tipo === "COMENTARIO" && <MessageSquareText className="mr-1 inline size-3.5 text-gris" aria-hidden />}{m.texto}</p>}
          </li>
        ))}
        {!items.length && <li className="text-sm text-gris">Sin movimientos todavía.</li>}
      </ol>
    </section>
  );
}

const CAMPOS = {
  titulo: "Título", necesidades: "Necesidades", departamento: "Departamento", responsable: "Responsable", fecha_contacto: "Primer contacto",
  proximo_seguimiento: "Próximo seguimiento", motivo_no_concretado: "Motivo", cliente: "Cliente", servicio: "Servicio",
  servicio_detalle: "Servicio", descripcion: "Descripción",
};

// ---------------------------------------------------------------- Oportunidad: alta y edición
export function FormOportunidad({ abierto, onCerrar, inicial, onGuardado }) {
  const { usuario } = useSesion();
  const [deptos] = useRecurso("departamentos");
  const [f, setF] = useState({});
  const [servicios, setServicios] = useState([]);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const editando = !!inicial?.id;
  useEffect(() => {
    if (!abierto) return;
    setError(""); setServicios([]);
    setF(editando ? {
      id: inicial.id, cliente: String(inicial.cliente), titulo: inicial.titulo, necesidades: inicial.necesidades || "",
      responsable: inicial.responsable ? String(inicial.responsable) : "", departamento: inicial.departamento ? String(inicial.departamento) : "",
      fecha_contacto: inicial.fecha_contacto || "", proximo_seguimiento: inicial.proximo_seguimiento || "",
    } : {
      cliente: inicial?.cliente ? String(inicial.cliente) : "", titulo: "", necesidades: "", responsable: String(usuario.id),
      departamento: usuario.departamento_id ? String(usuario.departamento_id) : "", fecha_contacto: hoyISO(), proximo_seguimiento: "",
    });
  }, [abierto, inicial, editando, usuario]);
  const cambiar = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const alternar = (codigo) => setServicios((l) => (l.includes(codigo) ? l.filter((c) => c !== codigo) : [...l, codigo]));
  const guardar = async (e) => {
    e.preventDefault();
    if (!f.cliente) return setError("Elige el cliente o regístralo.");
    if (!f.titulo?.trim()) return setError("Escribe un título para la oportunidad.");
    setGuardando(true); setError("");
    try {
      const o = await guardarOportunidad({
        ...f, cliente: Number(f.cliente), titulo: f.titulo.trim(), responsable: f.responsable ? Number(f.responsable) : null,
        departamento: f.departamento ? Number(f.departamento) : null, fecha_contacto: f.fecha_contacto || null,
        proximo_seguimiento: f.proximo_seguimiento || null,
      });
      for (const codigo of servicios) {
        const sugerido = deptoSugerido(deptos, codigo);
        await guardarSolicitud({ oportunidad: o.id, servicio: codigo, servicio_detalle: codigo === "OTRO" ? "Por definir" : "",
          departamento: sugerido || (f.departamento ? Number(f.departamento) : null), descripcion: f.necesidades || "" });
      }
      onGuardado(o);
    } catch (err) { setError(err.message); }
    setGuardando(false);
  };
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={editando ? "Editar oportunidad" : "Nueva oportunidad comercial"} ancho="md:max-w-2xl"
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton type="submit" form="form-oportunidad" cargando={guardando}>Guardar</Boton></>}>
      <form id="form-oportunidad" onSubmit={guardar} className="grid gap-4 sm:grid-cols-2">
        {error && <Alerta className="sm:col-span-2">{error}</Alerta>}
        <div className="sm:col-span-2"><SelectorCliente valor={f.cliente} onCambio={(v) => setF((x) => ({ ...x, cliente: v }))} /></div>
        <Campo etiqueta="Título" className="sm:col-span-2">{(id) => <input id={id} className="campo" value={f.titulo || ""} onChange={cambiar("titulo")} maxLength={200} placeholder="Ej.: Campaña de lanzamiento 2027" />}</Campo>
        <Campo etiqueta="Qué necesita el cliente" className="sm:col-span-2">{(id) => <textarea id={id} rows={3} className="campo" value={f.necesidades || ""} onChange={cambiar("necesidades")} />}</Campo>
        <SelectorPersona etiqueta="Responsable comercial" valor={f.responsable} onCambio={(v) => setF((x) => ({ ...x, responsable: v }))} />
        <SelectorDepto etiqueta="Departamento que la lleva" valor={f.departamento} onCambio={(v) => setF((x) => ({ ...x, departamento: v }))} />
        <Campo etiqueta="Primer contacto">{(id) => <input id={id} type="date" className="campo" value={f.fecha_contacto || ""} onChange={cambiar("fecha_contacto")} />}</Campo>
        <Campo etiqueta="Próximo seguimiento" ayuda="Ese día le llega un aviso al responsable.">{(id) => <input id={id} type="date" className="campo" value={f.proximo_seguimiento || ""} onChange={cambiar("proximo_seguimiento")} />}</Campo>
        {!editando && (
          <fieldset className="sm:col-span-2">
            <legend className="mb-1.5 text-sm font-medium">Servicios que necesita <span className="font-normal text-gris">(se crea una solicitud para cada departamento)</span></legend>
            <div className="flex flex-wrap gap-2">
              {SERVICIOS.map(([codigo, nombre, depto]) => (
                <label key={codigo} className={cx("flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-1.5 text-sm", servicios.includes(codigo) ? "border-azul bg-azul/5" : "border-linea")}>
                  <input type="checkbox" className="size-4 accent-azul" checked={servicios.includes(codigo)} onChange={() => alternar(codigo)} />
                  {nombre}{depto && <span className="text-xs text-gris">· {depto}</span>}
                </label>
              ))}
            </div>
          </fieldset>
        )}
      </form>
    </Modal>
  );
}

// ---------------------------------------------------------------- Agregar un servicio (solicitud) a una oportunidad
function NuevaSolicitud({ oportunidad, onCreada, onCancelar }) {
  const [deptos] = useRecurso("departamentos");
  const [f, setF] = useState({ servicio: "", servicio_detalle: "", departamento: "", descripcion: "", responsable: "" });
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const elegir = (servicio) => setF((x) => ({ ...x, servicio, departamento: String(deptoSugerido(deptos, servicio) || x.departamento || "") }));
  const guardar = async (e) => {
    e.preventDefault();
    if (!f.servicio) return setError("Elige el servicio.");
    if (!f.departamento) return setError("Elige el departamento responsable.");
    setGuardando(true); setError("");
    try {
      await guardarSolicitud({ ...f, oportunidad: oportunidad.id, departamento: Number(f.departamento), responsable: f.responsable ? Number(f.responsable) : null });
      onCreada();
    } catch (err) { setError(err.message); }
    setGuardando(false);
  };
  return (
    <form onSubmit={guardar} className="grid gap-3 rounded-xl border border-azul/30 bg-azul/5 p-4 sm:grid-cols-2">
      {error && <Alerta className="sm:col-span-2">{error}</Alerta>}
      <Campo etiqueta="Servicio">{(id) => (
        <select id={id} className="campo" value={f.servicio} onChange={(e) => elegir(e.target.value)}>
          <option value="">Elige…</option>
          {SERVICIOS.map(([c, n]) => <option key={c} value={c}>{n}</option>)}
        </select>
      )}</Campo>
      {f.servicio === "OTRO"
        ? <Campo etiqueta="¿Qué servicio?">{(id) => <input id={id} className="campo" maxLength={150} value={f.servicio_detalle} onChange={(e) => setF({ ...f, servicio_detalle: e.target.value })} />}</Campo>
        : <span className="hidden sm:block" />}
      <SelectorDepto valor={f.departamento} onCambio={(v) => setF((x) => ({ ...x, departamento: v }))} />
      <SelectorPersona etiqueta="Responsable (opcional)" vacio="Lo asigna el departamento" valor={f.responsable} onCambio={(v) => setF((x) => ({ ...x, responsable: v }))} />
      <Campo etiqueta="Descripción del requerimiento" className="sm:col-span-2">{(id) => <textarea id={id} rows={2} className="campo" value={f.descripcion} onChange={(e) => setF({ ...f, descripcion: e.target.value })} />}</Campo>
      <div className="flex justify-end gap-2 sm:col-span-2">
        <Boton variante="secundario" onClick={onCancelar}>Cancelar</Boton>
        <Boton type="submit" cargando={guardando}>Crear solicitud</Boton>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------- Oportunidad: detalle
export function DetalleOportunidad({ id, onCerrar, onCambio, onAbrirSolicitud }) {
  const avisar = useAviso();
  const [o, setO] = useState(null);
  const [error, setError] = useState("");
  const [editar, setEditar] = useState(false);
  const [agregando, setAgregando] = useState(false);
  const [motivo, setMotivo] = useState(null);
  const cargar = useCallback(() => { if (id) obtenerOportunidad(id).then(setO).catch((e) => setError(e.message)); }, [id]);
  useEffect(() => { setO(null); setError(""); setAgregando(false); setMotivo(null); cargar(); }, [cargar]);
  const cambiarEstado = async (estado, motivoTexto) => {
    if (estado === "NO_CONCRETADA" && !motivoTexto) return setMotivo("");
    try {
      await guardarOportunidad({ id: o.id, estado, ...(motivoTexto ? { motivo_no_concretado: motivoTexto, motivo: motivoTexto } : {}) });
      setMotivo(null); cargar(); onCambio?.(); avisar("Estado actualizado");
    } catch (e) { avisar(e.message, "rojo"); }
  };
  return (
    <Modal abierto={!!id} onCerrar={onCerrar} titulo={o ? `${o.codigo} · ${o.titulo}` : "Oportunidad"} descripcion={o?.cliente_nombre} ancho="md:max-w-3xl">
      {error ? <Alerta>{error}</Alerta> : !o ? <Cargando /> : (
        <div className="space-y-5">
          <div className="flex flex-wrap items-end gap-3">
            <Campo etiqueta="Estado" className="min-w-56">{(cid) => (
              <select id={cid} className="campo" value={o.estado} onChange={(e) => cambiarEstado(e.target.value)}>
                {Object.entries(ESTADOS_OP).map(([k, [n]]) => <option key={k} value={k}>{n}</option>)}
              </select>
            )}</Campo>
            <Boton variante="secundario" icono={Pencil} onClick={() => setEditar(true)}>Editar</Boton>
            {o.seguimiento_vencido && <Insignia tono="rojo">Seguimiento pendiente</Insignia>}
          </div>
          {motivo !== null && (
            <form onSubmit={(e) => { e.preventDefault(); if (motivo.trim()) cambiarEstado("NO_CONCRETADA", motivo.trim()); }} className="flex gap-2">
              <input className="campo" autoFocus value={motivo} onChange={(e) => setMotivo(e.target.value)} maxLength={255} placeholder="¿Por qué no se concretó?" aria-label="Motivo" />
              <Boton type="submit">Marcar no concretado</Boton>
              <Boton variante="secundario" onClick={() => setMotivo(null)}>Cancelar</Boton>
            </form>
          )}
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
            <div><dt className="text-gris">Cliente</dt><dd className="font-medium"><Link to={`/clientes/${o.cliente}`} className="text-azul hover:underline">{o.cliente_nombre}</Link></dd></div>
            <div><dt className="text-gris">Responsable</dt><dd className="font-medium">{o.responsable_nombre || "—"}</dd></div>
            <div><dt className="text-gris">Departamento</dt><dd className="font-medium">{o.departamento_nombre || "—"}</dd></div>
            <div><dt className="text-gris">Primer contacto</dt><dd className="font-medium">{fechaCorta(o.fecha_contacto) || "—"}</dd></div>
            <div><dt className="text-gris">Próximo seguimiento</dt><dd className={cx("font-medium", o.seguimiento_vencido && "text-rojo")}>{fechaCorta(o.proximo_seguimiento) || "—"}</dd></div>
            <div><dt className="text-gris">Registrada</dt><dd className="font-medium">{fechaCorta(o.fecha_creacion)} · {o.creado_por_nombre}</dd></div>
          </dl>
          {o.necesidades && <p className="whitespace-pre-line rounded-xl bg-fondo px-4 py-3 text-[15px]">{o.necesidades}</p>}
          {o.estado === "NO_CONCRETADA" && o.motivo_no_concretado && <Alerta tono="rojo"><b>No concretado:</b> {o.motivo_no_concretado}</Alerta>}

          <section className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <h3 className="flex items-center gap-2 font-semibold"><FolderKanban className="size-4 text-azul" aria-hidden />Servicios solicitados ({o.solicitudes.length})</h3>
              {!agregando && <Boton tam="sm" variante="secundario" icono={Plus} onClick={() => setAgregando(true)}>Agregar servicio</Boton>}
            </div>
            {agregando && <NuevaSolicitud oportunidad={o} onCancelar={() => setAgregando(false)} onCreada={() => { setAgregando(false); cargar(); onCambio?.(); avisar("Solicitud creada y enviada al departamento"); }} />}
            <ul className="divide-y divide-linea rounded-xl border border-linea">
              {o.solicitudes.map((s) => (
                <li key={s.id}>
                  <button type="button" onClick={() => onAbrirSolicitud(s.id)} className="flex w-full flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2.5 text-left hover:bg-fondo">
                    <span className="font-medium">{s.servicio_nombre}</span>
                    <span className="text-sm text-gris">{s.codigo} · {s.departamento_nombre} · {s.responsable_nombre || "sin responsable"}</span>
                    <span className="ml-auto"><EstadoSol estado={s.estado} /></span>
                  </button>
                </li>
              ))}
              {!o.solicitudes.length && <li className="px-4 py-3 text-sm text-gris">Todavía no hay servicios. Agrega uno por cada departamento que debe atenderlo.</li>}
            </ul>
          </section>

          <Historial items={o.historial} onComentar={async (t) => { await comentarOportunidad(o.id, t); cargar(); }} />
          <FormOportunidad abierto={editar} inicial={o} onCerrar={() => setEditar(false)} onGuardado={() => { setEditar(false); cargar(); onCambio?.(); avisar("Oportunidad actualizada"); }} />
        </div>
      )}
    </Modal>
  );
}

// ---------------------------------------------------------------- Solicitud: detalle
export function DetalleSolicitud({ id, onCerrar, onCambio }) {
  const avisar = useAviso();
  const [s, setS] = useState(null);
  const [error, setError] = useState("");
  const [ordenes, setOrdenes] = useState(null);
  const [orden, setOrden] = useState("");
  const [trabajando, setTrabajando] = useState(false);
  const cargar = useCallback(() => { if (id) obtenerSolicitud(id).then(setS).catch((e) => setError(e.message)); }, [id]);
  useEffect(() => { setS(null); setError(""); setOrdenes(null); setOrden(""); cargar(); }, [cargar]);
  const guardar = async (datos, aviso) => {
    try { await guardarSolicitud({ id: s.id, ...datos }); cargar(); onCambio?.(); avisar(aviso); } catch (e) { avisar(e.message, "rojo"); }
  };
  const convertir = async (datos) => {
    setTrabajando(true);
    try {
      const r = await convertirSolicitud(s.id, datos);
      cargar(); onCambio?.(); avisar(r.proyecto_codigo ? `Proyecto ${r.proyecto_codigo} creado` : `Enlazada a la orden ${r.orden_codigo}`);
    } catch (e) { avisar(e.message, "rojo"); }
    setTrabajando(false);
  };
  const verOrdenes = () => listarOrdenes({ cliente: s.cliente }).then((l) => setOrdenes((l.results || l).filter((x) => x.cliente === s.cliente))).catch((e) => avisar(e.message, "rojo"));
  return (
    <Modal abierto={!!id} onCerrar={onCerrar} titulo={s ? `${s.codigo} · ${s.servicio_nombre}` : "Solicitud de servicio"} descripcion={s?.cliente_nombre} ancho="md:max-w-2xl">
      {error ? <Alerta>{error}</Alerta> : !s ? <Cargando /> : (
        <div className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-2">
            {s.puedo_cambiar && s.estado !== "EN_EJECUCION" ? (
              <Campo etiqueta="Estado">{(cid) => (
                <select id={cid} className="campo" value={s.estado} onChange={(e) => guardar({ estado: e.target.value }, "Estado actualizado")}>
                  {Object.entries(ESTADOS_SOL).filter(([k]) => k !== "EN_EJECUCION").map(([k, [n]]) => <option key={k} value={k}>{n}</option>)}
                </select>
              )}</Campo>
            ) : <div><p className="mb-1.5 text-sm font-medium">Estado</p><EstadoSol estado={s.estado} /></div>}
            {s.puedo_cambiar
              ? <SelectorPersona etiqueta="Responsable" vacio="Sin responsable" valor={s.responsable ? String(s.responsable) : ""} onCambio={(v) => guardar({ responsable: v ? Number(v) : null }, "Responsable asignado")} />
              : <div><p className="mb-1.5 text-sm font-medium">Responsable</p><p>{s.responsable_nombre || "Sin responsable"}</p></div>}
          </div>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
            <div><dt className="text-gris">Cliente</dt><dd className="font-medium">{s.cliente_nombre}</dd></div>
            <div><dt className="text-gris">Departamento</dt><dd className="font-medium">{s.departamento_nombre}</dd></div>
            <div><dt className="text-gris">Registrada</dt><dd className="font-medium">{fechaCorta(s.fecha_creacion)} · {s.creado_por_nombre}</dd></div>
            {s.oportunidad_codigo && <div className="col-span-2 sm:col-span-3"><dt className="text-gris">Oportunidad</dt><dd className="font-medium">{s.oportunidad_codigo} · {s.oportunidad_titulo}</dd></div>}
          </dl>
          {s.descripcion && <p className="whitespace-pre-line rounded-xl bg-fondo px-4 py-3 text-[15px]">{s.descripcion}</p>}
          {!s.puedo_cambiar && <Alerta tono="amarillo">El estado y el responsable los cambia {s.departamento_nombre} (su responsable o quien lo gestiona). Puedes dejar comentarios.</Alerta>}

          {(s.proyecto || s.orden) && (
            <Alerta tono="verde">
              {s.proyecto && <>Proyecto: <Link className="font-medium underline" to={`/proyectos/${s.proyecto}`}>{s.proyecto_codigo}</Link>. </>}
              {s.orden && <>Orden de trabajo: <Link className="font-medium underline" to={`/ordenes/${s.orden}`}>{s.orden_codigo}</Link>.</>}
            </Alerta>
          )}
          {s.puedo_cambiar && s.estado === "APROBADA" && (
            <section className="space-y-2 rounded-xl border border-verde/40 bg-verde-50/40 p-4">
              <h3 className="flex items-center gap-2 font-semibold"><ArrowRightLeft className="size-4 text-verde" aria-hidden />El cliente aprobó: iniciar el trabajo</h3>
              <p className="text-sm text-gris">Se enlaza con el cliente, la oportunidad y esta solicitud; nada se copia a mano.</p>
              <div className="flex flex-wrap gap-2">
                <Boton icono={FolderKanban} cargando={trabajando} onClick={() => convertir({})}>Crear proyecto</Boton>
                {ordenes === null && <Boton variante="secundario" onClick={verOrdenes}>Enlazar una orden de trabajo</Boton>}
              </div>
              {ordenes !== null && (ordenes.length ? (
                <div className="flex flex-wrap gap-2">
                  <select className="campo max-w-sm" value={orden} onChange={(e) => setOrden(e.target.value)} aria-label="Orden de trabajo">
                    <option value="">Elige la orden…</option>
                    {ordenes.map((x) => <option key={x.id} value={x.id}>{x.codigo} · {x.titulo}</option>)}
                  </select>
                  <Boton variante="secundario" disabled={!orden} cargando={trabajando} onClick={() => convertir({ orden: Number(orden) })}>Enlazar</Boton>
                </div>
              ) : <p className="text-sm text-gris">Este cliente no tiene órdenes que puedas ver. Créala en <Link className="text-azul underline" to="/ordenes">Órdenes de trabajo</Link> y vuelve a enlazarla.</p>)}
            </section>
          )}
          <Historial estados={ESTADOS_SOL} items={s.historial} onComentar={async (t) => { await comentarSolicitud(s.id, t); cargar(); }} />
        </div>
      )}
    </Modal>
  );
}
