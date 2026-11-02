import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { KeyRound, Pencil, Plus, Search, UserRound } from "lucide-react";
import { guardarUsuario, puestos as cargarPuestos, usuarios as cargarUsuarios } from "@/lib/api";
import { fechaCorta } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import { Alerta, Avatar, Boton, Cabecera, Campo, Cargando, Insignia, Modal, Panel, Vacio, useAviso } from "@/components/ui";

// Los perfiles de acceso (qué puede hacer cada persona) se manejan en «Accesos y permisos».
const perfilesDe = (roles = []) => roles.filter((r) => r !== "Colaborador").join(", ") || "Colaborador";

function generarClave() {
  const letras = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const arr = new Uint32Array(10);
  crypto.getRandomValues(arr);
  return "Adz-" + Array.from(arr, (n) => letras[n % letras.length]).join("");
}

function FormPersona({ abierto, inicial, puestos, onCerrar, onGuardado }) {
  const { veSalarios } = useSesion();
  const [f, setF] = useState({});
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const nuevo = !inicial?.id;
  useEffect(() => {
    if (!abierto) return;
    setError("");
    setF(nuevo ? { first_name: "", last_name: "", username: "", email: "", puesto_trabajo_id: "", password: generarClave(), is_active: true, horas_semana: 44, costo_hora: "", salario_mensual: "", nomina: "" }
      : { ...inicial, puesto_trabajo_id: inicial.puesto_id || "", password: "", horas_semana: inicial.horas_semana ?? 44, costo_hora: inicial.costo_hora ?? "",
        salario_mensual: inicial.salario_mensual ?? "", nomina: inicial.nomina || "" });
  }, [abierto, inicial, nuevo]);
  const cambiar = (c) => (e) => setF({ ...f, [c]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  const guardar = async (e) => {
    e.preventDefault();
    setError("");
    if (!f.first_name?.trim() || !f.username?.trim()) return setError("Nombre y usuario son obligatorios.");
    setGuardando(true);
    try {
      const datos = {
        id: f.id, first_name: f.first_name.trim(), last_name: (f.last_name || "").trim(), username: f.username.trim().toLowerCase(),
        email: (f.email || "").trim().toLowerCase(), puesto_trabajo_id: f.puesto_trabajo_id ? Number(f.puesto_trabajo_id) : null,
        is_active: !!f.is_active, horas_semana: f.horas_semana || 44,
      };
      if (nuevo) datos.roles_asignados = ["Colaborador"]; // si su puesto supervisa a otros, recibe «Supervisor» solo
      if (veSalarios) Object.assign(datos, {
        costo_hora: f.costo_hora === "" || f.costo_hora == null ? null : f.costo_hora,
        salario_mensual: f.salario_mensual === "" || f.salario_mensual == null ? null : f.salario_mensual, nomina: (f.nomina || "").trim(),
      });
      if (f.password) datos.password = f.password;
      const u = await guardarUsuario(datos);
      onGuardado(u, f.password);
    } catch (err) { setError(err.message); }
    setGuardando(false);
  };

  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={nuevo ? "Nueva persona" : `Editar a ${inicial?.nombre}`} ancho="md:max-w-2xl"
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton type="submit" form="form-persona" cargando={guardando}>{nuevo ? "Crear cuenta" : "Guardar cambios"}</Boton></>}>
      <form id="form-persona" onSubmit={guardar} className="space-y-4" autoComplete="off">
        {error && <Alerta>{error}</Alerta>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Nombre">{(id) => <input id={id} className="campo" value={f.first_name || ""} onChange={cambiar("first_name")} autoFocus />}</Campo>
          <Campo etiqueta="Apellidos">{(id) => <input id={id} className="campo" value={f.last_name || ""} onChange={cambiar("last_name")} />}</Campo>
          <Campo etiqueta="Usuario" ayuda="Para entrar. Sin espacios.">{(id) => <input id={id} className="campo" value={f.username || ""} onChange={cambiar("username")} autoCapitalize="none" />}</Campo>
          <Campo etiqueta="Correo (opcional)" ayuda="Si lo pones, también sirve para entrar.">{(id) => <input id={id} type="email" className="campo" value={f.email || ""} onChange={cambiar("email")} />}</Campo>
        </div>
        <Campo etiqueta="Puesto" ayuda="Define su departamento, su supervisor y sus KPIs.">
          {(id) => (
            <select id={id} className="campo" value={f.puesto_trabajo_id || ""} onChange={cambiar("puesto_trabajo_id")}>
              <option value="">Sin puesto</option>
              {puestos.map((p) => <option key={p.id} value={p.id}>{p.nombre} ({p.departamento_nombre})</option>)}
            </select>
          )}
        </Campo>
        <p className="rounded-lg border border-linea bg-niebla/60 p-3 text-sm text-gris">
          {nuevo ? "Entra como Colaborador (solo ve y entrega lo suyo). Si su puesto supervisa a otros, recibe el perfil Supervisor."
            : <>Perfiles: <span className="font-medium text-noche">{perfilesDe(inicial?.roles)}</span>.</>}{" "}
          Los perfiles, las excepciones y el equipo adicional se cambian en <Link to="/accesos" className="font-medium text-azul hover:underline">Accesos y permisos</Link>.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Horas por semana" ayuda="Su capacidad, para medir la carga.">
            {(id) => <input id={id} type="number" min={1} max={80} step="0.5" className="campo" value={f.horas_semana ?? ""} onChange={cambiar("horas_semana")} />}
          </Campo>
          {veSalarios && <>
          <Campo etiqueta="Salario mensual (RD$)" ayuda="Solo lo ven quienes manejan salarios.">
            {(id) => <input id={id} type="number" min={0} step="any" className="campo" value={f.salario_mensual ?? ""}
              onChange={(e) => setF({ ...f, salario_mensual: e.target.value, costo_hora: "" })} />}
          </Campo>
          <Campo etiqueta="Nómina" ayuda="En qué nómina cobra.">
            {(id) => <input id={id} className="campo" list="nominas" placeholder="ADZONE, Call Center, Iguala…" value={f.nomina || ""} onChange={cambiar("nomina")} />}
          </Campo>
          <Campo etiqueta="Costo por hora (RD$)" ayuda="Para la rentabilidad. Vacío: se calcula del salario (÷ 23.83 días ÷ 8 h).">
            {(id) => <input id={id} type="number" min={0} step="any" className="campo" value={f.costo_hora ?? ""} onChange={cambiar("costo_hora")} />}
          </Campo>
          </>}
        </div>
        <datalist id="nominas"><option value="ADZONE" /><option value="Call Center" /><option value="Iguala" /></datalist>
        <Campo etiqueta={nuevo ? "Contraseña inicial" : "Nueva contraseña (opcional)"} ayuda={nuevo ? "Compártela con la persona; luego puede cambiarla en Mi cuenta." : "Déjala vacía para no cambiarla."}>
          {(id) => (
            <div className="flex gap-2">
              <input id={id} className="campo font-mono" value={f.password || ""} onChange={cambiar("password")} autoComplete="new-password" />
              <Boton variante="secundario" icono={KeyRound} onClick={() => setF({ ...f, password: generarClave() })}>Generar</Boton>
            </div>
          )}
        </Campo>
        {!nuevo && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!f.is_active} onChange={cambiar("is_active")} className="accent-azul" />Cuenta activa (si la desactivas no puede entrar y sale del ranking)</label>}
      </form>
    </Modal>
  );
}

export default function Personas() {
  const { usuario, veSalarios } = useSesion();
  const avisar = useAviso();
  const [lista, setLista] = useState(null);
  const [puestos, setPuestos] = useState([]);
  const [error, setError] = useState("");
  const [buscar, setBuscar] = useState("");
  const [filtro, setFiltro] = useState("activos");
  const [form, setForm] = useState(null);
  const [claveNueva, setClaveNueva] = useState(null);

  const cargar = useCallback(() => { cargarUsuarios().then(setLista).catch((e) => setError(e.message)); }, []);
  useEffect(() => { cargar(); cargarPuestos().then(setPuestos).catch(() => {}); }, [cargar]);

  const filtrada = useMemo(() => (lista || []).filter((u) => {
    if (filtro === "activos" && !u.is_active) return false;
    if (filtro === "inactivos" && u.is_active) return false;
    if (filtro === "sin_puesto" && (u.puesto_id || !u.is_active)) return false;
    const t = buscar.toLowerCase();
    return !t || [u.nombre, u.username, u.email, u.puesto, u.departamento].some((x) => (x || "").toLowerCase().includes(t));
  }), [lista, filtro, buscar]);

  if (error) return <Alerta>{error}</Alerta>;
  if (!lista) return <Cargando />;
  const sinPuesto = lista.filter((u) => u.is_active && !u.puesto_id).length;

  return (
    <div>
      <Cabecera titulo="Personas" descripcion="Cuentas del equipo, su puesto y su rol en la plataforma.">
        <Boton icono={Plus} onClick={() => setForm({})}>Nueva persona</Boton>
      </Cabecera>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative min-w-56 flex-1 md:max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" />
          <input className="campo h-11 pl-9" placeholder="Buscar por nombre, correo o puesto" value={buscar} onChange={(e) => setBuscar(e.target.value)} aria-label="Buscar persona" />
        </div>
        <select className="campo h-11 w-auto py-0" value={filtro} onChange={(e) => setFiltro(e.target.value)} aria-label="Mostrar">
          <option value="activos">Activas ({lista.filter((u) => u.is_active).length})</option>
          <option value="sin_puesto">Sin puesto ({sinPuesto})</option>
          <option value="inactivos">Desactivadas</option>
          <option value="todos">Todas</option>
        </select>
      </div>
      {sinPuesto > 0 && filtro !== "sin_puesto" && (
        <Alerta tono="amarillo" className="mb-4">{sinPuesto} persona(s) activa(s) sin puesto: no tienen supervisor ni KPIs. <button type="button" className="font-medium underline" onClick={() => setFiltro("sin_puesto")}>Ver quiénes</button></Alerta>
      )}

      {filtrada.length === 0 ? <Vacio icono={UserRound} titulo="Nadie coincide con la búsqueda" /> : (
        <Panel cuerpo="p-0">
          <div className="overflow-x-auto">
            <table className="tabla">
              <thead><tr><th>Persona</th><th className="hidden md:table-cell">Puesto</th><th className="hidden md:table-cell">Perfiles</th>{veSalarios && <th className="hidden text-right lg:table-cell">Salario</th>}<th className="hidden xl:table-cell">Último acceso</th><th className="w-16"><span className="sr-only">Acciones</span></th></tr></thead>
              <tbody>
                {filtrada.map((u) => (
                  <tr key={u.id} className={u.is_active ? "" : "opacity-60"}>
                    <td>
                      <div className="flex items-center gap-3">
                        <Avatar nombre={u.nombre} tam="sm" />
                        <div className="min-w-0">
                          <p className="font-medium">{u.nombre}{u.id === usuario.id && <span className="ml-1.5 text-xs text-gris">(tú)</span>}</p>
                          <p className="truncate text-sm text-gris">{u.username}{u.email && ` · ${u.email}`}</p>
                          {/* En el celular, el puesto va aquí porque sus columnas se ocultan */}
                          <p className="text-xs text-gris md:hidden">{u.puesto || "Sin puesto"}{!u.is_active && " · Desactivada"}</p>
                        </div>
                      </div>
                    </td>
                    <td className="hidden md:table-cell">{u.puesto ? <><p className="text-sm">{u.puesto}</p><p className="text-xs text-gris">{u.departamento}</p></> : <Insignia tono="amarillo">Sin puesto</Insignia>}</td>
                    <td className="hidden md:table-cell"><Insignia tono={u.roles.includes("Administrador") ? "noche" : "neutro"}>{perfilesDe(u.roles)}</Insignia>{!u.is_active && <Insignia className="ml-1">Desactivada</Insignia>}</td>
                    {veSalarios && <td className="hidden whitespace-nowrap text-right lg:table-cell">{u.salario_mensual != null ? <><span className="num">{Number(u.salario_mensual).toLocaleString("es-DO", { maximumFractionDigits: 0 })}</span>{u.nomina && <span className="block text-xs text-gris">{u.nomina}</span>}</> : <span className="text-sm text-gris">—</span>}</td>}
                    <td className="hidden whitespace-nowrap text-sm text-gris xl:table-cell">{u.last_login ? fechaCorta(u.last_login) : "Nunca"}</td>
                    <td className="text-right"><Boton variante="fantasma" tam="sm" icono={Pencil} aria-label={`Editar a ${u.nombre}`} onClick={() => setForm(u)} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      <FormPersona abierto={!!form} inicial={form} puestos={puestos} onCerrar={() => setForm(null)}
        onGuardado={(u, clave) => {
          const nuevo = !form?.id;
          setForm(null);
          cargar();
          if (clave) setClaveNueva({ nombre: u.nombre, usuario: u.username, clave });
          else avisar(nuevo ? "Cuenta creada." : "Cambios guardados.");
        }} />
      <Modal abierto={!!claveNueva} onCerrar={() => setClaveNueva(null)} titulo="Datos para entrar" ancho="max-w-md"
        descripcion={`Compártelos con ${claveNueva?.nombre} por un medio privado. No se vuelven a mostrar.`}
        pie={<Boton onClick={() => { navigator.clipboard?.writeText(`Usuario: ${claveNueva.usuario}\nContraseña: ${claveNueva.clave}`); avisar("Copiado."); }}>Copiar</Boton>}>
        {claveNueva && <dl className="space-y-2 rounded-lg bg-fondo p-4 font-mono text-[15px]"><div><dt className="font-sans text-sm text-gris">Usuario</dt><dd>{claveNueva.usuario}</dd></div><div><dt className="font-sans text-sm text-gris">Contraseña</dt><dd>{claveNueva.clave}</dd></div></dl>}
      </Modal>
    </div>
  );
}
