// Guía paso a paso: el recorrido de bienvenida (sale solo la primera vez), la guía de cada pantalla
// y los «¿Cómo hago…?». Resalta en la pantalla lo que explica y lleva a la pantalla que hace falta.
import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowRight, Compass, Lightbulb, MapPin, X } from "lucide-react";
import { Modal, cx } from "@/components/ui";
import { useSesion } from "@/lib/sesion";
import { RECETAS, guiaDePantalla, recorridoGeneral } from "@/lib/guia";

const GuiaCtx = createContext(null);
export const useGuia = () => useContext(GuiaCtx);

// Lo que ya vio cada persona, en este navegador. Sin almacenamiento (modo privado) la guía funciona igual.
function useMemoria(usuarioId) {
  const clave = `adzone:guia:${usuarioId}`;
  const leer = () => {
    try { return { general: false, vistas: [], sugerencias: true, ...JSON.parse(localStorage.getItem(clave) || "{}") }; }
    catch { return { general: false, vistas: [], sugerencias: true }; }
  };
  const [memoria, setMemoria] = useState(leer);
  const guardar = useCallback((cambio) => setMemoria((m) => {
    const nueva = { ...m, ...(typeof cambio === "function" ? cambio(m) : cambio) };
    try { localStorage.setItem(clave, JSON.stringify(nueva)); } catch { /* sin almacenamiento */ }
    return nueva;
  }), [clave]);
  return [memoria, guardar];
}

const filtrar = (lista, sesion) => lista.filter((x) => !x.para || x.para(sesion));

function visible(el) {
  if (!el?.getClientRects().length) return false;
  const r = el.getBoundingClientRect();
  return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== "hidden";
}

function buscarObjetivo(objetivo) {
  if (!objetivo) return null;
  for (const sel of [].concat(objetivo)) {
    const el = [...document.querySelectorAll(sel)].find(visible);
    if (el) return el;
  }
  return null;
}

/** Dónde poner la tarjeta: debajo, arriba, a la derecha o a la izquierda de lo resaltado; si no cabe, abajo al centro. */
function ubicar(r, ancho, alto) {
  const vw = window.innerWidth, vh = window.innerHeight, m = 12, sep = 14;
  const x = Math.min(Math.max(m, r.left + r.width / 2 - ancho / 2), vw - ancho - m);
  const y = Math.min(Math.max(m, r.top + r.height / 2 - alto / 2), vh - alto - m);
  if (r.bottom + sep + alto <= vh - m) return { left: x, top: r.bottom + sep };
  if (r.top - sep - alto >= m) return { left: x, top: r.top - sep - alto };
  if (r.right + sep + ancho <= vw - m) return { left: r.right + sep, top: y };
  if (r.left - sep - ancho >= m) return { left: r.left - sep - ancho, top: y };
  return { left: (vw - ancho) / 2, top: vh - alto - m };
}

function Recorrido({ pasos, indice, onIr, onCerrar }) {
  const paso = pasos[indice];
  const navigate = useNavigate();
  const location = useLocation();
  const [rect, setRect] = useState(null);
  const [listo, setListo] = useState(false);
  const [pos, setPos] = useState(null);
  const tarjeta = useRef(null);
  const objetivo = useRef(null);
  const ultimo = indice === pasos.length - 1;

  // Ir a la pantalla del paso y esperar a que aparezca lo que hay que resaltar (las pantallas cargan al abrirlas).
  useEffect(() => {
    setListo(false);
    objetivo.current = null;
    if (paso.ruta && location.pathname !== paso.ruta) { navigate(paso.ruta); return undefined; }
    let intentos = 0;
    const t = setInterval(() => {
      const el = buscarObjetivo(paso.objetivo);
      if (el || !paso.objetivo || ++intentos > 30) {
        clearInterval(t);
        objetivo.current = el;
        if (el) {
          const r = el.getBoundingClientRect();
          if (r.top < 70 || r.bottom > window.innerHeight - 80) el.scrollIntoView({ block: "center" });
        }
        setListo(true);
      }
    }, 100);
    return () => clearInterval(t);
  }, [paso, location.pathname, navigate]);

  const medir = useCallback(() => {
    const el = objetivo.current;
    setRect(el && el.isConnected && visible(el) ? el.getBoundingClientRect() : null);
  }, []);

  useEffect(() => {
    if (!listo) return undefined;
    medir();
    window.addEventListener("resize", medir);
    window.addEventListener("scroll", medir, true);
    return () => { window.removeEventListener("resize", medir); window.removeEventListener("scroll", medir, true); };
  }, [listo, medir]);

  useLayoutEffect(() => {
    if (!listo || !tarjeta.current) return;
    const { offsetWidth: w, offsetHeight: h } = tarjeta.current;
    const r = rect && { top: rect.top - 6, bottom: rect.bottom + 6, left: rect.left - 6, right: rect.right + 6, width: rect.width + 12, height: rect.height + 12 };
    setPos(r ? ubicar(r, w, h) : { left: (window.innerWidth - w) / 2, top: Math.max(12, (window.innerHeight - h) / 2) });
  }, [listo, rect, indice]);

  useEffect(() => { if (listo) tarjeta.current?.querySelector("[data-principal]")?.focus(); }, [listo, indice]);

  useEffect(() => {
    const tecla = (e) => {
      if (e.repeat) return; // una flecha sostenida no se salta media guía
      if (e.key === "Escape") onCerrar();
      else if (e.key === "ArrowRight") { if (ultimo) onCerrar(true); else onIr(indice + 1); }
      else if (e.key === "ArrowLeft" && indice > 0) onIr(indice - 1);
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [indice, ultimo, onIr, onCerrar]);

  return createPortal(
    <div className="fixed inset-0 z-[70]" role="dialog" aria-modal="true" aria-labelledby="guia-titulo">
      {/* Capa que oscurece todo menos lo resaltado; no deja tocar la pantalla mientras dura la guía */}
      {listo && rect ? (
        <div className="pointer-events-none absolute rounded-xl ring-4 ring-amarillo transition-all duration-300 motion-reduce:transition-none"
          style={{ top: rect.top - 6, left: rect.left - 6, width: rect.width + 12, height: rect.height + 12, boxShadow: "0 0 0 9999px rgb(15 37 80 / 0.6)" }} />
      ) : <div className="absolute inset-0 bg-noche-900/60" />}

      {listo && (
        <div ref={tarjeta} style={pos ? { left: pos.left, top: pos.top } : { visibility: "hidden" }}
          className="absolute w-[min(22rem,calc(100vw-1.5rem))] overflow-hidden rounded-2xl border-t-4 border-amarillo bg-white shadow-2xl">
          <div className="px-5 pb-4 pt-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-azul num">Paso {indice + 1} de {pasos.length}</p>
              <button type="button" onClick={() => onCerrar()} className="-mr-2 rounded-lg p-1.5 text-gris hover:bg-fondo" aria-label="Cerrar la guía"><X className="size-4" /></button>
            </div>
            <h2 id="guia-titulo" className="mt-1 text-lg font-semibold leading-snug">{paso.titulo}</h2>
            <p className="mt-1.5 whitespace-pre-line text-[15px] leading-relaxed text-tinta">{paso.texto}</p>
          </div>
          <div className="flex items-center gap-2 border-t border-linea-suave bg-fondo px-4 py-3">
            <div className="mr-auto flex gap-1" aria-hidden>
              {pasos.length <= 8 && pasos.map((_, i) => <span key={i} className={cx("h-1.5 rounded-full transition-all", i === indice ? "w-4 bg-azul" : "w-1.5 bg-linea")} />)}
            </div>
            {indice > 0 && (
              <button type="button" onClick={() => onIr(indice - 1)} className="flex h-9 items-center gap-1 rounded-lg px-2.5 text-sm font-medium text-gris hover:bg-white hover:text-tinta">
                <ArrowLeft className="size-4" />Atrás
              </button>
            )}
            <button type="button" data-principal onClick={() => (ultimo ? onCerrar(true) : onIr(indice + 1))}
              className="flex h-9 items-center gap-1 rounded-lg bg-noche px-3.5 text-sm font-semibold text-white hover:bg-noche-900">
              {ultimo ? "Terminar" : <>Siguiente<ArrowRight className="size-4" /></>}
            </button>
          </div>
        </div>
      )}
    </div>,
    document.body
  );
}

function Opcion({ icono: Icono, titulo, sub, onClick }) {
  return (
    <button type="button" onClick={onClick} className="flex w-full items-center gap-3 rounded-xl border border-linea bg-white px-4 py-3 text-left hover:border-azul/40 hover:bg-fondo">
      <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-azul/10 text-azul">{Icono && <Icono className="size-4" />}</span>
      <span className="min-w-0"><span className="block font-medium">{titulo}</span>{sub && <span className="block text-sm text-gris">{sub}</span>}</span>
    </button>
  );
}

function Ayuda({ abierto, onCerrar, sesion, memoria, guardar, iniciar }) {
  const location = useLocation();
  const pantalla = guiaDePantalla(location.pathname);
  // El agente de call center no trabaja tareas ni órdenes: solo le sirven las recetas generales
  const recetas = filtrar(RECETAS, sesion).filter((r) => !sesion.esAgente || ["avisos", "instalar", "contrasena"].includes(r.id));
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo="Ayuda" descripcion="Elige una guía: te lleva a la pantalla y te muestra cada paso.">
      <div className="space-y-2">
        <Opcion icono={Compass} titulo="Recorrido de bienvenida" sub="Dónde está todo y cómo se trabaja, en un par de minutos"
          onClick={() => iniciar(filtrar(recorridoGeneral(sesion), sesion), "general")} />
        {pantalla && (
          <Opcion icono={MapPin} titulo={`Cómo usar esta pantalla: ${pantalla.nombre}`}
            onClick={() => iniciar(filtrar(pantalla.pasos, sesion), `pantalla:${pantalla.id}`)} />
        )}
      </div>
      <p className="mb-2 mt-5 text-sm font-semibold text-gris">¿Cómo hago…?</p>
      <ul className="grid gap-1.5 sm:grid-cols-2">
        {recetas.map((r) => (
          <li key={r.id}>
            <button type="button" onClick={() => iniciar(filtrar(r.pasos, sesion), `receta:${r.id}`)}
              className="flex h-full w-full items-center gap-2 rounded-lg px-3 py-2.5 text-left text-[15px] hover:bg-fondo">
              <Lightbulb className="size-4 shrink-0 text-[#a86a00]" aria-hidden />{r.titulo}
            </button>
          </li>
        ))}
      </ul>
      <label className="mt-5 flex items-start gap-2.5 border-t border-linea-suave pt-4 text-sm text-gris">
        <input type="checkbox" className="mt-0.5 size-4 accent-azul" checked={memoria.sugerencias} onChange={(e) => guardar({ sugerencias: e.target.checked })} />
        Ofrecerme la guía la primera vez que entro a cada pantalla
      </label>
    </Modal>
  );
}

/** Invitación discreta la primera vez que se entra a una pantalla con guía. */
function Sugerencia({ guia, onVer, onDescartar }) {
  return (
    <div className="fixed inset-x-3 top-[4.25rem] z-30 flex items-center gap-3 rounded-xl border border-linea bg-white py-2.5 pl-4 pr-2 shadow-lg lg:inset-x-auto lg:bottom-6 lg:left-[17rem] lg:top-auto lg:max-w-sm" role="status">
      <Lightbulb className="size-5 shrink-0 text-[#a86a00]" aria-hidden />
      <p className="min-w-0 flex-1 text-sm">¿Primera vez en <span className="font-medium">{guia.nombre}</span>?</p>
      <button type="button" onClick={onVer} className="h-9 shrink-0 rounded-lg bg-amarillo px-3 text-sm font-semibold text-tinta hover:bg-amarillo-600">Muéstrame</button>
      <button type="button" onClick={onDescartar} className="rounded-lg p-2 text-gris hover:bg-fondo" aria-label="Ahora no"><X className="size-4" /></button>
    </div>
  );
}

export function GuiaProvider({ children }) {
  const sesion = useSesion();
  const location = useLocation();
  const [memoria, guardar] = useMemoria(sesion.usuario.id);
  const [recorrido, setRecorrido] = useState(null);
  const [ayuda, setAyuda] = useState(false);

  const iniciar = useCallback((pasos, id) => {
    setAyuda(false);
    if (pasos.length) setRecorrido({ pasos, indice: 0, id });
  }, []);
  const ir = useCallback((indice) => setRecorrido((r) => r && { ...r, indice }), []);
  const cerrar = useCallback(() => {
    setRecorrido((r) => {
      if (r?.id === "general") guardar({ general: true });
      else if (r?.id?.startsWith("pantalla:")) guardar((m) => ({ vistas: [...new Set([...m.vistas, r.id.slice(9)])] }));
      return null;
    });
  }, [guardar]);

  // La primera vez que la persona entra, el recorrido de bienvenida empieza solo.
  useEffect(() => {
    if (memoria.general) return undefined;
    const t = setTimeout(() => setRecorrido((r) => r || { pasos: filtrar(recorridoGeneral(sesion), sesion), indice: 0, id: "general" }), 700);
    return () => clearTimeout(t);
  }, [memoria.general]); // eslint-disable-line react-hooks/exhaustive-deps

  const pantalla = guiaDePantalla(location.pathname);
  const sugerir = !recorrido && !ayuda && memoria.general && memoria.sugerencias && pantalla && !memoria.vistas.includes(pantalla.id);
  const descartar = () => guardar((m) => ({ vistas: [...new Set([...m.vistas, pantalla.id])] }));

  return (
    <GuiaCtx.Provider value={{ iniciar, abrirAyuda: () => setAyuda(true) }}>
      {children}
      {sugerir && <Sugerencia guia={pantalla} onDescartar={descartar}
        onVer={() => iniciar(filtrar(pantalla.pasos, sesion), `pantalla:${pantalla.id}`)} />}
      <Ayuda abierto={ayuda} onCerrar={() => setAyuda(false)} sesion={sesion} memoria={memoria} guardar={guardar} iniciar={iniciar} />
      {recorrido && <Recorrido key={recorrido.id} pasos={recorrido.pasos} indice={recorrido.indice} onIr={ir} onCerrar={cerrar} />}
    </GuiaCtx.Provider>
  );
}
