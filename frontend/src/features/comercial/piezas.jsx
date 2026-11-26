// Piezas del módulo comercial: estados, formularios y ventanas de oportunidad y de solicitud de servicio, e historial.
// Las reglas (quién ve y quién cambia) las aplica el servidor; aquí solo se reflejan con `puedo_cambiar` y los datos de sesión.
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRightLeft, Building2, FileText, FolderKanban, History, Mail, MessageCircle, MessageSquareText, Pencil, Phone, Plus, Search,
  Send, UserPlus, Users, X,
} from "lucide-react";
import {
  coincidenciasCliente, comentarOportunidad, comentarSolicitud, convertirEnCliente, convertirSolicitud, guardarOportunidad,
  guardarSolicitud, listarOrdenes, obtenerOportunidad, obtenerSolicitud, registrarInteraccion,
} from "@/lib/api";
import { dinero, fechaCorta, fechaHora, hoyISO } from "@/lib/formato";
import { useRecurso } from "@/lib/recursos";
import { useSesion } from "@/lib/sesion";
import { SelectorPersona } from "@/components/Selectores";
import { Alerta, Boton, Campo, Cargando, Insignia, Modal, cx, useAviso } from "@/components/ui";

// Flujo de la oportunidad, en este orden: 1 Nueva oportunidad → 2 Contactado → 3 En negociación → 4 Propuesta enviada → 5 Ganada / 6 Perdida.
// «Evaluación» es un estado anterior: ya no se ofrece, pero las oportunidades que lo tienen se siguen viendo.
export const ESTADOS_OP = {
  NUEVO: ["Nueva oportunidad", "neutro"], CONTACTADO: ["Contactado", "azul"], NEGOCIACION: ["En negociación", "amarillo"],
  COTIZADA: ["Propuesta enviada", "amarillo"], APROBADA: ["Ganada", "verde"], NO_CONCRETADA: ["Perdida", "rojo"],
  EVALUACION: ["Evaluación (estado anterior)", "neutro"],
};
export const FLUJO_OP = ["NUEVO", "CONTACTADO", "NEGOCIACION", "COTIZADA", "APROBADA", "NO_CONCRETADA"];
export const ESTADOS_OP_FLUJO = Object.fromEntries(FLUJO_OP.map((k) => [k, ESTADOS_OP[k]]));
const TIPOS_INTERACCION = {
  LLAMADA: ["Llamada", Phone], REUNION: ["Reunión", Users], CORREO: ["Correo", Mail], WHATSAPP: ["WhatsApp", MessageCircle],
  PROPUESTA: ["Propuesta comercial", FileText], OTRO: ["Otro", MessageSquareText],
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
    if (m.tipo === "INTERACCION") return "anotó un seguimiento";
    if (m.tipo === "CLIENTE") return "la convirtió en cliente";
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
  servicio_detalle: "Servicio", descripcion: "Descripción", prospecto_nombre: "Posible cliente", prospecto_contacto: "Contacto",
  prospecto_telefono: "Teléfono", prospecto_correo: "Correo", prospecto_rnc: "RNC", servicios_interes: "Servicios de interés",
  valor_estimado: "Valor potencial",
};

const nombreServicio = (codigo) => SERVICIOS.find((s) => s[0] === codigo)?.[1] || codigo;
const sinTildes = (t = "") => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

// ---------------------------------------------------------------- Buscar un cliente registrado escribiendo su nombre o RNC
export function BuscadorCliente({ valor, onCambio, etiqueta = "Cliente registrado" }) {
  const [clientes] = useRecurso("clientes");
  const [texto, setTexto] = useState("");
  const elegido = (clientes || []).find((c) => String(c.id) === String(valor));
  const lista = useMemo(() => {
    const t = sinTildes(texto.trim());
    if (!t) return [];
    return (clientes || []).filter((c) => sinTildes(c.nombre).includes(t) || (c.rnc || "").replace(/\D/g, "").includes(t.replace(/\D/g, "") || "—")).slice(0, 8);
  }, [clientes, texto]);
  if (valor) {
    return (
      <Campo etiqueta={etiqueta}>{() => (
        <div className="flex items-center gap-2 rounded-xl border border-azul bg-azul/5 px-3 py-2">
          <Building2 className="size-4 shrink-0 text-azul" aria-hidden />
          <span className="flex-1 font-medium">{elegido?.nombre || "Cliente elegido"}</span>
          <button type="button" onClick={() => onCambio("")} className="rounded-lg p-1 text-gris hover:bg-white hover:text-tinta" aria-label="Elegir otro cliente"><X className="size-4" /></button>
        </div>
      )}</Campo>
    );
  }
  return (
    <Campo etiqueta={etiqueta} ayuda="Escribe parte del nombre o el RNC y elige de la lista.">{(id) => (
      <div className="space-y-1.5">
        <label className="relative block">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" aria-hidden />
          <input id={id} className="campo pl-9" value={texto} onChange={(e) => setTexto(e.target.value)} placeholder={clientes ? "Buscar cliente…" : "Cargando clientes…"} autoComplete="off" />
        </label>
        {texto.trim() && (
          <ul className="max-h-56 overflow-y-auto rounded-xl border border-linea bg-white">
            {lista.map((c) => (
              <li key={c.id}><button type="button" onClick={() => { onCambio(String(c.id)); setTexto(""); }} className="w-full px-3 py-2 text-left text-sm hover:bg-fondo">{c.nombre}{c.rnc && <span className="text-gris"> · RNC {c.rnc}</span>}</button></li>
            ))}
            {!lista.length && <li className="px-3 py-2 text-sm text-gris">No hay clientes con ese nombre. Si todavía no es cliente, regístralo como posible cliente.</li>}
          </ul>
        )}
      </div>
    )}</Campo>
  );
}

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
    setError(""); setServicios(editando ? inicial.servicios_interes || [] : []);
    const prospecto = {
      prospecto_nombre: inicial?.prospecto_nombre || "", prospecto_contacto: inicial?.prospecto_contacto || "",
      prospecto_telefono: inicial?.prospecto_telefono || "", prospecto_correo: inicial?.prospecto_correo || "", prospecto_rnc: inicial?.prospecto_rnc || "",
    };
    setF(editando ? {
      id: inicial.id, modo: inicial.cliente ? "cliente" : "prospecto", cliente: inicial.cliente ? String(inicial.cliente) : "", ...prospecto,
      titulo: inicial.titulo, necesidades: inicial.necesidades || "", valor_estimado: inicial.valor_estimado ?? "",
      responsable: inicial.responsable ? String(inicial.responsable) : "", departamento: inicial.departamento ? String(inicial.departamento) : "",
      fecha_contacto: inicial.fecha_contacto || "", proximo_seguimiento: inicial.proximo_seguimiento || "",
    } : {
      modo: inicial?.cliente ? "cliente" : "prospecto", cliente: inicial?.cliente ? String(inicial.cliente) : "", ...prospecto,
      titulo: "", necesidades: "", valor_estimado: "", responsable: String(usuario.id),
      departamento: usuario.departamento_id ? String(usuario.departamento_id) : "", fecha_contacto: hoyISO(), proximo_seguimiento: "",
    });
  }, [abierto, inicial, editando, usuario]);
  const cambiar = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const alternar = (codigo) => setServicios((l) => (l.includes(codigo) ? l.filter((c) => c !== codigo) : [...l, codigo]));
  const esProspecto = f.modo === "prospecto";
  const guardar = async (e) => {
    e.preventDefault();
    if (esProspecto && !f.prospecto_nombre?.trim()) return setError("Escribe el nombre de la empresa o persona interesada.");
    if (!esProspecto && !f.cliente) return setError("Busca y elige el cliente registrado.");
    if (!f.titulo?.trim()) return setError("Escribe un título para la oportunidad.");
    if (f.valor_estimado !== "" && Number(f.valor_estimado) < 0) return setError("El valor potencial no puede ser negativo.");
    setGuardando(true); setError("");
    try {
      const datos = { ...f };
      delete datos.modo;
      const o = await guardarOportunidad({
        ...datos, cliente: esProspecto ? null : Number(f.cliente), prospecto_nombre: f.prospecto_nombre.trim(), titulo: f.titulo.trim(),
        responsable: f.responsable ? Number(f.responsable) : null, departamento: f.departamento ? Number(f.departamento) : null,
        fecha_contacto: f.fecha_contacto || null, proximo_seguimiento: f.proximo_seguimiento || null,
        valor_estimado: f.valor_estimado === "" ? null : String(f.valor_estimado), servicios_interes: servicios,
      });
      // Con un cliente registrado, cada servicio nuevo se vuelve una solicitud para su departamento (como siempre).
      // Con un posible cliente, quedan anotados y se envían cuando se convierta en cliente.
      if (!esProspecto && !editando) {
        for (const codigo of servicios) {
          const sugerido = deptoSugerido(deptos, codigo);
          await guardarSolicitud({ oportunidad: o.id, servicio: codigo, servicio_detalle: codigo === "OTRO" ? "Por definir" : "",
            departamento: sugerido || (f.departamento ? Number(f.departamento) : null), descripcion: f.necesidades || "" });
        }
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
        {!editando && (
          <fieldset className="sm:col-span-2">
            <legend className="mb-1.5 text-sm font-medium">¿Con quién es la oportunidad?</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              {[["prospecto", "Posible cliente", "Todavía no está registrado como cliente", <UserPlus key="i" className="size-4 text-azul" aria-hidden />],
                ["cliente", "Cliente registrado", "Ya está en la lista de clientes", <Building2 key="i" className="size-4 text-azul" aria-hidden />]].map(([valor, titulo, ayuda, icono]) => (
                <label key={valor} className={cx("flex cursor-pointer items-start gap-2.5 rounded-xl border px-3 py-2.5", f.modo === valor ? "border-azul bg-azul/5" : "border-linea")}>
                  <input type="radio" name="modo-oportunidad" className="mt-1 size-4 accent-azul" checked={f.modo === valor} onChange={() => setF((x) => ({ ...x, modo: valor }))} />
                  <span><span className="flex items-center gap-1.5 font-medium">{icono}{titulo}</span><span className="block text-xs text-gris">{ayuda}</span></span>
                </label>
              ))}
            </div>
          </fieldset>
        )}
        {esProspecto ? (
          <>
            <Campo etiqueta="Empresa o persona interesada" className="sm:col-span-2">{(id) => <input id={id} className="campo" value={f.prospecto_nombre || ""} onChange={cambiar("prospecto_nombre")} maxLength={200} placeholder="Ej.: Ferretería La Unión" />}</Campo>
            <Campo etiqueta="Persona de contacto">{(id) => <input id={id} className="campo" value={f.prospecto_contacto || ""} onChange={cambiar("prospecto_contacto")} maxLength={150} />}</Campo>
            <Campo etiqueta="Teléfono">{(id) => <input id={id} type="tel" className="campo" value={f.prospecto_telefono || ""} onChange={cambiar("prospecto_telefono")} maxLength={40} placeholder="809-000-0000" />}</Campo>
            <Campo etiqueta="Correo">{(id) => <input id={id} type="email" className="campo" value={f.prospecto_correo || ""} onChange={cambiar("prospecto_correo")} maxLength={254} />}</Campo>
            <Campo etiqueta="RNC o cédula (opcional)" ayuda="Ayuda a no registrar el mismo cliente dos veces.">{(id) => <input id={id} className="campo" value={f.prospecto_rnc || ""} onChange={cambiar("prospecto_rnc")} maxLength={20} />}</Campo>
          </>
        ) : (
          <div className="sm:col-span-2"><BuscadorCliente valor={f.cliente} onCambio={(v) => setF((x) => ({ ...x, cliente: v }))} /></div>
        )}
        <Campo etiqueta="Título" className="sm:col-span-2">{(id) => <input id={id} className="campo" value={f.titulo || ""} onChange={cambiar("titulo")} maxLength={200} placeholder="Ej.: Campaña de lanzamiento 2027" />}</Campo>
        <Campo etiqueta="Qué necesita" className="sm:col-span-2">{(id) => <textarea id={id} rows={3} className="campo" value={f.necesidades || ""} onChange={cambiar("necesidades")} />}</Campo>
        <Campo etiqueta="Valor potencial (RD$)" ayuda="Cuánto podría facturarse si se gana. Un estimado basta.">{(id) => <input id={id} type="number" min="0" step="0.01" inputMode="decimal" className="campo num" value={f.valor_estimado ?? ""} onChange={cambiar("valor_estimado")} placeholder="0.00" />}</Campo>
        <SelectorPersona etiqueta="Quién la gestiona" valor={f.responsable} onCambio={(v) => setF((x) => ({ ...x, responsable: v }))} />
        <SelectorDepto etiqueta="Departamento que la lleva" valor={f.departamento} onCambio={(v) => setF((x) => ({ ...x, departamento: v }))} />
        <Campo etiqueta="Primer contacto">{(id) => <input id={id} type="date" className="campo" value={f.fecha_contacto || ""} onChange={cambiar("fecha_contacto")} />}</Campo>
        <Campo etiqueta="Próximo seguimiento" ayuda="Ese día le llega un aviso a quien la gestiona.">{(id) => <input id={id} type="date" className="campo" value={f.proximo_seguimiento || ""} onChange={cambiar("proximo_seguimiento")} />}</Campo>
        <fieldset className="sm:col-span-2">
          <legend className="mb-1.5 text-sm font-medium">Servicios que le interesan{" "}
            <span className="font-normal text-gris">{esProspecto ? "(se envían a cada departamento cuando se convierta en cliente)" : editando ? "(para pedirlos a un departamento usa «Agregar servicio»)" : "(se crea una solicitud para cada departamento)"}</span>
          </legend>
          <div className="flex flex-wrap gap-2">
            {SERVICIOS.map(([codigo, nombre, depto]) => (
              <label key={codigo} className={cx("flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-1.5 text-sm", servicios.includes(codigo) ? "border-azul bg-azul/5" : "border-linea")}>
                <input type="checkbox" className="size-4 accent-azul" checked={servicios.includes(codigo)} onChange={() => alternar(codigo)} />
                {nombre}{depto && <span className="text-xs text-gris">· {depto}</span>}
              </label>
            ))}
          </div>
        </fieldset>
      </form>
    </Modal>
  );
}

// ---------------------------------------------------------------- Seguimiento: llamadas, reuniones, correos, WhatsApp y propuestas
const ahoraLocal = () => {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
};

function IconoTipo({ tipo, className }) {
  const Icono = TIPOS_INTERACCION[tipo]?.[1] || MessageSquareText;
  return <Icono className={className} aria-hidden />;
}

function Interacciones({ o, onCambio, onMarcarPropuesta }) {
  const { usuario } = useSesion();
  const avisar = useAviso();
  const [abierto, setAbierto] = useState(false);
  const [f, setF] = useState({});
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const empezar = () => { setF({ tipo: "LLAMADA", fecha: ahoraLocal(), nota: "", monto_propuesta: "", usuario: String(usuario.id), proximo_seguimiento: "" }); setError(""); setAbierto(true); };
  const cambiar = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const guardar = async (e) => {
    e.preventDefault();
    if (!f.nota.trim()) return setError("Escribe qué se habló o qué se envió.");
    setGuardando(true); setError("");
    try {
      await registrarInteraccion(o.id, {
        tipo: f.tipo, fecha: f.fecha || undefined, nota: f.nota.trim(), usuario: f.usuario ? Number(f.usuario) : null,
        monto_propuesta: f.tipo === "PROPUESTA" && f.monto_propuesta !== "" ? String(f.monto_propuesta) : null,
        ...(f.proximo_seguimiento ? { proximo_seguimiento: f.proximo_seguimiento } : {}),
      });
      setAbierto(false); onCambio(); avisar("Seguimiento anotado");
    } catch (err) { setError(err.message); }
    setGuardando(false);
  };
  const ultima = o.interacciones?.[0];
  const sugerirPropuesta = ultima?.tipo === "PROPUESTA" && !["COTIZADA", "APROBADA", "NO_CONCRETADA"].includes(o.estado);
  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 font-semibold"><MessageCircle className="size-4 text-azul" aria-hidden />Reuniones, conversaciones y propuestas ({o.interacciones?.length || 0})</h3>
        {!abierto && <Boton tam="sm" variante="secundario" icono={Plus} onClick={empezar}>Anotar seguimiento</Boton>}
      </div>
      {abierto && (
        <form onSubmit={guardar} className="grid gap-3 rounded-xl border border-azul/30 bg-azul/5 p-4 sm:grid-cols-2">
          {error && <Alerta className="sm:col-span-2">{error}</Alerta>}
          <fieldset className="sm:col-span-2">
            <legend className="mb-1.5 text-sm font-medium">¿Qué fue?</legend>
            <div className="flex flex-wrap gap-2">
              {Object.entries(TIPOS_INTERACCION).map(([k, [n]]) => (
                <label key={k} className={cx("flex cursor-pointer items-center gap-1.5 rounded-xl border px-3 py-1.5 text-sm", f.tipo === k ? "border-azul bg-white" : "border-linea bg-white/60")}>
                  <input type="radio" name="tipo-interaccion" className="sr-only" checked={f.tipo === k} onChange={() => setF({ ...f, tipo: k })} />
                  <IconoTipo tipo={k} className={cx("size-4", f.tipo === k ? "text-azul" : "text-gris")} />{n}
                </label>
              ))}
            </div>
          </fieldset>
          <Campo etiqueta="Cuándo">{(id) => <input id={id} type="datetime-local" className="campo" value={f.fecha} onChange={cambiar("fecha")} />}</Campo>
          <SelectorPersona etiqueta="Quién lo hizo" valor={f.usuario} onCambio={(v) => setF((x) => ({ ...x, usuario: v }))} />
          <Campo etiqueta={f.tipo === "PROPUESTA" ? "Qué se propuso" : "Qué se habló"} className="sm:col-span-2">{(id) => <textarea id={id} rows={3} className="campo" value={f.nota} onChange={cambiar("nota")} maxLength={4000} placeholder={f.tipo === "PROPUESTA" ? "Ej.: Plan trimestral de redes con 12 publicaciones al mes" : "Ej.: Le interesa empezar en enero; pidió precios"} />}</Campo>
          {f.tipo === "PROPUESTA"
            ? <Campo etiqueta="Monto de la propuesta (RD$)">{(id) => <input id={id} type="number" min="0" step="0.01" inputMode="decimal" className="campo num" value={f.monto_propuesta} onChange={cambiar("monto_propuesta")} />}</Campo>
            : <span className="hidden sm:block" />}
          <Campo etiqueta="Próximo seguimiento (opcional)" ayuda="Agenda la siguiente llamada o visita.">{(id) => <input id={id} type="date" className="campo" value={f.proximo_seguimiento} onChange={cambiar("proximo_seguimiento")} />}</Campo>
          <div className="flex justify-end gap-2 sm:col-span-2">
            <Boton variante="secundario" onClick={() => setAbierto(false)}>Cancelar</Boton>
            <Boton type="submit" cargando={guardando}>Guardar</Boton>
          </div>
        </form>
      )}
      {sugerirPropuesta && (
        <Alerta tono="amarillo">Se anotó una propuesta. <button type="button" className="font-medium underline" onClick={onMarcarPropuesta}>Pasar la oportunidad a «Propuesta enviada»</button></Alerta>
      )}
      <ol className="space-y-2">
        {(o.interacciones || []).map((i) => {
          const nombre = TIPOS_INTERACCION[i.tipo]?.[0] || i.tipo_nombre;
          return (
            <li key={i.id} className="flex gap-3 rounded-xl border border-linea px-3 py-2 text-sm">
              <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-full bg-azul/10 text-azul"><IconoTipo tipo={i.tipo} className="size-4" /></span>
              <div className="min-w-0 flex-1">
                <p className="text-gris"><span className="font-medium text-tinta">{nombre}</span> · {fechaHora(i.fecha)} · {i.usuario_nombre || i.registrado_por_nombre || "—"}
                  {i.monto_propuesta != null && <> · <span className="num font-medium text-tinta">{dinero(i.monto_propuesta)}</span></>}</p>
                <p className="mt-0.5 whitespace-pre-line">{i.nota}</p>
              </div>
            </li>
          );
        })}
        {!o.interacciones?.length && <li className="text-sm text-gris">Todavía no hay seguimientos. Anota cada llamada, reunión, correo, WhatsApp o propuesta para que el equipo sepa en qué va.</li>}
      </ol>
    </section>
  );
}

// ---------------------------------------------------------------- Posible cliente → cliente registrado (sin duplicar)
function ConvertirCliente({ o, onHecho, onCancelar }) {
  const avisar = useAviso();
  const [datos, setDatos] = useState(null);
  const [otro, setOtro] = useState("");
  const [trabajando, setTrabajando] = useState(false);
  const [error, setError] = useState("");
  const buscar = useCallback(() => coincidenciasCliente(o.id).then(setDatos).catch((e) => setError(e.message)), [o.id]);
  useEffect(() => { buscar(); }, [buscar]);
  const convertir = async (cliente) => {
    setTrabajando(true); setError("");
    try {
      const r = await convertirEnCliente(o.id, cliente ? Number(cliente) : null);
      avisar(r.cliente_nuevo ? `Cliente «${r.cliente_nombre}» registrado` : `Oportunidad enlazada a «${r.cliente_nombre}»`);
      onHecho();
    } catch (e) {
      if (e.status === 409) buscar();
      setError(e.message);
    }
    setTrabajando(false);
  };
  const fila = (c, principal = false) => (
    <li key={c.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2">
      <span className="font-medium">{c.nombre}</span>
      <span className="text-sm text-gris">{[c.rnc && `RNC ${c.rnc}`, c.contacto, c.telefono].filter(Boolean).join(" · ")}</span>
      <Boton tam="sm" variante={principal ? "primario" : "secundario"} className="ml-auto" cargando={trabajando} onClick={() => convertir(c.id)}>Es este: enlazar</Boton>
    </li>
  );
  return (
    <section className="space-y-3 rounded-xl border border-verde/40 bg-verde-50/40 p-4">
      <h3 className="flex items-center gap-2 font-semibold"><UserPlus className="size-4 text-verde" aria-hidden />Convertir «{o.prospecto_nombre}» en cliente</h3>
      <p className="text-sm text-gris">Queda en la lista de clientes y los servicios que le interesan pasan a cada departamento para iniciar el proyecto o la orden de trabajo.</p>
      {error && <Alerta>{error}</Alerta>}
      {!datos ? <Cargando texto="Buscando si ya está registrado…" /> : (
        <>
          {datos.iguales.length > 0 ? (
            <div className="space-y-1.5">
              <p className="text-sm font-medium">Ya hay un cliente registrado con el mismo nombre o RNC. Enlázalo para no tenerlo repetido:</p>
              <ul className="divide-y divide-linea rounded-xl border border-linea bg-white">{datos.iguales.map((c) => fila(c, true))}</ul>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <Boton icono={UserPlus} cargando={trabajando} onClick={() => convertir(null)}>Registrar como cliente nuevo</Boton>
              <span className="text-sm text-gris">Se usan los datos que ya se anotaron (contacto, teléfono, correo y RNC).</span>
            </div>
          )}
          {datos.parecidos.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-sm font-medium">Clientes con nombre parecido: ¿es alguno de estos?</p>
              <ul className="divide-y divide-linea rounded-xl border border-linea bg-white">{datos.parecidos.map((c) => fila(c))}</ul>
            </div>
          )}
          <div className="grid gap-2 sm:grid-cols-[1fr_auto] sm:items-end">
            <BuscadorCliente etiqueta="O busca otro cliente registrado" valor={otro} onCambio={setOtro} />
            <Boton variante="secundario" disabled={!otro} cargando={trabajando} onClick={() => convertir(otro)}>Enlazar</Boton>
          </div>
        </>
      )}
      {onCancelar && <div className="flex justify-end"><Boton tam="sm" variante="secundario" onClick={onCancelar}>Ahora no</Boton></div>}
    </section>
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
  const [convirtiendo, setConvirtiendo] = useState(false);
  const cargar = useCallback(() => { if (id) obtenerOportunidad(id).then(setO).catch((e) => setError(e.message)); }, [id]);
  useEffect(() => { setO(null); setError(""); setAgregando(false); setMotivo(null); setConvirtiendo(false); cargar(); }, [cargar]);
  const cambiarEstado = async (estado, motivoTexto) => {
    if (estado === "NO_CONCRETADA" && !motivoTexto) return setMotivo("");
    try {
      await guardarOportunidad({ id: o.id, estado, ...(motivoTexto ? { motivo_no_concretado: motivoTexto, motivo: motivoTexto } : {}) });
      setMotivo(null); cargar(); onCambio?.(); avisar(`Estado: ${ESTADOS_OP[estado]?.[0] || estado}`);
      // Ganada con un posible cliente: el siguiente paso es registrarlo como cliente (o enlazar el que ya existe)
      if (estado === "APROBADA" && o.es_prospecto) setConvirtiendo(true);
    } catch (e) { avisar(e.message, "rojo"); }
  };
  // Los 6 estados del flujo; el estado anterior solo aparece en la lista si la oportunidad todavía lo tiene
  const opciones = o ? (FLUJO_OP.includes(o.estado) ? FLUJO_OP : [o.estado, ...FLUJO_OP]) : FLUJO_OP;
  const paso = FLUJO_OP.indexOf(o?.estado);
  return (
    <Modal abierto={!!id} onCerrar={onCerrar} titulo={o ? `${o.codigo} · ${o.titulo}` : "Oportunidad"} descripcion={o?.cliente_nombre} ancho="md:max-w-3xl">
      {error ? <Alerta>{error}</Alerta> : !o ? <Cargando /> : (
        <div className="space-y-5">
          <ol className="flex snap-x gap-1.5 overflow-x-auto pb-1 text-xs [scrollbar-width:none]" aria-label="Avance de la oportunidad">
            {FLUJO_OP.map((k, i) => {
              const actual = k === o.estado;
              const hecho = paso >= 0 && i < paso && !(o.estado === "NO_CONCRETADA" && k === "APROBADA") && !(o.estado === "APROBADA" && k === "NO_CONCRETADA");
              return (
                <li key={k} className={cx("flex shrink-0 snap-start items-center gap-1.5 rounded-full border px-2.5 py-1",
                  actual ? (k === "NO_CONCRETADA" ? "border-rojo bg-rojo-50 font-medium text-[#a3170f]" : k === "APROBADA" ? "border-verde bg-verde-50 font-medium text-verde" : "border-azul bg-azul/5 font-medium text-azul")
                    : hecho ? "border-linea bg-fondo text-tinta" : "border-linea text-gris")} aria-current={actual ? "step" : undefined}>
                  <span className="num">{i + 1}</span>{ESTADOS_OP[k][0]}
                </li>
              );
            })}
          </ol>
          <div className="flex flex-wrap items-end gap-3">
            <Campo etiqueta="Estado" className="min-w-56">{(cid) => (
              <select id={cid} className="campo" value={o.estado} onChange={(e) => cambiarEstado(e.target.value)}>
                {opciones.map((k) => <option key={k} value={k} disabled={!FLUJO_OP.includes(k)}>{FLUJO_OP.includes(k) ? `${FLUJO_OP.indexOf(k) + 1}. ` : ""}{ESTADOS_OP[k]?.[0] || k}</option>)}
              </select>
            )}</Campo>
            <Boton variante="secundario" icono={Pencil} onClick={() => setEditar(true)}>Editar</Boton>
            {o.es_prospecto && o.estado !== "NO_CONCRETADA" && !convirtiendo && (
              <Boton variante={o.estado === "APROBADA" ? "primario" : "secundario"} icono={UserPlus} onClick={() => setConvirtiendo(true)}>Convertir en cliente</Boton>
            )}
            {o.seguimiento_vencido && <Insignia tono="rojo">Seguimiento pendiente</Insignia>}
          </div>
          {o.estado === "EVALUACION" && <Alerta tono="amarillo">Esta oportunidad está en un estado que ya no se usa («Evaluación»). Pásala al paso que corresponda del flujo.</Alerta>}
          {motivo !== null && (
            <form onSubmit={(e) => { e.preventDefault(); if (motivo.trim()) cambiarEstado("NO_CONCRETADA", motivo.trim()); }} className="flex gap-2">
              <input className="campo" autoFocus value={motivo} onChange={(e) => setMotivo(e.target.value)} maxLength={255} placeholder="¿Por qué se perdió?" aria-label="Motivo" />
              <Boton type="submit">Marcar perdida</Boton>
              <Boton variante="secundario" onClick={() => setMotivo(null)}>Cancelar</Boton>
            </form>
          )}
          {o.es_prospecto && o.estado === "APROBADA" && !convirtiendo && (
            <Alerta tono="verde">¡Negocio ganado! Conviértelo en cliente para pasar los servicios a cada departamento e iniciar el proyecto o la orden de trabajo.</Alerta>
          )}
          {convirtiendo && o.es_prospecto && (
            <ConvertirCliente o={o} onCancelar={() => setConvirtiendo(false)} onHecho={() => { setConvirtiendo(false); cargar(); onCambio?.(); }} />
          )}
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-gris">{o.es_prospecto ? "Posible cliente" : "Cliente"}</dt>
              <dd className="font-medium">{o.es_prospecto
                ? <span className="flex flex-wrap items-center gap-1.5">{o.cliente_nombre}<Insignia tono="amarillo">Aún no es cliente</Insignia></span>
                : <Link to={`/clientes/${o.cliente}`} className="text-azul hover:underline">{o.cliente_nombre}</Link>}</dd>
            </div>
            <div><dt className="text-gris">Valor potencial</dt><dd className="num font-medium">{o.valor_estimado != null ? dinero(o.valor_estimado) : "—"}</dd></div>
            <div><dt className="text-gris">Quién la gestiona</dt><dd className="font-medium">{o.responsable_nombre || "—"}</dd></div>
            {o.es_prospecto && (
              <>
                <div><dt className="text-gris">Contacto</dt><dd className="font-medium">{o.prospecto_contacto || "—"}</dd></div>
                <div><dt className="text-gris">Teléfono</dt><dd className="font-medium">{o.prospecto_telefono ? <a className="text-azul hover:underline" href={`tel:${o.prospecto_telefono}`}>{o.prospecto_telefono}</a> : "—"}</dd></div>
                <div><dt className="text-gris">Correo</dt><dd className="break-all font-medium">{o.prospecto_correo ? <a className="text-azul hover:underline" href={`mailto:${o.prospecto_correo}`}>{o.prospecto_correo}</a> : "—"}</dd></div>
              </>
            )}
            <div><dt className="text-gris">Departamento</dt><dd className="font-medium">{o.departamento_nombre || "—"}</dd></div>
            <div><dt className="text-gris">Primer contacto</dt><dd className="font-medium">{fechaCorta(o.fecha_contacto) || "—"}</dd></div>
            <div><dt className="text-gris">Próximo seguimiento</dt><dd className={cx("font-medium", o.seguimiento_vencido && "text-rojo")}>{fechaCorta(o.proximo_seguimiento) || "—"}</dd></div>
            <div><dt className="text-gris">Registrada</dt><dd className="font-medium">{fechaCorta(o.fecha_creacion)} · {o.creado_por_nombre}</dd></div>
          </dl>
          {o.necesidades && <p className="whitespace-pre-line rounded-xl bg-fondo px-4 py-3 text-[15px]">{o.necesidades}</p>}
          {o.estado === "NO_CONCRETADA" && o.motivo_no_concretado && <Alerta tono="rojo"><b>Perdida:</b> {o.motivo_no_concretado}</Alerta>}

          <Interacciones o={o} onCambio={() => { cargar(); onCambio?.(); }} onMarcarPropuesta={() => cambiarEstado("COTIZADA")} />

          <section className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <h3 className="flex items-center gap-2 font-semibold"><FolderKanban className="size-4 text-azul" aria-hidden />
                {o.es_prospecto ? `Servicios que le interesan (${o.servicios_interes?.length || 0})` : `Servicios solicitados (${o.solicitudes.length})`}</h3>
              {!o.es_prospecto && !agregando && <Boton tam="sm" variante="secundario" icono={Plus} onClick={() => setAgregando(true)}>Agregar servicio</Boton>}
            </div>
            {o.es_prospecto ? (
              <>
                <div className="flex flex-wrap gap-1.5">
                  {(o.servicios_interes || []).map((c) => <span key={c} className="rounded-full bg-fondo px-2.5 py-1 text-sm">{nombreServicio(c)}</span>)}
                  {!o.servicios_interes?.length && <span className="text-sm text-gris">Todavía no se anotaron. Usa «Editar» para marcarlos.</span>}
                </div>
                <p className="text-sm text-gris">Cuando se convierta en cliente, cada servicio pasa como solicitud a su departamento para iniciar el proyecto o la orden de trabajo.</p>
              </>
            ) : (
              <>
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
                  {!o.solicitudes.length && <li className="px-4 py-3 text-sm text-gris">Todavía no hay servicios. Agrega uno por cada departamento que debe atenderlo; cuando el cliente lo apruebe, el departamento lo convierte en proyecto u orden de trabajo.</li>}
                </ul>
              </>
            )}
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
