// Espacio de un departamento: resumen (qué hace, objetivos, estructura), KPIs del mes o trimestre, personal,
// políticas, procedimientos, documentación y seguimiento. Cada persona ve solo lo que le toca (lo decide el servidor).
import { useCallback, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  BookOpen, ChevronLeft, ChevronRight, ClipboardList, Download, FileText, FolderOpen, Info, LayoutGrid, LineChart, ListChecks,
  Pencil, Plus, Settings2, SquarePen, Target, Trash2, UserPlus, Users,
} from "lucide-react";
import { borrarDocumentoArea, guardarDocumentoArea, guardarInfoDepartamento, tableroDepartamento, urlDocumentoArea } from "@/lib/api";
import { dinero, fechaCorta } from "@/lib/formato";
import { Alerta, Avatar, Boton, Campo, Cargando, Insignia, Modal, Panel, Pestanas, Vacio, cx, useAviso, useConfirmar } from "@/components/ui";

const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
const ESTADO = {
  CUMPLE: { texto: "Meta cumplida", tono: "verde", borde: "border-l-verde" },
  CERCA: { texto: "Cerca de la meta", tono: "amarillo", borde: "border-l-amarillo" },
  BAJO: { texto: "Bajo la meta", tono: "rojo", borde: "border-l-rojo" },
  SIN_DATO: { texto: "Sin dato", tono: "neutro", borde: "border-l-linea" },
  RESERVADO: { texto: "Reservado", tono: "neutro", borde: "border-l-linea" },
};
const numero = (v) => (v == null ? "—" : Number(v).toLocaleString("es-DO", { maximumFractionDigits: 2 }));
const unidadCorta = (u) => (u === "%" || u === "porcentaje" ? "%" : u || "");

// ------------------------------------------------------------------ Piezas
function TarjetaKPI({ k, extra }) {
  const e = ESTADO[k.estado] || ESTADO.SIN_DATO;
  const u = unidadCorta(k.unidad);
  return (
    <div className={cx("flex min-h-36 flex-col rounded-xl border border-l-4 border-linea bg-white p-4", e.borde)}
      title={[k.formula, k.fuente_datos].filter(Boolean).join(" · ") || undefined}>
      <p className="text-xs font-medium uppercase tracking-wide text-gris">{k.nombre}</p>
      <p className="mt-2 flex items-baseline gap-1">
        <span className={cx("font-display text-3xl font-semibold num", k.valor == null && "text-gris/60")}>{k.estado === "RESERVADO" ? "·" : numero(k.valor)}</span>
        {k.valor != null && u && <span className="text-sm text-gris">{u}</span>}
      </p>
      <div className="mt-auto flex flex-wrap items-center justify-between gap-2 pt-3">
        <Insignia tono={e.tono}>{e.texto}{k.cumplimiento != null && k.estado !== "CUMPLE" ? ` · ${numero(k.cumplimiento)} %` : ""}</Insignia>
        <span className="text-xs text-gris">{k.meta != null ? `Meta: ${numero(k.meta)}${u ? ` ${u}` : ""}` : "Sin meta"}</span>
      </div>
      {extra && <p className="mt-2 text-xs text-gris">{extra}</p>}
    </div>
  );
}
const Rejilla = ({ children }) => <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{children}</div>;

/** Texto con pasos: «1.» o «-» al inicio de línea se muestran como lista. */
function Pasos({ texto }) {
  const lineas = (texto || "").split("\n").map((l) => l.trim()).filter(Boolean);
  if (!lineas.length) return null;
  return (
    <div className="space-y-1.5 text-[15px] leading-relaxed">
      {lineas.map((l, i) => {
        const n = l.match(/^(\d+)[.)]\s+(.*)$/);
        if (n) return <p key={i} className="flex gap-3"><span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-azul/10 text-xs font-semibold text-azul">{n[1]}</span><span>{n[2]}</span></p>;
        if (/^[-•*]\s+/.test(l)) return <p key={i} className="flex gap-2 pl-1"><span className="text-azul">•</span><span>{l.replace(/^[-•*]\s+/, "")}</span></p>;
        return <p key={i}>{l}</p>;
      })}
    </div>
  );
}

function Periodo({ anio, mes, vista, onCambio }) {
  const hoy = new Date();
  const futuro = (m) => anio > hoy.getFullYear() || (anio === hoy.getFullYear() && m > hoy.getMonth() + 1);
  const opciones = vista === "trimestral"
    ? [1, 4, 7, 10].map((m, i) => ({ m, texto: `T${i + 1} · ${MESES[m - 1].slice(0, 3)}–${MESES[m + 1].slice(0, 3)}`, activo: Math.floor((mes - 1) / 3) === i }))
    : MESES.map((t, i) => ({ m: i + 1, texto: t, activo: mes === i + 1 }));
  return (
    <Panel cuerpo="p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold uppercase tracking-wide text-gris">Periodo</span>
        <button type="button" className="rounded p-1 hover:bg-fondo" aria-label="Año anterior" onClick={() => onCambio({ anio: anio - 1 })}><ChevronLeft className="size-4" /></button>
        <span className="font-semibold num">{anio}</span>
        <button type="button" className="rounded p-1 hover:bg-fondo disabled:opacity-30" aria-label="Año siguiente" disabled={anio >= hoy.getFullYear()} onClick={() => onCambio({ anio: anio + 1 })}><ChevronRight className="size-4" /></button>
        <div className="ml-auto flex rounded-lg border border-linea p-0.5" role="group" aria-label="Vista">
          {[["mensual", "Mensual"], ["trimestral", "Trimestral"]].map(([v, t]) => (
            <button key={v} type="button" aria-pressed={vista === v} onClick={() => onCambio({ vista: v })}
              className={cx("rounded-md px-3 py-1 text-sm font-medium", vista === v ? "bg-azul/10 text-azul" : "text-gris hover:text-tinta")}>{t}</button>
          ))}
        </div>
      </div>
      <div className="-mx-1 flex gap-1 overflow-x-auto px-1 pb-1 [scrollbar-width:thin]">
        {opciones.map((o) => (
          <button key={o.m} type="button" disabled={futuro(o.m)} aria-pressed={o.activo} onClick={() => onCambio({ mes: o.m })}
            ref={o.activo ? (el) => el?.scrollIntoView({ block: "nearest", inline: "center" }) : undefined}
            className={cx("shrink-0 rounded-lg px-3.5 py-2 text-sm font-medium whitespace-nowrap", o.activo ? "bg-azul text-white" : "text-tinta hover:bg-fondo disabled:text-gris/50 disabled:hover:bg-transparent")}>
            {o.texto}
          </button>
        ))}
      </div>
    </Panel>
  );
}

// ------------------------------------------------------------------ Pestañas
function Resumen({ d, recargar }) {
  const [editando, setEditando] = useState(false);
  const [f, setF] = useState({ descripcion: "", objetivos: "" });
  const [error, setError] = useState("");
  const avisar = useAviso();
  const abrir = () => { setF({ descripcion: d.departamento.descripcion || "", objetivos: d.departamento.objetivos.join("\n") }); setError(""); setEditando(true); };
  const guardar = async (e) => {
    e.preventDefault();
    try { await guardarInfoDepartamento(d.departamento.id, f); setEditando(false); avisar("Información del área guardada"); recargar(); } catch (er) { setError(er.message); }
  };
  const Grupo = ({ titulo, lista }) => lista.length > 0 && (
    <div>
      <p className="etiqueta">{titulo}</p>
      <ul className="space-y-2">{lista.map((p) => (
        <li key={p.id} className="flex items-center gap-2.5"><Avatar nombre={p.nombre} tam="sm" /><span className="min-w-0"><span className="block font-medium">{p.nombre}</span><span className="block truncate text-sm text-gris">{p.cargo}</span></span></li>
      ))}</ul>
    </div>
  );
  const e = d.estructura;
  return (
    <div className="grid gap-5 lg:grid-cols-[1.2fr_1fr]">
      <div className="space-y-5">
        <Panel titulo="Qué hace el área" accion={d.puede.editar && <Boton tam="sm" variante="fantasma" icono={Pencil} onClick={abrir}>Editar</Boton>}>
          <p className="text-[15px] leading-relaxed">{d.departamento.descripcion || <span className="text-gris">Todavía sin descripción.</span>}</p>
        </Panel>
        <Panel titulo={<span className="flex items-center gap-2"><Target className="size-4 text-azul" />Objetivos</span>}>
          {d.departamento.objetivos.length
            ? <ul className="space-y-2">{d.departamento.objetivos.map((o, i) => <li key={i} className="flex gap-2"><span className="mt-2 size-1.5 shrink-0 rounded-full bg-azul" />{o}</li>)}</ul>
            : <p className="text-gris">Todavía no se han escrito los objetivos del área.</p>}
        </Panel>
        {d.nivel !== "miembro" && (
          <Panel titulo="Seguimiento rápido">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[["Tareas abiertas", d.seguimiento.abiertas], ["Vencidas", d.seguimiento.vencidas, d.seguimiento.vencidas > 0], ["Por validar", d.seguimiento.por_validar],
                ["Evaluaciones pendientes", d.seguimiento.evaluaciones_pendientes]].map(([t, n, mal]) => (
                <div key={t} className="rounded-lg bg-fondo p-3"><p className={cx("font-display text-2xl font-semibold num", mal && "text-rojo")}>{n}</p><p className="text-sm text-gris">{t}</p></div>
              ))}
            </div>
          </Panel>
        )}
      </div>
      <Panel titulo={<span className="flex items-center gap-2"><Users className="size-4 text-azul" />Estructura · {d.resumen.personas}</span>}>
        <div className="space-y-5">
          <Grupo titulo="Encargado" lista={e.encargados} />
          <Grupo titulo="Supervisores" lista={e.supervisores} />
          <Grupo titulo="Personal" lista={e.personal} />
          {!e.encargados.length && !e.supervisores.length && !e.personal.length && <p className="text-gris">Nadie asignado a este departamento todavía.</p>}
        </div>
      </Panel>
      <Modal abierto={editando} onCerrar={() => setEditando(false)} titulo={`${d.departamento.nombre}: información del área`}
        pie={<><Boton variante="secundario" onClick={() => setEditando(false)}>Cancelar</Boton><Boton type="submit" form="form-area">Guardar</Boton></>}>
        <form id="form-area" onSubmit={guardar} className="space-y-4">
          {error && <Alerta>{error}</Alerta>}
          <Campo etiqueta="Qué hace el área">{(id) => <textarea id={id} rows={3} maxLength={255} className="campo" value={f.descripcion} onChange={(ev) => setF({ ...f, descripcion: ev.target.value })} />}</Campo>
          <Campo etiqueta="Objetivos" ayuda="Uno por línea.">{(id) => <textarea id={id} rows={6} className="campo" value={f.objetivos} onChange={(ev) => setF({ ...f, objetivos: ev.target.value })} />}</Campo>
        </form>
      </Modal>
    </div>
  );
}

function Kpis({ d }) {
  if (d.nivel === "miembro") {
    const yo = d.personas.find((p) => p.soy_yo);
    return yo?.kpis?.length ? <div className="space-y-3"><p className="text-sm text-gris">Tus KPIs del periodo. Los del resto del área los ve tu supervisor.</p><Rejilla>{yo.kpis.map((k) => <TarjetaKPI key={k.id} k={k} />)}</Rejilla></div>
      : <Vacio titulo="Tu puesto todavía no tiene KPIs asignados" />;
  }
  return d.kpis.length === 0
    ? <Vacio titulo="Sin KPIs asignados">Asigna KPIs a los puestos de este departamento en Departamentos y puestos.</Vacio>
    : <Rejilla>{d.kpis.map((k) => <TarjetaKPI key={k.plantilla} k={k} extra={k.personas > 1 ? `${k.con_dato} de ${k.personas} personas con dato · promedio` : null} />)}</Rejilla>;
}

function Persona({ p, nivel }) {
  const [abierta, setAbierta] = useState(false);
  const medidos = (p.kpis || []).filter((k) => k.cumplimiento != null);
  const cumple = medidos.filter((k) => k.cumplimiento >= 100).length;
  const s = p.seguimiento;
  return (
    <Panel cuerpo="p-4" titulo={
      <span className="flex items-center gap-3">
        <Avatar nombre={p.nombre} tam="sm" />
        <span className="min-w-0">{p.detalle ? <Link to={p.soy_yo ? "/ficha" : `/ficha?usuario=${p.id}`} className="hover:text-azul hover:underline">{p.nombre}</Link> : p.nombre}
          {p.soy_yo && <span className="ml-2 text-xs font-normal text-azul">(tú)</span>}
          <span className="block text-sm font-normal text-gris">{p.cargo}{p.supervisor && ` · reporta a ${p.supervisor}`}{p.salario != null && <> · <span className="num text-verde">{dinero(p.salario)}</span></>}</span></span>
      </span>
    } accion={
      <span className="flex flex-wrap items-center justify-end gap-2 text-sm">
        {medidos.length > 0 && <Insignia tono={cumple === medidos.length ? "verde" : "neutro"}>{cumple}/{medidos.length} metas</Insignia>}
        {p.puntaje != null && <Insignia tono="azul">Puntaje {numero(p.puntaje)}</Insignia>}
        {s && s.vencidas > 0 && <Insignia tono="rojo">{s.vencidas} vencida(s)</Insignia>}
      </span>
    }>
      <div className="space-y-4">
        {p.funciones.length > 0 && (
          <div>
            <button type="button" className="text-sm font-medium text-azul hover:underline" onClick={() => setAbierta(!abierta)} aria-expanded={abierta}>
              {abierta ? "Ocultar funciones" : `Funciones del puesto (${p.funciones.length})`}
            </button>
            {abierta && <ul className="mt-2 space-y-1 text-[15px]">{p.funciones.map((f, i) => <li key={i} className="flex gap-2"><span className="text-azul">•</span>{f}</li>)}</ul>}
          </div>
        )}
        {p.detalle && !(nivel === "miembro" && p.soy_yo) && (p.kpis.length === 0 ? <p className="text-sm text-gris">Su puesto todavía no tiene KPIs asignados.</p>
          : <Rejilla>{p.kpis.map((k) => <TarjetaKPI key={k.id} k={k} />)}</Rejilla>)}
      </div>
    </Panel>
  );
}

function Politicas({ lista, puede, nivel }) {
  if (!lista.length) return <Vacio titulo="Sin políticas para este departamento">Se publican en Políticas → Administrar, eligiendo el departamento.</Vacio>;
  const grupos = [["Del departamento", lista.filter((p) => p.alcance !== "Toda la empresa")], ["De toda la empresa", lista.filter((p) => p.alcance === "Toda la empresa")]];
  return (
    <div className="space-y-5">
      {grupos.filter(([, l]) => l.length).map(([titulo, l]) => (
        <Panel key={titulo} titulo={titulo} cuerpo="p-0">
          <ul className="divide-y divide-linea-suave">
            {l.map((p) => (
              <li key={p.id} className="flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-start">
                <FileText className="mt-0.5 hidden size-5 shrink-0 text-gris sm:block" />
                <div className="min-w-0 flex-1">
                  <p className="font-medium"><span className="mr-2 font-mono text-xs text-gris">{p.codigo}</span><Link to={`/politicas?abrir=${p.id}`} className="hover:text-azul hover:underline">{p.titulo}</Link>
                    <span className="ml-2 text-sm font-normal text-gris">v{p.version} · {p.categoria} · desde {fechaCorta(p.vigente_desde)}</span></p>
                  <p className="text-xs text-gris">Aplica a: {p.aplica_a}{p.responsable && ` · Responsable: ${p.responsable}`}</p>
                  {p.resumen && <p className="text-sm text-gris">{p.resumen}</p>}
                  {p.pendientes?.length > 0 && <p className="mt-1 text-sm"><span className="text-gris">Falta aceptarla:</span> {p.pendientes.join(", ")}</p>}
                </div>
                {nivel !== "miembro"
                  ? (p.requiere_aceptacion ? <Insignia tono={p.aceptaron >= p.aplican ? "verde" : "amarillo"}>{p.aceptaron}/{p.aplican} aceptaron</Insignia> : <Insignia>Informativa</Insignia>)
                  : !p.me_aplica ? <Insignia>No te aplica</Insignia>
                    : p.requiere_aceptacion ? (p.la_acepte ? <Insignia tono="verde">Aceptada</Insignia> : <Link to={`/politicas?abrir=${p.id}`}><Insignia tono="amarillo">Leer y aceptar</Insignia></Link>)
                      : <Insignia>Informativa</Insignia>}
              </li>
            ))}
          </ul>
        </Panel>
      ))}
      {puede.politicas && <Link to="/politicas?ver=administrar" className="inline-block text-sm font-medium text-azul hover:underline">Administrar políticas</Link>}
    </div>
  );
}

const TIPOS_DOC = [["PROCEDIMIENTO", "Procedimiento"], ["MANUAL", "Manual"], ["FORMULARIO", "Formulario"], ["REPORTE", "Reporte"], ["OTRO", "Otro"]];

function Documentos({ d, procedimientos, recargar }) {
  const lista = d.documentos.filter((x) => (procedimientos ? x.tipo === "PROCEDIMIENTO" : x.tipo !== "PROCEDIMIENTO"));
  const [leyendo, setLeyendo] = useState(null);
  const [form, setForm] = useState(null);
  const [archivo, setArchivo] = useState(null);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const nuevo = () => { setError(""); setArchivo(null); setForm({ tipo: procedimientos ? "PROCEDIMIENTO" : "MANUAL", titulo: "", resumen: "", contenido: "", solo_encargados: false }); };
  const guardar = async (e) => {
    e.preventDefault(); setError(""); setGuardando(true);
    try { await guardarDocumentoArea(d.departamento.id, form, archivo); setForm(null); avisar("Guardado"); recargar(); } catch (er) { setError(er.message); }
    setGuardando(false);
  };
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <p className="flex-1 text-sm text-gris">{procedimientos ? "Cómo se hace cada trabajo del área, paso a paso." : "Manuales, formularios, reportes y archivos del área."}</p>
        {d.puede.editar && <Boton icono={Plus} onClick={nuevo}>{procedimientos ? "Procedimiento" : "Documento"}</Boton>}
      </div>
      {lista.length === 0 ? <Vacio titulo={procedimientos ? "Sin procedimientos todavía" : "Sin documentos todavía"}>{d.puede.editar ? "Agrega el primero con el botón de arriba." : "El encargado del área los publicará aquí."}</Vacio> : (
        <div className="grid gap-3 md:grid-cols-2">
          {lista.map((x) => (
            <article key={x.id} className="flex flex-col rounded-xl border border-linea bg-white p-4">
              <div className="flex items-start gap-2">
                {procedimientos ? <ListChecks className="mt-0.5 size-5 shrink-0 text-azul" /> : <FolderOpen className="mt-0.5 size-5 shrink-0 text-azul" />}
                <div className="min-w-0 flex-1">
                  <button type="button" className="text-left font-medium hover:text-azul hover:underline" onClick={() => setLeyendo(x)}><span className="mr-2 font-mono text-xs text-gris">{x.codigo}</span>{x.titulo}</button>
                  <p className="text-xs text-gris">{x.tipo_nombre} · v{x.version} · {fechaCorta(x.actualizado)}{x.actualizado_por && ` · ${x.actualizado_por}`}</p>
                </div>
                {x.solo_encargados && <Insignia>Solo encargados</Insignia>}
              </div>
              {x.resumen && <p className="mt-2 text-sm text-gris">{x.resumen}</p>}
              <div className="mt-auto flex flex-wrap items-center gap-2 pt-3">
                {x.contenido && <Boton tam="sm" variante="secundario" icono={BookOpen} onClick={() => setLeyendo(x)}>Leer</Boton>}
                {x.archivo && <a href={urlDocumentoArea(x.id)} className="inline-flex items-center gap-1.5 rounded-lg border border-linea px-3 py-1.5 text-sm font-medium hover:bg-fondo"><Download className="size-4" />{x.nombre_archivo || "Archivo"}</a>}
                {d.puede.editar && <>
                  <Boton tam="sm" variante="fantasma" icono={Pencil} aria-label={`Editar ${x.titulo}`} onClick={() => { setError(""); setArchivo(null); setForm({ ...x }); }} />
                  <Boton tam="sm" variante="fantasma" icono={Trash2} className="text-rojo" aria-label={`Borrar ${x.titulo}`} onClick={async () => {
                    if (await confirmar({ titulo: `¿Borrar «${x.titulo}»?`, boton: "Borrar", peligro: true })) { await borrarDocumentoArea(x.id); recargar(); }
                  }} />
                </>}
              </div>
            </article>
          ))}
        </div>
      )}
      <Modal abierto={!!leyendo} onCerrar={() => setLeyendo(null)} titulo={leyendo?.titulo} ancho="md:max-w-2xl"
        descripcion={leyendo && `${leyendo.tipo_nombre} · versión ${leyendo.version} · actualizado ${fechaCorta(leyendo.actualizado)}`}>
        {leyendo && <div className="space-y-4">{leyendo.resumen && <p className="text-gris">{leyendo.resumen}</p>}<Pasos texto={leyendo.contenido} />
          {leyendo.archivo && <a href={urlDocumentoArea(leyendo.id)} className="inline-flex items-center gap-1.5 text-azul hover:underline"><Download className="size-4" />{leyendo.nombre_archivo}</a>}</div>}
      </Modal>
      <Modal abierto={!!form} onCerrar={() => setForm(null)} titulo={form?.id ? "Editar" : procedimientos ? "Nuevo procedimiento" : "Nuevo documento"} ancho="md:max-w-2xl"
        pie={<><Boton variante="secundario" onClick={() => setForm(null)}>Cancelar</Boton><Boton type="submit" form="form-doc" cargando={guardando}>Guardar</Boton></>}>
        {form && (
          <form id="form-doc" onSubmit={guardar} className="space-y-4">
            {error && <Alerta>{error}</Alerta>}
            <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
              <Campo etiqueta="Título">{(id) => <input id={id} className="campo" value={form.titulo} onChange={(e) => setForm({ ...form, titulo: e.target.value })} />}</Campo>
              <Campo etiqueta="Tipo">{(id) => <select id={id} className="campo" value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })}>{TIPOS_DOC.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select>}</Campo>
            </div>
            <Campo etiqueta="Resumen (opcional)">{(id) => <input id={id} className="campo" maxLength={300} value={form.resumen} onChange={(e) => setForm({ ...form, resumen: e.target.value })} />}</Campo>
            <Campo etiqueta={form.tipo === "PROCEDIMIENTO" ? "Pasos" : "Contenido"} ayuda="Una línea por paso. Empieza con «1.» para numerar o con «-» para viñetas.">
              {(id) => <textarea id={id} rows={10} className="campo font-mono text-sm" value={form.contenido} onChange={(e) => setForm({ ...form, contenido: e.target.value })} placeholder={"1. Recibir la solicitud en la OT\n2. Revisar el brief con el cliente\n3. …"} />}
            </Campo>
            <Campo etiqueta={form.archivo ? `Archivo (reemplaza «${form.nombre_archivo}»)` : "Archivo (opcional)"} ayuda="PDF, Word, Excel, PowerPoint, imagen o ZIP · máximo 20 MB.">
              {(id) => <input id={id} type="file" className="campo py-2" onChange={(e) => setArchivo(e.target.files?.[0] || null)} />}
            </Campo>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-azul" checked={!!form.solo_encargados} onChange={(e) => setForm({ ...form, solo_encargados: e.target.checked })} />Solo para el encargado, los supervisores y la Dirección</label>
          </form>
        )}
      </Modal>
    </div>
  );
}

function Seguimiento({ d }) {
  const lista = d.personas.filter((p) => p.detalle);
  if (!lista.length) return <Vacio titulo="Sin seguimiento" />;
  return (
    <Panel cuerpo="p-0">
      <div className="overflow-x-auto">
        <table className="tabla min-w-[860px]">
          <thead><tr><th>Persona</th><th className="text-right">Abiertas</th><th className="text-right">Vencidas</th><th className="text-right">Por validar</th><th className="text-right">Validadas</th><th className="text-right">A tiempo</th><th className="text-right">Evaluaciones</th><th>Última evaluación</th><th>Plan de mejora</th></tr></thead>
          <tbody>
            {lista.map((p) => {
              const s = p.seguimiento;
              return (
                <tr key={p.id}>
                  <td><Link to={p.soy_yo ? "/ficha" : `/ficha?usuario=${p.id}`} className="font-medium hover:text-azul hover:underline">{p.nombre}</Link><span className="block text-xs text-gris">{p.cargo}</span></td>
                  <td className="text-right num">{s.abiertas}</td>
                  <td className={cx("text-right num", s.vencidas > 0 && "font-semibold text-rojo")}>{s.vencidas}</td>
                  <td className="text-right num">{s.por_validar}</td>
                  <td className="text-right num">{s.validadas}</td>
                  <td className="text-right num">{s.a_tiempo_pct == null ? "—" : `${s.a_tiempo_pct} %`}</td>
                  <td className="text-right">{s.evaluaciones.total === 0 ? <span className="text-gris">—</span> : s.evaluaciones.pendientes ? <Insignia tono="amarillo">{s.evaluaciones.pendientes} pendiente(s)</Insignia> : <Insignia tono="verde">Al día</Insignia>}</td>
                  <td>{s.ultima_evaluacion ? <span className="text-sm"><b className="num">{s.ultima_evaluacion.promedio ?? "—"}</b>/5 · {s.ultima_evaluacion.ciclo}</span> : <span className="text-gris">—</span>}</td>
                  <td>{s.plan_mejora ? <Link to={`/talento?ver=planes&usuario=${p.id}`}><Insignia tono="amarillo">En curso</Insignia></Link> : <span className="text-gris">—</span>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

// ------------------------------------------------------------------ Página
const PESTANAS = ["resumen", "kpis", "personal", "politicas", "procedimientos", "documentos", "seguimiento"];

export default function TableroDepartamento() {
  const { id } = useParams();
  const [params, setParams] = useSearchParams();
  const hoy = new Date();
  const anio = Number(params.get("anio")) || hoy.getFullYear();
  const mes = Number(params.get("mes")) || hoy.getMonth() + 1;
  const vista = params.get("vista") === "trimestral" ? "trimestral" : "mensual";
  const ver = PESTANAS.includes(params.get("ver")) ? params.get("ver") : "resumen";
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const cambiar = (x) => setParams((p) => { const n = new URLSearchParams(p); Object.entries(x).forEach(([k, v]) => n.set(k, v)); return n; }, { replace: true });
  const recargar = useCallback(() => tableroDepartamento(id, { anio, mes, vista }).then(setD).catch((e) => setError(e.message)), [id, anio, mes, vista]);
  useEffect(() => { setD(null); setError(""); recargar(); }, [recargar]);

  if (error) return <Alerta>{error}</Alerta>;
  const miembro = d?.nivel === "miembro";
  const nPro = d ? d.documentos.filter((x) => x.tipo === "PROCEDIMIENTO").length : 0;
  const opciones = d ? [
    { valor: "resumen", etiqueta: <><LayoutGrid className="size-4" />Resumen</> },
    { valor: "kpis", etiqueta: <><LineChart className="size-4" />{miembro ? "Mis KPIs" : "KPIs"}</> },
    { valor: "personal", etiqueta: <><Users className="size-4" />Personal · {d.personas.length}</> },
    { valor: "politicas", etiqueta: <><FileText className="size-4" />Políticas · {d.politicas.length}</> },
    { valor: "procedimientos", etiqueta: <><ListChecks className="size-4" />Procesos · {nPro}</> },
    { valor: "documentos", etiqueta: <><FolderOpen className="size-4" />Documentos · {d.documentos.length - nPro}</> },
    ...(!miembro ? [{ valor: "seguimiento", etiqueta: <><ClipboardList className="size-4" />Evaluaciones</> }] : []),
  ] : [];
  const conPeriodo = ["kpis", "personal", "seguimiento"].includes(ver) || (ver === "resumen" && !miembro);

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-[26px] font-semibold leading-tight md:text-3xl">{d?.departamento.nombre || "Departamento"}</h1>
            {d?.puede.metas && <Link to="/puestos" className="inline-flex items-center gap-1.5 rounded-lg bg-amarillo-50 px-2.5 py-1 text-sm font-medium text-[#7a5000] hover:underline"><Settings2 className="size-4" />Gestionar metas</Link>}
          </div>
          <p className="mt-1 text-gris">{miembro ? "Tu departamento: información del área, tus compañeros, políticas y procedimientos" : "Espacio del departamento"}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {d?.puede.ingresar && <Link to="/kpis-del-mes" className="inline-flex items-center gap-1.5 rounded-lg bg-[#5b3fd6] px-3.5 py-2 text-sm font-medium text-white hover:opacity-90"><SquarePen className="size-4" />Ingresar datos</Link>}
          {d?.puede.integrante && <Link to="/personas?nuevo=1" className="inline-flex items-center gap-1.5 rounded-lg bg-verde px-3.5 py-2 text-sm font-medium text-white hover:opacity-90"><UserPlus className="size-4" />Nuevo integrante</Link>}
        </div>
      </header>

      {!d ? <Cargando /> : <>
        <Pestanas opciones={opciones} valor={ver} onCambio={(v) => cambiar({ ver: v })} className="md:!flex" />
        {conPeriodo && <Periodo anio={anio} mes={mes} vista={vista} onCambio={cambiar} />}
        {conPeriodo && (
          <section className="rounded-xl border border-azul/20 bg-azul/5 p-5">
            <p className="flex items-center gap-2 font-semibold text-azul"><Info className="size-4" />Resumen del periodo</p>
            <p className="mt-2 text-[17px] leading-relaxed">{d.resumen.texto}</p>
          </section>
        )}
        {ver === "resumen" && <Resumen d={d} recargar={recargar} />}
        {ver === "kpis" && <Kpis d={d} />}
        {ver === "personal" && (d.personas.length === 0 ? <Vacio titulo="Sin personal en este departamento" /> : <div className="space-y-4">{[...d.personas].sort((a, b) => b.soy_yo - a.soy_yo).map((p) => <Persona key={p.id} p={p} nivel={d.nivel} />)}</div>)}
        {ver === "politicas" && <Politicas lista={d.politicas} puede={d.puede} nivel={d.nivel} />}
        {ver === "procedimientos" && <Documentos d={d} procedimientos recargar={recargar} />}
        {ver === "documentos" && <Documentos d={d} recargar={recargar} />}
        {ver === "seguimiento" && !miembro && <Seguimiento d={d} />}
      </>}
    </div>
  );
}
