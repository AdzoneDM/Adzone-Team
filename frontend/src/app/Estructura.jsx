// Estructura de la app: menú lateral en la PC, barra inferior en el celular, campanita de avisos.
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Bell, Building2, ChartNoAxesColumn, CircleCheckBig, ClipboardList, Ellipsis, House, KeyRound, ListChecks, LogOut,
  BellRing, Network, Settings2, SquarePen, Target, Trophy, Users, X,
} from "lucide-react";
import { avisos as cargarAvisos, leerAvisos } from "@/lib/api";
import { hace } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import Marca from "@/components/Marca";
import { Avatar, cx } from "@/components/ui";

function secciones({ esAdmin, puedeValidar }) {
  const s = [
    { titulo: "Mi trabajo", items: [
      { a: "/", texto: "Inicio", icono: House, fin: true },
      { a: "/mis-tareas", texto: "Mis tareas", icono: ListChecks },
    ] },
  ];
  if (puedeValidar) {
    s.push({ titulo: "Mi equipo", items: [
      { a: "/validar", texto: "Por validar", icono: CircleCheckBig, cuenta: "por_validar" },
      { a: "/equipo", texto: "Equipo y tareas", icono: ClipboardList },
    ] });
  }
  if (esAdmin) {
    s.push({ titulo: "Resultados", items: [
      { a: "/desempeno", texto: "Desempeño y ranking", icono: Trophy },
      { a: "/kpis-del-mes", texto: "KPIs del mes", icono: SquarePen },
    ] });
    s.push({ titulo: "Administración", items: [
      { a: "/organigrama", texto: "Organigrama", icono: Network },
      { a: "/puestos", texto: "Departamentos y puestos", icono: Building2 },
      { a: "/personas", texto: "Personas", icono: Users },
      { a: "/plantillas-kpi", texto: "Plantillas de KPI", icono: Target },
      { a: "/configuracion", texto: "Reglas del puntaje", icono: Settings2 },
    ] });
  } else {
    s[0].items.push({ a: "/organigrama", texto: "Organigrama", icono: Network });
  }
  return s;
}

/** Dos tonos cortos y una vibración: para que un «Recordar» del supervisor no pase desapercibido. */
function sonarAviso() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    const ctx = new Ctx();
    [[880, 0], [1175, 0.18]].forEach(([hz, t]) => {
      const o = ctx.createOscillator(); const g = ctx.createGain();
      o.frequency.value = hz; o.type = "sine";
      g.gain.setValueAtTime(0.0001, ctx.currentTime + t);
      g.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + t + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + t + 0.16);
      o.connect(g).connect(ctx.destination); o.start(ctx.currentTime + t); o.stop(ctx.currentTime + t + 0.2);
    });
    setTimeout(() => ctx.close(), 800);
  } catch { /* el navegador no deja sonar sin tocar la pantalla primero */ }
  try { navigator.vibrate?.([120, 80, 120]); } catch { /* sin vibración */ }
}

function useAvisos() {
  const [datos, setDatos] = useState({ no_leidas: 0, avisos: [], por_validar: 0 });
  const vistos = useRef(null);
  const refrescar = useCallback(() => cargarAvisos().then((d) => {
    const recordatorios = d.avisos.filter((a) => a.tipo === "RECORDATORIO" && !a.leida).map((a) => a.id);
    if (vistos.current && recordatorios.some((id) => !vistos.current.has(id))) sonarAviso();
    vistos.current = new Set(recordatorios);
    setDatos(d);
  }).catch(() => {}), []);
  useEffect(() => {
    refrescar();
    const t = setInterval(() => { if (document.visibilityState === "visible") refrescar(); }, 30000);
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
  if (!pendientes.length) return null;
  const a = pendientes[0];
  const entendido = async (ir) => {
    try { await leerAvisos(pendientes.map((x) => x.id)); } catch { /* se reintenta en el próximo refresco */ }
    refrescar();
    if (ir && a.enlace) navigate(a.tarea ? `${a.enlace}?tarea=${a.tarea}` : a.enlace);
  };
  return (
    <div className="sticky top-14 z-20 border-b border-amarillo bg-amarillo-50 md:top-16" role="alert">
      <div className="mx-auto flex max-w-[1320px] flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 md:px-8">
        <BellRing className="size-5 shrink-0 animate-[pulse_1.5s_ease-in-out_3] text-[#a86a00]" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="font-medium text-tinta">{a.titulo}{pendientes.length > 1 && <span className="font-normal text-gris"> · y {pendientes.length - 1} más</span>}</p>
          {a.mensaje && <p className="text-sm text-[#5c3d00]">{a.mensaje}</p>}
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={() => entendido(false)} className="min-h-10 rounded-lg px-3 text-sm font-medium text-[#5c3d00] hover:bg-amarillo/30">Entendido</button>
          {a.enlace && <button type="button" onClick={() => entendido(true)} className="min-h-10 rounded-lg bg-noche px-3.5 text-sm font-medium text-white">Ver tarea</button>}
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
    <div className="relative" ref={ref}>
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
        <Link to="/mi-cuenta" className="flex items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-xs text-white/75 hover:bg-white/10 hover:text-white">
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

export default function Estructura() {
  const sesion = useSesion();
  const { usuario, logout } = sesion;
  const [datos, refrescar] = useAvisos();
  const [mas, setMas] = useState(false);
  const location = useLocation();
  const grupos = secciones(sesion);
  useEffect(() => { setMas(false); }, [location.pathname]);

  // Barra inferior del celular: lo del día a día; el resto en «Más».
  const inferior = [
    { a: "/", texto: "Inicio", icono: House, fin: true },
    { a: "/mis-tareas", texto: "Mis tareas", icono: ListChecks },
  ];
  if (sesion.puedeValidar) inferior.push({ a: "/validar", texto: "Validar", icono: CircleCheckBig, cuenta: "por_validar" });
  if (sesion.esAdmin) inferior.push({ a: "/desempeno", texto: "Ranking", icono: ChartNoAxesColumn });
  else if (sesion.puedeValidar) inferior.push({ a: "/equipo", texto: "Equipo", icono: ClipboardList });
  const usados = new Set(inferior.map((i) => i.a));
  const resto = grupos.flatMap((g) => g.items).filter((i) => !usados.has(i.a));

  return (
    <div className="min-h-dvh md:pl-64">
      {/* PC: menú lateral fijo */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col bg-noche md:flex">
        <div className="flex h-16 items-center px-5"><Link to="/" aria-label="Inicio"><Marca /></Link></div>
        <nav className="flex-1 overflow-y-auto px-3 pb-4" aria-label="Menú principal">
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
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-linea bg-fondo/90 px-4 backdrop-blur md:h-16 md:justify-end md:px-8">
        <Link to="/" className="md:hidden" aria-label="Inicio"><Marca oscuro={false} className="text-[15px]" /></Link>
        <div className="flex items-center gap-2">
          <span className="hidden text-sm text-gris md:inline">{usuario.departamento}</span>
          <Campanita datos={datos} refrescar={refrescar} />
        </div>
      </header>

      <Recordatorio datos={datos} refrescar={refrescar} />

      <main className="mx-auto w-full max-w-[1320px] px-4 pb-28 pt-5 md:px-8 md:pb-12 md:pt-7">
        <Outlet context={{ refrescarAvisos: refrescar }} />
      </main>

      {/* Celular: barra inferior tipo app */}
      <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-linea bg-white md:hidden" style={{ paddingBottom: "env(safe-area-inset-bottom)" }} aria-label="Menú">
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
        <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-modal="true" aria-label="Más opciones">
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
