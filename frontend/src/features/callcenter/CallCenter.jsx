// Call Center: campañas con sus metas y los agentes que las atienden.
// Quien gestiona el call center crea campañas y ve a todos los agentes; el agente ve solo lo suyo.
import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Clock, Headset, Languages, Pencil, Plus, Target, Trash2, Trophy, Users } from "lucide-react";
import { eliminarCampana, guardarCampana, listarCampanas, resumenCallCenter } from "@/lib/api";
import { fechaCorta } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import { useRecurso } from "@/lib/recursos";
import { Alerta, Barra, Boton, Cabecera, Campo, Cargando, Insignia, Modal, Panel, Pestanas, Puntaje, Vacio, cx, useAviso, useConfirmar } from "@/components/ui";

const TIPOS = [["ATENCION", "Atención al cliente"], ["VENTAS", "Ventas"], ["COBROS", "Cobros"], ["SOPORTE", "Soporte técnico"], ["ENCUESTAS", "Encuestas"], ["CITAS", "Agendamiento de citas"]];
const IDIOMAS = [["ES", "Español"], ["EN", "Inglés"], ["BI", "Bilingüe"]];
const CANALES = ["Llamadas entrantes", "Llamadas salientes", "WhatsApp", "Chat web", "Correo", "Redes sociales"];
const EVALUACION = { CUMPLE: ["Cumple", "verde"], BAJO_MINIMO: ["Bajo el mínimo", "rojo"], POCOS_DATOS: ["Pocos datos", "neutro"] };
const hoy = () => new Date().toLocaleDateString("en-CA");
const vacia = () => ({ nombre: "", cliente: "", tipo: "ATENCION", idioma: "ES", canales: [], horario: "", fecha_inicio: hoy(), fecha_fin: "",
  meta_contactos_dia: 0, meta_conversion: 0, meta_calidad: 85, agentes: [], guion: "", notas: "", activa: true });

function Metas({ c }) {
  const meta = (icono, valor, texto) => (
    <div className="rounded-lg bg-fondo px-3 py-2">
      <p className="flex items-center gap-1.5 text-xs text-gris">{icono}{texto}</p>
      <p className="font-display text-xl font-semibold num">{valor}</p>
    </div>
  );
  return (
    <div className="grid grid-cols-3 gap-2">
      {meta(<Target className="size-3.5" />, c.meta_contactos_dia || "—", "Contactos al día")}
      {meta(<Trophy className="size-3.5" />, `${Number(c.meta_conversion)} %`, "Conversión")}
      {meta(<Headset className="size-3.5" />, `${Number(c.meta_calidad)} %`, "Calidad mínima")}
    </div>
  );
}

function TarjetaCampana({ c, onEditar }) {
  return (
    <article className={cx("rounded-xl border bg-white p-5", c.activa ? "border-linea" : "border-dashed border-linea opacity-70")}>
      <header className="flex flex-wrap items-start gap-2">
        <div className="min-w-[min(100%,12rem)] flex-1">
          <h3 className="text-lg font-semibold leading-snug">{c.nombre}</h3>
          <p className="text-sm text-gris">{c.tipo_nombre}{c.cliente_nombre ? ` · ${c.cliente_nombre}` : ""}</p>
        </div>
        {!c.activa && <Insignia>En pausa</Insignia>}
        {onEditar && <Boton variante="fantasma" tam="sm" icono={Pencil} aria-label={`Editar ${c.nombre}`} onClick={() => onEditar(c)} />}
      </header>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-gris">
        <span className="flex items-center gap-1.5"><Languages className="size-4" />{c.idioma_nombre}</span>
        {c.horario && <span className="flex items-center gap-1.5"><Clock className="size-4" />{c.horario}</span>}
        <span>Desde {fechaCorta(c.fecha_inicio)}{c.fecha_fin ? ` hasta ${fechaCorta(c.fecha_fin)}` : ""}</span>
      </div>
      {c.canales.length > 0 && <div className="mt-2 flex flex-wrap gap-1.5">{c.canales.map((x) => <Insignia key={x} tono="azul">{x}</Insignia>)}</div>}
      <div className="mt-4"><Metas c={c} /></div>
      {onEditar && (
        <p className="mt-3 flex flex-wrap items-center gap-1.5 text-sm"><Users className="size-4 text-gris" />
          {c.agentes_detalle.length ? c.agentes_detalle.map((a) => a.nombre).join(", ") : <span className="text-gris">Sin agentes asignados</span>}</p>
      )}
    </article>
  );
}

function Editor({ inicial, agentes, onCerrar, onGuardado }) {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const [clientes] = useRecurso("clientes");
  const [f, setF] = useState(inicial);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  useEffect(() => { setF(inicial); setError(""); }, [inicial]);
  if (!f) return null;
  const poner = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const alternar = (k, v) => setF({ ...f, [k]: f[k].includes(v) ? f[k].filter((x) => x !== v) : [...f[k], v] });

  const guardar = async (e) => {
    e.preventDefault();
    setGuardando(true);
    setError("");
    try {
      await guardarCampana({ ...f, cliente: f.cliente || null, fecha_fin: f.fecha_fin || null,
        meta_contactos_dia: Number(f.meta_contactos_dia) || 0, meta_conversion: Number(f.meta_conversion) || 0, meta_calidad: Number(f.meta_calidad) || 0 });
      onGuardado(f.id ? "Campaña actualizada." : "Campaña creada. Los agentes ya la ven en su pantalla.");
    } catch (err) { setError(err.message); }
    setGuardando(false);
  };
  const borrar = async () => {
    if (!(await confirmar({ titulo: "¿Borrar la campaña?", mensaje: `${f.nombre}. Si solo terminó, mejor desmárcala como activa.`, boton: "Borrar", peligro: true }))) return;
    try { await eliminarCampana(f.id); onGuardado("Campaña borrada."); } catch (err) { avisar(err.message, "rojo"); }
  };

  return (
    <Modal abierto onCerrar={onCerrar} titulo={f.id ? "Editar campaña" : "Nueva campaña"} ancho="md:max-w-2xl"
      pie={<>
        {f.id && <Boton variante="peligro" icono={Trash2} onClick={borrar} className="mr-auto">Borrar</Boton>}
        <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
        <Boton type="submit" form="form-campana" cargando={guardando}>Guardar</Boton>
      </>}>
      <form id="form-campana" onSubmit={guardar} className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        <Campo etiqueta="Nombre de la campaña">{(id) => <input id={id} className="campo" required value={f.nombre} onChange={poner("nombre")} placeholder="Ej.: Cobros Banco X, noviembre" />}</Campo>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Cliente (opcional)">{(id) => (
            <select id={id} className="campo" value={f.cliente || ""} onChange={poner("cliente")}>
              <option value="">Interna / sin cliente</option>
              {(clientes || []).map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
            </select>)}</Campo>
          <Campo etiqueta="Tipo">{(id) => <select id={id} className="campo" value={f.tipo} onChange={poner("tipo")}>{TIPOS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select>}</Campo>
          <Campo etiqueta="Idioma">{(id) => <select id={id} className="campo" value={f.idioma} onChange={poner("idioma")}>{IDIOMAS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select>}</Campo>
          <Campo etiqueta="Horario de atención">{(id) => <input id={id} className="campo" value={f.horario} onChange={poner("horario")} placeholder="Lunes a viernes, 8:00 a 5:00" />}</Campo>
          <Campo etiqueta="Empieza">{(id) => <input id={id} type="date" className="campo" required value={f.fecha_inicio} onChange={poner("fecha_inicio")} />}</Campo>
          <Campo etiqueta="Termina (opcional)">{(id) => <input id={id} type="date" className="campo" value={f.fecha_fin || ""} onChange={poner("fecha_fin")} />}</Campo>
        </div>
        <fieldset>
          <legend className="etiqueta">Canales</legend>
          <div className="flex flex-wrap gap-2">
            {CANALES.map((x) => (
              <label key={x} className={cx("flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 text-sm", f.canales.includes(x) ? "border-azul bg-azul/10 text-azul" : "border-linea")}>
                <input type="checkbox" className="accent-azul" checked={f.canales.includes(x)} onChange={() => alternar("canales", x)} />{x}
              </label>
            ))}
          </div>
        </fieldset>
        <div className="grid gap-4 sm:grid-cols-3">
          <Campo etiqueta="Contactos efectivos al día" ayuda="Por agente.">{(id) => <input id={id} type="number" min={0} className="campo" value={f.meta_contactos_dia} onChange={poner("meta_contactos_dia")} />}</Campo>
          <Campo etiqueta="Conversión o resolución (%)">{(id) => <input id={id} type="number" min={0} max={100} step="any" className="campo" value={f.meta_conversion} onChange={poner("meta_conversion")} />}</Campo>
          <Campo etiqueta="Calidad mínima (%)" ayuda="De la ficha de monitoreo.">{(id) => <input id={id} type="number" min={0} max={100} step="any" className="campo" value={f.meta_calidad} onChange={poner("meta_calidad")} />}</Campo>
        </div>
        <fieldset>
          <legend className="etiqueta">Agentes</legend>
          {agentes.length === 0 ? (
            <p className="text-sm text-gris">Todavía no hay agentes. Se dan en <Link to="/personas" className="font-medium text-azul hover:underline">Personas</Link> → editar → acceso «Agente de call center».</p>
          ) : (
            <div className="grid gap-1.5 sm:grid-cols-2">
              {agentes.map((a) => (
                <label key={a.id} className="flex items-center gap-2 rounded-lg border border-linea px-3 py-2 text-sm">
                  <input type="checkbox" className="accent-azul" checked={f.agentes.includes(a.id)} onChange={() => alternar("agentes", a.id)} />
                  <span className="min-w-0 truncate">{a.nombre}</span>
                </label>
              ))}
            </div>
          )}
        </fieldset>
        <Campo etiqueta="Guion y protocolos" ayuda="Los agentes lo ven en su pantalla.">{(id) => <textarea id={id} rows={4} className="campo" value={f.guion} onChange={poner("guion")} />}</Campo>
        <Campo etiqueta="Notas internas">{(id) => <textarea id={id} rows={2} className="campo" value={f.notas} onChange={poner("notas")} />}</Campo>
        <label className="flex items-center gap-2 text-sm font-medium"><input type="checkbox" className="size-4 accent-azul" checked={f.activa} onChange={poner("activa")} />Campaña activa</label>
      </form>
    </Modal>
  );
}

function KpisAgente({ kpis }) {
  if (!kpis.length) return <p className="text-sm text-gris">Sin KPIs medidos este mes. La gerencia los anota en «KPIs del mes».</p>;
  return (
    <ul className="space-y-3">
      {kpis.map((k) => (
        <li key={k.kpi_asignado_id}>
          <div className="flex justify-between gap-3 text-sm"><span className="min-w-0 truncate">{k.nombre}</span><span className="shrink-0 font-medium num">{Math.round(k.cumplimiento)}%</span></div>
          <Barra valor={k.cumplimiento} className="mt-1" />
          <p className="mt-0.5 text-xs text-gris">{k.valor} de {k.meta} {k.unidad_medida}</p>
        </li>
      ))}
    </ul>
  );
}

/** Lo que ve el agente: sus campañas activas, metas, guion y su mes. */
function VistaAgente({ campanas, yo }) {
  const { usuario } = useSesion();
  return (
    <div className="space-y-6">
      <section className="rounded-2xl bg-noche p-6 text-white">
        <p className="text-white/70">Call Center</p>
        <h1 className="mt-1 text-[28px] font-semibold text-white">Hola, {usuario.nombre.split(" ")[0]}</h1>
        <div className="mt-4 flex flex-wrap items-end gap-6">
          <div><p className="text-sm text-white/60">Tu puntaje del mes</p><p className="font-display text-4xl font-semibold num">{yo?.puntaje != null ? Math.round(yo.puntaje * 10) / 10 : "—"}</p></div>
          {yo?.evaluacion && <Insignia tono={EVALUACION[yo.evaluacion][1]}>{EVALUACION[yo.evaluacion][0]}</Insignia>}
          <p className="text-sm text-white/60">{campanas.length ? `${campanas.length} campaña${campanas.length > 1 ? "s" : ""} activa${campanas.length > 1 ? "s" : ""}` : "Sin campaña asignada"}</p>
        </div>
      </section>
      {campanas.length === 0 ? (
        <Vacio icono={Headset} titulo="Todavía no tienes campaña">Cuando la gerencia del call center te asigne una, aquí verás sus metas, el horario y el guion.</Vacio>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {campanas.map((c) => (
            <div key={c.id} className="space-y-3">
              <TarjetaCampana c={c} />
              {c.guion && (
                <details className="rounded-xl border border-linea bg-white p-4">
                  <summary className="cursor-pointer font-medium">Guion y protocolos</summary>
                  <p className="mt-3 whitespace-pre-line text-[15px] leading-relaxed">{c.guion}</p>
                </details>
              )}
            </div>
          ))}
        </div>
      )}
      <Panel titulo="Mis KPIs del mes"><KpisAgente kpis={yo?.kpis || []} /></Panel>
    </div>
  );
}

export default function CallCenter() {
  const avisar = useAviso();
  const { esAdmin } = useSesion();
  const [params, setParams] = useSearchParams();
  const [datos, setDatos] = useState(null);
  const [campanas, setCampanas] = useState(null);
  const [error, setError] = useState("");
  const [editando, setEditando] = useState(null);
  const ver = params.get("ver") === "agentes" ? "agentes" : "campanas";

  const cargar = useCallback(() => {
    Promise.all([resumenCallCenter(), listarCampanas()])
      .then(([r, c]) => { setDatos(r); setCampanas(c); })
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => { if (params.get("nueva") === "1") { setEditando(vacia()); params.delete("nueva"); setParams(params, { replace: true }); } }, [params, setParams]);

  if (error) return <Alerta>{error}</Alerta>;
  if (!datos || !campanas) return <Cargando />;
  if (!datos.gestiona) return <VistaAgente campanas={campanas.filter((c) => c.activa)} yo={datos.agentes[0]} />;

  return (
    <div>
      <Cabecera titulo="Call Center" descripcion="Campañas con sus metas y los agentes que las atienden. Los agentes tienen su propia pantalla y se evalúan en un ranking aparte del resto del equipo.">
        {esAdmin && <Link to="/desempeno?grupo=agentes" className="inline-flex h-11 items-center gap-2 rounded-lg border border-linea bg-white px-4 text-[15px] font-medium hover:bg-fondo"><Trophy className="size-4" />Ranking del call center</Link>}
        <Boton icono={Plus} onClick={() => setEditando(vacia())}>Nueva campaña</Boton>
      </Cabecera>
      <Pestanas className="mb-5 md:w-96" valor={ver} onCambio={(v) => { if (v === "agentes") params.set("ver", v); else params.delete("ver"); setParams(params, { replace: true }); }} opciones={[
        { valor: "campanas", etiqueta: "Campañas", cuenta: campanas.length },
        { valor: "agentes", etiqueta: "Agentes", cuenta: datos.agentes.length },
      ]} />

      {ver === "campanas" ? (
        campanas.length === 0 ? (
          <Vacio icono={Headset} titulo="Todavía no hay campañas" accion={<Boton icono={Plus} onClick={() => setEditando(vacia())}>Nueva campaña</Boton>}>
            Una campaña dice qué se atiende (cobros, ventas, soporte…), para qué cliente, en qué horario y canales, y las metas diarias de cada agente.
          </Vacio>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {campanas.map((c) => <TarjetaCampana key={c.id} c={c} onEditar={(x) => setEditando({ ...x, cliente: x.cliente || "", fecha_fin: x.fecha_fin || "" })} />)}
          </div>
        )
      ) : datos.agentes.length === 0 ? (
        <Vacio icono={Users} titulo="Todavía no hay agentes">
          Dale a cada agente el acceso «Agente de call center» en Personas → editar. Así entra a su propia pantalla y se evalúa aparte del resto del equipo.
        </Vacio>
      ) : (
        <Panel cuerpo="p-0">
          <div className="overflow-x-auto">
            <table className="tabla">
              <thead><tr><th>Agente</th><th>Campañas</th><th className="min-w-40">Puntaje del mes</th><th>KPIs medidos</th></tr></thead>
              <tbody>
                {datos.agentes.map((a) => (
                  <tr key={a.id}>
                    <td><p className="font-medium">{a.nombre}</p><p className="text-sm text-gris">{a.puesto || "Sin puesto"}</p></td>
                    <td className="text-sm">{a.campanas.length ? a.campanas.map((c) => c.nombre).join(", ") : <span className="text-[#a3170f]">Sin campaña</span>}</td>
                    <td>{a.puntaje != null ? <div className="flex items-center gap-2"><Puntaje valor={a.puntaje} className="w-12" /><Insignia tono={EVALUACION[a.evaluacion][1]}>{EVALUACION[a.evaluacion][0]}</Insignia></div> : <span className="text-sm text-gris">Sin evaluar</span>}</td>
                    <td className="text-sm">{a.kpis.length ? a.kpis.map((k) => `${k.nombre} ${Math.round(k.cumplimiento)}%`).join(" · ") : <span className="text-gris">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {editando && <Editor inicial={editando} agentes={datos.agentes} onCerrar={() => setEditando(null)}
        onGuardado={(msg) => { setEditando(null); avisar(msg); cargar(); }} />}
    </div>
  );
}
