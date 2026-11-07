// Políticas y cumplimiento + documentos del expediente.
import { useCallback, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { CheckCircle2, Download, FileText, History, Pencil, Plus, Printer, ScrollText, Send, Trash2, Upload } from "lucide-react";
import {
  aceptarPoliticaEmpresa, borrarDocumento, borrarPolitica, constanciaPolitica, cumplimientoPoliticas, documentosEmpleado, editarDocumento,
  estadoDocumentos, guardarPolitica, nuevaVersionPolitica, politicas, subirDocumento, urlCumplimientoCsv, urlDocumento, versionesPolitica,
} from "@/lib/api";
import { useSesion } from "@/lib/sesion";
import { useRecurso } from "@/lib/recursos";
import { Alerta, Barra, Boton, Cabecera, Campo, Cargando, Insignia, Modal, Panel, Pestanas, Vacio, cx, useAviso, useConfirmar } from "@/components/ui";
import { SelectorPersona } from "@/components/Selectores";

const fecha = (iso) => (iso ? new Date(iso).toLocaleDateString("es-DO", { day: "numeric", month: "short", year: "numeric" }) : "—");
const CATEGORIAS = [["REGLAMENTO", "Reglamento interno"], ["ASISTENCIA", "Asistencia y puntualidad"], ["PERMISOS", "Permisos y vacaciones"],
  ["TECNOLOGIA", "Uso de computadoras e internet"], ["MONITOREO", "Monitoreo y privacidad"], ["DATOS", "Protección de datos"],
  ["SEGURIDAD", "Seguridad informática"], ["EQUIPOS", "Equipos de la empresa"], ["REMOTO", "Trabajo remoto"], ["IA", "Inteligencia artificial"],
  ["REDES", "Redes sociales"], ["VEHICULOS", "Vehículos y herramientas"], ["CALIDAD", "Calidad y entregas"], ["DISCIPLINA", "Disciplina"], ["OTRA", "Otra"]];
const TIPOS_DOC = [["CONTRATO", "Contrato de trabajo"], ["IDENTIFICACION", "Copia de identificación"], ["CONFIDENCIALIDAD", "Acuerdo de confidencialidad"],
  ["TITULO", "Título académico"], ["CERTIFICACION", "Certificación o curso"], ["CARTA", "Carta o constancia"], ["ACTA", "Acta firmada"], ["POLIZA", "Póliza o seguro"], ["OTRO", "Otro"]];

/** Texto de una política: párrafos y listas numeradas o con guiones, sin HTML. */
function Texto({ contenido }) {
  return (
    <div className="space-y-2 text-[15px] leading-relaxed">
      {contenido.split(/\n+/).map((l, i) => {
        const lista = /^\s*(\d+[.)]|-|•)\s+/.test(l);
        return <p key={i} className={cx(lista && "pl-5 -indent-5")}>{l.trim()}</p>;
      })}
    </div>
  );
}

export default function Politicas() {
  const { esRRHH } = useSesion();
  const [params, setParams] = useSearchParams();
  const opciones = [
    { valor: "mias", etiqueta: "Mis políticas" },
    { valor: "mis-documentos", etiqueta: "Mis documentos" },
    ...(esRRHH ? [{ valor: "administrar", etiqueta: "Administrar" }, { valor: "cumplimiento", etiqueta: "Cumplimiento" }, { valor: "documentos", etiqueta: "Documentos" }] : []),
  ];
  const ver = opciones.some((o) => o.valor === params.get("ver")) ? params.get("ver") : "mias";
  return (
    <div className="space-y-5">
      <Cabecera titulo="Políticas y documentos" descripcion="El reglamento y las políticas de ADZONE que te aplican, tu aceptación de cada versión y tus documentos laborales." />
      <Pestanas opciones={opciones} valor={ver} onCambio={(v) => setParams({ ver: v })} />
      {ver === "mias" && <MisPoliticas abrir={params.get("ver") && /^\d+$/.test(params.get("ver")) ? params.get("ver") : params.get("abrir")} />}
      {ver === "mis-documentos" && <ListaDocumentos />}
      {ver === "administrar" && <Administrar />}
      {ver === "cumplimiento" && <Cumplimiento />}
      {ver === "documentos" && <Documentos usuarioInicial={params.get("usuario") || ""} />}
    </div>
  );
}

// ---------------------------------------------------------------- Mis políticas
function MisPoliticas({ abrir }) {
  const avisar = useAviso();
  const { esRRHH, recargar } = useSesion();
  const [lista, setLista] = useState(null);
  const [error, setError] = useState("");
  const [leyendo, setLeyendo] = useState(null);
  const [aceptando, setAceptando] = useState(false);
  const cargar = useCallback(() => politicas().then((l) => {
    const visibles = esRRHH ? l.filter((p) => !p.borrador && p.activa) : l;
    setLista(visibles);
    if (abrir) setLeyendo(visibles.find((p) => String(p.id) === String(abrir)) || null);
  }).catch((e) => setError(e.message)), [esRRHH, abrir]);
  useEffect(() => { cargar(); }, [cargar]);
  const aceptar = async () => {
    setAceptando(true);
    try { await aceptarPoliticaEmpresa(leyendo.id, leyendo.version); avisar("Aceptada. Queda tu constancia con fecha y versión."); setLeyendo(null); cargar(); recargar?.(); }
    catch (e) { setError(e.message); if (e.status === 409) { setLeyendo(null); cargar(); } }
    setAceptando(false);
  };
  if (error) return <Alerta>{error}</Alerta>;
  if (!lista) return <Cargando />;
  if (!lista.length) return <Vacio icono={ScrollText} titulo="No hay políticas publicadas para ti">Cuando la empresa publique una, te llegará un aviso para leerla y aceptarla.</Vacio>;
  const pendientes = lista.filter((p) => p.requiere_aceptacion && !p.aceptada);
  return (
    <div className="space-y-4">
      {pendientes.length > 0 && <Alerta tono="amarillo">Tienes {pendientes.length} política(s) por leer y aceptar.</Alerta>}
      <Panel cuerpo="p-0">
        <ul className="divide-y divide-linea-suave">{[...pendientes, ...lista.filter((p) => !pendientes.includes(p))].map((p) => (
          <li key={p.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
            <ScrollText className="size-5 shrink-0 text-azul" />
            <span className="min-w-0 flex-1"><span className="font-medium">{p.titulo}</span> <span className="text-xs text-gris">{p.codigo} · v{p.version} · {p.categoria_nombre}</span>
              {p.resumen && <span className="block text-sm text-gris">{p.resumen}</span>}</span>
            {!p.requiere_aceptacion ? <Insignia>Informativa</Insignia> : p.aceptada ? <Insignia tono="verde"><CheckCircle2 className="size-3" />Aceptada {fecha(p.aceptada_en)}</Insignia> : <Insignia tono="amarillo">Pendiente</Insignia>}
            <Boton tam="sm" variante={p.aceptada || !p.requiere_aceptacion ? "secundario" : "primario"} onClick={() => setLeyendo(p)}>{p.aceptada || !p.requiere_aceptacion ? "Leer" : "Leer y aceptar"}</Boton>
            {p.aceptada && <Link to={`/politicas/${p.id}/constancia`} className="text-sm font-medium text-azul hover:underline">Constancia</Link>}
          </li>))}</ul>
      </Panel>
      {leyendo && (
        <Modal abierto onCerrar={() => setLeyendo(null)} ancho="max-w-3xl" titulo={leyendo.titulo} descripcion={`Versión ${leyendo.version} · vigente desde ${fecha(leyendo.vigente_desde)}`}
          pie={leyendo.requiere_aceptacion && !leyendo.aceptada
            ? <><Boton variante="secundario" onClick={() => setLeyendo(null)}>Después</Boton><Boton icono={CheckCircle2} cargando={aceptando} onClick={aceptar}>Leí y acepto</Boton></>
            : <Boton variante="secundario" onClick={() => setLeyendo(null)}>Cerrar</Boton>}>
          <div className="max-h-[60vh] overflow-y-auto pr-1"><Texto contenido={leyendo.contenido} /></div>
          {leyendo.requiere_aceptacion && !leyendo.aceptada && <p className="mt-4 rounded-lg bg-fondo px-3 py-2 text-sm text-gris">Al aceptar queda registrada la fecha, la hora, la versión y el equipo desde el que aceptaste.</p>}
        </Modal>
      )}
    </div>
  );
}

/** Constancia imprimible de la aceptación. */
export function Constancia() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { constanciaPolitica(id, params.get("usuario") || "").then(setD).catch((e) => setError(e.message)); }, [id, params]);
  if (error) return <Alerta>{error}</Alerta>;
  if (!d) return <Cargando />;
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex justify-end gap-2 print:hidden"><Boton variante="secundario" icono={Printer} onClick={() => window.print()}>Imprimir o guardar PDF</Boton></div>
      <article className="rounded-xl border border-linea bg-white p-8 print:border-0 print:p-0">
        <p className="text-sm text-gris">ADZONE Digital Marketing SRL · Constancia de aceptación</p>
        <h1 className="mt-1 font-display text-2xl font-semibold">{d.politica}</h1>
        <p className="mt-1 text-sm text-gris">Versión {d.version}</p>
        <div className="my-6 border-y border-linea py-6"><Texto contenido={d.contenido} /></div>
        <p className="text-[15px]"><strong>{d.persona}</strong> aceptó esta versión el {new Date(d.fecha).toLocaleString("es-DO", { dateStyle: "long", timeStyle: "short" })}.</p>
        <p className="mt-1 text-xs text-gris">Desde la dirección {d.ip || "—"} · {d.navegador || "—"}</p>
      </article>
    </div>
  );
}

// ---------------------------------------------------------------- Administrar (Gestión del Talento)
const NUEVA = { titulo: "", categoria: "OTRA", resumen: "", contenido: "", para_todos: true, departamentos: [], puestos: [], requiere_aceptacion: true, activa: true, borrador: true };
function Administrar() {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const [deptos] = useRecurso("departamentos");
  const [lista, setLista] = useState(null);
  const [form, setForm] = useState(null);
  const [version, setVersion] = useState(null);
  const [historial, setHistorial] = useState(null);
  const [error, setError] = useState("");
  const cargar = () => politicas().then(setLista).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);
  const guardar = async (datos, msg) => {
    setError("");
    try { await guardarPolitica(datos); setForm(null); avisar(msg); cargar(); } catch (e) { setError(e.message); }
  };
  const publicar = async (p) => {
    if (!(await confirmar({ titulo: `¿Publicar «${p.titulo}»?`, mensaje: "Les llega un aviso a las personas a las que aplica para que la lean y la acepten.", boton: "Publicar" }))) return;
    guardar({ id: p.id, borrador: false }, "Publicada. Ya llegó el aviso.");
  };
  const versionar = async () => {
    setError("");
    try { await nuevaVersionPolitica(version.id, version); setVersion(null); avisar("Nueva versión publicada: todos deben aceptarla de nuevo."); cargar(); } catch (e) { setError(e.message); }
  };
  if (!lista) return error ? <Alerta>{error}</Alerta> : <Cargando />;
  return (
    <Panel titulo={`Políticas (${lista.length})`} cuerpo="p-0" accion={<Boton tam="sm" icono={Plus} onClick={() => setForm(NUEVA)}>Política</Boton>}>
      {error && <Alerta className="m-4">{error}</Alerta>}
      <p className="px-5 pt-4 text-sm text-gris">Las iniciales entran como <strong>borrador</strong>: revísalas (idealmente con su asesor legal), ajústalas y publícalas. Una publicada no se edita en silencio: se crea una nueva versión y todos la aceptan de nuevo.</p>
      <ul className="mt-2 divide-y divide-linea-suave">{lista.map((p) => (
        <li key={p.id} className={cx("flex flex-wrap items-center gap-3 px-5 py-3", !p.activa && "opacity-55")}>
          <span className="min-w-0 flex-1"><span className="font-medium">{p.titulo}</span> <span className="text-xs text-gris">{p.codigo} · v{p.version} · {p.categoria_nombre}</span>
            <span className="block text-xs text-gris">{p.para_todos ? "Toda la empresa" : `${p.departamentos.map((id) => (deptos || []).find((x) => x.id === id)?.nombre).filter(Boolean).join(", ") || "—"}${p.puestos.length ? ` · ${p.puestos.length} puesto(s)` : ""}`}{p.requiere_aceptacion ? "" : " · informativa"}</span></span>
          {p.borrador ? <Insignia tono="amarillo">Borrador</Insignia> : <Insignia tono="verde">Publicada</Insignia>}
          {p.borrador && <Boton tam="sm" icono={Send} onClick={() => publicar(p)}>Publicar</Boton>}
          {!p.borrador && <Boton tam="sm" variante="secundario" onClick={() => setVersion({ id: p.id, titulo: p.titulo, contenido: p.contenido, cambio: "" })}>Nueva versión</Boton>}
          <Boton tam="sm" variante="fantasma" icono={History} aria-label={`Versiones de ${p.titulo}`} onClick={async () => setHistorial({ p, v: await versionesPolitica(p.id) })} />
          <Boton tam="sm" variante="fantasma" icono={Pencil} aria-label={`Editar ${p.titulo}`} onClick={() => setForm(p)} />
          {p.borrador && <Boton tam="sm" variante="fantasma" icono={Trash2} className="text-rojo" aria-label={`Borrar ${p.titulo}`} onClick={async () => {
            if (await confirmar({ titulo: `¿Borrar «${p.titulo}»?`, mensaje: "Es un borrador: nadie lo ha aceptado.", boton: "Borrar", peligro: true })) { await borrarPolitica(p.id); cargar(); }
          }} />}
        </li>))}</ul>
      {form && (
        <Modal abierto onCerrar={() => setForm(null)} ancho="max-w-3xl" titulo={form.id ? "Editar política" : "Nueva política"}
          pie={<><Boton variante="secundario" onClick={() => setForm(null)}>Cancelar</Boton><Boton onClick={() => guardar(form, "Guardada.")}>Guardar</Boton></>}>
          {error && <Alerta className="mb-3">{error}</Alerta>}
          {form.id && !form.borrador && <Alerta tono="azul" className="mb-3">Está publicada: aquí cambias el alcance o la categoría. Para cambiar el texto usa «Nueva versión».</Alerta>}
          <div className="grid gap-3 sm:grid-cols-2">
            <Campo etiqueta="Título" className="sm:col-span-2">{(id) => <input id={id} className="campo" value={form.titulo} onChange={(e) => setForm({ ...form, titulo: e.target.value })} />}</Campo>
            <Campo etiqueta="Categoría">{(id) => <select id={id} className="campo" value={form.categoria} onChange={(e) => setForm({ ...form, categoria: e.target.value })}>{CATEGORIAS.map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>}</Campo>
            <div className="flex flex-col justify-end gap-1">
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-azul" checked={form.requiere_aceptacion} onChange={(e) => setForm({ ...form, requiere_aceptacion: e.target.checked })} />Pide aceptación</label>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-azul" checked={form.activa} onChange={(e) => setForm({ ...form, activa: e.target.checked })} />Activa</label>
            </div>
            <Campo etiqueta="Responsable" ayuda="Puesto o área que responde por la política (p. ej. Gerente TI).">{(id) => <input id={id} className="campo" maxLength={120} value={form.responsable || ""} onChange={(e) => setForm({ ...form, responsable: e.target.value })} />}</Campo>
            <Campo etiqueta="Resumen" className="sm:col-span-2">{(id) => <input id={id} className="campo" maxLength={300} value={form.resumen} onChange={(e) => setForm({ ...form, resumen: e.target.value })} />}</Campo>
            <Campo etiqueta="Texto" ayuda="Un párrafo o punto por línea. Los que empiezan con «1.» o «-» se ven como lista." className="sm:col-span-2">
              {(id) => <textarea id={id} rows={12} disabled={form.id && !form.borrador} className="campo" value={form.contenido} onChange={(e) => setForm({ ...form, contenido: e.target.value })} />}</Campo>
            <label className="flex items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" className="accent-azul" checked={form.para_todos} onChange={(e) => setForm({ ...form, para_todos: e.target.checked })} />Para toda la empresa</label>
            {!form.para_todos && (
              <Campo etiqueta="Departamentos a los que aplica" className="sm:col-span-2">{() => (
                <div className="flex flex-wrap gap-1.5">{(deptos || []).map((x) => {
                  const on = form.departamentos.includes(x.id);
                  return <button key={x.id} type="button" aria-pressed={on} onClick={() => setForm({ ...form, departamentos: on ? form.departamentos.filter((v) => v !== x.id) : [...form.departamentos, x.id] })}
                    className={cx("min-h-9 rounded-full border px-3 text-sm", on ? "border-azul bg-azul text-white" : "border-linea bg-white")}>{x.nombre}</button>;
                })}</div>)}</Campo>
            )}
          </div>
        </Modal>
      )}
      {version && (
        <Modal abierto onCerrar={() => setVersion(null)} ancho="max-w-3xl" titulo="Nueva versión" descripcion="Al publicarla, todas las personas a las que aplica deben aceptarla de nuevo. La versión anterior y quién la aceptó se conservan."
          pie={<><Boton variante="secundario" onClick={() => setVersion(null)}>Cancelar</Boton><Boton icono={Send} onClick={versionar}>Publicar versión</Boton></>}>
          {error && <Alerta className="mb-3">{error}</Alerta>}
          <Campo etiqueta="Qué cambió">{(id) => <input id={id} className="campo" placeholder="Ej.: la tolerancia pasa a 10 minutos" value={version.cambio} onChange={(e) => setVersion({ ...version, cambio: e.target.value })} />}</Campo>
          <Campo etiqueta="Texto" className="mt-3">{(id) => <textarea id={id} rows={14} className="campo" value={version.contenido} onChange={(e) => setVersion({ ...version, contenido: e.target.value })} />}</Campo>
        </Modal>
      )}
      {historial && (
        <Modal abierto onCerrar={() => setHistorial(null)} ancho="max-w-2xl" titulo={`Versiones de ${historial.p.titulo}`}>
          <ul className="divide-y divide-linea-suave">{historial.v.map((v) => (
            <li key={v.version} className="py-2"><p className="font-medium">Versión {v.version} <span className="text-sm font-normal text-gris">· {fecha(v.fecha)}{v.por ? ` · ${v.por}` : ""}</span></p>
              <p className="text-sm text-gris">{v.cambio || "—"} · {v.aceptaron} aceptación(es)</p></li>))}</ul>
        </Modal>
      )}
    </Panel>
  );
}

// ---------------------------------------------------------------- Cumplimiento
function Cumplimiento() {
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [abierta, setAbierta] = useState(null);
  useEffect(() => { cumplimientoPoliticas().then(setD).catch((e) => setError(e.message)); }, []);
  if (error) return <Alerta>{error}</Alerta>;
  if (!d) return <Cargando />;
  if (!d.length) return <Vacio icono={ScrollText} titulo="Ninguna política publicada pide aceptación">Publica las políticas en «Administrar».</Vacio>;
  return (
    <Panel titulo="Cumplimiento" cuerpo="p-0" accion={<a href={urlCumplimientoCsv()} className="inline-flex items-center gap-1.5 text-sm font-medium text-azul hover:underline"><Download className="size-4" />Excel</a>}>
      <ul className="divide-y divide-linea-suave">{d.map((p) => (
        <li key={p.id} className="px-5 py-3">
          <button type="button" className="flex w-full flex-wrap items-center gap-3 text-left" onClick={() => setAbierta(abierta === p.id ? null : p.id)}>
            <span className="min-w-0 flex-1 font-medium">{p.titulo} <span className="text-xs font-normal text-gris">v{p.version}</span></span>
            <span className="w-40"><Barra valor={p.porcentaje} /></span>
            <span className="w-28 text-right text-sm num">{p.aceptaron} de {p.personas}</span>
          </button>
          {abierta === p.id && (p.faltan.length ? (
            <p className="mt-2 text-sm text-gris">Faltan: {p.faltan.map((x) => x.nombre).join(", ")}</p>) : <p className="mt-2 text-sm text-verde">Todos aceptaron.</p>)}
        </li>))}</ul>
    </Panel>
  );
}

// ---------------------------------------------------------------- Documentos
function ListaDocumentos({ usuario, rrhh, recargarEstado }) {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const [lista, setLista] = useState(null);
  const [error, setError] = useState("");
  const cargar = useCallback(() => documentosEmpleado(usuario).then(setLista).catch((e) => setError(e.message)), [usuario]);
  useEffect(() => { setLista(null); cargar(); }, [cargar]);
  if (error) return <Alerta>{error}</Alerta>;
  if (!lista) return <Cargando />;
  if (!lista.length) return <Vacio icono={FileText} titulo="Sin documentos">{rrhh ? "Sube el contrato, la copia de identificación y el acuerdo de confidencialidad." : "Gestión del Talento sube aquí tu contrato y documentos laborales."}</Vacio>;
  return (
    <Panel cuerpo="p-0">
      <ul className="divide-y divide-linea-suave">{lista.map((d) => (
        <li key={d.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
          <FileText className="size-5 shrink-0 text-azul" />
          <span className="min-w-0 flex-1"><a href={urlDocumento(d.id)} target="_blank" rel="noreferrer" className="font-medium hover:text-azul">{d.titulo}</a>
            <span className="block text-xs text-gris">{d.tipo_nombre}{d.emitido ? ` · ${fecha(d.emitido)}` : ""}{d.subido_por_nombre ? ` · subió ${d.subido_por_nombre}` : ""}</span></span>
          {d.vence && <Insignia tono={d.vencido ? "rojo" : "amarillo"}>{d.vencido ? "Venció" : "Vence"} {fecha(d.vence)}</Insignia>}
          {rrhh && !d.visible_al_colaborador && <Insignia>Interno</Insignia>}
          {rrhh && <Boton tam="sm" variante="fantasma" onClick={async () => { await editarDocumento(d.id, { visible_al_colaborador: !d.visible_al_colaborador }); cargar(); }}>{d.visible_al_colaborador ? "Ocultar a la persona" : "Mostrar a la persona"}</Boton>}
          {rrhh && <Boton tam="sm" variante="fantasma" icono={Trash2} className="text-rojo" aria-label={`Borrar ${d.titulo}`} onClick={async () => {
            if (await confirmar({ titulo: `¿Borrar «${d.titulo}»?`, mensaje: "El archivo se borra del expediente.", boton: "Borrar", peligro: true })) { await borrarDocumento(d.id); avisar("Borrado."); cargar(); recargarEstado?.(); }
          }} />}
        </li>))}</ul>
    </Panel>
  );
}

function Documentos({ usuarioInicial }) {
  const avisar = useAviso();
  const [persona, setPersona] = useState(usuarioInicial);
  const [estado, setEstado] = useState(null);
  const [nuevo, setNuevo] = useState(null);
  const [archivo, setArchivo] = useState(null);
  const [vuelta, setVuelta] = useState(0);
  const [error, setError] = useState("");
  const cargarEstado = useCallback(() => estadoDocumentos().then(setEstado).catch((e) => setError(e.message)), []);
  useEffect(() => { cargarEstado(); }, [cargarEstado]);
  const subir = async () => {
    setError("");
    if (!archivo) return setError("Elige el archivo.");
    try { await subirDocumento({ ...nuevo, colaborador: persona }, archivo); setNuevo(null); setArchivo(null); avisar("Documento guardado en el expediente."); setVuelta((v) => v + 1); cargarEstado(); }
    catch (e) { setError(e.message); }
  };
  return (
    <div className="space-y-4">
      {estado && (estado.vencen.length > 0 || estado.faltantes.length > 0) && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel titulo={`Vencen en 30 días (${estado.vencen.length})`} cuerpo="p-0">
            {!estado.vencen.length ? <p className="p-5 text-sm text-gris">Nada por vencer.</p> : (
              <ul className="divide-y divide-linea-suave">{estado.vencen.map((d) => (
                <li key={d.id} className="flex items-center gap-3 px-5 py-2"><button type="button" className="min-w-0 flex-1 truncate text-left hover:text-azul" onClick={() => setPersona(String(d.usuario))}>{d.persona} · {d.titulo}</button>
                  <Insignia tono={d.vencido ? "rojo" : "amarillo"}>{fecha(d.vence)}</Insignia></li>))}</ul>
            )}
          </Panel>
          <Panel titulo={`Expedientes incompletos (${estado.faltantes.length})`} cuerpo="p-0">
            <ul className="max-h-72 divide-y divide-linea-suave overflow-y-auto">{estado.faltantes.map((f) => (
              <li key={f.id} className="px-5 py-2"><button type="button" className="text-left hover:text-azul" onClick={() => setPersona(String(f.id))}>{f.nombre}</button>
                <span className="block text-xs text-gris">Falta: {f.faltan.join(", ")}</span></li>))}</ul>
          </Panel>
        </div>
      )}
      {error && <Alerta>{error}</Alerta>}
      <div className="flex flex-wrap items-end gap-3">
        <SelectorPersona etiqueta="Persona" valor={persona} onCambio={setPersona} />
        {persona && <Boton icono={Upload} onClick={() => setNuevo({ tipo: "CONTRATO", titulo: "", emitido: "", vence: "", visible_al_colaborador: true, notas: "" })}>Subir documento</Boton>}
      </div>
      {persona ? <ListaDocumentos key={`${persona}-${vuelta}`} usuario={persona} rrhh recargarEstado={cargarEstado} /> : <p className="text-sm text-gris">Elige una persona para ver o subir sus documentos. Solo Gestión del Talento y la persona los ven; los supervisores no.</p>}
      {nuevo && (
        <Modal abierto onCerrar={() => setNuevo(null)} titulo="Subir documento" pie={<><Boton variante="secundario" onClick={() => setNuevo(null)}>Cancelar</Boton><Boton icono={Upload} onClick={subir}>Guardar</Boton></>}>
          {error && <Alerta className="mb-3">{error}</Alerta>}
          <div className="grid gap-3 sm:grid-cols-2">
            <Campo etiqueta="Tipo">{(id) => <select id={id} className="campo" value={nuevo.tipo} onChange={(e) => setNuevo({ ...nuevo, tipo: e.target.value, titulo: nuevo.titulo || TIPOS_DOC.find(([k]) => k === e.target.value)[1] })}>{TIPOS_DOC.map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>}</Campo>
            <Campo etiqueta="Título">{(id) => <input id={id} className="campo" value={nuevo.titulo} onChange={(e) => setNuevo({ ...nuevo, titulo: e.target.value })} />}</Campo>
            <Campo etiqueta="Fecha del documento">{(id) => <input id={id} type="date" className="campo" value={nuevo.emitido} onChange={(e) => setNuevo({ ...nuevo, emitido: e.target.value })} />}</Campo>
            <Campo etiqueta="Vence (si aplica)">{(id) => <input id={id} type="date" className="campo" value={nuevo.vence} onChange={(e) => setNuevo({ ...nuevo, vence: e.target.value })} />}</Campo>
            <Campo etiqueta="Archivo" ayuda="PDF, imagen o Word, hasta 15 MB." className="sm:col-span-2">{(id) => <input id={id} type="file" accept=".pdf,.jpg,.jpeg,.png,.webp,.doc,.docx" className="campo pt-2" onChange={(e) => setArchivo(e.target.files[0] || null)} />}</Campo>
            <label className="flex items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" className="accent-azul" checked={nuevo.visible_al_colaborador} onChange={(e) => setNuevo({ ...nuevo, visible_al_colaborador: e.target.checked })} />La persona lo ve y lo descarga</label>
          </div>
        </Modal>
      )}
    </div>
  );
}
