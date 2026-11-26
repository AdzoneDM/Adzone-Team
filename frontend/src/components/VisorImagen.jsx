// Visor de imágenes dentro de la plataforma (no abre otra pestaña): vista previa a pantalla completa, agrandar y achicar
// (botones, rueda del mouse, doble clic o doble toque, pellizco en el celular), arrastrar para moverse por la imagen ampliada,
// pasar a la anterior/siguiente (flechas, teclado o deslizando) y descargar. Esc o la X lo cierran.
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Download, Maximize2, Minus, Plus, X } from "lucide-react";
import { cx } from "@/components/ui";

const VisorCtx = createContext(() => {});
/** `ver(imagenes, indice)` — imagenes: [{ src, nombre?, descargar? }] (o una sola). */
export const useVisor = () => useContext(VisorCtx);

const MIN = 1, MAX = 8;
const limitar = (v, a, b) => Math.min(b, Math.max(a, v));

export function VisorProvider({ children }) {
  const [estado, setEstado] = useState(null);   // { lista, i }
  const ver = useCallback((imagenes, indice = 0) => {
    const lista = (Array.isArray(imagenes) ? imagenes : [imagenes]).filter((x) => x?.src);
    if (lista.length) setEstado({ lista, i: Math.min(Math.max(indice, 0), lista.length - 1) });
  }, []);
  return (
    <VisorCtx.Provider value={ver}>
      {children}
      {estado && <Visor lista={estado.lista} inicio={estado.i} onCerrar={() => setEstado(null)} />}
    </VisorCtx.Provider>
  );
}

function Visor({ lista, inicio, onCerrar }) {
  const [i, setI] = useState(inicio);
  const [zoom, setZoom] = useState(1);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const [cargando, setCargando] = useState(true);
  const caja = useRef(null);
  const imagen = useRef(null);
  const punteros = useRef(new Map());
  const gesto = useRef(null);
  const ultimoToque = useRef(0);
  const actual = lista[i];
  const varias = lista.length > 1;

  const reiniciar = () => { setZoom(1); setPos({ x: 0, y: 0 }); };
  const ir = useCallback((d) => { if (!varias) return; setI((n) => (n + d + lista.length) % lista.length); setZoom(1); setPos({ x: 0, y: 0 }); setCargando(true); }, [varias, lista.length]);

  // Zoom hacia un punto (el cursor o el centro del pellizco), para que lo que se mira no se escape
  const zoomEn = useCallback((nuevo, cx0, cy0) => {
    const el = caja.current;
    setZoom((z) => {
      const z2 = limitar(nuevo(z), MIN, MAX);
      if (z2 === 1) { setPos({ x: 0, y: 0 }); return 1; }
      if (el && cx0 != null) {
        const r = el.getBoundingClientRect();
        const px = cx0 - (r.left + r.width / 2), py = cy0 - (r.top + r.height / 2);
        setPos((p) => ({ x: px - ((px - p.x) * z2) / z, y: py - ((py - p.y) * z2) / z }));
      } else setPos((p) => ({ x: (p.x * z2) / z, y: (p.y * z2) / z }));
      return z2;
    });
  }, []);

  useEffect(() => {
    const tecla = (e) => {
      if (e.key === "Escape") onCerrar();
      else if (e.key === "ArrowRight") ir(1);
      else if (e.key === "ArrowLeft") ir(-1);
      else if (e.key === "+" || e.key === "=") zoomEn((z) => z * 1.5);
      else if (e.key === "-") zoomEn((z) => z / 1.5);
      else if (e.key === "0") reiniciar();
    };
    window.addEventListener("keydown", tecla);
    const previo = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", tecla); document.body.style.overflow = previo; };
  }, [ir, onCerrar, zoomEn]);

  useEffect(() => {   // la rueda hace zoom (no desplaza la página de fondo)
    const el = caja.current;
    if (!el) return undefined;
    const rueda = (e) => { e.preventDefault(); zoomEn((z) => z * (e.deltaY < 0 ? 1.2 : 1 / 1.2), e.clientX, e.clientY); };
    el.addEventListener("wheel", rueda, { passive: false });
    return () => el.removeEventListener("wheel", rueda);
  }, [zoomEn]);

  const abajo = (e) => {
    caja.current?.setPointerCapture?.(e.pointerId);
    punteros.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const ps = [...punteros.current.values()];
    if (ps.length === 2) {
      gesto.current = { tipo: "pellizco", dist: Math.hypot(ps[0].x - ps[1].x, ps[0].y - ps[1].y), zoom };
    } else {
      gesto.current = { tipo: "mover", x: e.clientX, y: e.clientY, pos, inicio: { x: e.clientX, y: e.clientY }, t: Date.now() };
    }
  };
  const mover = (e) => {
    if (!punteros.current.has(e.pointerId)) return;
    punteros.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const g = gesto.current;
    if (!g) return;
    if (g.tipo === "pellizco") {
      const ps = [...punteros.current.values()];
      if (ps.length < 2) return;
      const d = Math.hypot(ps[0].x - ps[1].x, ps[0].y - ps[1].y);
      zoomEn(() => g.zoom * (d / g.dist), (ps[0].x + ps[1].x) / 2, (ps[0].y + ps[1].y) / 2);
    } else if (zoom > 1) {
      setPos({ x: g.pos.x + e.clientX - g.x, y: g.pos.y + e.clientY - g.y });
    }
  };
  const arriba = (e) => {
    const g = gesto.current;
    punteros.current.delete(e.pointerId);
    if (punteros.current.size === 0) gesto.current = null;
    if (!g || g.tipo !== "mover") return;
    const dx = e.clientX - g.inicio.x, dy = e.clientY - g.inicio.y;
    if (zoom === 1 && Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) { ir(dx < 0 ? 1 : -1); return; }   // deslizar: siguiente/anterior
    if (Math.abs(dx) < 6 && Math.abs(dy) < 6) {
      const ahora = Date.now();
      if (ahora - ultimoToque.current < 300) {   // doble toque / doble clic: agrandar ahí o volver a ajustar
        ultimoToque.current = 0;
        if (zoom > 1) reiniciar(); else zoomEn(() => 2.5, e.clientX, e.clientY);
      } else {
        ultimoToque.current = ahora;
        const r = imagen.current?.getBoundingClientRect();
        const fuera = !r || e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom;
        if (zoom === 1 && fuera) onCerrar();   // un toque fuera de la imagen cierra
      }
    }
  };

  const boton = "inline-flex size-10 items-center justify-center rounded-full text-white/90 hover:bg-white/15 hover:text-white disabled:opacity-40";
  return (
    <div role="dialog" aria-modal="true" aria-label={`Imagen: ${actual.nombre || "vista previa"}`} className="fixed inset-0 z-[95] flex flex-col bg-[#0b0d12] text-white">
      <div className="flex shrink-0 items-center gap-1 px-2 py-2 pt-[max(0.5rem,env(safe-area-inset-top))] sm:px-4">
        <p className="min-w-0 flex-1 truncate px-2 text-sm font-medium">{actual.nombre || "Imagen"}{varias && <span className="ml-2 text-white/60 num">{i + 1} / {lista.length}</span>}</p>
        <button type="button" className={boton} onClick={() => zoomEn((z) => z / 1.5)} disabled={zoom <= MIN} aria-label="Achicar" title="Achicar (−)"><Minus className="size-5" /></button>
        <button type="button" className="hidden min-w-14 rounded-full px-2 py-2 text-sm text-white/90 hover:bg-white/15 sm:inline num" onClick={reiniciar} title="Ajustar a la pantalla (0)">{Math.round(zoom * 100)} %</button>
        <button type="button" className={boton} onClick={() => zoomEn((z) => z * 1.5)} disabled={zoom >= MAX} aria-label="Agrandar" title="Agrandar (+)"><Plus className="size-5" /></button>
        <button type="button" className={boton} onClick={reiniciar} aria-label="Ajustar a la pantalla" title="Ajustar a la pantalla"><Maximize2 className="size-5" /></button>
        <a href={actual.descargar || actual.src} download={actual.nombre || true} className={boton} aria-label="Descargar" title="Descargar"><Download className="size-5" /></a>
        <button type="button" className={boton} onClick={onCerrar} aria-label="Cerrar la imagen" title="Cerrar (Esc)" autoFocus><X className="size-6" /></button>
      </div>
      <div ref={caja} className={cx("relative min-h-0 flex-1 touch-none select-none overflow-hidden", zoom > 1 ? "cursor-grab active:cursor-grabbing" : "cursor-zoom-in")}
        onPointerDown={abajo} onPointerMove={mover} onPointerUp={arriba} onPointerCancel={arriba}>
        {cargando && <span className="absolute inset-0 m-auto size-8 animate-spin rounded-full border-2 border-white/30 border-t-white" aria-hidden />}
        <img ref={imagen} key={actual.src} src={actual.src} alt={actual.nombre || ""} draggable={false} onLoad={() => setCargando(false)} onError={() => setCargando(false)}
          className="pointer-events-none absolute inset-0 m-auto max-h-full max-w-full object-contain p-2 sm:p-6"
          style={{ transform: `translate(${pos.x}px, ${pos.y}px) scale(${zoom})`, transition: gesto.current ? "none" : "transform 120ms ease-out" }} />
        {varias && (
          <>
            <button type="button" onPointerDown={(e) => e.stopPropagation()} onPointerUp={(e) => e.stopPropagation()} onClick={() => ir(-1)} aria-label="Imagen anterior"
              className="absolute left-2 top-1/2 hidden size-11 -translate-y-1/2 items-center justify-center rounded-full bg-black/50 text-white hover:bg-black/70 sm:flex"><ChevronLeft className="size-6" /></button>
            <button type="button" onPointerDown={(e) => e.stopPropagation()} onPointerUp={(e) => e.stopPropagation()} onClick={() => ir(1)} aria-label="Imagen siguiente"
              className="absolute right-2 top-1/2 hidden size-11 -translate-y-1/2 items-center justify-center rounded-full bg-black/50 text-white hover:bg-black/70 sm:flex"><ChevronRight className="size-6" /></button>
          </>
        )}
      </div>
      <p className="shrink-0 px-4 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-1 text-center text-xs text-white/50">
        <span className="hidden sm:inline">Rueda del mouse o doble clic para agrandar · arrastra para moverte · ← → para pasar · Esc para cerrar</span>
        <span className="sm:hidden">Pellizca o toca dos veces para agrandar{varias ? " · desliza para pasar" : ""}</span>
      </p>
    </div>
  );
}
