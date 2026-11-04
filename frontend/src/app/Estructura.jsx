// Estructura de la app: menú lateral en la PC, barra inferior en el celular, campanita de avisos.
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Bell, BellRing, Boxes, Headset, Building, Building2, SlidersHorizontal, CircleCheckBig, CircleHelp, Clock, ClipboardList, Ellipsis, FolderKanban, House, KeyRound,
  Award, CalendarClock, Gauge, Laptop, LayoutDashboard, ScrollText, ListChecks, LogOut, MonitorSmartphone, Network, Plus, Search, Settings2, ShieldCheck, DatabaseBackup, Sparkles, Square, SquarePen, Target, Trophy, Users, Wallet, X, Zap,
} from "lucide-react";
import { avisos as cargarAvisos, leerAvisos } from "@/lib/api";
import { hace, relojSeg } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import Marca from "@/components/Marca";
import { Avatar, cx } from "@/components/ui";
import Buscador from "@/app/Buscador";
import { CronometroProvider, nombreRegistro, useCronometro } from "@/features/tiempo/cronometro";
import { anunciarNovedades } from "@/lib/novedades";
import { GuiaProvider, useGuia } from "@/app/Guia";
import BotonJornada from "@/features/asistencia/BotonJornada";
import { SugerenciaApp } from "@/features/cuenta/AvisosCelular";

function secciones({ esAdmin, puedeValidar, esFinanzas, esCoordinacion, esAlmacen, esAgente, gestionaCallCenter, gestionaActivos, misAreas = [],
  veMonitoreo, gestionaPersonas, configuraSistema, esRRHH }) {
  // El agente de call center tiene una plataforma simple: su pantalla y poco más.
  if (esAgente) return [{ titulo: "Mi trabajo", items: [
    { a: "/call-center", texto: "Call Center", icono: Headset },
    { a: "/asistencia", texto: "Asistencia", icono: CalendarClock },
    { a: "/monitoreo", texto: "Mi actividad", icono: MonitorSmartphone },
    { a: "/ficha", texto: "Mi ficha", icono: Gauge },
    { a: "/talento", texto: "Evaluaciones", icono: Award },
    { a: "/politicas", texto: "Políticas", icono: ScrollText },
    { a: "/organigrama", texto: "Organigrama", icono: Network },
  ] }];
  const s = [
    { titulo: "Mi trabajo", items: [
      { a: "/", texto: "Inicio", icono: House, fin: true },
      { a: "/mis-tareas", texto: "Mis tareas", icono: ListChecks },
      { a: "/tiempo", texto: "Tiempo", icono: Clock },
      { a: "/asistencia", texto: "Asistencia", icono: CalendarClock },
      { a: "/monitoreo", texto: veMonitoreo ? "Monitoreo" : "Mi actividad", icono: MonitorSmartphone },
      { a: "/ficha", texto: "Mi ficha", icono: Gauge },
      { a: "/talento", texto: puedeValidar || esAdmin || esRRHH ? "Talento" : "Evaluaciones", icono: Award },
      { a: "/politicas", texto: "Políticas", icono: ScrollText },
      ...(gestionaActivos ? [] : [{ a: "/activos", texto: "Equipos asignados", icono: Laptop }]),
    ] },
    { titulo: "Operación", items: [
      { a: "/ordenes", texto: "Órdenes de trabajo", icono: ClipboardList },
      { a: "/proyectos", texto: "Proyectos", icono: FolderKanban },
      { a: "/clientes", texto: "Clientes", icono: Building },
    ] },
  ];
  if (esAlmacen || esCoordinacion || esFinanzas || misAreas.length) s[1].items.splice(1, 0, { a: "/almacen", texto: "Almacén", icono: Boxes });
  if (gestionaCallCenter) s[1].items.push({ a: "/call-center", texto: "Call Center", icono: Headset });
  if (gestionaActivos) s[1].items.push({ a: "/activos", texto: "Activos y equipos", icono: Laptop });
  if (esAdmin || esCoordinacion) s[1].items.push({ a: "/produccion/ajustes", texto: "Áreas y tiempos", icono: SlidersHorizontal });
  if (puedeValidar) {
    s.push({ titulo: "Mi equipo", items: [
      { a: "/validar", texto: "Por validar", icono: CircleCheckBig, cuenta: "por_validar" },
      { a: "/equipo", texto: "Equipo y tareas", icono: Users },
    ] });
  }
  if (esFinanzas) s.push({ titulo: "Finanzas", items: [{ a: "/finanzas", texto: "Finanzas", icono: Wallet }] });
  if (esAdmin) {
    s.push({ titulo: "Resultados", items: [
      { a: "/panel", texto: "Panel gerencial", icono: LayoutDashboard },
      { a: "/resumen-semanal", texto: "Resumen de la semana", icono: Sparkles },
      { a: "/desempeno", texto: "Desempeño y ranking", icono: Trophy },
      { a: "/kpis-del-mes", texto: "KPIs del mes", icono: SquarePen },
    ] });
  }
  // Administración: cada opción aparece solo con su permiso (mínimo privilegio)
  const admin = [
    esAdmin && { a: "/puestos", texto: "Departamentos y puestos", icono: Building2 },
    gestionaPersonas && { a: "/personas", texto: "Personas", icono: Users },
    gestionaPersonas && { a: "/accesos", texto: "Accesos y permisos", icono: ShieldCheck },
    esAdmin && { a: "/plantillas-kpi", texto: "Plantillas de KPI", icono: Target },
    esAdmin && { a: "/configuracion", texto: "Reglas del puntaje", icono: Settings2 },
    configuraSistema && { a: "/automatizaciones", texto: "Automatizaciones", icono: Zap },
    esAdmin && { a: "/respaldos", texto: "Respaldos", icono: DatabaseBackup },
  ].filter(Boolean);
  if (admin.length) s.push({ titulo: "Administración", items: [{ a: "/organigrama", texto: "Organigrama", icono: Network }, ...admin] });
  else s[0].items.push({ a: "/organigrama", texto: "Organigrama", icono: Network });
  return s;
}

/** Dos tonos cortos y una vibración: para que un «Recordar» del supervisor no pase desapercibido. */
function sonarAviso() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    const ctx = new Ctx();
    [[880, 0], [1175, 0.18], [1480, 0.36]].forEach(([hz, t]) => {
      const o = ctx.createOscillator(); const g = ctx.createGain();
      o.frequency.value = hz; o.type = "sine";
      g.gain.setValueAtTime(0.0001, ctx.currentTime + t);
      g.gain.exponentialRampToValueAtTime(0.4, ctx.currentTime + t + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + t + 0.16);
      o.connect(g).connect(ctx.destination); o.start(ctx.currentTime + t); o.stop(ctx.currentTime + t + 0.2);
    });
    setTimeout(() => ctx.close(), 1000);
  } catch { /* el navegador no deja sonar sin tocar la pantalla primero */ }
  try { navigator.vibrate?.([200, 100, 200, 100, 200]); } catch { /* sin vibración */ }
}

function useAvisos() {
  const [datos, setDatos] = useState({ no_leidas: 0, avisos: [], por_validar: 0 });
  const vistos = useRef(null);
  const firma = useRef(null);
  const refrescar = useCallback(() => cargarAvisos().then((d) => {
    const recordatorios = d.avisos.filter((a) => a.tipo === "RECORDATORIO" && !a.leida).map((a) => a.id);
    if (vistos.current && recordatorios.some((id) => !vistos.current.has(id))) sonarAviso();
    vistos.current = new Set(recordatorios);
    // Aviso nuevo o cambio en «por validar»: las pantallas abiertas se recargan solas.
    const nueva = `${Math.max(0, ...d.avisos.map((a) => a.id))}-${d.no_leidas}-${d.por_validar}`;
    if (firma.current !== null && firma.current !== nueva) anunciarNovedades();
    firma.current = nueva;
    setDatos(d);
  }).catch(() => {}), []);
  useEffect(() => {
    refrescar();
    const t = setInterval(() => { if (document.visibilityState === "visible") refrescar(); }, 10000);
    const alVolver = () => document.visibilityState === "visible" && refrescar();
    document.addEventListener("visibilitychange", alVolver);
    window.addEventListener("adzone:refrescar-avisos", refrescar);
    return () => { clearInterval(t); document.removeEventListener("visibilitychange", alVolver); window.removeEventListener("adzone:refrescar-avisos", refrescar); };
  }, [refrescar]);
  return [datos, refrescar];
}

/** Llamar después de validar, entregar, etc., para actualizar contadores del menú al momento. */
export const refrescarAvisos = () => window.dispatchEvent(new Event("adzone:refrescar-avisos"));

/** Franja fija con el último «Recordar» sin leer. No se pierde entre los demás avisos. */
function Recordatorio({ datos, refrescar }) {
  const navigate = useNavigate();
  const pendientes = datos.avisos.filter((a) => a.tipo === "RECORDATORIO" && !a.leida);
  const hay = pendientes.length > 0;
  // Un poco insistente a propósito: suena cada 30 s y parpadea el título de la pestaña hasta que se atiende.
  useEffect(() => {
    if (!hay) return undefined;
    const original = document.title;
    let alterno = false;
    const titulo = setInterval(() => { alterno = !alterno; document.title = alterno ? "🔔 Recordatorio" : original; }, 1200);
    const sonido = setInterval(sonarAviso, 30000);
    return () => { clearInterval(titulo); clearInterval(sonido); document.title = original; };
  }, [hay]);
  if (!hay) return null;
  const a = pendientes[0];
  const entendido = async (ir) => {
    try { await leerAvisos(pendientes.map((x) => x.id)); } catch { /* se reintenta en el próximo refresco */ }
    refrescar();
    if (ir && a.enlace) navigate(a.tarea && !a.enlace.includes("tarea=") ? `${a.enlace}?tarea=${a.tarea}` : a.enlace);
  };
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-noche/50 p-4 backdrop-blur-sm" role="alertdialog" aria-modal="true" aria-labelledby="recordatorio-titulo">
      <div key={a.id} className="w-full max-w-lg animate-[sacudir_0.6s_ease-in-out_2] overflow-hidden motion-reduce:animate-none rounded-2xl border-t-8 border-amarillo bg-white shadow-2xl">
        <div className="flex flex-col items-center px-6 pb-6 pt-8 text-center sm:px-8">
          <span className="relative flex size-20 items-center justify-center">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-amarillo/40 motion-reduce:animate-none" />
            <span className="relative flex size-20 items-center justify-center rounded-full bg-amarillo-50 ring-4 ring-amarillo">
              <BellRing className="size-10 text-[#a86a00]" aria-hidden />
            </span>
          </span>
          <p className="mt-5 text-sm font-semibold uppercase tracking-wide text-[#a86a00]">Recordatorio</p>
          <h2 id="recordatorio-titulo" className="mt-1 text-2xl font-semibold leading-snug sm:text-[28px]">{a.titulo}</h2>
          {a.mensaje && <p className="mt-3 whitespace-pre-line text-lg text-tinta">{a.mensaje}</p>}
          {pendientes.length > 1 && <p className="mt-3 text-sm text-gris">Tienes {pendientes.length - 1} recordatorio(s) más.</p>}
        </div>
        <div className="grid gap-2 border-t border-linea-suave bg-fondo p-4 sm:grid-cols-2">
          {a.enlace && <button type="button" onClick={() => entendido(true)} className="h-12 rounded-xl bg-noche px-4 text-base font-semibold text-white hover:bg-noche-900 sm:order-2" autoFocus>Ver tarea</button>}
          <button type="button" onClick={() => entendido(false)} className={cx("h-12 rounded-xl border border-linea bg-white px-4 text-base font-semibold text-tinta hover:bg-linea-suave sm:order-1", !a.enlace && "sm:col-span-2")}>Entendido</button>
        </div>
      </div>
    </div>
  );
}

function Campanita({ datos, refrescar, alto = false }) {
  const [abierto, setAbierto] = useState(false);
  const ref = useRef(null);
  const navigate = useNavigate();
  useEffect(() => {
    if (!abierto) return;
    const fuera = (e) => ref.current && !ref.current.contains(e.target) && setAbierto(false);
    const esc = (e) => e.key === "Escape" && setAbierto(false);
    document.addEventListener("mousedown", fuera);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", fuera); document.removeEventListener("keydown", esc); };
  }, [abierto]);

  const abrir = async (aviso) => {
    setAbierto(false);
    if (!aviso.leida) await leerAvisos([aviso.id]).catch(() => {});
    refrescar();
    if (aviso.enlace) navigate(aviso.enlace);
  };

  return (
    <div className="relative" ref={ref} data-guia="avisos">
      <button type="button" onClick={() => setAbierto((a) => !a)} aria-expanded={abierto}
        aria-label={datos.no_leidas ? `Avisos: ${datos.no_leidas} sin leer` : "Avisos"}
        className="relative flex size-10 items-center justify-center rounded-lg text-gris hover:bg-white hover:text-azul">
        <Bell className="size-5" />
        {datos.no_leidas > 0 && (
          <span className="absolute right-1 top-1 flex min-w-4 items-center justify-center rounded-full bg-rojo px-1 text-[10px] font-semibold leading-4 text-white num">
            {datos.no_leidas > 9 ? "9+" : datos.no_leidas}
          </span>
        )}
      </button>
      {abierto && (
        <div className={cx("absolute right-0 z-50 w-[min(24rem,calc(100vw-1.5rem))] overflow-hidden rounded-xl border border-linea bg-white shadow-xl", alto ? "bottom-12" : "top-12")}>
          <div className="flex items-center justify-between border-b border-linea-suave px-4 py-3">
            <p className="font-display font-semibold text-noche">Avisos</p>
            {datos.no_leidas > 0 && (
              <button type="button" className="text-sm font-medium text-azul hover:underline"
                onClick={async () => { await leerAvisos().catch(() => {}); refrescar(); }}>
                Marcar todo como leído
              </button>
            )}
          </div>
          <ul className="max-h-[60vh] overflow-y-auto">
            {datos.avisos.length === 0 && <li className="px-4 py-8 text-center text-sm text-gris">No tienes avisos todavía.</li>}
            {datos.avisos.map((a) => (
              <li key={a.id}>
                <button type="button" onClick={() => abrir(a)}
                  className={cx("flex w-full gap-3 border-b border-linea-suave px-4 py-3 text-left hover:bg-fondo", !a.leida && "bg-amarillo-50/50")}>
                  <span className={cx("mt-1.5 size-2 shrink-0 rounded-full", a.leida ? "bg-transparent" : a.tipo === "DEVUELTA" ? "bg-rojo" : "bg-azul")} />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-tinta">{a.titulo}</span>
                    {a.mensaje && <span className="mt-0.5 block line-clamp-2 text-[13px] text-gris">{a.mensaje}</span>}
                    <span className="mt-0.5 block text-xs text-gris">{hace(a.fecha)}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function MenuUsuario({ usuario, logout }) {
  const navigate = useNavigate();
  return (
    <div className="border-t border-white/10 p-3">
      <div className="flex items-center gap-3 rounded-lg px-2 py-2">
        <Avatar nombre={usuario.nombre} tam="sm" className="bg-white/10 text-white" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-white">{usuario.nombre}</p>
          <p className="truncate text-xs text-white/60">{usuario.puesto || (usuario.es_administrador ? "Administración" : "Sin puesto asignado")}</p>
        </div>
      </div>
      <div className="mt-1 grid grid-cols-2 gap-1">
        <Link to="/mi-cuenta" data-guia="cuenta" className="flex items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-xs text-white/75 hover:bg-white/10 hover:text-white">
          <KeyRound className="size-3.5" /> Mi cuenta
        </Link>
        <button type="button" onClick={async () => { await logout(); navigate("/entrar"); }}
          className="flex items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-xs text-white/75 hover:bg-white/10 hover:text-white">
          <LogOut className="size-3.5" /> Salir
        </button>
      </div>
    </div>
  );
}

function Enlace({ item, cuentas, onClick }) {
  const n = item.cuenta ? cuentas[item.cuenta] : 0;
  return (
    <NavLink to={item.a} end={item.fin} onClick={onClick}
      className={({ isActive }) => cx(
        "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-[14px] transition-colors",
        isActive ? "bg-white/10 font-medium text-white before:absolute before:inset-y-2 before:-left-3 before:w-1 before:rounded-r before:bg-amarillo" : "text-white/70 hover:bg-white/5 hover:text-white"
      )}>
      <item.icono className="size-[18px] shrink-0" aria-hidden />
      <span className="flex-1">{item.texto}</span>
      {n > 0 && <span className="rounded-full bg-amarillo px-1.5 text-xs font-semibold text-tinta num">{n}</span>}
    </NavLink>
  );
}

/** Botón «Crear»: lo que más se hace, a un toque desde cualquier pantalla. */
function Crear({ sesion }) {
  const [abierto, setAbierto] = useState(false);
  const navigate = useNavigate();
  const ref = useRef(null);
  useEffect(() => {
    if (!abierto) return undefined;
    const fuera = (e) => ref.current && !ref.current.contains(e.target) && setAbierto(false);
    document.addEventListener("mousedown", fuera);
    return () => document.removeEventListener("mousedown", fuera);
  }, [abierto]);
  const opciones = [
    { texto: "Orden de trabajo (F-01)", sub: "Se entrega a Coordinación para el G0", a: "/ordenes?nueva=1", icono: ClipboardList },
    sesion.puedeValidar && { texto: "Tarea para mi equipo", sub: "Con pasos, fecha y responsable", a: "/equipo?ver=tareas&nueva=1", icono: ListChecks },
    (sesion.gestiona || sesion.esFinanzas) && { texto: "Proyecto", sub: "Agrupa tareas y órdenes", a: "/proyectos?nuevo=1", icono: FolderKanban },
    { texto: "Cliente", sub: "Datos de contacto", a: "/clientes?nuevo=1", icono: Building },
    sesion.esFinanzas && { texto: "Cotización", sub: "Con ITBIS calculado", a: "/finanzas?ver=cotizaciones&nueva=1", icono: Wallet },
    sesion.gestionaCallCenter && { texto: "Campaña de call center", sub: "Metas, horario y agentes", a: "/call-center?nueva=1", icono: Headset },
  ].filter(Boolean);
  return (
    <div className="relative" ref={ref} data-guia="crear">
      <button type="button" onClick={() => setAbierto((a) => !a)} aria-expanded={abierto} aria-label="Crear"
        className="flex h-10 items-center gap-1.5 rounded-lg bg-amarillo px-3 text-sm font-semibold text-tinta hover:bg-amarillo-600">
        <Plus className="size-4" /><span className="hidden sm:inline">Crear</span>
      </button>
      {abierto && (
        <ul className="absolute right-0 top-12 z-50 w-72 overflow-hidden rounded-xl border border-linea bg-white p-1.5 shadow-xl">
          {opciones.map((o) => (
            <li key={o.a}><button type="button" onClick={() => { setAbierto(false); navigate(o.a); }} className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left hover:bg-fondo">
              <span className="flex size-9 items-center justify-center rounded-lg bg-azul/10 text-azul"><o.icono className="size-4" /></span>
              <span><span className="block text-sm font-medium">{o.texto}</span><span className="block text-xs text-gris">{o.sub}</span></span></button></li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** El cronómetro corriendo, siempre visible arriba. */
function CronometroBarra() {
  const { activo, segundos, detener } = useCronometro();
  const navigate = useNavigate();
  if (!activo) return null;
  return (
    <div className="flex h-10 items-center overflow-hidden rounded-lg border border-rojo/30 bg-rojo-50">
      <button type="button" onClick={() => navigate("/tiempo")} className="flex h-full min-w-0 items-center gap-2 pl-3 pr-2 text-sm" title={nombreRegistro(activo)}>
        <span className="relative flex size-2"><span className="absolute inline-flex size-full animate-ping rounded-full bg-rojo opacity-60" /><span className="relative inline-flex size-2 rounded-full bg-rojo" /></span>
        <span className="hidden max-w-40 truncate lg:inline">{nombreRegistro(activo)}</span>
        <span className="font-semibold num">{relojSeg(segundos)}</span>
      </button>
      <button type="button" onClick={detener} className="flex h-full items-center border-l border-rojo/20 px-2.5 text-rojo hover:bg-rojo/10" aria-label="Detener cronómetro"><Square className="size-4 fill-current" /></button>
    </div>
  );
}

export default function Estructura() {
  return <CronometroProvider><GuiaProvider><EstructuraInterna /></GuiaProvider></CronometroProvider>;
}

function EstructuraInterna() {
  const sesion = useSesion();
  const { usuario, logout } = sesion;
  const guia = useGuia();
  const [datos, refrescar] = useAvisos();
  const [mas, setMas] = useState(false);
  const [buscando, setBuscando] = useState(false);
  const location = useLocation();
  useEffect(() => {
    const tecla = (e) => {
      const escribiendo = /input|textarea|select/i.test(document.activeElement?.tagName || "") || document.activeElement?.isContentEditable;
      if ((e.key === "k" && (e.ctrlKey || e.metaKey)) || (e.key === "/" && !escribiendo)) { e.preventDefault(); setBuscando(true); }
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, []);
  const grupos = secciones(sesion);
  useEffect(() => { setMas(false); }, [location.pathname]);

  // Barra inferior del celular: lo del día a día; el resto en «Más».
  const inferior = sesion.esAgente ? [{ a: "/call-center", texto: "Call Center", icono: Headset }] : [
    { a: "/", texto: "Inicio", icono: House, fin: true },
    { a: "/mis-tareas", texto: "Mis tareas", icono: ListChecks },
    { a: "/ordenes", texto: "Órdenes", icono: ClipboardList },
  ];
  if (sesion.esAgente) { /* nada más: el resto queda en «Más» */ } else if (sesion.puedeValidar) inferior.push({ a: "/validar", texto: "Validar", icono: CircleCheckBig, cuenta: "por_validar" });
  else inferior.push({ a: "/tiempo", texto: "Tiempo", icono: Clock });
  const usados = new Set(inferior.map((i) => i.a));
  const resto = grupos.flatMap((g) => g.items).filter((i) => !usados.has(i.a));

  return (
    <div className="min-h-dvh lg:pl-64">
      {/* PC (desde 1024 px): menú lateral fijo. En tablet no cabe junto al contenido: usa la barra inferior */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col bg-noche lg:flex">
        <div className="flex h-16 items-center px-5"><Link to="/" aria-label="Inicio"><Marca /></Link></div>
        <nav className="scroll-oscuro flex-1 overflow-y-auto px-3 pb-4" aria-label="Menú principal" data-guia="menu">
          {grupos.map((g) => (
            <div key={g.titulo} className="mt-4 first:mt-1">
              <p className="px-3 pb-1.5 text-xs font-medium text-white/45">{g.titulo}</p>
              <div className="space-y-0.5">{g.items.map((i) => <Enlace key={i.a} item={i} cuentas={datos} />)}</div>
            </div>
          ))}
        </nav>
        <MenuUsuario usuario={usuario} logout={logout} />
      </aside>

      {/* Barra superior: campanita (PC) y marca + campanita (celular) */}
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-2 border-b border-linea bg-fondo/90 px-4 backdrop-blur lg:h-16 lg:px-8">
        <Link to="/" className="lg:hidden" aria-label="Inicio"><Marca oscuro={false} className="text-[15px]" /></Link>
        <button type="button" onClick={() => setBuscando(true)} data-guia="buscar" className="hidden h-10 w-full max-w-sm items-center gap-2 rounded-lg border border-linea bg-white px-3 text-sm text-gris hover:border-azul/40 lg:flex">
          <Search className="size-4" /> <span className="truncate">Buscar órdenes, clientes, tareas…</span><kbd className="ml-auto hidden shrink-0 whitespace-nowrap rounded border border-linea px-1.5 text-xs xl:inline">Ctrl K</kbd>
        </button>
        <div className="flex items-center gap-1.5 lg:gap-2">
          <BotonJornada />
          <CronometroBarra />
          <button type="button" onClick={() => setBuscando(true)} data-guia="buscar-movil" className="flex size-10 items-center justify-center rounded-lg text-gris hover:bg-white lg:hidden" aria-label="Buscar"><Search className="size-5" /></button>
          {/* El botón «Crear» es para quien dirige o gestiona; el empleado solo trabaja lo que le asignan */}
          {!sesion.esAgente && (sesion.esAdmin || sesion.puedeValidar || sesion.gestiona || sesion.esFinanzas || sesion.esCoordinacion || sesion.gestionaCallCenter) && <Crear sesion={sesion} />}
          <Campanita datos={datos} refrescar={refrescar} />
          <button type="button" onClick={guia.abrirAyuda} data-guia="ayuda" aria-label="Ayuda: guía paso a paso" title="Ayuda"
            className="flex size-10 items-center justify-center rounded-lg text-gris hover:bg-white hover:text-azul">
            <CircleHelp className="size-5" />
          </button>
        </div>
      </header>
      <Buscador abierto={buscando} onCerrar={() => setBuscando(false)} />

      <Recordatorio datos={datos} refrescar={refrescar} />

      {usuario?.politicas_pendientes > 0 && !location.pathname.startsWith("/politicas") && (
        <div className="border-b border-amarillo-600/30 bg-amarillo-50 px-4 py-2 text-center text-sm text-[#7a5000]">
          Tienes {usuario.politicas_pendientes} política(s) por leer y aceptar. <Link to="/politicas" className="font-semibold underline">Revisar ahora</Link>
        </div>
      )}

      <main className="mx-auto w-full max-w-[1320px] px-4 pb-28 pt-5 md:px-6 lg:px-8 lg:pb-12 lg:pt-7">
        <SugerenciaApp />
        <Outlet context={{ refrescarAvisos: refrescar }} />
      </main>

      {/* Celular: barra inferior tipo app */}
      <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-linea bg-white lg:hidden" style={{ paddingBottom: "env(safe-area-inset-bottom)" }} aria-label="Menú" data-guia="menu-movil">
        <div className="flex">
          {inferior.map((i) => {
            const n = i.cuenta ? datos[i.cuenta] : 0;
            return (
              <NavLink key={i.a} to={i.a} end={i.fin} className={({ isActive }) => cx("relative flex min-h-14 flex-1 flex-col items-center justify-center gap-0.5 text-[11px] font-medium", isActive ? "text-azul" : "text-gris")}>
                {({ isActive }) => (<>
                  <span className={cx("absolute top-0 h-0.5 w-8 rounded-b", isActive ? "bg-amarillo" : "bg-transparent")} />
                  <span className="relative"><i.icono className="size-6" aria-hidden />
                    {n > 0 && <span className="absolute -right-2.5 -top-1 rounded-full bg-rojo px-1 text-[10px] leading-4 text-white num">{n}</span>}
                  </span>
                  {i.texto}
                </>)}
              </NavLink>
            );
          })}
          <button type="button" onClick={() => setMas(true)} className="flex min-h-14 flex-1 flex-col items-center justify-center gap-0.5 text-[11px] font-medium text-gris">
            <Ellipsis className="size-6" aria-hidden /> Más
          </button>
        </div>
      </nav>

      {/* Celular: hoja «Más» */}
      {mas && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Más opciones">
          <button type="button" className="absolute inset-0 bg-noche-900/50" aria-label="Cerrar" onClick={() => setMas(false)} />
          <div className="absolute inset-x-0 bottom-0 rounded-t-2xl bg-noche pb-[env(safe-area-inset-bottom)]">
            <div className="flex items-center justify-between px-5 pt-4"><Marca /><button type="button" onClick={() => setMas(false)} className="rounded-lg p-2 text-white/70" aria-label="Cerrar"><X className="size-5" /></button></div>
            <nav className="max-h-[60dvh] space-y-0.5 overflow-y-auto px-3 py-3">{resto.map((i) => <Enlace key={i.a} item={i} cuentas={datos} />)}</nav>
            <MenuUsuario usuario={usuario} logout={logout} />
          </div>
        </div>
      )}
    </div>
  );
}
