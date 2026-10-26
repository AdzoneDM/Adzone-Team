// Automatizaciones: «cuando pase esto, haz aquello». Avisan, crean tareas o mandan datos a n8n.
import { useCallback, useEffect, useState } from "react";
import { BellRing, CheckCircle2, CircleX, ListPlus, Pencil, Plus, Trash2, Webhook, Zap } from "lucide-react";
import { catalogoAutomatizaciones, ejecuciones, eliminarRegla, guardarRegla, listarReglas } from "@/lib/api";
import { fechaHora } from "@/lib/formato";
import { SelectorPersona } from "@/components/Selectores";
import { Alerta, Boton, Cabecera, Campo, Cargando, Modal, Panel, Vacio, cx, useAviso, useConfirmar } from "@/components/ui";

const ICONO = { AVISAR: BellRing, CREAR_TAREA: ListPlus, WEBHOOK: Webhook };

function frase(r, cat) {
  const ev = cat.eventos.find((e) => e.valor === r.evento)?.nombre || r.evento;
  const cond = [];
  if (r.condiciones?.area) cond.push(`con ${cat.areas.find((t) => t.valor === r.condiciones.area)?.nombre}`);
  if (r.condiciones?.estado) cond.push(`a «${cat.estados.find((t) => t.valor === r.condiciones.estado)?.nombre}»`);
  let accion = "";
  if (r.accion === "AVISAR") {
    const a = (r.parametros?.a || []).map((x) => cat.destinos.find((d) => d.valor === x)?.nombre.toLowerCase());
    if (r.parametros?.usuario_id) a.push("una persona");
    accion = `avisar a ${a.join(", ") || "nadie"}`;
  } else if (r.accion === "CREAR_TAREA") accion = `crear la tarea «${r.parametros?.titulo}»`;
  else accion = "enviar los datos a n8n";
  return <>Cuando <b>{ev.toLowerCase()}</b>{cond.length ? ` ${cond.join(" ")}` : ""}, <b>{accion}</b>.</>;
}

function Editor({ abierto, inicial, cat, onCerrar, onGuardado }) {
  const [f, setF] = useState({});
  const [error, setError] = useState("");
  useEffect(() => {
    if (!abierto) return;
    setError("");
    setF(inicial?.id ? JSON.parse(JSON.stringify(inicial)) : { nombre: "", activa: true, evento: "ORDEN_ESTADO", condiciones: {}, accion: "AVISAR", parametros: { a: ["responsable"], titulo: "{numero}: {estado_nombre}", mensaje: "{titulo} · {cliente}" } });
  }, [abierto, inicial]);
  if (!f.evento) return null;
  const esOrden = f.evento.startsWith("ORDEN");
  const p = f.parametros || {};
  const setP = (cambios) => setF({ ...f, parametros: { ...p, ...cambios } });
  const guardar = async (e) => {
    e.preventDefault();
    if (!f.nombre?.trim()) return setError("Ponle un nombre que diga qué hace.");
    try { await guardarRegla({ ...f, nombre: f.nombre.trim() }); onGuardado(); } catch (err) { setError(err.message); }
  };
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={inicial?.id ? "Editar automatización" : "Nueva automatización"} ancho="md:max-w-2xl"
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton type="submit" form="form-regla">Guardar</Boton></>}>
      <form id="form-regla" onSubmit={guardar} className="space-y-5">
        {error && <Alerta>{error}</Alerta>}
        <Campo etiqueta="Nombre">{(id) => <input id={id} className="campo" value={f.nombre} onChange={(e) => setF({ ...f, nombre: e.target.value })} maxLength={150} placeholder="Ej.: Orden de impresión lista: avisar a ventas" autoFocus />}</Campo>
        <fieldset className="rounded-xl border border-linea p-4">
          <legend className="px-1 text-sm font-semibold text-azul">Cuando…</legend>
          <div className="grid gap-4 sm:grid-cols-3">
            <Campo etiqueta="Pasa esto" className="sm:col-span-3">{(id) => <select id={id} className="campo" value={f.evento} onChange={(e) => setF({ ...f, evento: e.target.value, condiciones: {} })}>
              {cat.eventos.map((x) => <option key={x.valor} value={x.valor}>{x.nombre}</option>)}</select>}</Campo>
            {esOrden && <Campo etiqueta="Solo OT que pasan por">{(id) => <select id={id} className="campo" value={f.condiciones?.area || ""} onChange={(e) => setF({ ...f, condiciones: { ...f.condiciones, area: e.target.value } })}>
              <option value="">Cualquier área</option>{cat.areas.map((x) => <option key={x.valor} value={x.valor}>{x.nombre}</option>)}</select>}</Campo>}
            {f.evento === "ORDEN_ESTADO" && <Campo etiqueta="Que pasa a">{(id) => <select id={id} className="campo" value={f.condiciones?.estado || ""} onChange={(e) => setF({ ...f, condiciones: { ...f.condiciones, estado: e.target.value } })}>
              <option value="">Cualquier estado</option>{cat.estados.map((x) => <option key={x.valor} value={x.valor}>{x.nombre}</option>)}</select>}</Campo>}
          </div>
        </fieldset>
        <fieldset className="rounded-xl border border-linea p-4">
          <legend className="px-1 text-sm font-semibold text-azul">…haz esto</legend>
          <div className="mb-4 grid grid-cols-3 gap-2">
            {cat.acciones.map((a) => {
              const I = ICONO[a.valor];
              return <button key={a.valor} type="button" aria-pressed={f.accion === a.valor} onClick={() => setF({ ...f, accion: a.valor, parametros: a.valor === "AVISAR" ? { a: ["responsable"] } : a.valor === "CREAR_TAREA" ? { titulo: "", asignar: "responsable", dias: 2 } : { url: "" } })}
                className={cx("flex flex-col items-center gap-1 rounded-xl border p-3 text-center text-sm font-medium", f.accion === a.valor ? "border-azul bg-azul/5 text-azul" : "border-linea")}><I className="size-5" />{a.nombre}</button>;
            })}
          </div>
          {f.accion === "AVISAR" && (
            <div className="space-y-4">
              <fieldset><legend className="etiqueta">A quién</legend>
                <div className="flex flex-wrap gap-2">{cat.destinos.map((x) => {
                  const on = (p.a || []).includes(x.valor);
                  return <button key={x.valor} type="button" aria-pressed={on} onClick={() => setP({ a: on ? p.a.filter((y) => y !== x.valor) : [...(p.a || []), x.valor] })}
                    className={cx("min-h-10 rounded-full border px-3.5 text-sm font-medium", on ? "border-azul bg-azul text-white" : "border-linea bg-white")}>{x.nombre}</button>;
                })}</div></fieldset>
              <SelectorPersona etiqueta="Y también a (opcional)" valor={p.usuario_id || ""} onCambio={(v) => setP({ usuario_id: v ? Number(v) : null })} vacio="Nadie más" />
              <Campo etiqueta="Título del aviso">{(id) => <input id={id} className="campo" value={p.titulo || ""} onChange={(e) => setP({ titulo: e.target.value })} />}</Campo>
              <Campo etiqueta="Mensaje" ayuda={`Puedes usar: ${cat.variables.join(" ")}`}>{(id) => <textarea id={id} rows={2} className="campo" value={p.mensaje || ""} onChange={(e) => setP({ mensaje: e.target.value })} />}</Campo>
            </div>
          )}
          {f.accion === "CREAR_TAREA" && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Campo etiqueta="Título de la tarea" className="sm:col-span-2" ayuda={`Puedes usar: ${cat.variables.slice(0, 4).join(" ")}`}>{(id) => <input id={id} className="campo" value={p.titulo || ""} onChange={(e) => setP({ titulo: e.target.value })} placeholder="Ej.: Llamar a {cliente} para coordinar la entrega" />}</Campo>
              <Campo etiqueta="Para">{(id) => <select id={id} className="campo" value={p.asignar || "responsable"} onChange={(e) => setP({ asignar: e.target.value })}>
                <option value="responsable">El responsable</option><option value="solicitante">Quien la pidió</option><option value="usuario">Una persona fija</option></select>}</Campo>
              <Campo etiqueta="Plazo (días)">{(id) => <input id={id} type="number" min={0} max={90} className="campo" value={p.dias ?? 2} onChange={(e) => setP({ dias: Number(e.target.value) })} />}</Campo>
              {p.asignar === "usuario" && <SelectorPersona etiqueta="Persona" valor={p.usuario_id || ""} onCambio={(v) => setP({ usuario_id: v ? Number(v) : null })} />}
            </div>
          )}
          {f.accion === "WEBHOOK" && (
            <div className="space-y-3">
              <Campo etiqueta="Dirección del webhook de n8n" ayuda="En n8n: nodo «Webhook» → método POST → copia la URL de producción.">{(id) => <input id={id} type="url" className="campo" value={p.url || ""} onChange={(e) => setP({ url: e.target.value })} placeholder="https://n8n.adzone.marketing/webhook/…" />}</Campo>
              <p className="text-sm text-gris">Se envía en JSON: <code className="rounded bg-fondo px-1">evento</code>, <code className="rounded bg-fondo px-1">regla</code>, <code className="rounded bg-fondo px-1">fecha</code> y <code className="rounded bg-fondo px-1">datos</code> (número, título, cliente, estado, responsable, monto…). Si el servidor tiene la clave <code className="rounded bg-fondo px-1">AUTOMATIZACIONES_SECRETO</code>, va firmado en la cabecera <code className="rounded bg-fondo px-1">X-Adzone-Firma</code>.</p>
            </div>
          )}
        </fieldset>
      </form>
    </Modal>
  );
}

export default function Automatizaciones() {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const [cat, setCat] = useState(null);
  const [reglas, setReglas] = useState(null);
  const [log, setLog] = useState([]);
  const [editor, setEditor] = useState(null);
  const [error, setError] = useState("");
  const cargar = useCallback(() => {
    Promise.all([catalogoAutomatizaciones(), listarReglas(), ejecuciones()]).then(([c, r, l]) => { setCat(c); setReglas(r); setLog(l); }).catch((e) => setError(e.message));
  }, []);
  useEffect(() => { cargar(); }, [cargar]);
  if (error) return <Alerta>{error}</Alerta>;
  if (!cat || !reglas) return <Cargando />;
  return (
    <div className="max-w-5xl">
      <Cabecera titulo="Automatizaciones" descripcion="Reglas que trabajan solas: avisan a la persona correcta, crean tareas de seguimiento o mandan los datos a n8n para conectar WhatsApp, correo, Google Sheets o la IA.">
        <Boton icono={Plus} onClick={() => setEditor({})}>Nueva automatización</Boton>
      </Cabecera>
      {reglas.length === 0 ? <Vacio icono={Zap} titulo="Sin automatizaciones" /> : (
        <ul className="space-y-3">
          {reglas.map((r) => {
            const I = ICONO[r.accion];
            return (
              <li key={r.id} className={cx("flex flex-wrap items-center gap-4 rounded-xl border bg-white p-4", r.activa ? "border-linea" : "border-dashed border-linea opacity-70")}>
                <span className={cx("flex size-10 shrink-0 items-center justify-center rounded-xl", r.activa ? "bg-amarillo-50 text-[#a86a00]" : "bg-linea-suave text-gris")}><I className="size-5" /></span>
                <div className="min-w-0 flex-1">
                  <p className="font-semibold">{r.nombre}</p>
                  <p className="text-sm text-gris">{frase(r, cat)}</p>
                  <p className="mt-0.5 text-xs text-gris">{r.veces ? `Se ejecutó ${r.veces} vez/veces · última ${fechaHora(r.ultima_vez)}` : "Todavía no se ha ejecutado"}</p>
                </div>
                <label className="flex items-center gap-2 text-sm font-medium">
                  <input type="checkbox" role="switch" checked={r.activa} className="size-5 accent-azul" onChange={async () => {
                    try { await guardarRegla({ id: r.id, activa: !r.activa }); cargar(); } catch (e) { avisar(e.message, "rojo"); }
                  }} />{r.activa ? "Activa" : "En pausa"}
                </label>
                <Boton variante="fantasma" tam="sm" icono={Pencil} aria-label={`Editar ${r.nombre}`} onClick={() => setEditor(r)} />
                <Boton variante="fantasma" tam="sm" icono={Trash2} aria-label={`Borrar ${r.nombre}`} className="text-rojo" onClick={async () => {
                  if (await confirmar({ titulo: "¿Borrar esta automatización?", mensaje: r.nombre, boton: "Borrar", peligro: true })) { await eliminarRegla(r.id); cargar(); }
                }} />
              </li>
            );
          })}
        </ul>
      )}
      <Panel titulo="Últimas ejecuciones" className="mt-6" cuerpo="p-0">
        {log.length === 0 ? <p className="p-5 text-sm text-gris">Aquí verás cada vez que una regla se ejecute.</p> : (
          <ul className="max-h-96 divide-y divide-linea-suave overflow-y-auto">
            {log.map((x) => (
              <li key={x.id} className="flex items-center gap-3 px-5 py-2.5 text-sm">
                {x.exito ? <CheckCircle2 className="size-4 shrink-0 text-verde" /> : <CircleX className="size-4 shrink-0 text-rojo" />}
                <span className="min-w-0 flex-1 truncate"><span className="font-medium">{x.regla_nombre}</span> · {x.resultado}</span>
                <span className="shrink-0 text-gris">{fechaHora(x.fecha)}</span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
      <Editor abierto={!!editor} inicial={editor} cat={cat} onCerrar={() => setEditor(null)} onGuardado={() => { setEditor(null); avisar("Automatización guardada."); cargar(); }} />
    </div>
  );
}
