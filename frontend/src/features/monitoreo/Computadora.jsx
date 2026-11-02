// Ficha de una computadora: cómo se usó su tiempo (como el «Computer Details» de Teramind, con nuestro agente).
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Camera, Globe, History, Laptop, ListTree, Monitor, Search, ShieldAlert } from "lucide-react";
import { api, urlCaptura } from "@/lib/api";
import { hace, hoyISO, reloj } from "@/lib/formato";
import { Alerta, Boton, Cargando, Insignia, Modal, Panel, Pestanas, Puntaje, Vacio, cx, useAviso } from "@/components/ui";

const MO = "/api/monitoreo";
const q = (p) => { const s = new URLSearchParams(Object.fromEntries(Object.entries(p).filter(([, v]) => v !== "" && v != null))).toString(); return s ? `?${s}` : ""; };
const local = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const menos = (n) => { const d = new Date(); d.setDate(d.getDate() - n); return local(d); };
const fechaHora = (iso) => new Date(iso).toLocaleString("es-DO", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
const pct = (v) => (v == null ? "—" : `${Number(v).toLocaleString("es-DO", { maximumFractionDigits: 1 })} %`);
const DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
const CAT = { P: ["Productivo", "bg-verde"], N: ["Neutral", "bg-[#9aa7bd]"], I: ["Improductivo", "bg-rojo"] };
const RIESGO = { BAJO: ["Bajo", "azul"], MEDIO: ["Medio", "amarillo"], ALTO: ["Alto", "rojo"], CRITICO: ["Crítico", "rojo"] };

/** Etiqueta flotante al pasar el ratón o tocar una barra o celda. */
function useTip() {
  const [tip, setTip] = useState(null);
  const props = (texto) => ({
    onMouseEnter: (e) => setTip({ x: e.clientX, y: e.clientY, texto }), onMouseMove: (e) => setTip({ x: e.clientX, y: e.clientY, texto }),
    onMouseLeave: () => setTip(null), onClick: (e) => setTip({ x: e.clientX, y: e.clientY, texto }), "aria-label": texto,
  });
  const nodo = tip && (
    <div className="pointer-events-none fixed z-50 max-w-64 rounded-lg bg-noche px-3 py-2 text-xs text-white shadow-lg" style={{ left: Math.min(tip.x + 12, window.innerWidth - 270), top: tip.y + 12 }}>{tip.texto}</div>
  );
  return [props, nodo];
}

function ActividadPorDia({ dias }) {
  const [tip, nodo] = useTip();
  const max = Math.max(60, ...dias.map((d) => d.registrados));
  const corto = dias.length > 14;
  return (
    <Panel titulo="Actividad por día">
      {!dias.some((d) => d.registrados) ? <p className="text-sm text-gris">Sin actividad en estas fechas.</p> : (
        <>
          <div className="flex h-44 items-end gap-1.5" role="img" aria-label="Minutos por día: productivo, neutral, improductivo e inactivo">
            {dias.map((d) => {
              const seg = (n, clase) => (n ? <div className={cx(clase, "w-full")} style={{ height: `${(n / max) * 100}%` }} /> : null);
              const fecha = new Date(`${d.dia}T12:00`);
              return (
                <div key={d.dia} className="flex h-full min-w-0 flex-1 cursor-default flex-col items-center justify-end gap-[2px]"
                  {...tip(`${fecha.toLocaleDateString("es-DO", { weekday: "short", day: "numeric", month: "short" })} · ${reloj(d.registrados)} registrado: ${reloj(d.productivos)} productivo, ${reloj(d.neutrales)} neutral, ${reloj(d.improductivos)} improductivo, ${reloj(d.inactivos)} inactivo`)}>
                  <div className="flex h-full w-full max-w-9 flex-col justify-end gap-[2px] overflow-hidden rounded-t">
                    {seg(d.inactivos, "bg-linea")}{seg(d.improductivos, "bg-rojo")}{seg(d.neutrales, "bg-[#9aa7bd]")}{seg(d.productivos, "bg-verde")}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-1 flex gap-1.5 text-[11px] text-gris num">{dias.map((d, i) => {
            const f = new Date(`${d.dia}T12:00`);
            const mostrar = corto ? i % 5 === 0 || i === dias.length - 1 : true;
            return <span key={d.dia} className="relative min-w-0 flex-1 text-center"><span className="absolute left-1/2 -translate-x-1/2 whitespace-nowrap">{mostrar ? `${f.getDate()}/${f.getMonth() + 1}` : ""}</span>&nbsp;</span>;
          })}</div>
          <div className="mt-3 flex flex-wrap gap-3 text-xs text-gris">
            {[["bg-verde", "Productivo"], ["bg-[#9aa7bd]", "Neutral"], ["bg-rojo", "Improductivo"], ["bg-linea", "Inactivo"]].map(([c, t]) => <span key={t} className="flex items-center gap-1.5"><span className={cx("size-2.5 rounded-sm", c)} />{t}</span>)}
          </div>
        </>
      )}
      {nodo}
    </Panel>
  );
}

function MapaHoras({ mapa }) {
  const [tip, nodo] = useTip();
  const tono = (c) => (c.intensidad == null ? "bg-linea-suave" : c.intensidad >= 75 ? "bg-azul" : c.intensidad >= 50 ? "bg-azul/70" : c.intensidad >= 25 ? "bg-azul/45" : "bg-azul/20");
  return (
    <Panel titulo="Teclado y ratón por hora">
      <div className="overflow-x-auto">
        <div className="grid min-w-[520px] grid-cols-[2.25rem_repeat(24,minmax(0,1fr))] gap-[3px]" role="img" aria-label="Nivel de actividad de teclado y ratón por día de la semana y hora">
          {mapa.map((fila, dia) => [
            <span key={`d${dia}`} className="pr-1 text-right text-[11px] leading-4 text-gris">{DIAS[dia]}</span>,
            ...fila.map((c, h) => <span key={`${dia}-${h}`} className={cx("h-4 rounded-[3px]", tono(c))}
              {...tip(c.minutos ? `${DIAS[dia]} ${h}:00 · ${c.intensidad} % de los minutos con teclado o ratón · ${reloj(c.minutos)} registrados` : `${DIAS[dia]} ${h}:00 · sin datos`)} />),
          ])}
          <span />
          {Array.from({ length: 24 }, (_, h) => <span key={`h${h}`} className="text-center text-[10px] text-gris num">{h % 3 === 0 ? h : ""}</span>)}
        </div>
      </div>
      <div className="mt-3 flex items-center gap-1.5 text-xs text-gris">Menos
        {["bg-azul/20", "bg-azul/45", "bg-azul/70", "bg-azul"].map((c) => <span key={c} className={cx("size-3 rounded-[3px]", c)} />)} Más · gris = sin datos</div>
      {nodo}
    </Panel>
  );
}

function Barras({ titulo, filas, vacio }) {
  const max = Math.max(1, ...filas.map((f) => f.minutos));
  return (
    <Panel titulo={titulo} cuerpo="p-0">
      {!filas.length ? <p className="p-5 text-sm text-gris">{vacio}</p> : (
        <ul className="divide-y divide-linea-suave">{filas.map((f) => (
          <li key={f.nombre} className="px-5 py-2">
            <div className="flex items-center gap-3 text-[15px]"><span className="min-w-0 flex-1 truncate" title={f.nombre}>{f.nombre}</span><span className="shrink-0 text-sm num">{reloj(f.minutos)}</span></div>
            <div className="mt-1 h-1.5 rounded-full bg-linea-suave"><div className={cx("h-full rounded-full", f.categoria ? CAT[f.categoria][1] : "bg-azul")} style={{ width: `${(f.minutos / max) * 100}%` }} /></div>
          </li>))}</ul>
      )}
    </Panel>
  );
}

export default function Computadora() {
  const { id } = useParams();
  const navigate = useNavigate();
  const avisar = useAviso();
  const [rango, setRango] = useState({ desde: menos(6), hasta: hoyISO() });
  const [persona, setPersona] = useState("");
  const [texto, setTexto] = useState("");
  const [buscar, setBuscar] = useState("");
  const [ver, setVer] = useState("actividad");
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [foto, setFoto] = useState(null);
  const [vivo, setVivo] = useState(0);
  const [filasVer, setFilasVer] = useState(100);
  useEffect(() => { const t = setTimeout(() => setBuscar(texto), 350); return () => clearTimeout(t); }, [texto]);
  useEffect(() => {
    setError("");
    api(`${MO}/computadoras/${id}/${q({ ...rango, persona, q: buscar })}`).then(setD).catch((e) => setError(e.message));
  }, [id, rango, persona, buscar, vivo]);
  useEffect(() => {
    if (ver !== "vivo") return undefined;
    const t = setInterval(() => document.visibilityState === "visible" && setVivo((v) => v + 1), 60000);
    return () => clearInterval(t);
  }, [ver]);
  const cambiarMonitoreo = async () => {
    try {
      const r = await api(`${MO}/computadoras/${id}/monitorear/`, { method: "POST", body: { monitorear: !d.equipo.monitorear } });
      setD({ ...d, equipo: { ...d.equipo, monitorear: r.monitorear } });
      avisar(r.monitorear ? "Monitoreo encendido en este equipo." : "Monitoreo apagado: el agente deja de registrar en su próxima consulta.");
    } catch (e) { setError(e.message); }
  };
  const r = d?.resumen;
  const opciones = useMemo(() => [
    { valor: "actividad", etiqueta: "Actividad" }, { valor: "registro", etiqueta: "Registro", cuenta: d?.sesiones_total },
    { valor: "alertas", etiqueta: "Alertas", cuenta: d?.alertas.length }, { valor: "capturas", etiqueta: "Capturas", cuenta: d?.capturas.length },
    { valor: "vivo", etiqueta: "Pantalla en vivo" }, { valor: "ips", etiqueta: "Historial de IP" },
  ], [d]);
  if (error && !d) return <Alerta>{error}</Alerta>;
  if (!d) return <Cargando />;
  const e = d.equipo;
  return (
    <div className="space-y-5">
      <button type="button" onClick={() => navigate(-1)} className="inline-flex items-center gap-1.5 text-sm font-medium text-azul hover:underline"><ArrowLeft className="size-4" />Volver</button>
      <section className="rounded-xl border border-linea bg-white p-5">
        <div className="flex flex-wrap items-start gap-3">
          <Laptop className="mt-1 size-6 text-azul" />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="font-display text-2xl font-semibold">{e.nombre}</h1>
              {e.en_linea ? <Insignia tono="verde">En línea</Insignia> : <Insignia>{e.ultimo_contacto ? `Visto ${hace(e.ultimo_contacto)}` : "Nunca conectado"}</Insignia>}
              {!e.monitorear && <Insignia tono="amarillo">Monitoreo apagado</Insignia>}
              {!e.activo && <Insignia>Desvinculado</Insignia>}
            </div>
            <p className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm text-gris">
              {e.nombre_equipo && <span>Equipo: {e.nombre_equipo}</span>}<span>Sistema: {e.sistema || "—"}</span><span>IP: {e.ip || "—"}</span>
              <span>Agente {e.version_agente || "—"}</span><span>De: <Link to={`/monitoreo?ver=persona&persona=${e.usuario}`} className="text-azul hover:underline">{e.persona}</Link></span>
              {e.activo_fijo && <Link to={`/activos?ver=${e.activo_fijo.id}`} className="text-azul hover:underline">Activo {e.activo_fijo.codigo}</Link>}
            </p>
          </div>
          {d.puede_cambiar && (
            <label className="flex min-h-11 cursor-pointer items-center gap-2 text-sm font-medium">
              <input type="checkbox" role="switch" className="peer sr-only" checked={e.monitorear} onChange={cambiarMonitoreo} />
              <span className={cx("relative h-6 w-11 rounded-full transition-colors", e.monitorear ? "bg-verde" : "bg-linea")}><span className={cx("absolute top-0.5 size-5 rounded-full bg-white shadow transition-all", e.monitorear ? "left-[22px]" : "left-0.5")} /></span>
              Monitoreo
            </label>
          )}
        </div>
      </section>

      <div className="flex flex-wrap items-center gap-2">
        {[[7, "7 días"], [14, "14 días"], [30, "30 días"]].map(([n, t]) => (
          <button key={n} type="button" onClick={() => setRango({ desde: menos(n - 1), hasta: hoyISO() })}
            className={cx("h-9 rounded-lg border px-3 text-sm font-medium", rango.desde === menos(n - 1) && rango.hasta === hoyISO() ? "border-azul bg-azul text-white" : "border-linea bg-white hover:border-azul")}>{t}</button>))}
        <input type="date" aria-label="Desde" className="campo !h-9 w-40" value={rango.desde} max={rango.hasta} onChange={(ev) => setRango({ ...rango, desde: ev.target.value })} />
        <input type="date" aria-label="Hasta" className="campo !h-9 w-40" value={rango.hasta} max={hoyISO()} onChange={(ev) => setRango({ ...rango, hasta: ev.target.value })} />
        {d.personas.length > 1 && (
          <select className="campo !h-9 !w-auto" aria-label="Persona" value={persona} onChange={(ev) => setPersona(ev.target.value)}>
            <option value="">Todas las personas</option>{d.personas.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}</select>)}
      </div>
      {error && <Alerta>{error}</Alerta>}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {[["Registrado", reloj(r.minutos_registrados), `${d.personas.length} persona(s)`], ["Tiempo activo", pct(r.actividad), `${reloj(r.minutos_activos)} activo`],
          ["Productivo", <Puntaje key="p" valor={r.productividad} />, `${reloj(r.minutos_productivos)} productivo`], ["Improductivo", pct(r.improductividad), reloj(r.minutos_improductivos)],
          ["Tiempo de foco", reloj(r.minutos_foco), `${r.sesiones_foco} bloque(s) de 25+ min`], ["Cambios de ventana", r.cambios_por_hora ?? "—", "por hora"]].map(([t, v, s]) => (
          <div key={t} className="rounded-xl border border-linea bg-white p-4"><p className="text-sm text-gris">{t}</p><p className="mt-1 font-display text-2xl font-semibold num">{v}</p><p className="text-xs text-gris">{s}</p></div>))}
      </div>

      <Pestanas opciones={opciones} valor={ver} onCambio={setVer} />

      {ver === "actividad" && (
        <div className="space-y-4">
          <div className="grid gap-4 xl:grid-cols-2"><ActividadPorDia dias={d.por_dia} /><MapaHoras mapa={d.mapa_horas} /></div>
          <div className="grid gap-4 lg:grid-cols-3">
            <Barras titulo="Tareas principales" filas={d.tareas} vacio="Sin cronómetro en tareas mientras se usaba este equipo." />
            <Barras titulo="Aplicaciones" filas={r.apps.slice(0, 10)} vacio="Sin datos." />
            <Barras titulo="Sitios web" filas={r.sitios.slice(0, 10)} vacio="Sin sitios reconocidos." />
          </div>
        </div>
      )}

      {ver === "registro" && (
        <Panel cuerpo="p-0" titulo="Registro de actividad" accion={
          <label className="relative"><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" />
            <input className="campo !h-9 w-56 pl-9" placeholder="Aplicación, sitio o ventana" aria-label="Buscar en el registro" value={texto} onChange={(ev) => setTexto(ev.target.value)} /></label>}>
          {!d.registro.length ? <Vacio icono={ListTree} titulo="Sin actividad">Nada registrado con esos filtros.</Vacio> : (
            <div className="overflow-x-auto"><table className="tabla">
              <thead><tr><th>Inicio</th><th>Persona</th><th>Aplicación / sitio</th><th className="text-right">Tiempo</th><th>Ventana</th><th>Tarea</th></tr></thead>
              <tbody>{d.registro.slice(0, filasVer).map((s, i) => (
                <tr key={i}>
                  <td className="whitespace-nowrap text-sm num">{fechaHora(s.inicio)}</td>
                  <td className="whitespace-nowrap text-sm">{s.persona}</td>
                  <td className="min-w-44"><span className="flex items-center gap-2"><span className={cx("size-2 shrink-0 rounded-full", CAT[s.categoria][1])} title={CAT[s.categoria][0]} />
                    <span className="truncate">{s.dominio || s.app || "—"}</span></span>{s.dominio && <span className="block pl-4 text-xs text-gris">{s.app}</span>}</td>
                  <td className="whitespace-nowrap text-right num">{reloj(s.minutos)}{s.activos < s.minutos && <span className="block text-xs text-gris">{reloj(s.activos)} activo</span>}</td>
                  <td className="max-w-80 truncate text-sm text-gris" title={s.titulo}>{s.titulo || "—"}</td>
                  <td className="max-w-48 truncate text-sm" title={s.tarea || ""}>{s.tarea || "—"}</td>
                </tr>))}</tbody>
            </table></div>
          )}
          {d.registro.length > filasVer && <div className="border-t border-linea-suave p-3 text-center"><Boton tam="sm" variante="secundario" onClick={() => setFilasVer(filasVer + 100)}>Ver 100 más ({d.registro.length - filasVer} restantes)</Boton></div>}
          {d.sesiones_total > d.registro.length && <p className="px-5 py-3 text-sm text-gris">Se muestran las {d.registro.length} más recientes de {d.sesiones_total}. Acorta las fechas o busca para ver otras.</p>}
        </Panel>
      )}

      {ver === "alertas" && (!d.alertas.length ? <Vacio icono={ShieldAlert} titulo="Sin alertas en estas fechas">Aquí salen las reglas de comportamiento que se activaron y los avisos de inactividad o computadora sin reportar.</Vacio> : (
        <Panel cuerpo="p-0"><ul className="divide-y divide-linea-suave">{d.alertas.map((a) => (
          <li key={`${a.tipo}${a.id}`} className="flex flex-wrap items-center gap-2 px-5 py-3">
            {a.riesgo ? <Insignia tono={RIESGO[a.riesgo][1]}>{RIESGO[a.riesgo][0]}</Insignia> : <Insignia tono="amarillo">Aviso</Insignia>}
            <span className="font-medium">{a.titulo}</span><span className="text-sm text-gris">· {a.persona} · {fechaHora(a.fecha)}</span>
            {a.estado && a.estado !== "NUEVA" && <Insignia className="ml-auto">{a.estado === "DESCARTADA" ? "Descartada" : "Revisada"}</Insignia>}
            {a.detalle && <p className="w-full truncate text-sm text-gris">{a.detalle}</p>}
          </li>))}</ul></Panel>
      ))}

      {ver === "capturas" && (!d.capturas.length ? <Vacio icono={Camera} titulo="Sin capturas">Solo hay capturas si el perfil de monitoreo de la persona las toma (Monitoreo → Reglas → Perfiles).</Vacio> : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">{d.capturas.map((c) => (
          <button key={c.id} type="button" onClick={() => setFoto(c)} className="overflow-hidden rounded-lg border border-linea bg-white text-left hover:border-azul">
            <img src={urlCaptura(c.id)} alt={`Captura ${c.hora}`} loading="lazy" className="aspect-video w-full bg-noche object-cover" />
            <span className="block truncate px-2 py-1 text-xs text-gris">{c.hora} · {c.app || "—"}</span></button>))}</div>
      ))}

      {ver === "vivo" && (
        <Panel titulo="Pantalla en vivo">
          {d.capturas[0] ? <>
            <img src={`${urlCaptura(d.capturas[0].id)}?v=${vivo}`} alt="Última captura" className="w-full rounded-lg bg-noche" />
            <p className="mt-2 text-sm text-gris">Última captura: {d.capturas[0].hora} · {d.capturas[0].app || "—"}. Se actualiza cada minuto.</p>
          </> : <Vacio icono={Monitor} titulo="Sin capturas hoy">Este equipo no está tomando capturas (depende del perfil de monitoreo).</Vacio>}
          <Boton tam="sm" variante="secundario" className="mt-3" onClick={() => setVivo((v) => v + 1)}>Actualizar</Boton>
        </Panel>
      )}

      {ver === "ips" && (!d.ips.length ? <Vacio icono={Globe} titulo="Sin conexiones registradas">El historial empieza con la primera conexión del agente en esta versión.</Vacio> : (
        <Panel cuerpo="p-0" titulo="Historial de IP"><div className="overflow-x-auto"><table className="tabla">
          <thead><tr><th>IP</th><th>Primera vez</th><th>Última vez</th><th className="text-right">Conexiones</th></tr></thead>
          <tbody>{d.ips.map((i) => <tr key={i.ip}><td className="font-mono text-sm">{i.ip}</td><td className="text-sm">{fechaHora(i.primera)}</td><td className="text-sm">{fechaHora(i.ultima)}</td><td className="text-right num">{i.veces}</td></tr>)}</tbody>
        </table></div></Panel>
      ))}

      <Modal abierto={!!foto} onCerrar={() => setFoto(null)} titulo={foto ? `Captura ${foto.hora}` : ""} ancho="md:max-w-5xl">
        {foto && <img src={urlCaptura(foto.id)} alt="" className="w-full rounded-lg" />}
      </Modal>
      <p className="flex items-center gap-1.5 text-xs text-gris"><History className="size-3" />Solo se registra en jornada. Nunca teclas, contenido de mensajes, archivos, audio ni cámara.</p>
    </div>
  );
}
