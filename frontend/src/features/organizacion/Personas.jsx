import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { KeyRound, Plus } from "lucide-react";
import { guardarUsuario, puestos as cargarPuestos, usuarios as cargarUsuarios } from "@/lib/api";
import { useSesion } from "@/lib/sesion";
import { Alerta, Boton, Cabecera, Campo, Cargando, Modal, useAviso } from "@/components/ui";
import ListaPersonas, { BuscadorPersonas, FiltrosPersonas } from "@/features/organizacion/PersonasLista";

// Los perfiles de acceso (qué puede hacer cada persona) se manejan en «Accesos y permisos».
const perfilesDe = (roles = []) => roles.filter((r) => r !== "Colaborador").join(", ") || "Colaborador";

function generarClave() {
  const letras = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const arr = new Uint32Array(10);
  crypto.getRandomValues(arr);
  return "Adz-" + Array.from(arr, (n) => letras[n % letras.length]).join("");
}

function FormPersona({ abierto, inicial, puestos, onCerrar, onGuardado }) {
  const { veSalarios, esAdmin, usuario: yo, soloDirectorio } = useSesion();
  const [f, setF] = useState({});
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const nuevo = !inicial?.id;
  // Con el permiso «Personas» (sin «Personas y accesos») de una cuenta existente solo se ve su ficha y se activa o desactiva
  const soloVer = soloDirectorio && !nuevo;
  const esMia = !nuevo && inicial?.id === yo?.id;
  useEffect(() => {
    if (!abierto) return;
    setError("");
    setF(nuevo ? { first_name: "", last_name: "", username: "", email: "", puesto_trabajo_id: "", password: generarClave(), is_active: true, horas_semana: 44, costo_hora: "", salario_mensual: "", nomina: "", adicionales: [] }
      : { ...inicial, puesto_trabajo_id: inicial.puesto_id || "", password: "", adicionales: (inicial.puestos_adicionales || []).map((p) => p.id), horas_semana: inicial.horas_semana ?? 44, costo_hora: inicial.costo_hora ?? "",
        salario_mensual: inicial.salario_mensual ?? "", nomina: inicial.nomina || "" });
  }, [abierto, inicial, nuevo]);
  const cambiar = (c) => (e) => setF({ ...f, [c]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  const guardar = async (e) => {
    e.preventDefault();
    setError("");
    if (soloVer) {
      setGuardando(true);
      try { const u = await guardarUsuario({ id: f.id, is_active: !!f.is_active }); onGuardado(u, ""); } catch (err) { setError(err.message); }
      setGuardando(false);
      return;
    }
    if (!f.first_name?.trim() || !f.username?.trim()) return setError("Nombre y usuario son obligatorios.");
    setGuardando(true);
    try {
      const datos = {
        id: f.id, first_name: f.first_name.trim(), last_name: (f.last_name || "").trim(), username: f.username.trim().toLowerCase(),
        email: (f.email || "").trim().toLowerCase(), puesto_trabajo_id: f.puesto_trabajo_id ? Number(f.puesto_trabajo_id) : null,
        is_active: !!f.is_active, horas_semana: f.horas_semana || 44,
      };
      // Solo la Dirección asigna puestos adicionales (dan el equipo de ese puesto)
      if (esAdmin) datos.puestos_adicionales_ids = (f.adicionales || []).filter((y) => String(y) !== String(f.puesto_trabajo_id));
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
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={nuevo ? "Nueva persona" : soloVer ? inicial?.nombre : `Editar a ${inicial?.nombre}`} ancho="md:max-w-2xl"
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton type="submit" form="form-persona" cargando={guardando} disabled={soloVer && esMia}>{nuevo ? "Crear cuenta" : "Guardar cambios"}</Boton></>}>
      <form id="form-persona" onSubmit={guardar} className="space-y-4" autoComplete="off">
        {error && <Alerta>{error}</Alerta>}
        {soloVer ? (
          <>
            <dl className="grid gap-x-6 gap-y-3 rounded-lg border border-linea bg-fondo p-4 text-sm sm:grid-cols-2">
              {[["Nombre", `${inicial.first_name || ""} ${inicial.last_name || ""}`.trim() || inicial.nombre], ["Usuario", inicial.username],
                ["Puesto", inicial.puesto || "Sin puesto"], ["Departamento", inicial.departamento || "—"], ["Perfiles", perfilesDe(inicial.roles)]].map(([k, v]) => (
                <div key={k}><dt className="text-xs font-medium text-gris">{k}</dt><dd className="mt-0.5 text-tinta">{v}</dd></div>
              ))}
            </dl>
            <p className="rounded-lg border border-linea bg-niebla/60 p-3 text-sm text-gris">Con tu permiso puedes ver a las personas, crear cuentas nuevas y desactivar o reactivar cuentas. Los correos, las contraseñas y los accesos los cambia quien tiene «Personas y accesos».</p>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!f.is_active} onChange={cambiar("is_active")} className="accent-azul" disabled={esMia} />
              Cuenta activa (si la desactivas no puede entrar y sale del ranking){esMia && <span className="text-gris"> · No puedes desactivar tu propia cuenta</span>}</label>
          </>
        ) : (<>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Nombre">{(id) => <input id={id} className="campo" value={f.first_name || ""} onChange={cambiar("first_name")} autoFocus />}</Campo>
          <Campo etiqueta="Apellidos">{(id) => <input id={id} className="campo" value={f.last_name || ""} onChange={cambiar("last_name")} />}</Campo>
          <Campo etiqueta="Usuario" ayuda="Para entrar. Sin espacios.">{(id) => <input id={id} className="campo" value={f.username || ""} onChange={cambiar("username")} autoCapitalize="none" />}</Campo>
          <Campo etiqueta="Correo (opcional)" ayuda="Si lo pones, también sirve para entrar.">{(id) => <input id={id} type="email" className="campo" value={f.email || ""} onChange={cambiar("email")} />}</Campo>
        </div>
        <Campo etiqueta="Puesto" ayuda="Define su departamento, su supervisor y sus KPIs.">
          {(id) => (
            <select id={id} className="campo" value={f.puesto_trabajo_id || ""} onChange={cambiar("puesto_trabajo_id")}
              disabled={!nuevo && inicial?.id === yo?.id && !esAdmin} title={!nuevo && inicial?.id === yo?.id && !esAdmin ? "Tu propio puesto lo cambia la Dirección" : undefined}>
              <option value="">Sin puesto</option>
              {puestos.map((p) => <option key={p.id} value={p.id}>{p.nombre} ({p.departamento_nombre})</option>)}
            </select>
          )}
        </Campo>
        {esAdmin && (
          <fieldset>
            <legend className="mb-1 text-sm font-medium">Puestos adicionales <span className="font-normal text-gris">(opcional)</span></legend>
            <p className="mb-2 text-sm text-gris">Si además cubre otro puesto (por ejemplo, Gerente de Marketing), recibe el equipo de ese puesto y puede asignarle tareas. Su puesto principal sigue mandando para KPIs y puntaje.</p>
            <div className="max-h-48 space-y-1 overflow-y-auto rounded-lg border border-linea p-2">
              {puestos.filter((p) => String(p.id) !== String(f.puesto_trabajo_id)).map((p) => {
                const si = (f.adicionales || []).includes(p.id);
                return (
                  <label key={p.id} className="flex min-h-9 items-center gap-2 rounded px-2 text-sm hover:bg-linea-suave">
                    <input type="checkbox" className="accent-azul" checked={si}
                      onChange={() => setF({ ...f, adicionales: si ? f.adicionales.filter((x) => x !== p.id) : [...(f.adicionales || []), p.id] })} />
                    {p.nombre} <span className="text-gris">({p.departamento_nombre})</span>
                  </label>
                );
              })}
            </div>
          </fieldset>
        )}
        <p className="rounded-lg border border-linea bg-niebla/60 p-3 text-sm text-gris">
          {nuevo ? "Entra como Colaborador (solo ve y entrega lo suyo). Si su puesto supervisa a otros, recibe el perfil Supervisor."
            : <>Perfiles: <span className="font-medium text-noche">{perfilesDe(inicial?.roles)}</span>.</>}{" "}
          {soloDirectorio ? "Los perfiles y los accesos los cambia quien tiene «Personas y accesos»." : <>Los perfiles, las excepciones y el equipo adicional se cambian en <Link to="/accesos" className="font-medium text-azul hover:underline">Accesos y permisos</Link>.</>}
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
        {!nuevo && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!f.is_active} onChange={cambiar("is_active")} className="accent-azul" disabled={esMia} />Cuenta activa (si la desactivas no puede entrar y sale del ranking)</label>}
        </>)}
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
  const [depto, setDepto] = useState("");
  const [params, setParams] = useSearchParams();
  const [form, setForm] = useState(() => (params.get("nuevo") ? {} : null));
  const [claveNueva, setClaveNueva] = useState(null);
  useEffect(() => { if (params.get("nuevo")) setParams({}, { replace: true }); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const cargar = useCallback(() => { cargarUsuarios().then(setLista).catch((e) => setError(e.message)); }, []);
  useEffect(() => { cargar(); cargarPuestos().then(setPuestos).catch(() => {}); }, [cargar]);

  const filtrada = useMemo(() => (lista || []).filter((u) => {
    if (filtro === "activos" && !u.is_active) return false;
    if (filtro === "inactivos" && u.is_active) return false;
    if (filtro === "sin_puesto" && (u.puesto_id || !u.is_active)) return false;
    if (filtro === "sin_acceso" && (u.last_login || !u.is_active)) return false;
    if (depto && u.departamento !== depto) return false;
    const t = buscar.toLowerCase();
    return !t || [u.nombre, u.username, u.email, u.puesto, u.departamento].some((x) => (x || "").toLowerCase().includes(t));
  }), [lista, filtro, buscar, depto]);
  const deptos = useMemo(() => [...new Set((lista || []).map((u) => u.departamento).filter(Boolean))].sort(), [lista]);

  if (error) return <Alerta>{error}</Alerta>;
  if (!lista) return <Cargando />;
  const sinPuesto = lista.filter((u) => u.is_active && !u.puesto_id).length;
  const conteos = { activos: lista.filter((u) => u.is_active).length, sin_acceso: lista.filter((u) => u.is_active && !u.last_login).length, sin_puesto: sinPuesto, inactivos: lista.filter((u) => !u.is_active).length, todos: lista.length };

  return (
    <div>
      <Cabecera titulo="Personas" descripcion="Cuentas del equipo, su puesto y su rol en la plataforma.">
        <Boton icono={Plus} onClick={() => setForm({})}>Nueva persona</Boton>
      </Cabecera>
      <div className="mb-5 space-y-3">
        <BuscadorPersonas valor={buscar} onCambio={setBuscar} depto={depto} onDepto={setDepto} deptos={deptos} />
        <FiltrosPersonas filtro={filtro} onFiltro={setFiltro} conteos={conteos} />
      </div>
      {sinPuesto > 0 && filtro !== "sin_puesto" && (
        <Alerta tono="amarillo" className="mb-4">{sinPuesto} persona(s) activa(s) sin puesto: no tienen supervisor ni KPIs. <button type="button" className="font-medium underline" onClick={() => setFiltro("sin_puesto")}>Ver quiénes</button></Alerta>
      )}

      <p className="mb-3 text-sm text-gris" aria-live="polite">Mostrando <b className="num text-tinta">{filtrada.length}</b> de <span className="num">{lista.length}</span> personas</p>
      <ListaPersonas personas={filtrada} yo={usuario.id} veSalarios={veSalarios} onEditar={setForm}
        onLimpiar={() => { setBuscar(""); setDepto(""); setFiltro("todos"); }} />

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
