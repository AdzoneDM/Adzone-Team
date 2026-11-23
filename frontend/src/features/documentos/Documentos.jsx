// Documentos compartidos: sube un archivo, organízalo en carpetas y envíalo a personas o a áreas completas, sin depender de una conversación.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Download, ExternalLink, FileSpreadsheet, FileText, FolderOpen, ImageIcon, Pencil, Plus, Search, Send, Trash2, Upload, Users, X } from "lucide-react";
import { chatPersonas, documentoEditar, documentoEliminar, documentoSubir, documentosLista, urlDocumentoCompartido } from "@/lib/api";
import { fechaHora, hace } from "@/lib/formato";
import { Alerta, Avatar, Boton, Cabecera, Campo, Cargando, Modal, Pestanas, Vacio, cx, useAviso, useConfirmar } from "@/components/ui";

const tamano = (b) => (b < 1024 * 1024 ? `${Math.max(1, Math.round(b / 1024))} KB` : `${(b / 1024 / 1024).toFixed(1)} MB`);
const PERMITIDOS = /\.(jpe?g|png|webp|gif|pdf|docx?|xlsx?|pptx?|txt|csv|zip|odt|ods)$/i;
const MAX = 25 * 1024 * 1024;

function IconoArchivo({ d, className = "size-6" }) {
  if (d.es_imagen) return <ImageIcon className={className} aria-hidden />;
  if (/\.(xlsx?|csv|ods)$/i.test(d.nombre_archivo)) return <FileSpreadsheet className={className} aria-hidden />;
  return <FileText className={className} aria-hidden />;
}

function Destino({ d }) {
  if (d.personal) return <span className="text-xs text-gris">Solo para ti</span>;
  const nombres = [...d.areas.map((a) => `Área ${a.nombre}`), ...d.destinatarios.map((p) => p.nombre)];
  return <span className="text-xs text-gris" title={nombres.join(", ")}>Para: {nombres.slice(0, 2).join(", ")}{nombres.length > 2 ? ` y ${nombres.length - 2} más` : ""}</span>;
}

function Tarjeta({ d, resaltado, onEditar, onEliminar }) {
  return (
    <li className={cx("flex flex-col overflow-hidden rounded-xl border bg-white transition-shadow hover:shadow-md", resaltado ? "border-azul ring-2 ring-azul/30" : "border-linea")}>
      <a href={urlDocumentoCompartido(d.id)} target="_blank" rel="noopener" className="block" aria-label={`Abrir ${d.titulo}`}>
        {d.es_imagen
          ? <img src={urlDocumentoCompartido(d.id)} alt="" loading="lazy" className="h-32 w-full object-cover" />
          : <span className="flex h-32 items-center justify-center bg-fondo text-azul/60"><IconoArchivo d={d} className="size-12" /></span>}
      </a>
      <div className="flex min-w-0 flex-1 flex-col gap-1 p-3">
        <div className="flex items-start gap-2">
          <h3 className="min-w-0 flex-1 truncate !text-[15px] font-semibold text-noche" title={d.titulo}>{d.titulo}</h3>
          {d.nuevo && <span className="shrink-0 rounded-full bg-rojo px-2 py-0.5 text-[10px] font-bold uppercase text-white">Nuevo</span>}
        </div>
        <p className="truncate text-xs text-gris" title={d.nombre_archivo}>{d.nombre_archivo} · {tamano(d.tamano)}</p>
        {d.nota && <p className="line-clamp-2 text-sm text-tinta">{d.nota}</p>}
        <p className="mt-auto pt-1 text-xs text-gris"><span title={fechaHora(d.creado)}>{d.mio ? "Tú" : d.subido_por_nombre} · {hace(d.creado)}</span></p>
        <Destino d={d} />
        {d.carpeta && <span className="inline-flex w-fit items-center gap-1 rounded-md bg-azul/10 px-1.5 py-0.5 text-xs font-medium text-azul"><FolderOpen className="size-3" aria-hidden />{d.carpeta}</span>}
      </div>
      <div className="flex items-center gap-1 border-t border-linea-suave px-2 py-1.5">
        <a href={urlDocumentoCompartido(d.id)} target="_blank" rel="noopener" className="inline-flex h-9 items-center gap-1.5 rounded-lg px-2.5 text-sm font-medium text-azul hover:bg-azul/5"><ExternalLink className="size-4" aria-hidden />Abrir</a>
        <a href={urlDocumentoCompartido(d.id, true)} aria-label={`Descargar ${d.titulo}`} title="Descargar" className="inline-flex size-9 items-center justify-center rounded-lg text-gris hover:bg-fondo hover:text-azul"><Download className="size-4" /></a>
        {d.mio && (
          <span className="ml-auto flex gap-1">
            <button type="button" onClick={() => onEditar(d)} aria-label={`Editar ${d.titulo}`} title="Cambiar con quién se comparte, la carpeta o la nota" className="inline-flex size-9 items-center justify-center rounded-lg text-gris hover:bg-fondo hover:text-azul"><Pencil className="size-4" /></button>
            <button type="button" onClick={() => onEliminar(d)} aria-label={`Eliminar ${d.titulo}`} title="Eliminar" className="inline-flex size-9 items-center justify-center rounded-lg text-gris hover:bg-rojo-50 hover:text-rojo"><Trash2 className="size-4" /></button>
          </span>
        )}
      </div>
    </li>
  );
}

/** Subir y enviar (sin `doc`) o cambiar un documento propio (con `doc`: título, nota, carpeta y con quién se comparte). */
function FormDocumento({ abierto, doc, carpetas, areas, onCerrar, onGuardado }) {
  const nuevo = !doc;
  const entrada = useRef(null);
  const [archivo, setArchivo] = useState(null);
  const [f, setF] = useState({ titulo: "", nota: "", carpeta: "" });
  const [personas, setPersonas] = useState([]);
  const [areasSel, setAreasSel] = useState([]);
  const [texto, setTexto] = useState("");
  const [resultados, setResultados] = useState([]);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [arrastrando, setArrastrando] = useState(false);

  useEffect(() => {
    if (!abierto) return;
    setError(""); setTexto(""); setResultados([]); setArchivo(null);
    setF({ titulo: doc?.titulo || "", nota: doc?.nota || "", carpeta: doc?.carpeta || "" });
    setPersonas(doc ? doc.destinatarios.map((p) => ({ id: p.id, nombre: p.nombre })) : []);
    setAreasSel(doc ? doc.areas.map((a) => a.id) : []);
  }, [abierto, doc]);

  useEffect(() => {
    if (!abierto || texto.trim().length < 2) { setResultados([]); return undefined; }
    const t = setTimeout(() => chatPersonas(texto.trim()).then(setResultados).catch(() => setResultados([])), 250);
    return () => clearTimeout(t);
  }, [texto, abierto]);

  const elegir = (file) => {
    if (!file) return;
    if (!PERMITIDOS.test(file.name)) return setError("Solo imágenes y documentos (PDF, Word, Excel, PowerPoint, texto, CSV o ZIP).");
    if (file.size > MAX) return setError("El archivo pesa más de 25 MB.");
    setError(""); setArchivo(file);
    setF((x) => ({ ...x, titulo: x.titulo || file.name.replace(/\.[^.]+$/, "") }));
  };

  const enviar = async () => {
    setError("");
    if (nuevo && !archivo) return setError("Elige el archivo que quieres subir.");
    if (!f.titulo.trim()) return setError("Ponle un título al documento.");
    setEnviando(true);
    try {
      const datos = { titulo: f.titulo.trim(), nota: f.nota.trim(), carpeta: f.carpeta.trim() };
      const ids = personas.map((p) => p.id);
      const r = nuevo ? await documentoSubir({ archivo, ...datos, destinatarios: ids, areas: areasSel }) : await documentoEditar(doc.id, { ...datos, destinatarios: ids, areas: areasSel });
      onGuardado(r, nuevo);
    } catch (e) { setError(e.message); }
    setEnviando(false);
  };

  const destinos = personas.length + areasSel.length;
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} ancho="md:max-w-xl" titulo={nuevo ? "Subir y enviar un documento" : "Cambiar el documento"}
      descripcion={nuevo ? "Elige el archivo y a quién se lo envías. Si no eliges a nadie, queda guardado solo para ti." : "Los cambios de con quién se comparte avisan a las personas nuevas."}
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton icono={nuevo ? Send : undefined} cargando={enviando} onClick={enviar}>{nuevo ? (destinos ? "Subir y enviar" : "Subir para mí") : "Guardar cambios"}</Boton></>}>
      <div className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        {nuevo && (
          <div onDragOver={(e) => { e.preventDefault(); setArrastrando(true); }} onDragLeave={() => setArrastrando(false)}
            onDrop={(e) => { e.preventDefault(); setArrastrando(false); elegir(e.dataTransfer.files?.[0]); }}
            className={cx("rounded-xl border-2 border-dashed p-5 text-center transition-colors", arrastrando ? "border-azul bg-azul/5" : "border-linea")}>
            <input ref={entrada} type="file" className="hidden" onChange={(e) => { elegir(e.target.files?.[0]); e.target.value = ""; }} aria-label="Elegir el archivo"
              accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.zip,.odt,.ods" />
            {archivo ? (
              <div className="flex items-center gap-3 text-left">
                <span className="flex size-11 items-center justify-center rounded-lg bg-azul/10 text-azul"><FileText className="size-5" aria-hidden /></span>
                <span className="min-w-0 flex-1"><span className="block truncate font-medium">{archivo.name}</span><span className="text-xs text-gris">{tamano(archivo.size)}</span></span>
                <button type="button" onClick={() => setArchivo(null)} aria-label="Quitar el archivo" className="rounded-lg p-2 text-gris hover:bg-fondo hover:text-rojo"><X className="size-4" /></button>
              </div>
            ) : (
              <button type="button" onClick={() => entrada.current?.click()} className="flex w-full flex-col items-center gap-1.5 text-sm text-gris">
                <Upload className="size-7 text-azul" aria-hidden />
                <span><span className="font-semibold text-azul">Elige un archivo</span> o arrástralo aquí</span>
                <span className="text-xs">Imágenes, PDF, Word, Excel, PowerPoint, texto, CSV o ZIP · hasta 25 MB</span>
              </button>
            )}
          </div>
        )}
        <Campo etiqueta="Título">{(id) => <input id={id} className="campo" value={f.titulo} maxLength={150} onChange={(e) => setF({ ...f, titulo: e.target.value })} placeholder="Contrato de la campaña…" autoComplete="off" />}</Campo>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Carpeta (opcional)" ayuda="Para encontrarlo después.">
            {(id) => (<><input id={id} list="carpetas-doc" className="campo" value={f.carpeta} maxLength={60} onChange={(e) => setF({ ...f, carpeta: e.target.value })} placeholder="Contratos, Campañas…" autoComplete="off" />
              <datalist id="carpetas-doc">{carpetas.map((c) => <option key={c} value={c} />)}</datalist></>)}
          </Campo>
          <Campo etiqueta="Nota (opcional)">{(id) => <input id={id} className="campo" value={f.nota} maxLength={300} onChange={(e) => setF({ ...f, nota: e.target.value })} placeholder="Revísalo antes del viernes" autoComplete="off" />}</Campo>
        </div>

        <fieldset>
          <legend className="etiqueta flex items-center gap-1.5"><Users className="size-4" aria-hidden />Enviar a</legend>
          <div className="relative mt-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" aria-hidden />
            <input className="campo pl-9" value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Busca personas por nombre, cargo o área…" aria-label="Buscar personas" autoComplete="off" />
          </div>
          {resultados.length > 0 && (
            <ul className="mt-1 max-h-40 overflow-y-auto rounded-xl border border-linea bg-white shadow-sm">
              {resultados.filter((p) => !personas.some((x) => x.id === p.id)).map((p) => (
                <li key={p.id}><button type="button" onClick={() => { setPersonas((l) => [...l, p]); setTexto(""); setResultados([]); }} className="flex w-full items-center gap-2.5 px-3 py-2 text-left hover:bg-fondo">
                  <Avatar nombre={p.nombre} tam="sm" /><span className="min-w-0"><span className="block truncate text-sm font-medium">{p.nombre}</span><span className="block truncate text-xs text-gris">{[p.puesto, p.departamento].filter(Boolean).join(" · ")}</span></span>
                </button></li>
              ))}
            </ul>
          )}
          {personas.length > 0 && (
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {personas.map((p) => (
                <li key={p.id} className="flex items-center gap-1.5 rounded-full border border-linea bg-fondo py-1 pl-1 pr-2 text-sm"><Avatar nombre={p.nombre} tam="sm" className="!size-6 !text-[10px]" />{p.nombre}
                  <button type="button" onClick={() => setPersonas((l) => l.filter((x) => x.id !== p.id))} aria-label={`Quitar a ${p.nombre}`} className="rounded-full p-0.5 text-gris hover:text-rojo"><X className="size-3.5" /></button></li>
              ))}
            </ul>
          )}
          <p className="mb-1 mt-3 text-sm font-medium text-tinta">o a un área completa</p>
          <div className="flex flex-wrap gap-1.5">
            {areas.map((a) => {
              const on = areasSel.includes(a.id);
              return <button key={a.id} type="button" aria-pressed={on} onClick={() => setAreasSel((l) => (on ? l.filter((x) => x !== a.id) : [...l, a.id]))}
                className={cx("rounded-full border px-3 py-1 text-sm transition-colors", on ? "border-azul bg-azul text-white" : "border-linea bg-white text-tinta hover:border-azul/50")}>{a.nombre}</button>;
            })}
          </div>
        </fieldset>
      </div>
    </Modal>
  );
}

export default function Documentos() {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const [params, setParams] = useSearchParams();
  const [vista, setVista] = useState("todos");
  const [carpeta, setCarpeta] = useState("");
  const [buscar, setBuscar] = useState("");
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState(null); // null | "nuevo" | documento
  const resaltado = Number(params.get("id")) || null;

  const cargar = useCallback(() => {
    documentosLista({ vista: vista === "todos" ? "" : vista, carpeta, q: buscar.trim() }).then((d) => { setDatos(d); setError(""); }).catch((e) => setError(e.message));
  }, [vista, carpeta, buscar]);
  useEffect(() => { const t = setTimeout(cargar, buscar ? 250 : 0); return () => clearTimeout(t); }, [cargar, buscar]);
  useEffect(() => { if (resaltado && datos) { document.getElementById(`doc-${resaltado}`)?.scrollIntoView({ block: "center" }); } }, [resaltado, datos]);

  const eliminar = async (d) => {
    if (!(await confirmar({ titulo: `¿Eliminar «${d.titulo}»?`, mensaje: d.personal ? "Se borra el archivo." : "Las personas con quienes lo compartiste dejarán de verlo.", boton: "Eliminar", peligro: true }))) return;
    try { await documentoEliminar(d.id); avisar("Documento eliminado."); cargar(); } catch (e) { avisar(e.message, "rojo"); }
  };

  const lista = datos?.documentos || [];
  const nuevos = datos?.nuevos || 0;
  const opciones = useMemo(() => [{ valor: "todos", etiqueta: "Todos" }, { valor: "recibidos", etiqueta: nuevos ? `Recibidos (${nuevos} ${nuevos === 1 ? "nuevo" : "nuevos"})` : "Recibidos" }, { valor: "enviados", etiqueta: "Enviados por mí" }], [nuevos]);

  return (
    <div>
      <Cabecera titulo="Documentos" descripcion="Sube un archivo, ordénalo en carpetas y envíalo a una persona o a un área completa.">
        <Boton icono={Plus} onClick={() => setForm("nuevo")}>Subir y enviar</Boton>
      </Cabecera>
      <Pestanas className="mb-4 max-w-xl" opciones={opciones} valor={vista} onCambio={(v) => { setVista(v); setCarpeta(""); }} />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative min-w-52 flex-1 md:max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" aria-hidden />
          <input className="campo h-11 pl-9" placeholder="Buscar por título, archivo o nota" value={buscar} onChange={(e) => setBuscar(e.target.value)} aria-label="Buscar documentos" autoComplete="off" />
        </div>
        {(datos?.carpetas || []).length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Carpetas">
            <button type="button" onClick={() => setCarpeta("")} aria-pressed={!carpeta} className={cx("rounded-full border px-3 py-1 text-sm", !carpeta ? "border-azul bg-azul text-white" : "border-linea bg-white hover:border-azul/50")}>Todas</button>
            {datos.carpetas.map((c) => (
              <button key={c} type="button" onClick={() => setCarpeta(c)} aria-pressed={carpeta === c} className={cx("inline-flex items-center gap-1 rounded-full border px-3 py-1 text-sm", carpeta === c ? "border-azul bg-azul text-white" : "border-linea bg-white hover:border-azul/50")}><FolderOpen className="size-3.5" aria-hidden />{c}</button>
            ))}
          </div>
        )}
      </div>
      {error ? <Alerta>{error}</Alerta> : !datos ? <Cargando /> : lista.length === 0 ? (
        <Vacio icono={FolderOpen} titulo={buscar || carpeta ? "No hay documentos con ese filtro" : vista === "recibidos" ? "No has recibido documentos" : "Aún no hay documentos"}>
          {buscar || carpeta ? "Prueba con otra búsqueda o carpeta." : "Sube un archivo y envíaselo a quien lo necesite: llega con un aviso y queda guardado aquí."}
        </Vacio>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {lista.map((d) => <div key={d.id} id={`doc-${d.id}`} className="contents"><Tarjeta d={d} resaltado={d.id === resaltado} onEditar={setForm} onEliminar={eliminar} /></div>)}
        </ul>
      )}
      <FormDocumento abierto={!!form} doc={form && form !== "nuevo" ? form : null} carpetas={datos?.carpetas || []} areas={datos?.areas || []} onCerrar={() => setForm(null)}
        onGuardado={(d, nuevo) => { setForm(null); avisar(nuevo ? (d.personal ? "Documento guardado para ti." : "Documento enviado.") : "Cambios guardados."); cargar(); if (params.get("id")) { params.delete("id"); setParams(params, { replace: true }); } }} />
    </div>
  );
}
