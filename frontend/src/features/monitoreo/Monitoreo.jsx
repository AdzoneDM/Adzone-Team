// Monitoreo de actividad: en vivo del equipo, el día de cada persona, mis equipos, reglas y configuración.
import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Copy, Laptop, MonitorSmartphone, Plus, RefreshCw, ShieldCheck, Trash2 } from "lucide-react";
import {
  aceptarPolitica, borrarReglaProductividad as borrarRegla, configMonitoreo, departamentos as cargarDeptos, dispositivos, guardarConfigMonitoreo, guardarReglaProductividad as guardarRegla,
  monitoreoDia, monitoreoEquipo, politicaMonitoreo, quitarDispositivo, reclasificar, reglasProductividad, urlCaptura, usuarios as cargarUsuarios,
  vincularDispositivo,
} from "@/lib/api";
import { hace, hoyISO, reloj } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import { Alerta, Boton, Cabecera, Campo, Cargando, Insignia, Modal, Panel, Pestanas, Puntaje, Vacio, cx, useAviso, useConfirmar } from "@/components/ui";

const CAT = { P: ["Productiva", "verde", "bg-verde"], N: ["Neutral", "neutro", "bg-[#9aa7bd]"], I: ["Improductiva", "rojo", "bg-rojo"] };
const pct = (v) => (v == null ? "—" : `${Number(v).toLocaleString("es-DO", { maximumFractionDigits: 1 })} %`);
const hora = (iso) => (iso ? new Date(iso).toLocaleTimeString("es-DO", { hour: "numeric", minute: "2-digit" }) : "—");

function Dato({ titulo, valor, detalle, tono }) {
  return (
    <div className="rounded-xl border border-linea bg-white p-4">
      <p className="text-sm text-gris">{titulo}</p>
      <p className={cx("mt-1 font-display text-2xl font-semibold num", tono)}>{valor}</p>
      {detalle && <p className="mt-0.5 text-xs text-gris">{detalle}</p>}
    </div>
  );
}

function Linea({ bloques }) {
  if (!bloques.length) return null;
  return (
    <div>
      <div className="flex h-28 items-end gap-px overflow-x-auto pb-1" role="img" aria-label="Actividad del día en bloques de 10 minutos">
        {bloques.map((b) => {
          const total = 10;
          const seg = (n, clase) => n ? <div className={clase} style={{ height: `${(n / total) * 100}%` }} /> : null;
          return (
            <div key={b.hora} className="flex h-full min-w-[6px] flex-1 flex-col justify-end" title={`${b.hora} · ${b.productivos} productivo · ${b.neutrales} neutral · ${b.improductivos} improductivo · ${b.inactivos} inactivo (min)`}>
              {seg(b.inactivos, "bg-linea")}
              {seg(b.improductivos, "bg-rojo")}
              {seg(b.neutrales, "bg-[#9aa7bd]")}
              {seg(b.productivos, "bg-verde")}
            </div>
          );
        })}
      </div>
      <div className="flex justify-between text-xs text-gris num"><span>{bloques[0].hora}</span><span>{bloques[Math.floor(bloques.length / 2)].hora}</span><span>{bloques[bloques.length - 1].hora}</span></div>
      <div className="mt-2 flex flex-wrap gap-3 text-xs text-gris">
        {[["bg-verde", "Productivo"], ["bg-[#9aa7bd]", "Neutral"], ["bg-rojo", "Improductivo"], ["bg-linea", "Inactivo"]].map(([c, t]) => <span key={t} className="flex items-center gap-1.5"><span className={cx("size-2.5 rounded-sm", c)} />{t}</span>)}
      </div>
    </div>
  );
}

function ListaUso({ titulo, filas }) {
  const max = Math.max(1, ...filas.map((f) => f.minutos));
  return (
    <Panel titulo={titulo} cuerpo="p-0">
      {filas.length === 0 ? <p className="p-5 text-sm text-gris">Sin datos.</p> : (
        <ul className="divide-y divide-linea-suave">
          {filas.map((f) => (
            <li key={f.nombre} className="px-5 py-2.5">
              <div className="flex items-center gap-3"><span className="min-w-0 flex-1 truncate text-[15px]" title={f.nombre}>{f.nombre}</span>
                <Insignia tono={CAT[f.categoria][1]}>{CAT[f.categoria][0]}</Insignia><span className="w-16 text-right text-sm num">{reloj(f.minutos)}</span></div>
              <div className="mt-1.5 h-1.5 rounded-full bg-linea-suave"><div className={cx("h-full rounded-full", CAT[f.categoria][2])} style={{ width: `${(f.minutos / max) * 100}%` }} /></div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

/** El día de una persona (o el mío). */
export function DiaPersona({ usuario }) {
  const [fecha, setFecha] = useState(hoyISO());
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [foto, setFoto] = useState(null);
  useEffect(() => { setD(null); setError(""); monitoreoDia({ usuario, fecha }).then(setD).catch((e) => setError(e.message)); }, [usuario, fecha]);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {d && <p className="text-gris">{d.persona.nombre}{d.persona.puesto ? ` · ${d.persona.puesto}` : ""}</p>}
        <input type="date" aria-label="Día" className="campo h-11 w-44" value={fecha} max={hoyISO()} onChange={(e) => setFecha(e.target.value)} />
      </div>
      {error ? <Alerta>{error}</Alerta> : !d ? <Cargando /> : (
        <>
          {!d.consentimiento && <Alerta tono="amarillo">{usuario ? "Esta persona" : "Tú"} todavía no {usuario ? "ha aceptado" : "has aceptado"} la política de monitoreo: su computadora no envía actividad.</Alerta>}
          {d.consentimiento && !d.equipos.length && <Alerta tono="azul">No hay computadora vinculada. Se vincula en «Mis equipos».</Alerta>}
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
            <Dato titulo="En jornada" valor={reloj(d.jornada.trabajados)} detalle={`Entró ${hora(d.jornada.entrada)}${d.jornada.llegada === "TARDE" ? ` · ${d.jornada.tardanza} min tarde` : ""}`} />
            <Dato titulo="Registrado en PC" valor={reloj(d.minutos_registrados)} detalle={d.cobertura != null ? `${pct(d.cobertura)} de la jornada` : "—"} />
            <Dato titulo="Tiempo activo" valor={pct(d.actividad)} detalle={`${reloj(d.minutos_activos)} activo · ${reloj(d.minutos_inactivos)} inactivo`} tono={d.actividad != null && d.actividad < 60 ? "text-rojo" : ""} />
            <Dato titulo="Productivo" valor={<Puntaje valor={d.productividad} />} detalle={`${reloj(d.minutos_productivos)} productivo · ${reloj(d.minutos_improductivos)} improductivo`} />
            <Dato titulo="Tiempo de foco" valor={reloj(d.minutos_foco)} detalle={`${d.sesiones_foco} bloque(s) de 25+ min`} />
            <Dato titulo="Nivel de actividad" valor={pct(d.intensidad)} detalle="Teclado o ratón por minuto" />
            <Dato titulo="Cambios de ventana" valor={d.cambios_por_hora ?? "—"} detalle="por hora" tono={d.cambios_por_hora > 60 ? "text-[#a86a00]" : ""} />
          </div>
          <Panel titulo="Línea de tiempo">{d.linea.length ? <Linea bloques={d.linea} /> : <Vacio icono={MonitorSmartphone} titulo="Sin actividad registrada este día">Solo se registra en jornada, con la computadora vinculada.</Vacio>}</Panel>
          <div className="grid gap-4 lg:grid-cols-2">
            <ListaUso titulo="Aplicaciones" filas={d.apps} />
            <ListaUso titulo="Sitios web" filas={d.sitios} />
          </div>
          {d.capturas.length > 0 && (
            <Panel titulo={`Capturas (${d.capturas.length})`}>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                {d.capturas.map((c) => (
                  <button key={c.id} type="button" onClick={() => setFoto(c)} className="overflow-hidden rounded-lg border border-linea text-left hover:border-azul">
                    <img src={urlCaptura(c.id)} alt={`Captura de las ${c.hora}`} loading="lazy" className="aspect-video w-full object-cover" />
                    <span className="block px-2 py-1 text-xs text-gris">{c.hora} · {c.app || "—"}</span>
                  </button>
                ))}
              </div>
            </Panel>
          )}
          <Modal abierto={!!foto} onCerrar={() => setFoto(null)} titulo={foto ? `Captura de las ${foto.hora}` : ""} ancho="md:max-w-5xl">
            {foto && <img src={urlCaptura(foto.id)} alt="" className="w-full rounded-lg" />}
          </Modal>
        </>
      )}
    </div>
  );
}

function EnVivo({ onVer }) {
  const [fecha, setFecha] = useState(hoyISO());
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const cargar = () => monitoreoEquipo(fecha).then(setD).catch((e) => setError(e.message));
    setD(null);
    cargar();
    const t = fecha === hoyISO() ? setInterval(cargar, 60000) : null;
    return () => t && clearInterval(t);
  }, [fecha]);
  if (error) return <Alerta>{error}</Alerta>;
  const personas = d?.personas || [];
  const conDatos = personas.filter((p) => p.minutos_registrados);
  const promedio = (k) => (conDatos.length ? conDatos.reduce((s, p) => s + (p[k] || 0), 0) / conDatos.length : null);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-gris">{fecha === hoyISO() ? "Se actualiza cada minuto." : ""}</p>
        <input type="date" aria-label="Día" className="campo h-11 w-44" value={fecha} max={hoyISO()} onChange={(e) => setFecha(e.target.value)} />
      </div>
      {!d ? <Cargando /> : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Dato titulo="Activos ahora" valor={personas.filter((p) => p.ahora?.en_vivo && p.ahora.activo).length} detalle={`de ${personas.filter((p) => p.jornada === "TRABAJANDO").length} en jornada`} />
            <Dato titulo="Productividad del equipo" valor={<Puntaje valor={promedio("productividad")} />} detalle="Promedio de quien tiene datos" />
            <Dato titulo="Tiempo activo" valor={pct(promedio("actividad"))} />
            <Dato titulo="Sin computadora vinculada" valor={personas.filter((p) => !p.tiene_equipo).length} detalle={`${personas.filter((p) => !p.consentimiento).length} sin aceptar la política`} />
          </div>
          <Panel cuerpo="p-0">
            <div className="overflow-x-auto">
              <table className="tabla">
                <thead><tr><th>Persona</th><th>Ahora</th><th className="text-right">Jornada</th><th className="text-right">Activo</th><th className="text-right">Productivo</th><th className="text-right">Foco</th><th className="text-right">Nivel</th><th className="text-right">Cambios/h</th></tr></thead>
                <tbody>
                  {personas.map((p) => (
                    <tr key={p.id} className="cursor-pointer hover:bg-fondo" onClick={() => onVer(p.id)}>
                      <td><p className="font-medium">{p.nombre}</p><p className="text-xs text-gris">{p.puesto || "Sin puesto"}</p></td>
                      <td className="max-w-56">{p.ahora ? (
                        <span className="flex items-center gap-1.5 text-sm"><span className={cx("size-2 shrink-0 rounded-full", p.ahora.en_vivo ? (p.ahora.activo ? "bg-verde" : "bg-amarillo-600") : "bg-gris")} />
                          <span className="truncate">{p.ahora.en_vivo ? (p.ahora.activo ? p.ahora.app || "Activo" : "Inactivo") : `Visto ${hace(p.ahora.minuto)}`}</span></span>
                      ) : <span className="text-sm text-gris">{!p.tiene_equipo ? "Sin computadora" : !p.consentimiento ? "Sin aceptar política" : p.jornada === "TRABAJANDO" ? "Sin datos" : "Fuera de jornada"}</span>}</td>
                      <td className="text-right num">{p.trabajados ? reloj(p.trabajados) : "—"}</td>
                      <td className={cx("text-right num", p.actividad != null && p.actividad < 60 && "text-rojo")}>{pct(p.actividad)}</td>
                      <td className="text-right"><Puntaje valor={p.productividad} /></td>
                      <td className="text-right num">{p.minutos_foco ? reloj(p.minutos_foco) : "—"}</td>
                      <td className="text-right num">{pct(p.intensidad)}</td>
                      <td className="text-right num">{p.cambios_por_hora ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </>
      )}
    </div>
  );
}

function MisEquipos() {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const { esAdmin } = useSesion();
  const [politica, setPolitica] = useState(null);
  const [lista, setLista] = useState(null);
  const [personas, setPersonas] = useState([]);
  const [nuevo, setNuevo] = useState(null);
  const [token, setToken] = useState(null);
  const cargar = useCallback(() => {
    politicaMonitoreo().then(setPolitica).catch(() => {});
    dispositivos().then(setLista).catch(() => setLista([]));
  }, []);
  useEffect(() => { cargar(); if (esAdmin) cargarUsuarios().then(setPersonas).catch(() => {}); }, [cargar, esAdmin]);
  if (!politica || !lista) return <Cargando />;
  return (
    <div className="space-y-5">
      <Panel titulo={`Política de monitoreo · versión ${politica.version}`}>
        <pre className="whitespace-pre-wrap font-sans text-[15px] leading-relaxed">{politica.texto}</pre>
        <div className="mt-4">
          {politica.aceptada ? <p className="flex items-center gap-2 text-verde"><ShieldCheck className="size-5" />La aceptaste el {new Date(politica.aceptada_en).toLocaleDateString("es-DO")}.</p>
            : <Boton icono={ShieldCheck} onClick={async () => { await aceptarPolitica(); avisar("Política aceptada."); cargar(); }}>Leí y acepto la política</Boton>}
        </div>
      </Panel>
      <Panel titulo={esAdmin ? "Computadoras vinculadas" : "Mis computadoras"} accion={<Boton tam="sm" icono={Plus} onClick={() => setNuevo({ nombre: "", usuario: "" })}>Vincular computadora</Boton>} cuerpo="p-0">
        {lista.length === 0 ? <p className="p-5 text-sm text-gris">Ninguna todavía. Vincula la computadora donde trabajas y abre en ella el agente de Adzone Team.</p> : (
          <ul className="divide-y divide-linea-suave">
            {lista.map((d) => (
              <li key={d.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
                <Laptop className="size-5 text-gris" />
                <div className="min-w-0 flex-1"><p className="font-medium">{d.nombre}{esAdmin && <span className="font-normal text-gris"> · {d.persona}</span>}</p>
                  <p className="text-sm text-gris">{d.ultimo_contacto ? `Último contacto ${hace(d.ultimo_contacto)}` : "Nunca se ha conectado"}{d.sistema ? ` · ${d.sistema}` : ""}{d.version_agente ? ` · agente ${d.version_agente}` : ""} · código adz_{d.prefijo}…</p></div>
                {!d.activo && <Insignia>Desactivada</Insignia>}
                <Boton tam="sm" variante="fantasma" icono={Trash2} className="text-rojo" aria-label={`Desvincular ${d.nombre}`} onClick={async () => {
                  if (await confirmar({ titulo: `¿Desvincular «${d.nombre}»?`, mensaje: "El agente de esa computadora deja de enviar datos. Lo ya registrado se conserva.", boton: "Desvincular", peligro: true })) {
                    try { await quitarDispositivo(d.id); cargar(); } catch (e) { avisar(e.message, "rojo"); }
                  }
                }} />
              </li>
            ))}
          </ul>
        )}
      </Panel>
      <Modal abierto={!!nuevo} onCerrar={() => setNuevo(null)} titulo="Vincular computadora"
        pie={<><Boton variante="secundario" onClick={() => setNuevo(null)}>Cancelar</Boton><Boton onClick={async () => {
          try { const r = await vincularDispositivo({ nombre: nuevo.nombre || "Computadora", ...(nuevo.usuario ? { usuario: Number(nuevo.usuario) } : {}) }); setNuevo(null); setToken(r.token); cargar(); } catch (e) { avisar(e.message, "rojo"); }
        }}>Vincular</Boton></>}>
        {nuevo && (
          <div className="space-y-4">
            <Campo etiqueta="Nombre de la computadora">{(id) => <input id={id} className="campo" placeholder="PC Diseño 2" value={nuevo.nombre} onChange={(e) => setNuevo({ ...nuevo, nombre: e.target.value })} autoFocus />}</Campo>
            {esAdmin && <Campo etiqueta="De quién es" ayuda="Vacío: tuya.">{(id) => <select id={id} className="campo" value={nuevo.usuario} onChange={(e) => setNuevo({ ...nuevo, usuario: e.target.value })}>
              <option value="">Mía</option>{personas.filter((p) => p.is_active).map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}</select>}</Campo>}
          </div>
        )}
      </Modal>
      <Modal abierto={!!token} onCerrar={() => setToken(null)} titulo="Código del equipo" descripcion="Cópialo ahora: no se vuelve a mostrar."
        pie={<Boton onClick={() => setToken(null)}>Listo</Boton>}>
        {token && (
          <div className="space-y-4">
            <div className="flex gap-2"><input readOnly aria-label="Código del equipo" className="campo font-mono text-sm" value={token} onFocus={(e) => e.target.select()} />
              <Boton variante="secundario" icono={Copy} onClick={() => navigator.clipboard?.writeText(token).then(() => avisar("Copiado."))}>Copiar</Boton></div>
            <ol className="list-decimal space-y-1.5 pl-5 text-[15px]">
              <li>En esa computadora abre <strong>AdzoneAgente.exe</strong> (lo instala Tecnología).</li>
              <li>Pega la dirección de Adzone Team (<span className="font-mono text-sm">{window.location.origin}</span>) y este código.</li>
              <li>Listo: el ícono queda en la barra de tareas; verde = midiendo, amarillo = fuera de jornada o en pausa.</li>
            </ol>
          </div>
        )}
      </Modal>
    </div>
  );
}

function Reglas() {
  const avisar = useAviso();
  const [lista, setLista] = useState(null);
  const [deptos, setDeptos] = useState([]);
  const [filtro, setFiltro] = useState("");
  const [nueva, setNueva] = useState({ tipo: "TITULO", patron: "", categoria: "P", departamento: "" });
  const cargar = useCallback(() => reglasProductividad().then(setLista).catch(() => setLista([])), []);
  useEffect(() => { cargar(); cargarDeptos().then(setDeptos).catch(() => {}); }, [cargar]);
  if (!lista) return <Cargando />;
  const visibles = lista.filter((r) => !filtro || r.patron.toLowerCase().includes(filtro.toLowerCase()) || (r.departamento_nombre || "").toLowerCase().includes(filtro.toLowerCase()));
  return (
    <div className="space-y-4">
      <Alerta tono="azul">Cada minuto se clasifica con la primera regla que coincida: primero las del departamento de la persona y luego las generales; dentro de cada nivel, sitio web, luego texto del título y luego aplicación. Lo que no coincide con nada es neutral.</Alerta>
      <Panel titulo={`Reglas (${lista.length})`} accion={<Boton tam="sm" variante="secundario" icono={RefreshCw} onClick={async () => { const r = await reclasificar(); avisar(`${r.cambiados} minutos reclasificados.`); }}>Aplicar a los últimos 30 días</Boton>} cuerpo="p-0">
        <div className="flex flex-wrap items-end gap-2 border-b border-linea-suave px-5 py-3">
          <select aria-label="Tipo" className="campo h-10 w-36" value={nueva.tipo} onChange={(e) => setNueva({ ...nueva, tipo: e.target.value })}><option value="APP">Aplicación</option><option value="DOMINIO">Sitio web</option><option value="TITULO">Título</option></select>
          <input aria-label="Patrón" className="campo h-10 min-w-0 flex-1" placeholder="photoshop, youtube.com, Netflix…" value={nueva.patron} onChange={(e) => setNueva({ ...nueva, patron: e.target.value })} />
          <select aria-label="Categoría" className="campo h-10 w-40" value={nueva.categoria} onChange={(e) => setNueva({ ...nueva, categoria: e.target.value })}><option value="P">Productiva</option><option value="N">Neutral</option><option value="I">Improductiva</option></select>
          <select aria-label="Departamento" className="campo h-10 w-44" value={nueva.departamento} onChange={(e) => setNueva({ ...nueva, departamento: e.target.value })}><option value="">Toda la empresa</option>{deptos.map((d) => <option key={d.id} value={d.id}>{d.nombre}</option>)}</select>
          <Boton tam="sm" icono={Plus} disabled={nueva.patron.trim().length < 2} onClick={async () => {
            try { await guardarRegla({ ...nueva, departamento: nueva.departamento ? Number(nueva.departamento) : null }); setNueva({ ...nueva, patron: "" }); cargar(); } catch (e) { avisar(e.message, "rojo"); }
          }}>Agregar</Boton>
        </div>
        <div className="px-5 py-3"><input aria-label="Buscar regla" className="campo h-10" placeholder="Buscar por texto o departamento" value={filtro} onChange={(e) => setFiltro(e.target.value)} /></div>
        <div className="max-h-[32rem] overflow-auto">
          <table className="tabla">
            <thead><tr><th>Tipo</th><th>Patrón</th><th>Categoría</th><th>Departamento</th><th /></tr></thead>
            <tbody>
              {visibles.map((r) => (
                <tr key={r.id}>
                  <td className="text-sm">{{ APP: "Aplicación", DOMINIO: "Sitio web", TITULO: "Título" }[r.tipo]}</td>
                  <td className="font-mono text-sm">{r.patron}</td>
                  <td><select aria-label={`Categoría de ${r.patron}`} className="campo h-9 w-36" value={r.categoria} onChange={async (e) => { await guardarRegla({ id: r.id, categoria: e.target.value }); cargar(); }}>
                    <option value="P">Productiva</option><option value="N">Neutral</option><option value="I">Improductiva</option></select></td>
                  <td className="text-sm">{r.departamento_nombre || <span className="text-gris">Toda la empresa</span>}</td>
                  <td className="text-right"><Boton tam="sm" variante="fantasma" icono={Trash2} className="text-rojo" aria-label={`Quitar ${r.patron}`} onClick={async () => { await borrarRegla(r.id); cargar(); }} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

const CAMPOS_CONFIG = [
  ["umbral_inactivo_seg", "Inactivo después de (segundos sin teclado ni ratón)"],
  ["alerta_inactivo_min", "Avisar al supervisor tras (minutos inactivo en jornada)"],
  ["alerta_sin_pc_min", "Avisar si marcó y su computadora no reporta en (minutos)"],
  ["alerta_improductivo_pct", "Avisar si el tiempo improductivo del día pasa (%)"],
  ["meta_productividad_pct", "Meta de productividad para la jornada y los KPIs (%)"],
  ["capturas_cada_min", "Una captura cada (minutos)"],
  ["retencion_dias", "Borrar la actividad a los (días)"],
  ["retencion_capturas_dias", "Borrar las capturas a los (días)"],
];

function Configuracion() {
  const avisar = useAviso();
  const [c, setC] = useState(null);
  useEffect(() => { configMonitoreo().then(setC).catch(() => {}); }, []);
  if (!c) return <Cargando />;
  const guardar = async () => { try { setC(await guardarConfigMonitoreo(c)); avisar("Configuración guardada."); } catch (e) { avisar(e.message, "rojo"); } };
  return (
    <div className="space-y-5">
      <Panel titulo="Monitoreo">
        <div className="space-y-3">
          <label className="flex items-center gap-2"><input type="checkbox" className="accent-azul" checked={c.activo} onChange={(e) => setC({ ...c, activo: e.target.checked })} />Monitoreo encendido</label>
          <label className="flex items-center gap-2"><input type="checkbox" className="accent-azul" checked={c.capturas} onChange={(e) => setC({ ...c, capturas: e.target.checked })} />Tomar capturas de pantalla en jornada</label>
          <label className="flex items-center gap-2 pl-6"><input type="checkbox" className="accent-azul" checked={c.desenfocar_capturas} onChange={(e) => setC({ ...c, desenfocar_capturas: e.target.checked })} />Desenfocarlas (se ve qué tipo de trabajo, no el contenido)</label>
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          {CAMPOS_CONFIG.map(([k, t]) => <Campo key={k} etiqueta={t}>{(id) => <input id={id} type="number" min={0} className="campo" value={c[k]} onChange={(e) => setC({ ...c, [k]: Number(e.target.value) })} />}</Campo>)}
        </div>
      </Panel>
      <Panel titulo="Política que acepta cada persona">
        <Campo etiqueta="Versión" ayuda="Si cambias el texto, sube la versión: todos tendrán que aceptarla de nuevo y mientras tanto su computadora no registra.">
          {(id) => <input id={id} className="campo w-32" value={c.version_politica} onChange={(e) => setC({ ...c, version_politica: e.target.value })} />}</Campo>
        <Campo etiqueta="Texto" className="mt-4">{(id) => <textarea id={id} rows={14} className="campo font-sans" value={c.texto_politica} onChange={(e) => setC({ ...c, texto_politica: e.target.value })} />}</Campo>
      </Panel>
      <Boton onClick={guardar}>Guardar</Boton>
    </div>
  );
}

export default function Monitoreo() {
  const { esAdmin, puedeValidar } = useSesion();
  const gestiona = esAdmin || puedeValidar;
  const [params, setParams] = useSearchParams();
  const persona = params.get("persona");
  const ver = params.get("ver") || (persona ? "persona" : gestiona ? "vivo" : "mia");
  const opciones = [
    gestiona && { valor: "vivo", etiqueta: "Equipo en vivo" },
    { valor: "mia", etiqueta: "Mi actividad" },
    { valor: "equipos", etiqueta: "Mis equipos y política" },
    esAdmin && { valor: "reglas", etiqueta: "Reglas" },
    esAdmin && { valor: "config", etiqueta: "Configuración" },
  ].filter(Boolean);
  return (
    <div className="space-y-5">
      <Cabecera titulo="Monitoreo" descripcion="Actividad en la computadora durante la jornada: aplicaciones, sitios, tiempo activo, productivo y de foco." />
      <Pestanas opciones={opciones} valor={ver === "persona" ? "vivo" : ver} onCambio={(v) => setParams({ ver: v })} />
      {ver === "persona" && persona ? (
        <div className="space-y-3">
          <button type="button" className="text-sm font-medium text-azul hover:underline" onClick={() => setParams({ ver: "vivo" })}>← Equipo en vivo</button>
          <DiaPersona usuario={persona} />
          <p className="text-sm"><Link to={`/ficha?usuario=${persona}`} className="text-azul hover:underline">Ver su ficha de productividad del mes</Link></p>
        </div>
      ) : ver === "vivo" ? <EnVivo onVer={(id) => setParams({ ver: "persona", persona: id })} />
        : ver === "equipos" ? <MisEquipos />
          : ver === "reglas" ? <Reglas />
            : ver === "config" ? <Configuracion />
              : <DiaPersona />}
    </div>
  );
}
