// Activos y equipos: inventario, asignación, mantenimiento, daños, depreciación e historial.
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AlertTriangle, ArrowRightLeft, Boxes, Pencil, Plus, Search, Undo2, UserPlus, Wrench } from "lucide-react";
import { activos, dispositivos, guardarActivo, historialActivo, listarProyectos, moverActivo, reportarActivo, resumenActivos } from "@/lib/api";
import { dinero, hace } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import { Alerta, Boton, Cabecera, Campo, Cargando, Insignia, Modal, Panel, Vacio, cx, useAviso, useConfirmar } from "@/components/ui";
import { SelectorPersona } from "@/components/Selectores";

const CATEGORIAS = [["COMPUTADORA", "Computadora de escritorio"], ["LAPTOP", "Laptop"], ["MONITOR", "Monitor"], ["CELULAR", "Celular o tableta"],
  ["CAMARA", "Cámara"], ["AUDIO", "Audio y micrófonos"], ["ILUMINACION", "Iluminación"], ["IMPRESION", "Máquina de impresión"], ["HERRAMIENTA", "Herramienta"],
  ["VEHICULO", "Vehículo"], ["RED", "Red y servidores"], ["MOBILIARIO", "Mobiliario"], ["OTRO", "Otro"]];
const TONO = { DISPONIBLE: "verde", ASIGNADO: "azul", MANTENIMIENTO: "amarillo", DANADO: "rojo", BAJA: "neutro" };
const fecha = (iso) => (iso ? new Date(`${String(iso).slice(0, 10)}T12:00`).toLocaleDateString("es-DO", { day: "numeric", month: "short", year: "numeric" }) : "—");
const local = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const hoy = () => local(new Date());

export default function Activos() {
  const { gestionaActivos } = useSesion();
  return gestionaActivos ? <Inventario /> : <MisEquipos />;
}

function MisEquipos() {
  const avisar = useAviso();
  const [lista, setLista] = useState(null);
  const [error, setError] = useState("");
  const [reporte, setReporte] = useState(null);
  const cargar = () => activos().then(setLista).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);
  const reportar = async () => {
    try { await reportarActivo(reporte.id, reporte.nota); avisar("Reportado. Tecnología ya recibió el aviso."); setReporte(null); cargar(); } catch (e) { setError(e.message); }
  };
  return (
    <div className="space-y-5">
      <Cabecera titulo="Equipos asignados" descripcion="Los equipos de la empresa a tu cargo. Si alguno se daña o falla, repórtalo aquí." />
      {error && <Alerta>{error}</Alerta>}
      {!lista ? <Cargando /> : !lista.length ? <Vacio icono={Boxes} titulo="No tienes equipos asignados">Cuando Tecnología o Almacén te asigne uno, aparecerá aquí.</Vacio> : (
        <Panel cuerpo="p-0"><ul className="divide-y divide-linea-suave">{lista.map((a) => (
          <li key={a.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
            <span className="min-w-0 flex-1"><span className="font-medium">{a.codigo} · {a.nombre}</span>
              <span className="block text-xs text-gris">{a.categoria_nombre}{a.marca ? ` · ${a.marca} ${a.modelo}` : ""}{a.serie ? ` · serie ${a.serie}` : ""}</span></span>
            <Insignia tono={TONO[a.estado]}>{a.estado_nombre}</Insignia>
            {a.estado !== "DANADO" && <Boton tam="sm" variante="secundario" icono={AlertTriangle} onClick={() => setReporte({ id: a.id, nombre: a.nombre, nota: "" })}>Reportar daño</Boton>}
          </li>))}</ul></Panel>
      )}
      {reporte && (
        <Modal abierto onCerrar={() => setReporte(null)} titulo={`Reportar daño: ${reporte.nombre}`} pie={<><Boton variante="secundario" onClick={() => setReporte(null)}>Cancelar</Boton><Boton onClick={reportar} disabled={!reporte.nota.trim()}>Reportar</Boton></>}>
          <Campo etiqueta="Qué pasó">{(id) => <textarea id={id} rows={3} className="campo" value={reporte.nota} onChange={(e) => setReporte({ ...reporte, nota: e.target.value })} />}</Campo>
        </Modal>
      )}
    </div>
  );
}

const NUEVO = { nombre: "", categoria: "LAPTOP", marca: "", modelo: "", serie: "", ubicacion: "", fecha_compra: "", costo: "", proveedor: "", garantia_hasta: "",
  vida_util_meses: 36, valor_residual: 0, mantenimiento_cada_meses: "", proximo_mantenimiento: "", notas: "", proyecto: null, dispositivo: null };

function Inventario() {
  const [params, setParams] = useSearchParams();
  const [filtros, setFiltros] = useState({ q: "", estado: "", categoria: "" });
  const [lista, setLista] = useState(null);
  const [resumen, setResumen] = useState(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState(null);
  const abierto = params.get("ver");
  const cargar = useCallback(() => {
    activos(filtros).then(setLista).catch((e) => setError(e.message));
    resumenActivos().then(setResumen).catch(() => {});
  }, [filtros]);
  useEffect(() => { const t = setTimeout(cargar, 250); return () => clearTimeout(t); }, [cargar]);
  return (
    <div className="space-y-5">
      <Cabecera titulo="Activos y equipos" descripcion="Inventario de computadoras, cámaras, audio, herramientas y vehículos: a quién están asignados, su mantenimiento y su valor.">
        <Boton icono={Plus} onClick={() => setForm(NUEVO)}>Equipo</Boton>
      </Cabecera>
      {resumen && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          {[["Equipos", resumen.total], ["Asignados", resumen.asignados], ["Disponibles", resumen.disponibles], ["Dañados", resumen.danados, resumen.danados ? "text-rojo" : ""],
            ["Mantenimiento vencido", resumen.mantenimiento_vencido, resumen.mantenimiento_vencido ? "text-[#a86a00]" : ""], ["Valor actual", dinero(resumen.valor_actual)]].map(([t, v, c]) => (
            <div key={t} className="rounded-xl border border-linea bg-white p-4"><p className="text-sm text-gris">{t}</p><p className={cx("mt-1 font-display text-2xl font-semibold num", c)}>{v}</p></div>))}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <label className="relative"><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" />
          <input className="campo !h-10 w-64 pl-9" placeholder="Código, nombre, serie o persona" aria-label="Buscar" value={filtros.q} onChange={(e) => setFiltros({ ...filtros, q: e.target.value })} /></label>
        <select className="campo !h-10 !w-auto" aria-label="Estado" value={filtros.estado} onChange={(e) => setFiltros({ ...filtros, estado: e.target.value })}>
          <option value="">Todos los estados</option><option value="DISPONIBLE">Disponibles</option><option value="ASIGNADO">Asignados</option>
          <option value="MANTENIMIENTO">En mantenimiento</option><option value="DANADO">Dañados</option><option value="BAJA">De baja</option></select>
        <select className="campo !h-10 !w-auto" aria-label="Categoría" value={filtros.categoria} onChange={(e) => setFiltros({ ...filtros, categoria: e.target.value })}>
          <option value="">Todas las categorías</option>{CATEGORIAS.map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
      </div>
      {error && <Alerta>{error}</Alerta>}
      {!lista ? <Cargando /> : !lista.length ? <Vacio icono={Boxes} titulo="Sin equipos">Registra las computadoras, cámaras, luces, herramientas y vehículos de la empresa.</Vacio> : (
        <div className="overflow-x-auto rounded-xl border border-linea bg-white"><table className="tabla">
          <thead><tr><th>Equipo</th><th>Asignado a</th><th>Ubicación</th><th>Mantenimiento</th><th className="text-right">Valor actual</th><th>Estado</th></tr></thead>
          <tbody>{lista.map((a) => (
            <tr key={a.id} className="cursor-pointer hover:bg-fondo" onClick={() => setParams({ ver: String(a.id) })}>
              <td className="min-w-56"><span className="font-medium">{a.codigo} · {a.nombre}</span><span className="block text-xs text-gris">{a.categoria_nombre}{a.marca ? ` · ${a.marca} ${a.modelo}` : ""}{a.serie ? ` · ${a.serie}` : ""}</span></td>
              <td className="text-sm">{a.asignado_nombre || "—"}{a.proyecto_nombre && <span className="block text-xs text-gris">{a.proyecto_nombre}</span>}</td>
              <td className="text-sm">{a.ubicacion || "—"}</td>
              <td className={cx("whitespace-nowrap text-sm", a.proximo_mantenimiento && a.proximo_mantenimiento < hoy() && "font-semibold text-[#a86a00]")}>{a.proximo_mantenimiento ? fecha(a.proximo_mantenimiento) : "—"}</td>
              <td className="text-right num">{a.valor_actual != null ? dinero(a.valor_actual) : "—"}</td>
              <td><Insignia tono={TONO[a.estado]}>{a.estado_nombre}</Insignia></td>
            </tr>))}</tbody>
        </table></div>
      )}
      {abierto && <Detalle id={abierto} lista={lista} onCerrar={() => setParams({})} onEditar={(a) => { setParams({}); setForm(a); }} onCambio={cargar} />}
      {form && <FormActivo inicial={form} onCerrar={() => setForm(null)} onListo={() => { setForm(null); cargar(); }} />}
    </div>
  );
}

function FormActivo({ inicial, onCerrar, onListo }) {
  const avisar = useAviso();
  const [f, setF] = useState(inicial);
  const [error, setError] = useState("");
  const [pcs, setPcs] = useState([]);
  const [proyectos, setProyectos] = useState([]);
  useEffect(() => {
    dispositivos().then(setPcs).catch(() => {});
    listarProyectos({ estado: "EN_CURSO" }).then((r) => setProyectos(r.results || r)).catch(() => {});
  }, []);
  const v = (k) => (f[k] ?? "");
  const poner = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const guardar = async () => {
    setError("");
    const limpio = Object.fromEntries(Object.entries(f).map(([k, x]) => [k, x === "" ? null : x]));
    try { await guardarActivo(limpio); avisar(f.id ? "Guardado." : "Equipo registrado."); onListo(); } catch (e) { setError(e.message); }
  };
  return (
    <Modal abierto onCerrar={onCerrar} ancho="max-w-3xl" titulo={f.id ? `Editar ${f.codigo}` : "Registrar equipo"} pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton onClick={guardar}>Guardar</Boton></>}>
      {error && <Alerta className="mb-3">{error}</Alerta>}
      <div className="grid gap-3 sm:grid-cols-3">
        <Campo etiqueta="Nombre" className="sm:col-span-2">{(id) => <input id={id} className="campo" value={v("nombre")} onChange={poner("nombre")} placeholder="Ej.: Laptop diseño 3" />}</Campo>
        <Campo etiqueta="Categoría">{(id) => <select id={id} className="campo" value={v("categoria")} onChange={poner("categoria")}>{CATEGORIAS.map(([k, x]) => <option key={k} value={k}>{x}</option>)}</select>}</Campo>
        <Campo etiqueta="Marca">{(id) => <input id={id} className="campo" value={v("marca")} onChange={poner("marca")} />}</Campo>
        <Campo etiqueta="Modelo">{(id) => <input id={id} className="campo" value={v("modelo")} onChange={poner("modelo")} />}</Campo>
        <Campo etiqueta="Número de serie">{(id) => <input id={id} className="campo" value={v("serie")} onChange={poner("serie")} />}</Campo>
        <Campo etiqueta="Ubicación">{(id) => <input id={id} className="campo" value={v("ubicacion")} onChange={poner("ubicacion")} placeholder="Oficina, estudio, taller…" />}</Campo>
        <Campo etiqueta="Fecha de compra">{(id) => <input id={id} type="date" className="campo" value={v("fecha_compra")} onChange={poner("fecha_compra")} />}</Campo>
        <Campo etiqueta="Costo (RD$)">{(id) => <input id={id} type="number" min={0} className="campo" value={v("costo")} onChange={poner("costo")} />}</Campo>
        <Campo etiqueta="Proveedor">{(id) => <input id={id} className="campo" value={v("proveedor")} onChange={poner("proveedor")} />}</Campo>
        <Campo etiqueta="Garantía hasta">{(id) => <input id={id} type="date" className="campo" value={v("garantia_hasta")} onChange={poner("garantia_hasta")} />}</Campo>
        <Campo etiqueta="Vida útil (meses)" ayuda="Para la depreciación.">{(id) => <input id={id} type="number" min={1} className="campo" value={v("vida_util_meses")} onChange={poner("vida_util_meses")} />}</Campo>
        <Campo etiqueta="Mantenimiento cada (meses)">{(id) => <input id={id} type="number" min={1} className="campo" value={v("mantenimiento_cada_meses")} onChange={poner("mantenimiento_cada_meses")} />}</Campo>
        <Campo etiqueta="Próximo mantenimiento">{(id) => <input id={id} type="date" className="campo" value={v("proximo_mantenimiento")} onChange={poner("proximo_mantenimiento")} />}</Campo>
        <Campo etiqueta="Proyecto (opcional)">{(id) => <select id={id} className="campo" value={v("proyecto")} onChange={poner("proyecto")}><option value="">—</option>{proyectos.map((p) => <option key={p.id} value={p.id}>{p.codigo} · {p.nombre}</option>)}</select>}</Campo>
        <Campo etiqueta="Computadora monitoreada" ayuda="Si este equipo tiene el agente instalado." className="sm:col-span-2">{(id) => <select id={id} className="campo" value={v("dispositivo")} onChange={poner("dispositivo")}><option value="">—</option>{pcs.filter((d) => d.activo).map((d) => <option key={d.id} value={d.id}>{d.nombre} · {d.persona || d.usuario}</option>)}</select>}</Campo>
        <Campo etiqueta="Notas" className="sm:col-span-3">{(id) => <textarea id={id} rows={2} className="campo" value={v("notas")} onChange={poner("notas")} />}</Campo>
      </div>
    </Modal>
  );
}

const ACCIONES = [["ASIGNACION", "Asignar", UserPlus], ["DEVOLUCION", "Recibir devolución", Undo2], ["TRASLADO", "Trasladar", ArrowRightLeft],
  ["MANTENIMIENTO", "Mantenimiento hecho", Wrench], ["REPARACION", "Reparado", Wrench], ["DANO", "Reportar daño", AlertTriangle], ["BAJA", "Dar de baja", AlertTriangle]];

function Detalle({ id, lista, onCerrar, onEditar, onCambio }) {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const [a, setA] = useState(() => (lista || []).find((x) => String(x.id) === String(id)) || null);
  const [hist, setHist] = useState(null);
  const [accion, setAccion] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { historialActivo(id).then(setHist).catch((e) => setError(e.message)); }, [id, a]);
  useEffect(() => { if (!a) activos({ bajas: 1 }).then((l) => setA(l.find((x) => String(x.id) === String(id)) || null)); }, [a, id]);
  const ejecutar = async () => {
    setError("");
    if (accion.tipo === "BAJA" && !(await confirmar({ titulo: "¿Dar de baja este equipo?", mensaje: "Sale del inventario activo; su historial se conserva.", boton: "Dar de baja", peligro: true }))) return;
    try { const r = await moverActivo(id, accion); setA(r); setAccion(null); avisar("Registrado."); onCambio(); } catch (e) { setError(e.message); }
  };
  if (!a) return <Modal abierto onCerrar={onCerrar} titulo="Equipo"><Cargando /></Modal>;
  const posibles = ACCIONES.filter(([t]) => a.estado !== "BAJA" && !(t === "DEVOLUCION" && !a.asignado_a) && !(t === "REPARACION" && a.estado !== "DANADO"));
  return (
    <Modal abierto onCerrar={onCerrar} ancho="max-w-3xl" titulo={`${a.codigo} · ${a.nombre}`} descripcion={`${a.categoria_nombre}${a.marca ? ` · ${a.marca} ${a.modelo}` : ""}${a.serie ? ` · serie ${a.serie}` : ""}`}>
      {error && <Alerta className="mb-3">{error}</Alerta>}
      <div className="flex flex-wrap items-center gap-2"><Insignia tono={TONO[a.estado]}>{a.estado_nombre}</Insignia>
        {a.asignado_nombre && <span className="text-sm">Asignado a <strong>{a.asignado_nombre}</strong></span>}
        {a.dispositivo_nombre && <span className="text-sm text-gris">· PC monitoreada: {a.dispositivo_nombre} ({a.dispositivo_contacto ? hace(a.dispositivo_contacto) : "sin contacto"})</span>}
        <Boton tam="sm" variante="fantasma" icono={Pencil} className="ml-auto" onClick={() => onEditar(a)}>Editar</Boton></div>
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {[["Costo", a.costo != null ? dinero(a.costo) : "—"], ["Valor actual", a.valor_actual != null ? dinero(a.valor_actual) : "—"], ["Compra", fecha(a.fecha_compra)], ["Garantía", fecha(a.garantia_hasta)]].map(([t, v]) => (
          <div key={t} className="rounded-lg bg-fondo p-3"><p className="text-xs text-gris">{t}</p><p className="font-semibold num">{v}</p></div>))}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">{posibles.map(([t, etiqueta, Icono]) => (
        <Boton key={t} tam="sm" variante={t === "BAJA" || t === "DANO" ? "fantasma" : "secundario"} icono={Icono} onClick={() => setAccion({ tipo: t, persona: "", nota: "", costo: "", ubicacion: a.ubicacion })}>{etiqueta}</Boton>))}</div>
      {accion && (
        <div className="mt-3 grid gap-2 rounded-lg border border-linea p-3 sm:grid-cols-3">
          {accion.tipo === "ASIGNACION" && <div className="sm:col-span-3"><SelectorPersona etiqueta="A quién" valor={accion.persona} onCambio={(v) => setAccion({ ...accion, persona: v })} /></div>}
          {accion.tipo === "TRASLADO" && <Campo etiqueta="Nueva ubicación">{(i) => <input id={i} className="campo" value={accion.ubicacion} onChange={(e) => setAccion({ ...accion, ubicacion: e.target.value })} />}</Campo>}
          {["MANTENIMIENTO", "REPARACION"].includes(accion.tipo) && <Campo etiqueta="Costo (RD$)">{(i) => <input id={i} type="number" min={0} className="campo" value={accion.costo} onChange={(e) => setAccion({ ...accion, costo: e.target.value })} />}</Campo>}
          <Campo etiqueta="Nota" className={accion.tipo === "ASIGNACION" ? "sm:col-span-2" : "sm:col-span-2"}>{(i) => <input id={i} className="campo" value={accion.nota} onChange={(e) => setAccion({ ...accion, nota: e.target.value })} />}</Campo>
          <div className="flex items-end gap-2"><Boton variante="secundario" onClick={() => setAccion(null)}>Cancelar</Boton><Boton onClick={ejecutar}>Registrar</Boton></div>
        </div>
      )}
      <h3 className="mb-1 mt-5 font-semibold">Historial</h3>
      {!hist ? <Cargando /> : (
        <ul className="divide-y divide-linea-suave">{hist.map((h) => (
          <li key={h.id} className="py-2 text-sm"><span className="font-medium">{h.tipo_nombre}</span> · {fecha(h.fecha)}{h.persona_nombre ? ` · ${h.persona_nombre}` : ""}{h.costo ? ` · ${dinero(h.costo)}` : ""}
            {h.nota && <span className="block text-gris">{h.nota}</span>}<span className="block text-xs text-gris">Registró {h.registrado_por_nombre || "—"}</span></li>))}</ul>
      )}
    </Modal>
  );
}
