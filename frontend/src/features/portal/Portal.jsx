// Portal del cliente (sin contraseña, con el enlace que le envió ADZONE): avance de sus órdenes, aprobar artes y firmar la entrega.
import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { CheckCircle2, FileText, PenLine, ThumbsUp } from "lucide-react";
import Marca from "@/components/Marca";
import FirmaCanvas from "@/components/FirmaCanvas";
import { portal, portalAprobar, portalArchivo, portalFirmar } from "@/lib/api";
import { dinero, fechaCorta } from "@/lib/formato";
import { Alerta, Barra, Boton, Campo, Cargando, Insignia, Modal, Panel } from "@/components/ui";

function Aprobar({ token, item, onHecho }) {
  const [modo, setModo] = useState(null); // aprobar | cambios
  const [nombre, setNombre] = useState("");
  const [comentario, setComentario] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const enviar = async (e) => {
    e.preventDefault(); setError(""); setEnviando(true);
    try { await portalAprobar(token, item.id, { aprobado: modo === "aprobar", nombre, comentario }); onHecho(modo === "aprobar" ? "¡Gracias! Quedó aprobado." : "Recibimos tus cambios: te enviaremos una nueva versión."); }
    catch (er) { setError(er.message); }
    setEnviando(false);
  };
  return (
    <div className="space-y-3 rounded-xl border border-amarillo bg-amarillo-50/60 p-4">
      <div><p className="font-medium">{item.que}</p><p className="text-sm text-gris">Versión {item.ronda} · espera tu aprobación</p></div>
      <ul className="space-y-2">
        {item.archivos.map((a) => (
          <li key={a.id}>
            {a.tipo?.startsWith("image/")
              ? <a href={portalArchivo(token, a.id)} target="_blank" rel="noreferrer"><img src={portalArchivo(token, a.id)} alt={a.nombre} className="max-h-80 w-full rounded-lg border border-linea bg-white object-contain" /></a>
              : <a className="inline-flex items-center gap-2 text-azul hover:underline" href={portalArchivo(token, a.id)} target="_blank" rel="noreferrer"><FileText className="size-4" />{a.nombre}</a>}
          </li>
        ))}
        {item.archivos.length === 0 && <li className="text-sm text-gris">El equipo te enviará el archivo por otra vía.</li>}
      </ul>
      {!modo ? (
        <div className="flex flex-wrap gap-2">
          <Boton icono={ThumbsUp} onClick={() => setModo("aprobar")}>Aprobar</Boton>
          <Boton variante="secundario" icono={PenLine} onClick={() => setModo("cambios")}>Pedir cambios</Boton>
        </div>
      ) : (
        <form onSubmit={enviar} className="space-y-3">
          {error && <Alerta>{error}</Alerta>}
          <Campo etiqueta="Tu nombre">{(id) => <input id={id} className="campo" value={nombre} onChange={(e) => setNombre(e.target.value)} autoComplete="name" />}</Campo>
          <Campo etiqueta={modo === "aprobar" ? "Comentario (opcional)" : "¿Qué cambios necesitas?"}>
            {(id) => <textarea id={id} rows={3} className="campo" value={comentario} onChange={(e) => setComentario(e.target.value)} />}
          </Campo>
          <div className="flex flex-wrap gap-2">
            <Boton type="submit" cargando={enviando}>{modo === "aprobar" ? "Confirmar aprobación" : "Enviar cambios"}</Boton>
            <Boton variante="fantasma" onClick={() => setModo(null)}>Volver</Boton>
          </div>
          {modo === "aprobar" && <p className="text-xs text-gris">Tu aprobación queda registrada con tu nombre, la fecha y la hora.</p>}
        </form>
      )}
    </div>
  );
}

function FirmarActa({ token, acta, onHecho, onCerrar }) {
  const [f, setF] = useState({ nombre: "", cedula: "", conformidad: "CONFORME", observaciones: "", firma: "" });
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const enviar = async (e) => {
    e.preventDefault(); setError(""); setEnviando(true);
    try { await portalFirmar(token, acta.id, f); onHecho("¡Gracias! El acta quedó firmada."); } catch (er) { setError(er.message); }
    setEnviando(false);
  };
  return (
    <Modal abierto onCerrar={onCerrar} titulo={`Acta de entrega ${acta.numero}`} ancho="md:max-w-lg"
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton type="submit" form="form-acta" cargando={enviando} disabled={!f.firma}>Firmar</Boton></>}>
      <form id="form-acta" onSubmit={enviar} className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        {acta.items?.length > 0 && (
          <ul className="list-disc space-y-1 pl-5 text-[15px]">{acta.items.map((i, n) => <li key={n}>{i.cantidad ? `${i.cantidad} · ` : ""}{i.descripcion}</li>)}</ul>
        )}
        <fieldset className="space-y-2">
          <legend className="etiqueta">¿Cómo lo recibes?</legend>
          {[["CONFORME", "Recibido conforme"], ["OBSERVACIONES", "Recibido con observaciones"]].map(([v, t]) => (
            <label key={v} className="flex items-center gap-2"><input type="radio" name="conformidad" className="accent-azul" checked={f.conformidad === v} onChange={() => setF({ ...f, conformidad: v })} />{t}</label>
          ))}
        </fieldset>
        {f.conformidad === "OBSERVACIONES" && <Campo etiqueta="Observaciones">{(id) => <textarea id={id} rows={3} className="campo" value={f.observaciones} onChange={(e) => setF({ ...f, observaciones: e.target.value })} />}</Campo>}
        <div className="grid gap-3 sm:grid-cols-2">
          <Campo etiqueta="Tu nombre">{(id) => <input id={id} className="campo" value={f.nombre} onChange={(e) => setF({ ...f, nombre: e.target.value })} autoComplete="name" />}</Campo>
          <Campo etiqueta="Cédula (opcional)">{(id) => <input id={id} className="campo" inputMode="numeric" value={f.cedula} onChange={(e) => setF({ ...f, cedula: e.target.value })} />}</Campo>
        </div>
        <FirmaCanvas etiqueta="Tu firma" onCambio={(firma) => setF((x) => ({ ...x, firma: firma || "" }))} />
      </form>
    </Modal>
  );
}

export default function Portal() {
  const { token } = useParams();
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [gracias, setGracias] = useState("");
  const [acta, setActa] = useState(null);
  const cargar = useCallback(() => portal(token).then(setD).catch((e) => setError(e.message)), [token]);
  useEffect(() => { cargar(); }, [cargar]);
  const hecho = (msg) => { setGracias(msg); setActa(null); cargar(); window.scrollTo({ top: 0, behavior: "smooth" }); };
  return (
    <div className="min-h-dvh bg-niebla">
      <header className="bg-noche px-4 py-5 text-white"><div className="mx-auto flex max-w-3xl items-center justify-between gap-3"><Marca className="text-lg" /><span className="text-sm text-white/70">Portal del cliente</span></div></header>
      <main className="mx-auto max-w-3xl space-y-5 px-4 py-6">
        {error ? <Alerta>{error}</Alerta> : !d ? <Cargando /> : <>
          <div><h1 className="text-2xl font-semibold">Hola{d.para ? `, ${d.para.split(" ")[0]}` : ""}</h1><p className="text-gris">{d.una_orden ? "El avance de tu orden" : "Tus órdenes"} con ADZONE · {d.cliente}</p></div>
          {gracias && <Alerta tono="verde"><CheckCircle2 className="mr-1 inline size-4" />{gracias}</Alerta>}
          {d.ordenes.map((o) => (
            <Panel key={o.id} titulo={<span>{o.titulo} <span className="ml-1 text-sm font-normal text-gris num">{o.numero}</span></span>} accion={<Insignia tono={o.estado === "Entregada" ? "verde" : "azul"}>{o.estado}</Insignia>}>
              <div className="space-y-4">
                {o.areas > 0 && (
                  <div className="flex items-center gap-3"><Barra valor={(o.terminadas / o.areas) * 100} className="flex-1" /><span className="text-sm text-gris">{o.terminadas} de {o.areas} partes listas</span></div>
                )}
                <p className="text-sm text-gris">{o.fecha_entrega ? `Entregada el ${fechaCorta(o.fecha_entrega)}` : o.fecha_compromiso ? `Entrega prevista: ${fechaCorta(o.fecha_compromiso)}` : "Fecha de entrega por confirmar"}</p>
                {o.por_aprobar.map((a) => <Aprobar key={a.id} token={token} item={a} onHecho={hecho} />)}
                {o.actas.filter((a) => a.lista).map((a) => (
                  <div key={a.id} className="flex flex-col gap-3 rounded-xl border border-azul/30 bg-azul/5 p-4 sm:flex-row sm:items-center">
                    <p className="min-w-0 sm:flex-1"><b>Acta de entrega {a.numero}</b><span className="block text-sm text-gris">{a.modalidad}{a.direccion ? ` · ${a.direccion}` : ""}: revisa y firma al recibir.</span></p>
                    <Boton icono={PenLine} onClick={() => setActa(a)}>Firmar la entrega</Boton>
                  </div>
                ))}
                {o.aprobadas.length > 0 && (
                  <ul className="space-y-1 text-sm">{o.aprobadas.map((a) => <li key={a.numero} className="flex items-center gap-2"><CheckCircle2 className="size-4 text-verde" />{a.que} · aprobado por {a.por} el {fechaCorta(a.fecha)}</li>)}</ul>
                )}
              </div>
            </Panel>
          ))}
          {d.ordenes.length === 0 && <Alerta tono="amarillo">No hay órdenes abiertas por ahora.</Alerta>}
          {d.facturas.length > 0 && (
            <Panel titulo="Facturas" cuerpo="p-0">
              <ul className="divide-y divide-linea-suave">
                {d.facturas.map((f) => (
                  <li key={f.numero} className="flex items-center gap-3 px-5 py-3 text-sm">
                    <span className="min-w-0 flex-1"><span className="font-medium num">{f.numero}</span><span className="block text-gris">{fechaCorta(f.fecha)}</span></span>
                    <span className="text-right num">{dinero(f.total, f.moneda)}<span className="block text-xs text-gris">{Number(f.pagado) >= Number(f.total) ? "Pagada" : `Pendiente ${dinero(Number(f.total) - Number(f.pagado), f.moneda)}`}</span></span>
                  </li>
                ))}
              </ul>
            </Panel>
          )}
          <p className="text-center text-xs text-gris">Este enlace es personal y vence el {fechaCorta(d.vence)}. ¿Dudas? Escríbele a tu contacto en ADZONE.</p>
        </>}
      </main>
      {acta && <FirmarActa token={token} acta={acta} onHecho={hecho} onCerrar={() => setActa(null)} />}
    </div>
  );
}
