// Un caso: su ficha, la evidencia, el historial completo y lo que cada quien puede hacer según su papel.
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  AlarmClock, ArrowLeft, ArrowUpRight, Ban, CheckCircle2, CircleDot, ClipboardCheck, FileText, Flag, GitMerge, Info, Lock, MessageSquarePlus,
  RotateCcw, Send, ShieldCheck, Unlock, UserCheck, UserPlus, Wrench,
} from "lucide-react";
import { accionCaso, casosOpciones, obtenerCaso, urlEvidenciaCaso } from "@/lib/api";
import { fechaCorta, fechaHora, hoyISO } from "@/lib/formato";
import { useVisor } from "@/components/VisorImagen";
import { Alerta, Boton, Campo, Cargando, Modal, cx, useAviso } from "@/components/ui";
import { Archivos, EstadoCaso, PrioridadCaso } from "./comun";

const sumar = (dias) => { const d = new Date(); d.setDate(d.getDate() + dias); return d.toLocaleDateString("en-CA"); };

const ICONOS = { RECIBIDO: Flag, INFO: MessageSquarePlus, CLASIFICADO: ClipboardCheck, DERIVADO: Send, RESPONSABLE: UserPlus, CONFIRMADO: UserCheck,
  AVANCE: CircleDot, BLOQUEO: Ban, DESBLOQUEO: Unlock, ESCALADO: ArrowUpRight, SOLUCION: CheckCircle2, TECNICA: Wrench, VALIDADO: ShieldCheck,
  CERRADO: Lock, REABIERTO: RotateCcw, UNIDO: GitMerge, REVISION: AlarmClock };
const COLOR = { BLOQUEO: "bg-rojo-50 text-rojo", ESCALADO: "bg-rojo-50 text-rojo", CERRADO: "bg-verde-50 text-verde", VALIDADO: "bg-verde-50 text-verde",
  SOLUCION: "bg-[#f0ebfb] text-[#6d4ac8]", TECNICA: "bg-[#e0f3f8] text-[#0e7490]", REABIERTO: "bg-amarillo-50 text-[#8a5a00]" };

function detalleMov(m) {
  const d = m.datos || {};
  const partes = [];
  if (d.area) partes.push(`Área: ${d.area}`);
  if (d.prioridad) partes.push(`Prioridad: ${({ ALTA: "alta", MEDIA: "media", BAJA: "baja" })[d.prioridad]}`);
  if (d.responsable) partes.push(`Responsable: ${d.responsable}${d.confirmado === false ? " (por confirmar)" : ""}`);
  if (d.accion_texto) partes.push(d.accion_texto);
  if (d.autorizacion) partes.push(`Autorización: ${d.autorizacion}`);
  if (d.fecha_estimada) partes.push(`Resolución estimada: ${fechaCorta(d.fecha_estimada)}`);
  if (d.proxima_revision) partes.push(`Próxima revisión: ${fechaCorta(d.proxima_revision)}`);
  if (d.validacion) partes.push(`Validación: ${d.validacion}`);
  if (d.a?.length) partes.push(`Se avisó a: ${d.a.join(", ")}`);
  return partes.join(" · ");
}

// Qué pide cada acción
const ACCIONES = {
  clasificar: { titulo: "Clasificar y derivar", boton: "Guardar y derivar", icono: Send },
  designar: { titulo: "Designar responsable", boton: "Designar", icono: UserPlus },
  avance: { titulo: "Registrar avance", boton: "Registrar", icono: CircleDot },
  bloquear: { titulo: "Registrar bloqueo", boton: "Registrar bloqueo", icono: Ban },
  desbloquear: { titulo: "Bloqueo resuelto", boton: "Quitar bloqueo", icono: Unlock },
  solucion: { titulo: "Comunicar la solución", boton: "Enviar a validación", icono: CheckCircle2 },
  tecnica: { titulo: "Respuesta de Tecnología", boton: "Registrar respuesta", icono: Wrench },
  escalar: { titulo: "Escalar el caso", boton: "Escalar", icono: ArrowUpRight },
  unir: { titulo: "Unir a un caso abierto", boton: "Unir", icono: GitMerge },
  validar: { titulo: "Validar el resultado", boton: "Guardar", icono: ShieldCheck },
  cerrar: { titulo: "Cerrar el caso", boton: "Cerrar caso", icono: Lock },
  reabrir: { titulo: "Reabrir el caso", boton: "Reabrir", icono: RotateCcw },
  info: { titulo: "Agregar información", boton: "Agregar", icono: MessageSquarePlus },
};

function ModalAccion({ accion, caso, opciones, onCerrar, onHecho }) {
  const [f, setF] = useState({});
  const [archivos, setArchivos] = useState([]);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  useEffect(() => {
    setError(""); setArchivos([]);
    const prio = caso.prioridad || "MEDIA";
    setF({
      clasificar: { prioridad: prio, area: caso.area_asignada_id || "", categoria: caso.categoria, tipo: caso.tipo, proxima_revision: sumar(opciones.dias_revision[prio]) },
      designar: { responsable: caso.responsable_id || "" },
      avance: { proxima_revision: sumar(opciones.dias_revision[prio]), fecha_estimada: caso.fecha_estimada || "" },
      bloquear: { proxima_revision: sumar(opciones.dias_revision[prio]) },
      tecnica: { resultado: "REALIZADA" },
      validar: { conforme: "true" },
      cerrar: { resultado: caso.resultado || "" },
    }[accion] || {});
  }, [accion, caso, opciones]);
  if (!accion) return null;
  const a = ACCIONES[accion];
  const poner = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value, ...(k === "prioridad" ? { proxima_revision: sumar(opciones.dias_revision[e.target.value]) } : {}) }));
  const enviar = async () => {
    setEnviando(true); setError("");
    try { onHecho(await accionCaso(caso.id, { accion, ...f }, archivos)); } catch (e) { setError(e.message); }
    setEnviando(false);
  };
  const nota = (etiqueta, ayuda) => <Campo etiqueta={etiqueta} ayuda={ayuda}>{(id) => <textarea id={id} rows={3} className="campo" value={f.nota || ""} onChange={poner("nota")} />}</Campo>;
  const fecha = (k, etiqueta, ayuda) => <Campo etiqueta={etiqueta} ayuda={ayuda}>{(id) => <input id={id} type="date" min={hoyISO()} className="campo" value={f[k] || ""} onChange={poner(k)} />}</Campo>;
  return (
    <Modal abierto onCerrar={onCerrar} titulo={a.titulo} descripcion={`${caso.codigo} · ${caso.titulo}`}
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton icono={a.icono} onClick={enviar} cargando={enviando}>{a.boton}</Boton></>}>
      <div className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        {accion === "clasificar" && <>
          <div className="grid gap-3 sm:grid-cols-2">
            <Campo etiqueta="Prioridad">{(id) => <select id={id} className="campo" value={f.prioridad} onChange={poner("prioridad")}>{opciones.prioridades.map(([v, t]) => <option key={v} value={v}>{t} · revisión cada {opciones.dias_revision[v]} día{opciones.dias_revision[v] > 1 ? "s" : ""}</option>)}</select>}</Campo>
            <Campo etiqueta="Área que lo atiende">{(id) => <select id={id} className="campo" value={f.area} onChange={poner("area")}><option value="">Elige…</option>{opciones.departamentos.map((d) => <option key={d.id} value={d.id}>{d.nombre}</option>)}</select>}</Campo>
            <Campo etiqueta="Tipo">{(id) => <select id={id} className="campo" value={f.tipo} onChange={poner("tipo")}>{opciones.tipos.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select>}</Campo>
            <Campo etiqueta="Tema">{(id) => <select id={id} className="campo" value={f.categoria} onChange={poner("categoria")}>{opciones.categorias.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select>}</Campo>
          </div>
          {fecha("proxima_revision", "Próxima revisión")}
          {["ACCESOS", "DATOS", "CONFIGURACION", "FUNCIONALIDAD"].includes(f.categoria) && <Alerta tono="azul">Es un tema técnico: derívalo a Tecnología, que evalúa, gestiona la autorización y ejecuta el cambio aprobado.</Alerta>}
          {nota("Nota (opcional)")}
        </>}
        {accion === "designar" && <Campo etiqueta={`Persona de ${caso.area_asignada}`}>{(id) => <select id={id} className="campo" value={f.responsable} onChange={poner("responsable")}><option value="">Elige…</option>{(caso.candidatos || []).map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}</select>}</Campo>}
        {accion === "avance" && <>{nota("¿Qué se hizo?")}<div className="grid gap-3 sm:grid-cols-2">{fecha("proxima_revision", "Próxima revisión")}{fecha("fecha_estimada", "Resolución estimada (si se sabe)")}</div></>}
        {accion === "bloquear" && <>{nota("Motivo del bloqueo", "Qué falta o de quién se depende.")}{fecha("proxima_revision", "Próxima revisión")}</>}
        {accion === "desbloquear" && nota("¿Cómo se resolvió? (opcional)")}
        {accion === "solucion" && nota("Solución aplicada", "Quien reportó recibe el aviso para confirmar si quedó resuelto.")}
        {accion === "escalar" && nota("Motivo", "Se avisa a quien dirige el área y a su superior directo.")}
        {accion === "reabrir" && nota("¿Por qué se reabre?", "El historial se conserva.")}
        {accion === "info" && <>{nota("Información")}<Archivos archivos={archivos} setArchivos={setArchivos} /></>}
        {accion === "unir" && <Campo etiqueta="Código del caso abierto" ayuda="Este reporte pasa al historial de ese caso (con su evidencia) y se cierra como unido.">{(id) => <input id={id} className="campo font-mono uppercase" placeholder="CAS-26-0001" value={f.destino || ""} onChange={poner("destino")} />}</Campo>}
        {accion === "tecnica" && <>
          <Campo etiqueta="Resultado">{(id) => <select id={id} className="campo" value={f.resultado} onChange={poner("resultado")}>{opciones.respuestas_tecnicas.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select>}</Campo>
          {nota(f.resultado === "REALIZADA" ? "Acción realizada" : "Motivo")}
          <Campo etiqueta="Autorización aplicada (opcional)" ayuda="Quién autorizó el cambio, si aplica.">{(id) => <input id={id} className="campo" value={f.autorizacion || ""} onChange={poner("autorizacion")} />}</Campo>
        </>}
        {accion === "validar" && <>
          <div role="radiogroup" className="grid grid-cols-2 gap-2">
            {[["true", "Sí, quedó resuelto"], ["false", "No, sigue pasando"]].map(([v, t]) => (
              <button key={v} type="button" role="radio" aria-checked={f.conforme === v} onClick={() => setF((x) => ({ ...x, conforme: v }))}
                className={cx("rounded-xl border px-3 py-2.5 text-sm font-medium", f.conforme === v ? "border-azul bg-azul/5 text-azul ring-2 ring-azul/15" : "border-linea hover:bg-fondo")}>{t}</button>
            ))}
          </div>
          {nota(f.conforme === "false" ? "¿Qué sigue pasando?" : "Comentario (opcional)")}
        </>}
        {accion === "cerrar" && <>
          <Campo etiqueta="Resultado documentado">{(id) => <textarea id={id} rows={3} className="campo" value={f.resultado || ""} onChange={poner("resultado")} />}</Campo>
          {!caso.validado_por && <Campo etiqueta="Validación" ayuda="Quien reportó no lo ha confirmado: escribe con quién y cómo se validó.">{(id) => <input id={id} className="campo" value={f.validacion || ""} onChange={poner("validacion")} placeholder="Ej.: confirmado por teléfono con el encargado de impresiones" />}</Campo>}
        </>}
      </div>
    </Modal>
  );
}

function Dato({ etiqueta, children }) {
  return <div><dt className="text-xs font-medium text-gris">{etiqueta}</dt><dd className="mt-0.5 text-sm text-tinta">{children || "—"}</dd></div>;
}

export default function CasoDetalle() {
  const { id } = useParams();
  const avisar = useAviso();
  const ver = useVisor();
  const [c, setC] = useState(null);
  const [opciones, setOpciones] = useState(null);
  const [error, setError] = useState("");
  const [accion, setAccion] = useState(null);
  const cargar = useCallback(() => obtenerCaso(id).then(setC).catch((e) => setError(e.message)), [id]);
  useEffect(() => { cargar(); casosOpciones().then(setOpciones).catch(() => {}); }, [cargar]);
  if (error) return <Alerta>{error}</Alerta>;
  if (!c || !opciones) return <Cargando />;
  const ac = c.acciones;
  const hacer = async (a) => {
    if (a === "confirmar") { try { setC(await accionCaso(c.id, { accion: a })); avisar("Responsable confirmado"); } catch (e) { avisar(e.message, "rojo"); } return; }
    setAccion(a);
  };
  // Lo que toca ahora, primero
  const principales = [
    ac.clasificar && !c.area_asignada && "clasificar",
    ac.designar && !c.responsable && "designar",
    ac.confirmar && "confirmar",
    ac.validar && "validar",
    ac.tecnica && "tecnica",
    ac.atender && "avance",
    ac.atender && "solucion",
    ac.cerrar && c.estado === "PENDIENTE_VALIDACION" && "cerrar",
    ac.reabrir && "reabrir",
  ].filter(Boolean);
  const secundarias = [
    ac.clasificar && c.area_asignada && "clasificar", ac.designar && c.responsable && "designar",
    ac.atender && (c.bloqueado ? "desbloquear" : "bloquear"), ac.escalar && "escalar", ac.unir && "unir",
    ac.cerrar && c.estado !== "PENDIENTE_VALIDACION" && "cerrar", "info",
  ].filter(Boolean).filter((a) => !principales.includes(a));
  const imagenes = c.evidencias.filter((e) => e.es_imagen).map((e) => ({ id: e.id, src: urlEvidenciaCaso(c.id, e.id), descargar: urlEvidenciaCaso(c.id, e.id, true), nombre: e.nombre, detalle: `${e.subido_por} · ${fechaHora(e.fecha)}` }));
  return (
    <div className="space-y-5">
      <Link to="/casos" className="inline-flex items-center gap-1.5 text-sm font-medium text-azul hover:underline"><ArrowLeft className="size-4" />Casos operativos</Link>
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-5">
          <section className={cx("rounded-2xl bg-white p-5 shadow-sm ring-1", c.vencido ? "ring-rojo/40" : "ring-linea")}>
            <p className="flex flex-wrap items-center gap-2 text-xs text-gris"><span className="font-mono text-sm font-bold text-noche">{c.codigo}</span>{c.tipo_texto} · {c.categoria_texto}</p>
            <h1 className="mt-1 text-2xl font-bold leading-tight">{c.titulo}</h1>
            <div className="mt-2 flex flex-wrap gap-1.5"><EstadoCaso c={c} /><PrioridadCaso p={c.prioridad} />
              {c.vencido && <span className="rounded-full bg-rojo px-2 py-0.5 text-[11.5px] font-semibold text-white">Vencido</span>}
              {c.reaperturas > 0 && <span className="rounded-full bg-amarillo-50 px-2 py-0.5 text-[11.5px] font-semibold text-[#8a5a00]">Reabierto {c.reaperturas}×</span>}</div>
            {c.bloqueado && <Alerta className="mt-3"><b>Bloqueado:</b> {c.motivo_bloqueo}</Alerta>}
            <p className="mt-4 whitespace-pre-line text-[15px] leading-relaxed text-tinta">{c.descripcion}</p>
            <p className="mt-3 text-sm text-gris">Impacto reportado: <b className="font-medium text-tinta">{c.impacto_texto}</b>{c.referencia && <> · Referencia: <b className="font-medium text-tinta">{c.referencia}</b></>}</p>
            {c.evidencias.length > 0 && (
              <ul className="mt-4 flex flex-wrap gap-2">
                {c.evidencias.map((e) => (
                  <li key={e.id}>{e.es_imagen ? (
                    <button type="button" onClick={() => ver(imagenes, imagenes.findIndex((x) => x.id === e.id))} className="block size-20 overflow-hidden rounded-lg ring-1 ring-linea" aria-label={`Ver ${e.nombre}`}>
                      <img src={urlEvidenciaCaso(c.id, e.id)} alt={e.nombre} className="size-full object-cover" loading="lazy" /></button>
                  ) : (
                    <a href={urlEvidenciaCaso(c.id, e.id, true)} className="flex h-20 max-w-48 items-center gap-2 rounded-lg bg-fondo px-3 text-sm ring-1 ring-linea hover:bg-linea-suave"><FileText className="size-5 shrink-0 text-azul" /><span className="truncate">{e.nombre}</span></a>
                  )}</li>
                ))}
              </ul>
            )}
            {c.resultado && <div className="mt-4 rounded-xl bg-verde-50/60 p-3 text-sm"><p className="font-semibold text-verde">Resultado</p><p className="mt-0.5 whitespace-pre-line">{c.resultado}</p>
              {c.validado_por && <p className="mt-1 text-xs text-gris">Validado por {c.validado_por}{c.validacion ? `: ${c.validacion}` : ""}</p>}</div>}
          </section>

          <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-linea">
            <h2 className="text-lg font-semibold">Historial</h2>
            <ol className="relative mt-4 space-y-5 before:absolute before:bottom-2 before:left-[15px] before:top-2 before:w-px before:bg-linea">
              {c.movimientos.map((m) => {
                const Icono = ICONOS[m.tipo] || Info;
                const extra = detalleMov(m);
                return (
                  <li key={m.id} className="relative flex gap-3">
                    <span className={cx("relative z-[1] flex size-8 shrink-0 items-center justify-center rounded-full ring-4 ring-white", COLOR[m.tipo] || "bg-azul/10 text-azul")}><Icono className="size-4" aria-hidden /></span>
                    <div className="min-w-0 flex-1 pt-1">
                      <p className="text-sm"><b className="font-semibold">{m.tipo_texto}</b> <span className="text-gris">· {m.usuario || "Plataforma"} · {fechaHora(m.fecha)}</span></p>
                      {m.nota && <p className="mt-1 whitespace-pre-line text-sm text-tinta">{m.nota}</p>}
                      {extra && <p className="mt-1 text-xs text-gris">{extra}</p>}
                    </div>
                  </li>
                );
              })}
            </ol>
          </section>
        </div>

        <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
          {(principales.length > 0 || secundarias.length > 0) && (
            <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-linea">
              <h2 className="text-sm font-semibold text-noche">Acciones</h2>
              <div className="mt-3 space-y-2">
                {principales.map((a, i) => {
                  const d = a === "confirmar" ? { titulo: "Confirmar responsable", icono: UserCheck } : ACCIONES[a];
                  return <Boton key={a} icono={d.icono} variante={i === 0 ? "primario" : "secundario"} className="w-full justify-start" onClick={() => hacer(a)}>{d.titulo}</Boton>;
                })}
              </div>
              {secundarias.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5 border-t border-linea-suave pt-3">
                  {secundarias.map((a) => { const d = ACCIONES[a]; return <button key={a} type="button" onClick={() => hacer(a)} className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-gris ring-1 ring-linea hover:bg-fondo hover:text-tinta"><d.icono className="size-3.5" aria-hidden />{d.titulo}</button>; })}
                </div>
              )}
            </section>
          )}
          <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-linea">
            <dl className="grid gap-3">
              <Dato etiqueta="Reportó">{c.reportado_por}{c.area_origen ? ` · ${c.area_origen}` : ""}<span className="block text-xs text-gris">{fechaHora(c.recibido)}</span></Dato>
              <Dato etiqueta="Área asignada">{c.area_asignada || <span className="text-gris">Sin derivar todavía</span>}</Dato>
              <Dato etiqueta="Responsable">{c.responsable ? <>{c.responsable}{!c.responsable_confirmado && <span className="ml-1 text-xs text-[#a86a00]">(por confirmar)</span>}</> : null}</Dato>
              <Dato etiqueta="Próxima revisión">{c.proxima_revision ? <span className={cx(c.vencido && "font-semibold text-rojo")}>{fechaCorta(c.proxima_revision)}{c.vencido ? " · vencida" : ""}</span> : null}</Dato>
              <Dato etiqueta="Resolución estimada">{c.fecha_estimada ? fechaCorta(c.fecha_estimada) : null}</Dato>
              {c.cerrado && <Dato etiqueta="Cerrado">{fechaHora(c.cerrado)}</Dato>}
            </dl>
          </section>
          <p className="px-1 text-xs text-gris">Este registro es independiente de los datos de origen: aquí solo se documenta el caso. Los cambios en la plataforma los hace el área autorizada.</p>
        </aside>
      </div>
      <ModalAccion accion={accion} caso={c} opciones={opciones} onCerrar={() => setAccion(null)} onHecho={(n) => { setC(n); setAccion(null); avisar("Caso actualizado"); }} />
    </div>
  );
}
