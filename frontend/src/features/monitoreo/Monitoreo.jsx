// Monitoreo de actividad: en vivo del equipo, el día de cada persona, mis equipos, reglas y configuración.
import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Check, Copy, FolderKanban, Laptop, MessageSquareText, MonitorSmartphone, Plus, RefreshCw, ShieldCheck, Trash2, WifiOff, X } from "lucide-react";
import {
  justificaciones, justificar, productividadProyectos, revisarJustificacion,
  aceptarPolitica, borrarReglaProductividad as borrarRegla, configMonitoreo, departamentos as cargarDeptos, dispositivos, guardarConfigMonitoreo, guardarReglaProductividad as guardarRegla,
  monitoreoDia, monitoreoEquipo, politicaMonitoreo, quitarDispositivo, reclasificar, reglasProductividad, urlCaptura, usuarios as cargarUsuarios,
  vincularDispositivo,
} from "@/lib/api";
import { hace, hoyISO, mesActual, nombreMes, reloj } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import { Computadoras, Incidencias, Pantallas, Perfiles, ReglasComportamiento, Resumen } from "./Analitica";
import { Alerta, Boton, Cabecera, Campo, Cargando, Insignia, Modal, Panel, Pestanas, Puntaje, SelectorMes, Vacio, cx, useAviso, useConfirmar } from "@/components/ui";

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

/** Mini gráfica de la última hora: 12 bloques de 5 minutos con los minutos activos de cada uno. */
function Chispa({ valores }) {
  if (!valores?.length || !valores.some(Boolean)) return <span className="text-xs text-gris">—</span>;
  return (
    <span className="inline-flex h-6 items-end gap-px" title="Minutos activos cada 5 minutos, última hora" aria-label={`Última hora: ${valores.join(", ")} minutos activos por bloque`}>
      {valores.map((v, i) => <span key={i} className={cx("w-1.5 rounded-sm", v >= 4 ? "bg-azul" : v ? "bg-[#9aa7bd]" : "bg-linea-suave")} style={{ height: `${Math.max(12, (v / 5) * 100)}%` }} />)}
    </span>
  );
}

/** El día de una persona (o el mío). */
export function DiaPersona({ usuario }) {
  const [fecha, setFecha] = useState(hoyISO());
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [foto, setFoto] = useState(null);
  const [justificando, setJustificando] = useState(false);
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
          {d.equipos.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 text-sm"><span className="text-gris">Computadora:</span>
              {d.equipos.map((x) => <Link key={x.id} to={`/monitoreo/computadoras/${x.id}`} className="inline-flex items-center gap-1.5 rounded-full border border-linea bg-white px-3 py-1 font-medium text-azul hover:border-azul"><Laptop className="size-3.5" />{x.nombre} · ver cómo usa su tiempo</Link>)}
            </div>
          )}
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
            <Dato titulo="En jornada" valor={reloj(d.jornada.trabajados)} detalle={`Entró ${hora(d.jornada.entrada)}${d.jornada.llegada === "TARDE" ? ` · ${d.jornada.tardanza} min tarde` : ""}`} />
            <Dato titulo="Registrado en PC" valor={reloj(d.minutos_registrados)} detalle={d.cobertura != null ? `${pct(d.cobertura)} de la jornada` : "—"} />
            <Dato titulo="Tiempo activo" valor={pct(d.actividad)} detalle={`${reloj(d.minutos_activos)} activo · ${reloj(d.minutos_inactivos)} inactivo`} tono={d.actividad != null && d.actividad < 60 ? "text-rojo" : ""} />
            <Dato titulo="Productivo" valor={<Puntaje valor={d.productividad} />} detalle={`${reloj(d.minutos_productivos)} productivo · ${reloj(d.minutos_improductivos)} improductivo`} />
            <Dato titulo="Tiempo de foco" valor={reloj(d.minutos_foco)} detalle={`${d.sesiones_foco} bloque(s) de 25+ min`} />
            <Dato titulo="Nivel de actividad" valor={pct(d.intensidad)} detalle="Teclado o ratón por minuto" />
            <Dato titulo="Cambios de ventana" valor={d.cambios_por_hora ?? "—"} detalle="por hora" tono={d.cambios_por_hora > 60 ? "text-[#a86a00]" : ""} />
          </div>
          <Panel titulo="Línea de tiempo" accion={!usuario && d.linea.length > 0 && <Boton tam="sm" variante="secundario" icono={MessageSquareText} onClick={() => setJustificando(true)}>Justificar un tramo</Boton>}>
            {d.linea.length ? <Linea bloques={d.linea} /> : <Vacio icono={MonitorSmartphone} titulo="Sin actividad registrada este día">Solo se registra en jornada, con la computadora vinculada.</Vacio>}
          </Panel>
          {d.desconexiones?.length > 0 && (
            <Panel titulo={`Desconexiones en jornada · ${reloj(d.minutos_desconectado)}`}>
              <p className="mb-2 text-sm text-gris">Tramos de 15 minutos o más, en jornada, sin datos de la computadora (agente cerrado, equipo apagado o sin internet).</p>
              <ul className="flex flex-wrap gap-2">{d.desconexiones.map((x) => (
                <li key={x.desde}><Insignia tono="amarillo"><WifiOff className="size-3" />{hora(x.desde)}–{hora(x.hasta)} · {reloj(x.minutos)}</Insignia></li>))}</ul>
            </Panel>
          )}
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
          {justificando && <FormJustificar fecha={fecha} onCerrar={() => setJustificando(false)} />}
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
                <thead><tr><th>Persona</th><th>Ahora</th><th className="text-right">Jornada</th><th className="text-right">Activo</th><th className="text-right">Productivo</th><th className="text-right">Foco</th><th className="text-right">Nivel</th><th className="text-right">Cambios/h</th><th>Última hora</th></tr></thead>
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
                      <td><Chispa valores={p.reciente} /></td>
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

function FormJustificar({ fecha, onCerrar }) {
  const avisar = useAviso();
  const [f, setF] = useState({ desde: "09:00", hasta: "10:00", motivo: "" });
  const [error, setError] = useState("");
  const enviar = async () => {
    setError("");
    try {
      await justificar({ desde: new Date(`${fecha}T${f.desde}`).toISOString(), hasta: new Date(`${fecha}T${f.hasta}`).toISOString(), motivo: f.motivo });
      avisar("Enviada a tu supervisor. Si la aprueba, esos minutos cuentan como productivos.");
      onCerrar();
    } catch (e) { setError(e.message); }
  };
  return (
    <Modal abierto onCerrar={onCerrar} titulo="Justificar un tramo" descripcion="Por ejemplo: YouTube para buscar referencias de un video del cliente, o WhatsApp Web para coordinar con un proveedor."
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton onClick={enviar} disabled={!f.motivo.trim()}>Enviar</Boton></>}>
      {error && <Alerta className="mb-3">{error}</Alerta>}
      <div className="grid gap-3 sm:grid-cols-2">
        <Campo etiqueta="Desde">{(id) => <input id={id} type="time" className="campo" value={f.desde} onChange={(e) => setF({ ...f, desde: e.target.value })} />}</Campo>
        <Campo etiqueta="Hasta">{(id) => <input id={id} type="time" className="campo" value={f.hasta} onChange={(e) => setF({ ...f, hasta: e.target.value })} />}</Campo>
        <Campo etiqueta="Qué estabas haciendo" className="sm:col-span-2">{(id) => <textarea id={id} rows={3} maxLength={300} className="campo" value={f.motivo} onChange={(e) => setF({ ...f, motivo: e.target.value })} />}</Campo>
      </div>
    </Modal>
  );
}

const ESTADO_J = { PENDIENTE: ["Pendiente", "amarillo"], APROBADA: ["Aprobada", "verde"], RECHAZADA: ["Rechazada", "rojo"] };
function Justificaciones({ gestiona }) {
  const avisar = useAviso();
  const [mias, setMias] = useState(null);
  const [equipo, setEquipo] = useState(null);
  const [error, setError] = useState("");
  const [notas, setNotas] = useState({});
  const cargar = useCallback(() => {
    justificaciones().then(setMias).catch((e) => setError(e.message));
    if (gestiona) justificaciones({ ver: "equipo", estado: "PENDIENTE" }).then(setEquipo).catch((e) => setError(e.message));
  }, [gestiona]);
  useEffect(() => { cargar(); }, [cargar]);
  const decidir = async (j, aprobar) => {
    try { const r = await revisarJustificacion(j.id, aprobar, notas[j.id] || ""); avisar(aprobar ? `${r.minutos} minutos pasaron a productivos.` : "Rechazada."); cargar(); }
    catch (e) { setError(e.message); }
  };
  const tramo = (j) => `${new Date(j.desde).toLocaleDateString("es-DO")} · ${hora(j.desde)}–${hora(j.hasta)}`;
  return (
    <div className="space-y-4">
      {error && <Alerta>{error}</Alerta>}
      {gestiona && (
        <Panel titulo={`Por revisar de tu equipo${equipo ? ` (${equipo.length})` : ""}`} cuerpo="p-0">
          {!equipo ? <Cargando /> : !equipo.length ? <p className="p-5 text-sm text-gris">Nada pendiente.</p> : (
            <ul className="divide-y divide-linea-suave">{equipo.map((j) => (
              <li key={j.id} className="px-5 py-3">
                <p><span className="font-medium">{j.usuario_nombre}</span> <span className="text-sm text-gris">· {tramo(j)}</span></p>
                <p className="text-[15px]">{j.motivo}</p>
                <p className="text-xs text-gris">En ese tramo: {reloj(j.resumen.productivos)} productivo, {reloj(j.resumen.neutrales)} neutral, {reloj(j.resumen.improductivos)} improductivo · {j.resumen.apps.join(", ") || "sin datos"}</p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <input className="campo !h-9 min-w-48 flex-1" placeholder="Nota (opcional)" value={notas[j.id] || ""} onChange={(e) => setNotas({ ...notas, [j.id]: e.target.value })} aria-label="Nota" />
                  <Boton tam="sm" variante="secundario" icono={X} onClick={() => decidir(j, false)}>Rechazar</Boton>
                  <Boton tam="sm" icono={Check} onClick={() => decidir(j, true)}>Aprobar</Boton>
                </div>
              </li>))}</ul>
          )}
        </Panel>
      )}
      <Panel titulo="Mis justificaciones" cuerpo="p-0">
        {!mias ? <Cargando /> : !mias.length ? <p className="p-5 text-sm text-gris">Desde «Mi actividad» puedes justificar un tramo que salió como neutral o improductivo.</p> : (
          <ul className="divide-y divide-linea-suave">{mias.map((j) => (
            <li key={j.id} className="flex flex-wrap items-center gap-3 px-5 py-2.5">
              <span className="min-w-0 flex-1"><span className="text-[15px]">{j.motivo}</span><span className="block text-xs text-gris">{tramo(j)}{j.nota ? ` · ${j.nota}` : ""}</span></span>
              <Insignia tono={ESTADO_J[j.estado][1]}>{ESTADO_J[j.estado][0]}{j.estado === "APROBADA" ? ` · ${j.minutos} min` : ""}</Insignia>
            </li>))}</ul>
        )}
      </Panel>
    </div>
  );
}

function Proyectos() {
  const [mes, setMes] = useState(mesActual());
  const [tipo, setTipo] = useState("ordenes");
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [abierto, setAbierto] = useState(null);
  useEffect(() => { setD(null); setError(""); productividadProyectos(mes).then(setD).catch((e) => setError(e.message)); }, [mes]);
  const dinero = (v) => (v == null ? "—" : `RD$ ${Number(v).toLocaleString("es-DO", { maximumFractionDigits: 0 })}`);
  const filas = d ? d[tipo] : [];
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Pestanas className="!flex" opciones={[{ valor: "ordenes", etiqueta: "Por OT", cuenta: d?.ordenes.length }, { valor: "proyectos", etiqueta: "Por proyecto", cuenta: d?.proyectos.length }]} valor={tipo} onCambio={setTipo} />
        <SelectorMes valor={mes} onCambio={setMes} />
      </div>
      {error ? <Alerta>{error}</Alerta> : !d ? <Cargando /> : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Dato titulo="Horas en cronómetro" valor={d.totales.horas} detalle={`${nombreMes(mes)}`} />
            <Dato titulo="OT con horas" valor={d.totales.ordenes} detalle={`${d.totales.sobre_estimado} sobre lo estimado`} tono={d.totales.sobre_estimado ? "text-rojo" : ""} />
            <Dato titulo="Productivo en PC" valor={<Puntaje valor={d.totales.productividad_pc} />} detalle="Durante el cronómetro" />
            {d.con_costos ? <Dato titulo="Costo de mano de obra" valor={dinero(d.totales.costo)} detalle="Horas × costo por hora" /> : <Dato titulo="Proyectos con horas" valor={d.totales.proyectos} />}
          </div>
          {!filas.length ? <Vacio icono={FolderKanban} titulo="Sin horas registradas en OT o proyectos este mes">Las horas salen del cronómetro de las tareas; los minutos de la computadora se unen solos al cronómetro que corría.</Vacio> : (
            <Panel cuerpo="p-0">
              <div className="overflow-x-auto"><table className="tabla">
                <thead><tr><th>{tipo === "ordenes" ? "OT" : "Proyecto"}</th><th className="text-right">Horas mes</th><th className="text-right">Estimado / real total</th><th className="text-right">Productivo PC</th>
                  <th className="text-right">Tareas validadas</th><th className="text-right">A la primera</th><th className="text-right">Correcciones</th>{d.con_costos && <th className="text-right">Costo</th>}</tr></thead>
                <tbody>{filas.map((o) => (
                  <tr key={o.id} className="cursor-pointer hover:bg-fondo" onClick={() => setAbierto(o)}>
                    <td className="min-w-52"><span className="font-medium">{o.numero}</span> <span className="text-sm">{o.titulo}</span><span className="block text-xs text-gris">{o.cliente} · {o.estado}</span></td>
                    <td className="text-right num">{o.horas}</td>
                    <td className={cx("text-right num", o.sobre_estimado && "font-semibold text-rojo")}>{o.horas_estimadas ?? "—"} / {o.horas_reales_total}{o.desvio_horas_pct != null && <span className="block text-xs">{o.desvio_horas_pct > 0 ? "+" : ""}{o.desvio_horas_pct} %</span>}</td>
                    <td className="text-right"><Puntaje valor={o.productividad_pc} />{o.cobertura_pc != null && <span className="block text-xs text-gris">{pct(o.cobertura_pc)} con PC</span>}</td>
                    <td className="text-right num">{o.validadas}{o.abiertas ? <span className="block text-xs text-gris">{o.abiertas} abiertas</span> : null}</td>
                    <td className="text-right num">{o.validadas ? `${Math.round((o.a_la_primera / o.validadas) * 100)} %` : "—"}</td>
                    <td className="text-right num">{o.correcciones}{o.cambios ? <span className="block text-xs text-gris">{o.cambios} cambio(s)</span> : null}</td>
                    {d.con_costos && <td className="text-right num">{dinero(o.costo)}{o.monto ? <span className="block text-xs text-gris">de {dinero(o.monto)}</span> : null}</td>}
                  </tr>))}</tbody>
              </table></div>
            </Panel>
          )}
          <Modal abierto={!!abierto} onCerrar={() => setAbierto(null)} titulo={abierto ? `${abierto.numero} · ${abierto.titulo}` : ""}>
            {abierto && (
              <ul className="divide-y divide-linea-suave">{abierto.personas.map((p) => (
                <li key={p.id} className="flex items-center justify-between gap-3 py-2"><Link to={`/ficha?usuario=${p.id}&mes=${mes}`} className="text-azul hover:underline">{p.nombre}</Link>
                  <span className="text-sm num">{p.horas} h · <Puntaje valor={p.productividad_pc} /> productivo</span></li>))}</ul>
            )}
          </Modal>
        </>
      )}
    </div>
  );
}

function TodasLasReglas() {
  const [sub, setSub] = useState("comportamiento");
  return (
    <div className="space-y-4">
      <Pestanas className="!flex" opciones={[{ valor: "comportamiento", etiqueta: "Comportamiento" }, { valor: "productividad", etiqueta: "Productividad" }, { valor: "perfiles", etiqueta: "Perfiles" }]} valor={sub} onCambio={setSub} />
      {sub === "comportamiento" ? <ReglasComportamiento /> : sub === "perfiles" ? <Perfiles /> : <Reglas />}
    </div>
  );
}

export default function Monitoreo() {
  const { esAdmin, puedeValidar, esFinanzas, esTecnologia } = useSesion();
  const gestiona = esAdmin || puedeValidar;
  const [params, setParams] = useSearchParams();
  const persona = params.get("persona");
  const ver = params.get("ver") || (persona ? "persona" : gestiona ? "vivo" : "mia");
  const opciones = [
    gestiona && { valor: "vivo", etiqueta: "Equipo en vivo" },
    gestiona && { valor: "resumen", etiqueta: "Resumen" },
    gestiona && { valor: "pantallas", etiqueta: "Pantallas" },
    { valor: "incidencias", etiqueta: "Incidencias" },
    { valor: "mia", etiqueta: "Mi actividad" },
    (gestiona || esFinanzas) && { valor: "proyectos", etiqueta: "Por proyecto y OT" },
    { valor: "justificaciones", etiqueta: "Justificaciones" },
    { valor: "equipos", etiqueta: "Mis equipos y política" },
    esTecnologia && { valor: "computadoras", etiqueta: "Computadoras" },
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
        : ver === "resumen" && gestiona ? <Resumen />
        : ver === "pantallas" && gestiona ? <Pantallas />
        : ver === "incidencias" ? <Incidencias persona={params.get("persona") || ""} gestiona={gestiona} />
        : ver === "computadoras" && esTecnologia ? <Computadoras />
        : ver === "proyectos" && (gestiona || esFinanzas) ? <Proyectos />
        : ver === "justificaciones" ? <Justificaciones gestiona={gestiona} />
        : ver === "equipos" ? <MisEquipos />
          : ver === "reglas" ? <TodasLasReglas />
            : ver === "config" ? <Configuracion />
              : <DiaPersona />}
    </div>
  );
}
