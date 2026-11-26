// Campo con autocompletado: se escribe, aparecen las coincidencias reales (sin importar mayúsculas ni tildes) y se elige
// con el mouse o con las flechas + Enter. Lo elegido queda como una ficha con una X para quitarlo.
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Check, ChevronDown, Plus, Search, X } from "lucide-react";
import { cx } from "@/components/ui";

const normal = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

/**
 * opciones: [{ id, texto, sub? }] · valor: id elegido (o "") · onCambio(id, opcion)
 * onCrear(texto): opcional; si no hay una coincidencia exacta, ofrece «Registrar «texto»».
 */
export default function Autocompletar({ etiqueta, ayuda, opciones = [], valor, onCambio, onCrear, textoCrear = "Registrar", placeholder = "Escribe para buscar…",
  vacio = "Sin coincidencias", cargando = false, disabled = false, requerido = false, error }) {
  const id = useId();
  const [texto, setTexto] = useState("");
  const [abierto, setAbierto] = useState(false);
  const [activo, setActivo] = useState(0);
  const caja = useRef(null);
  const entrada = useRef(null);
  const elegido = opciones.find((o) => String(o.id) === String(valor));
  const t = normal(texto);
  const lista = useMemo(() => {
    const l = t ? opciones.filter((o) => normal(`${o.texto} ${o.sub || ""}`).includes(t)) : opciones;
    // primero las que empiezan con lo escrito
    return [...l].sort((a, b) => Number(normal(b.texto).startsWith(t)) - Number(normal(a.texto).startsWith(t))).slice(0, 50);
  }, [opciones, t]);
  const exacta = opciones.some((o) => normal(o.texto) === t);
  const puedeCrear = onCrear && t.length >= 2 && !exacta && lista.length === 0;   // con parecidos a la vista, no se ofrece crear (evita duplicados)
  const total = lista.length + (puedeCrear ? 1 : 0);

  useEffect(() => {
    if (!abierto) return undefined;
    const fuera = (e) => { if (!caja.current?.contains(e.target)) setAbierto(false); };
    document.addEventListener("mousedown", fuera);
    return () => document.removeEventListener("mousedown", fuera);
  }, [abierto]);
  useEffect(() => { setActivo(0); }, [texto]);

  const elegir = (o) => { onCambio(String(o.id), o); setTexto(""); setAbierto(false); };
  const crear = async () => { const o = await onCrear(texto.trim()); if (o) elegir(o); };
  const tecla = (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setAbierto(true); setActivo((a) => Math.min(total - 1, a + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActivo((a) => Math.max(0, a - 1)); }
    else if (e.key === "Enter" && abierto && total) { e.preventDefault(); if (activo < lista.length) elegir(lista[activo]); else crear(); }
    else if (e.key === "Escape" && abierto) { e.stopPropagation(); setAbierto(false); }
  };

  return (
    <div ref={caja} className="relative">
      {etiqueta && <label htmlFor={id} className="etiqueta">{etiqueta}</label>}
      {elegido ? (
        <div className="campo flex items-center gap-2 !py-1.5">
          <Check className="size-4 shrink-0 text-verde" aria-hidden />
          <span className="min-w-0 flex-1 truncate"><span className="font-medium text-tinta">{elegido.texto}</span>{elegido.sub && <span className="ml-1.5 text-xs text-gris">{elegido.sub}</span>}</span>
          {!disabled && (
            <button type="button" onClick={() => { onCambio("", null); setTimeout(() => entrada.current?.focus(), 0); }} aria-label={`Quitar ${elegido.texto}`}
              className="rounded p-1 text-gris hover:bg-fondo hover:text-tinta"><X className="size-4" /></button>
          )}
        </div>
      ) : (
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" aria-hidden />
          <input ref={entrada} id={id} className="campo !pl-9 !pr-9" value={texto} placeholder={cargando ? "Cargando…" : placeholder} disabled={disabled}
            onChange={(e) => { setTexto(e.target.value); setAbierto(true); }} onFocus={() => setAbierto(true)} onKeyDown={tecla}
            role="combobox" aria-expanded={abierto} aria-controls={`${id}-lista`} aria-autocomplete="list" autoComplete="off" required={requerido} />
          <ChevronDown className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-gris" aria-hidden />
        </div>
      )}
      {abierto && !elegido && (
        <ul id={`${id}-lista`} role="listbox" className="absolute inset-x-0 top-full z-30 mt-1 max-h-64 overflow-y-auto rounded-xl border border-linea bg-white p-1 shadow-xl">
          {lista.map((o, i) => (
            <li key={o.id} role="option" aria-selected={i === activo}>
              <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => elegir(o)} onMouseEnter={() => setActivo(i)}
                className={cx("flex w-full items-baseline gap-2 rounded-lg px-3 py-2 text-left text-sm", i === activo ? "bg-azul/10" : "hover:bg-fondo")}>
                <span className="font-medium text-tinta">{o.texto}</span>{o.sub && <span className="truncate text-xs text-gris">{o.sub}</span>}
              </button>
            </li>
          ))}
          {!lista.length && !puedeCrear && <li className="px-3 py-2 text-sm text-gris">{cargando ? "Cargando…" : vacio}</li>}
          {puedeCrear && (
            <li role="option" aria-selected={activo === lista.length}>
              <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={crear} onMouseEnter={() => setActivo(lista.length)}
                className={cx("flex w-full items-center gap-2 rounded-lg border-t border-linea-suave px-3 py-2 text-left text-sm font-medium text-azul", activo === lista.length ? "bg-azul/10" : "hover:bg-fondo")}>
                <Plus className="size-4" aria-hidden />{textoCrear} «{texto.trim()}»
              </button>
            </li>
          )}
        </ul>
      )}
      {error ? <p className="mt-1 text-[13px] text-rojo">{error}</p> : ayuda && <p className="ayuda">{ayuda}</p>}
    </div>
  );
}
