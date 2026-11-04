// Accesos y permisos (mínimo privilegio): el PERFIL dice qué puede hacer cada persona; el ORGANIGRAMA, sobre quién.
// Encima de eso, excepciones por persona (dar o quitar un permiso) y equipo adicional (gestionar a alguien fuera de su rama).
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Minus, Plus, Search, ShieldCheck, Trash2, UserPlus } from "lucide-react";
import {
  accesos as cargarCatalogo, accesosPersonas, borrarEquipoExtra, borrarExcepcion, borrarPerfilAcceso, crearEquipoExtra,
  crearExcepcion, crearPerfilAcceso, guardarPerfilAcceso, perfilesDePersona, reiniciarDosPasos,
} from "@/lib/api";
import { fechaCorta } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import { Alerta, Avatar, Boton, Cabecera, Campo, Cargando, Insignia, Modal, Panel, Pestanas, Vacio, cx, useAviso, useConfirmar } from "@/components/ui";

// «Administrador» es el nombre histórico del grupo de Dirección
const nombrePerfil = (n) => (n === "Administrador" ? "Administrador (Dirección)" : n);

function ListaPermisos({ catalogo, marcados, onCambio, deshabilitado }) {
  const grupos = useMemo(() => {
    const g = {};
    catalogo.permisos.forEach((p) => { (g[p.grupo] ||= []).push(p); });
    return Object.entries(g);
  }, [catalogo]);
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {grupos.map(([grupo, lista]) => (
        <fieldset key={grupo} className="space-y-1.5">
          <legend className="etiqueta">{grupo === "Su equipo" ? "Sobre su equipo (según el organigrama)" : "Sobre toda la empresa"}</legend>
          {lista.map((p) => {
            const si = marcados.has(p.codigo);
            return (
              <label key={p.codigo} className={cx("flex items-start gap-2.5 rounded-lg border p-2.5 text-[15px]", si ? "border-azul/40 bg-azul/5" : "border-linea", deshabilitado ? "cursor-default" : "cursor-pointer")}>
                <input type="checkbox" className="mt-1 accent-azul" checked={si} disabled={deshabilitado}
                  onChange={() => { const n = new Set(marcados); if (si) n.delete(p.codigo); else n.add(p.codigo); onCambio(n); }} />
                <span><span className="font-medium">{p.nombre}</span><span className="block text-sm text-gris">{p.descripcion}</span></span>
              </label>
            );
          })}
        </fieldset>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- Perfiles
function Perfil({ perfil, catalogo, edita, onGuardado, onBorrado }) {
  const [marcados, setMarcados] = useState(() => new Set(perfil.permisos));
  const [abierto, setAbierto] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const avisar = useAviso();
  const confirmar = useConfirmar();
  useEffect(() => { setMarcados(new Set(perfil.permisos)); }, [perfil]);
  const cambiado = marcados.size !== perfil.permisos.length || perfil.permisos.some((p) => !marcados.has(p));
  const nombres = Object.fromEntries(catalogo.permisos.map((p) => [p.codigo, p.nombre]));

  const guardar = async () => {
    setError("");
    if (perfil.personas > 0 && !(await confirmar({ titulo: `¿Cambiar ${nombrePerfil(perfil.nombre)}?`, boton: "Guardar",
      mensaje: `Cambia lo que pueden hacer las ${perfil.personas} persona(s) con este perfil desde ahora mismo. Queda en la auditoría.` }))) return;
    setGuardando(true);
    try { onGuardado(await guardarPerfilAcceso(perfil.id, { permisos: [...marcados] })); avisar("Perfil guardado"); } catch (e) { setError(e.message); }
    setGuardando(false);
  };
  const borrar = async () => {
    if (!(await confirmar({ titulo: `¿Borrar ${perfil.nombre}?`, mensaje: "No tiene personas asignadas.", boton: "Borrar", peligro: true }))) return;
    try { await borrarPerfilAcceso(perfil.id); onBorrado(perfil.id); } catch (e) { setError(e.message); }
  };

  return (
    <Panel className="overflow-hidden" cuerpo="p-0">
      <button type="button" className="flex w-full items-start gap-3 p-4 text-left hover:bg-niebla/60" onClick={() => setAbierto(!abierto)} aria-expanded={abierto}>
        <ShieldCheck className={cx("mt-0.5 size-5 shrink-0", perfil.permisos.length ? "text-azul" : "text-gris")} />
        <div className="min-w-0 flex-1">
          <p className="font-display font-semibold">{nombrePerfil(perfil.nombre)} <span className="ml-1 text-sm font-normal text-gris">{perfil.personas} persona(s)</span></p>
          <p className="text-sm text-gris">{perfil.descripcion}</p>
          <div className="mt-2 flex flex-wrap gap-1">
            {perfil.permisos.length ? perfil.permisos.map((c) => <Insignia key={c} tono="azul">{nombres[c] || c}</Insignia>)
              : <Insignia>Solo lo suyo</Insignia>}
          </div>
        </div>
        <span className="text-sm text-azul">{abierto ? "Cerrar" : edita ? "Ajustar" : "Ver"}</span>
      </button>
      {abierto && (
        <div className="space-y-3 border-t border-linea-suave p-4">
          {error && <Alerta>{error}</Alerta>}
          <ListaPermisos catalogo={catalogo} marcados={marcados} onCambio={setMarcados} deshabilitado={!edita} />
          {edita && (
            <div className="flex flex-wrap items-center gap-2">
              <Boton onClick={guardar} cargando={guardando} disabled={!cambiado}>Guardar permisos</Boton>
              {cambiado && <Boton variante="secundario" onClick={() => setMarcados(new Set(perfil.permisos))}>Deshacer</Boton>}
              {!perfil.de_la_plataforma && <Boton variante="fantasma" icono={Trash2} className="ml-auto text-rojo" onClick={borrar}>Borrar perfil</Boton>}
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}

function NuevoPerfil({ abierto, catalogo, onCerrar, onCreado }) {
  const [f, setF] = useState({ nombre: "", descripcion: "" });
  const [marcados, setMarcados] = useState(new Set());
  const [error, setError] = useState("");
  useEffect(() => { if (abierto) { setF({ nombre: "", descripcion: "" }); setMarcados(new Set()); setError(""); } }, [abierto]);
  const crear = async (e) => {
    e.preventDefault();
    try { onCreado(await crearPerfilAcceso({ ...f, permisos: [...marcados] })); } catch (err) { setError(err.message); }
  };
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo="Nuevo perfil" ancho="md:max-w-3xl"
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton type="submit" form="form-perfil">Crear perfil</Boton></>}>
      <form id="form-perfil" onSubmit={crear} className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Nombre">{(id) => <input id={id} className="campo" value={f.nombre} onChange={(e) => setF({ ...f, nombre: e.target.value })} placeholder="Coordinador de proyecto" />}</Campo>
          <Campo etiqueta="Para qué es">{(id) => <input id={id} className="campo" value={f.descripcion} onChange={(e) => setF({ ...f, descripcion: e.target.value })} />}</Campo>
        </div>
        <p className="text-sm text-gris">Marca solo lo necesario. Los permisos «sobre su equipo» se aplican a quienes dependen de su puesto en el organigrama, más su equipo adicional.</p>
        <ListaPermisos catalogo={catalogo} marcados={marcados} onCambio={setMarcados} />
      </form>
    </Modal>
  );
}

function Perfiles({ catalogo, setCatalogo }) {
  const [nuevo, setNuevo] = useState(false);
  const cambiar = (p) => setCatalogo({ ...catalogo, perfiles: catalogo.perfiles.map((x) => (x.id === p.id ? p : x)) });
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <p className="flex-1 text-sm text-gris">{catalogo.edita_perfiles ? "Ajusta qué puede hacer cada perfil. Los cambios aplican de inmediato y quedan en la auditoría."
          : "Solo la Dirección ajusta los perfiles. Aquí puedes ver qué permite cada uno."}</p>
        {catalogo.edita_perfiles && <Boton icono={Plus} onClick={() => setNuevo(true)}>Nuevo perfil</Boton>}
      </div>
      {catalogo.perfiles.map((p) => (
        <Perfil key={p.id} perfil={p} catalogo={catalogo} edita={catalogo.edita_perfiles} onGuardado={cambiar}
          onBorrado={(id) => setCatalogo({ ...catalogo, perfiles: catalogo.perfiles.filter((x) => x.id !== id) })} />
      ))}
      <NuevoPerfil abierto={nuevo} catalogo={catalogo} onCerrar={() => setNuevo(false)}
        onCreado={(p) => { setNuevo(false); setCatalogo({ ...catalogo, perfiles: [p, ...catalogo.perfiles] }); }} />
    </div>
  );
}

// ---------------------------------------------------------------- Personas
function AccesosDePersona({ persona, catalogo, personas, onCerrar, onCambio }) {
  const { usuario } = useSesion();
  const [perfiles, setPerfiles] = useState(new Set());
  const [exc, setExc] = useState({ permiso: "", conceder: true, motivo: "" });
  const [extra, setExtra] = useState({ colaborador: "", hasta: "", motivo: "" });
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const avisar = useAviso();
  useEffect(() => { if (persona) { setPerfiles(new Set(persona.perfiles)); setError(""); setExc({ permiso: "", conceder: true, motivo: "" }); setExtra({ colaborador: "", hasta: "", motivo: "" }); } }, [persona]);
  if (!persona) return null;
  const propio = persona.id === usuario?.id;
  const nombres = Object.fromEntries(catalogo.permisos.map((p) => [p.codigo, p.nombre]));
  const cambiado = perfiles.size !== persona.perfiles.length || persona.perfiles.some((p) => !perfiles.has(p));
  const intentar = async (fn, ok) => {
    setError("");
    try { await fn(); onCambio(); if (ok) avisar(ok); } catch (e) { setError(e.message); }
  };
  const guardarPerfiles = async () => {
    setGuardando(true);
    await intentar(() => perfilesDePersona(persona.id, [...perfiles]), "Perfiles guardados");
    setGuardando(false);
  };
  const enEquipo = new Set(persona.equipo_extra.map((x) => x.colaborador));

  return (
    <Modal abierto={!!persona} onCerrar={onCerrar} titulo={`Accesos de ${persona.nombre}`} ancho="md:max-w-3xl"
      descripcion={[persona.puesto || "Sin puesto", persona.departamento, persona.jefe && `reporta a ${persona.jefe}`].filter(Boolean).join(" · ")}>
      <div className="space-y-6">
        {error && <Alerta>{error}</Alerta>}
        {propio && <Alerta tono="amarillo">Son tus propios accesos: los cambia otra persona con el permiso «Personas y accesos».</Alerta>}

        <section className="space-y-2">
          <h3 className="font-display font-semibold">Perfiles</h3>
          <div className="grid gap-2 sm:grid-cols-2">
            {catalogo.perfiles.map((p) => {
              const si = perfiles.has(p.nombre);
              return (
                <label key={p.id} className={cx("flex items-start gap-2.5 rounded-lg border p-2.5", si ? "border-azul/40 bg-azul/5" : "border-linea", propio ? "" : "cursor-pointer")}>
                  <input type="checkbox" className="mt-1 accent-azul" checked={si} disabled={propio}
                    onChange={() => { const n = new Set(perfiles); if (si) n.delete(p.nombre); else n.add(p.nombre); setPerfiles(n); }} />
                  <span><span className="font-medium">{nombrePerfil(p.nombre)}</span><span className="block text-sm text-gris">{p.descripcion}</span></span>
                </label>
              );
            })}
          </div>
          {!propio && <Boton onClick={guardarPerfiles} cargando={guardando} disabled={!cambiado || !perfiles.size}>Guardar perfiles</Boton>}
        </section>

        <section className="flex flex-wrap items-center gap-2">
          <h3 className="mr-auto font-display font-semibold">Verificación en dos pasos</h3>
          {persona.dos_pasos ? <Insignia tono="verde">Activa</Insignia> : <Insignia>Inactiva</Insignia>}
          {persona.dos_pasos && !propio && (
            <Boton tam="sm" variante="secundario" onClick={() => intentar(() => reiniciarDosPasos(persona.id), "Verificación reiniciada: la vuelve a activar al entrar")}>
              Reiniciar (perdió el celular)
            </Boton>
          )}
        </section>

        <section className="space-y-2">
          <h3 className="font-display font-semibold">Lo que puede hacer hoy</h3>
          <div className="flex flex-wrap gap-1">
            {persona.permisos.length ? persona.permisos.map((c) => <Insignia key={c} tono="azul">{nombres[c] || c}</Insignia>) : <Insignia>Solo lo suyo: ver y entregar sus tareas, su asistencia, su actividad y su ficha</Insignia>}
          </div>
        </section>

        <section className="space-y-2">
          <h3 className="font-display font-semibold">Excepciones</h3>
          <p className="text-sm text-gris">Para un caso puntual: dale o quítale un permiso sin cambiar su perfil. Siempre con motivo.</p>
          {persona.excepciones.length > 0 && (
            <ul className="divide-y divide-linea-suave rounded-lg border border-linea">
              {persona.excepciones.map((e) => (
                <li key={e.id} className="flex items-center gap-3 px-3 py-2">
                  <Insignia tono={e.conceder ? "verde" : "rojo"}>{e.conceder ? <Plus className="size-3" /> : <Minus className="size-3" />}{e.conceder ? "Se le da" : "Se le quita"}</Insignia>
                  <span className="min-w-0 flex-1"><span className="font-medium">{nombres[e.permiso] || e.permiso}</span><span className="block truncate text-sm text-gris">{e.motivo}</span></span>
                  {!propio && <Boton tam="sm" variante="fantasma" icono={Trash2} aria-label="Quitar excepción" className="text-rojo" onClick={() => intentar(() => borrarExcepcion(e.id), "Excepción quitada")} />}
                </li>
              ))}
            </ul>
          )}
          {!propio && (
            <form className="grid gap-2 sm:grid-cols-[1fr_auto_1fr_auto]" onSubmit={(ev) => { ev.preventDefault(); intentar(() => crearExcepcion({ usuario: persona.id, ...exc }), "Excepción guardada"); }}>
              <select className="campo" aria-label="Permiso" value={exc.permiso} onChange={(e) => setExc({ ...exc, permiso: e.target.value })}>
                <option value="">Permiso…</option>
                {catalogo.permisos.map((p) => <option key={p.codigo} value={p.codigo}>{p.nombre}</option>)}
              </select>
              <select className="campo" aria-label="Dar o quitar" value={exc.conceder ? "1" : "0"} onChange={(e) => setExc({ ...exc, conceder: e.target.value === "1" })}>
                <option value="1">Dar</option><option value="0">Quitar</option>
              </select>
              <input className="campo" placeholder="Motivo" aria-label="Motivo" value={exc.motivo} onChange={(e) => setExc({ ...exc, motivo: e.target.value })} />
              <Boton type="submit" variante="secundario" disabled={!exc.permiso || !exc.motivo.trim()}>Agregar</Boton>
            </form>
          )}
        </section>

        <section className="space-y-2">
          <h3 className="font-display font-semibold">Equipo adicional</h3>
          <p className="text-sm text-gris">Personas que gestiona aunque no dependan de su puesto (un proyecto, una suplencia). Sus permisos «sobre su equipo» también aplican a ellas.</p>
          {persona.equipo_extra.length > 0 && (
            <ul className="divide-y divide-linea-suave rounded-lg border border-linea">
              {persona.equipo_extra.map((x) => (
                <li key={x.id} className="flex items-center gap-3 px-3 py-2">
                  <Avatar nombre={x.nombre} tam="sm" />
                  <span className="min-w-0 flex-1"><span className="font-medium">{x.nombre}</span>
                    <span className="block truncate text-sm text-gris">{[x.motivo, x.hasta ? `hasta el ${fechaCorta(x.hasta)}` : "sin fecha de fin"].filter(Boolean).join(" · ")}</span></span>
                  {!propio && <Boton tam="sm" variante="fantasma" icono={Trash2} aria-label={`Quitar a ${x.nombre}`} className="text-rojo" onClick={() => intentar(() => borrarEquipoExtra(x.id), "Quitado del equipo")} />}
                </li>
              ))}
            </ul>
          )}
          {!propio && (
            <form className="grid gap-2 sm:grid-cols-[1fr_auto_1fr_auto]" onSubmit={(ev) => { ev.preventDefault(); intentar(() => crearEquipoExtra({ jefe: persona.id, ...extra, hasta: extra.hasta || null }), "Agregado al equipo"); }}>
              <select className="campo" aria-label="Persona" value={extra.colaborador} onChange={(e) => setExtra({ ...extra, colaborador: e.target.value })}>
                <option value="">Persona…</option>
                {personas.filter((p) => p.id !== persona.id && !enEquipo.has(p.id)).map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
              </select>
              <input type="date" className="campo" aria-label="Hasta" title="Hasta (vacío: sin fecha de fin)" value={extra.hasta} onChange={(e) => setExtra({ ...extra, hasta: e.target.value })} />
              <input className="campo" placeholder="Motivo" aria-label="Motivo del equipo adicional" value={extra.motivo} onChange={(e) => setExtra({ ...extra, motivo: e.target.value })} />
              <Boton type="submit" variante="secundario" icono={UserPlus} disabled={!extra.colaborador}>Agregar</Boton>
            </form>
          )}
        </section>
      </div>
    </Modal>
  );
}

function Personas({ catalogo, personas, recargar }) {
  const [texto, setTexto] = useState("");
  const [perfil, setPerfil] = useState("");
  const [abierta, setAbierta] = useState(null);
  const lista = personas.filter((p) => (!perfil || p.perfiles.includes(perfil))
    && (!texto || `${p.nombre} ${p.usuario} ${p.puesto || ""} ${p.departamento || ""}`.toLowerCase().includes(texto.toLowerCase())));
  const actual = abierta ? personas.find((p) => p.id === abierta) : null;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <label className="relative min-w-56 flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-gris" />
          <input className="campo pl-9" placeholder="Buscar persona, puesto o departamento" value={texto} onChange={(e) => setTexto(e.target.value)} aria-label="Buscar" />
        </label>
        <select className="campo w-auto" value={perfil} onChange={(e) => setPerfil(e.target.value)} aria-label="Filtrar por perfil">
          <option value="">Todos los perfiles</option>
          {catalogo.perfiles.map((p) => <option key={p.id} value={p.nombre}>{nombrePerfil(p.nombre)}</option>)}
        </select>
      </div>
      <Panel cuerpo="p-0">
        {lista.length === 0 ? <Vacio titulo="Nadie coincide con la búsqueda" /> : (
          <ul className="divide-y divide-linea-suave">
            {lista.map((p) => (
              <li key={p.id}>
                <button type="button" className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-niebla/60" onClick={() => setAbierta(p.id)}>
                  <Avatar nombre={p.nombre} tam="sm" />
                  <span className="min-w-0 flex-1">
                    <span className="block font-medium">{p.nombre}</span>
                    <span className="block truncate text-sm text-gris">{[p.puesto || "Sin puesto", p.jefe && `reporta a ${p.jefe}`].filter(Boolean).join(" · ")}</span>
                    <span className="block truncate text-xs font-medium text-azul sm:hidden">{p.perfiles.map(nombrePerfil).join(" · ")}</span>
                  </span>
                  <span className="hidden flex-wrap justify-end gap-1 sm:flex">
                    {p.perfiles.map((n) => <Insignia key={n} tono={n === "Administrador" ? "noche" : n === "Colaborador" ? "neutro" : "azul"}>{nombrePerfil(n)}</Insignia>)}
                    {p.excepciones.length > 0 && <Insignia tono="amarillo">{p.excepciones.length} excepción(es)</Insignia>}
                    {p.equipo_extra.length > 0 && <Insignia tono="verde">+{p.equipo_extra.length} en su equipo</Insignia>}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Panel>
      <AccesosDePersona persona={actual} catalogo={catalogo} personas={personas} onCerrar={() => setAbierta(null)} onCambio={recargar} />
    </div>
  );
}

export default function Accesos() {
  const [params, setParams] = useSearchParams();
  const ver = params.get("ver") === "perfiles" ? "perfiles" : "personas";
  const [catalogo, setCatalogo] = useState(null);
  const [personas, setPersonas] = useState([]);
  const [error, setError] = useState("");
  const recargar = useCallback(() => Promise.all([cargarCatalogo(), accesosPersonas()])
    .then(([c, p]) => { setCatalogo(c); setPersonas(p); }).catch((e) => setError(e.message)), []);
  useEffect(() => { recargar(); }, [recargar]);
  return (
    <div className="space-y-5">
      <Cabecera titulo="Accesos y permisos"
        descripcion="Mínimo privilegio: el perfil dice qué puede hacer cada persona y el organigrama, sobre quién. Nadie valida su propio trabajo ni cambia sus propios accesos." />
      {error && <Alerta>{error}</Alerta>}
      {!catalogo ? !error && <Cargando /> : <>
        <Pestanas opciones={[{ valor: "personas", etiqueta: "Personas" }, { valor: "perfiles", etiqueta: "Perfiles" }]} valor={ver} onCambio={(v) => setParams({ ver: v })} />
        {ver === "perfiles" ? <Perfiles catalogo={catalogo} setCatalogo={setCatalogo} /> : <Personas catalogo={catalogo} personas={personas} recargar={recargar} />}
      </>}
    </div>
  );
}
