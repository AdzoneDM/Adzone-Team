// Clientes: directorio con buscador, y el formulario de alta y edición.
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Building2, Plus, Search } from "lucide-react";
import { guardarCliente, listarClientes } from "@/lib/api";
import { olvidarRecurso } from "@/lib/recursos";
import { Alerta, Boton, Cabecera, Campo, Cargando, Modal, Vacio, cx, useAviso } from "@/components/ui";

export const TIPOS_CLIENTE = { EMPRESA: "Empresa", GOBIERNO: "Gobierno", ONG: "ONG / institución", PERSONA: "Persona", INTERNO: "Interno (ADZONE)" };

export function FormCliente({ abierto, onCerrar, inicial, onGuardado }) {
  const [f, setF] = useState({});
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  useEffect(() => { if (abierto) { setError(""); setF(inicial?.id ? { ...inicial } : { nombre: inicial?.nombre || "", tipo: "EMPRESA", activo: true }); } }, [abierto, inicial]);
  const campo = (k, etiqueta, props = {}) => (
    <Campo etiqueta={etiqueta}>{(id) => <input id={id} className="campo" value={f[k] || ""} onChange={(e) => setF({ ...f, [k]: e.target.value })} {...props} />}</Campo>
  );
  const guardar = async (e) => {
    e.preventDefault();
    if (!f.nombre?.trim()) return setError("Escribe el nombre del cliente.");
    setGuardando(true); setError("");
    try { const c = await guardarCliente({ ...f, nombre: f.nombre.trim() }); olvidarRecurso("clientes"); onGuardado(c); } catch (err) { setError(err.message); }
    setGuardando(false);
  };
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={inicial?.id ? "Editar cliente" : "Nuevo cliente"} ancho="md:max-w-2xl"
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton type="submit" form="form-cliente" cargando={guardando}>Guardar</Boton></>}>
      <form id="form-cliente" onSubmit={guardar} className="grid gap-4 sm:grid-cols-2">
        {error && <Alerta className="sm:col-span-2">{error}</Alerta>}
        <div className="sm:col-span-2">{campo("nombre", "Nombre o razón social", { maxLength: 200, autoFocus: true })}</div>
        <Campo etiqueta="Tipo">{(id) => <select id={id} className="campo" value={f.tipo} onChange={(e) => setF({ ...f, tipo: e.target.value })}>{Object.entries(TIPOS_CLIENTE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>}</Campo>
        {campo("rnc", "RNC o cédula", { maxLength: 20, inputMode: "numeric" })}
        {campo("contacto", "Persona de contacto", { maxLength: 150 })}
        {campo("telefono", "Teléfono", { maxLength: 40, inputMode: "tel", type: "tel" })}
        {campo("correo", "Correo", { type: "email", maxLength: 254 })}
        {campo("direccion", "Dirección", { maxLength: 255 })}
        <Campo etiqueta="Notas" className="sm:col-span-2">{(id) => <textarea id={id} rows={3} className="campo" value={f.notas || ""} onChange={(e) => setF({ ...f, notas: e.target.value })} />}</Campo>
        {inicial?.id && <label className="flex items-center gap-2 text-[15px] sm:col-span-2"><input type="checkbox" checked={!!f.activo} onChange={(e) => setF({ ...f, activo: e.target.checked })} className="size-4 accent-azul" /> Cliente activo</label>}
      </form>
    </Modal>
  );
}

export default function Clientes() {
  const avisar = useAviso();
  const navigate = useNavigate();
  const [lista, setLista] = useState(null);
  const [error, setError] = useState("");
  const [buscar, setBuscar] = useState("");
  const [inactivos, setInactivos] = useState(false);
  const [form, setForm] = useState(null);
  const [params, setParams] = useSearchParams();
  useEffect(() => { if (params.get("nuevo") === "1") { setForm({}); setParams({}, { replace: true }); } }, [params, setParams]);
  const cargar = useCallback(() => listarClientes().then(setLista).catch((e) => setError(e.message)), []);
  useEffect(() => { cargar(); }, [cargar]);
  const filtrada = useMemo(() => (lista || []).filter((c) => (inactivos || c.activo) &&
    (!buscar || `${c.nombre} ${c.contacto} ${c.rnc}`.toLowerCase().includes(buscar.toLowerCase()))), [lista, buscar, inactivos]);

  if (error) return <Alerta>{error}</Alerta>;
  return (
    <div>
      <Cabecera titulo="Clientes" descripcion="Con quién trabajamos: sus datos de contacto, proyectos, órdenes y, para Finanzas, lo que deben.">
        <Boton icono={Plus} onClick={() => setForm({})}>Nuevo cliente</Boton>
      </Cabecera>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative min-w-56 flex-1 md:max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" />
          <input className="campo h-11 pl-9" placeholder="Buscar por nombre, contacto o RNC" value={buscar} onChange={(e) => setBuscar(e.target.value)} aria-label="Buscar cliente" />
        </div>
        <label className="flex h-11 items-center gap-2 rounded-lg border border-linea bg-white px-3 text-sm"><input type="checkbox" checked={inactivos} onChange={(e) => setInactivos(e.target.checked)} className="accent-azul" /> Ver inactivos</label>
      </div>
      {!lista ? <Cargando /> : filtrada.length === 0 ? (
        <Vacio icono={Building2} titulo={buscar ? "Ningún cliente coincide" : "Todavía no hay clientes"} accion={<Boton icono={Plus} onClick={() => setForm({ nombre: buscar })}>Nuevo cliente</Boton>} />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-linea bg-white">
          <table className="tabla">
            <thead><tr><th>Cliente</th><th className="hidden md:table-cell">Contacto</th><th className="hidden md:table-cell">Teléfono</th><th className="text-right">Órdenes abiertas</th><th className="hidden text-right md:table-cell">Proyectos activos</th></tr></thead>
            <tbody>
              {filtrada.map((c) => (
                <tr key={c.id} className={cx("cursor-pointer", !c.activo && "opacity-60")} onClick={() => navigate(`/clientes/${c.id}`)}>
                  <td><p className="font-medium">{c.nombre}</p><p className="text-xs text-gris">{c.tipo_nombre}{c.rnc ? ` · RNC ${c.rnc}` : ""}</p></td>
                  <td className="hidden text-sm md:table-cell">{c.contacto || "—"}</td>
                  <td className="hidden text-sm md:table-cell">{c.telefono ? <a href={`tel:${c.telefono}`} onClick={(e) => e.stopPropagation()} className="hover:text-azul">{c.telefono}</a> : "—"}</td>
                  <td className="text-right num">{c.ordenes_abiertas || "—"}</td>
                  <td className="hidden text-right num md:table-cell">{c.proyectos_activos || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <FormCliente abierto={!!form} inicial={form} onCerrar={() => setForm(null)} onGuardado={(c) => { setForm(null); avisar(`«${c.nombre}» guardado.`); cargar(); }} />
    </div>
  );
}
