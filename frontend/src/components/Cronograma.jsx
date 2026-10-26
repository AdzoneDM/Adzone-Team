// Cronograma (Gantt): una barra por fila entre su inicio y su fin, con la línea de hoy.
import { useEffect, useMemo, useRef } from "react";
import { diasHasta, fechaCorta, hoyISO, sumarDias } from "@/lib/formato";
import { cx } from "@/components/ui";

const ANCHO_DIA = 28;
const dif = (a, b) => diasHasta(b) - diasHasta(a);

/**
 * filas: [{ id, etiqueta, sub, inicio, fin, color, fondo, progreso (0-100), alerta, onClick }]
 */
export default function Cronograma({ filas, vacio = "No hay nada con fechas todavía." }) {
  const hoy = hoyISO();
  const zona = useRef(null);
  const conFechas = filas.filter((f) => f.fin);
  const rango = useMemo(() => {
    if (!conFechas.length) return null;
    let desde = conFechas.reduce((m, f) => ((f.inicio || f.fin) < m ? f.inicio || f.fin : m), hoy);
    let hasta = conFechas.reduce((m, f) => (f.fin > m ? f.fin : m), hoy);
    desde = sumarDias(desde, -3);
    hasta = sumarDias(hasta, 5);
    const total = dif(desde, hasta) + 1;
    return { desde, total: Math.min(total, 400) };
  }, [conFechas, hoy]);

  const xHoyInicial = rango ? dif(rango.desde, hoy) * ANCHO_DIA : 0;
  // Abre con «hoy» a la vista (con una semana de contexto a la izquierda).
  useEffect(() => { if (zona.current) zona.current.scrollLeft = Math.max(0, xHoyInicial - 7 * ANCHO_DIA); }, [xHoyInicial]);
  if (!rango) return <p className="rounded-xl border border-dashed border-linea bg-white px-6 py-10 text-center text-sm text-gris">{vacio}</p>;
  const dias = Array.from({ length: rango.total }, (_, i) => sumarDias(rango.desde, i));
  const xHoy = dif(rango.desde, hoy) * ANCHO_DIA;

  return (
    <div className="overflow-hidden rounded-xl border border-linea bg-white">
      <div className="flex">
        {/* Columna fija con los nombres */}
        <div className="w-40 shrink-0 border-r border-linea-suave md:w-64">
          <div className="h-12 border-b border-linea-suave" />
          {conFechas.map((f) => (
            <button key={f.id} type="button" onClick={f.onClick} className="flex h-12 w-full flex-col justify-center border-b border-linea-suave px-3 text-left hover:bg-fondo">
              <span className="truncate text-sm font-medium">{f.etiqueta}</span>
              {f.sub && <span className="truncate text-xs text-gris">{f.sub}</span>}
            </button>
          ))}
        </div>
        {/* Zona con scroll horizontal */}
        <div ref={zona} className="min-w-0 flex-1 overflow-x-auto">
          <div className="relative" style={{ width: rango.total * ANCHO_DIA }}>
            <div className="flex h-12 border-b border-linea-suave">
              {dias.map((d) => {
                const dia = Number(d.slice(8));
                const finde = [0, 6].includes(new Date(d + "T12:00").getDay());
                return (
                  <div key={d} className={cx("flex shrink-0 flex-col items-center justify-end pb-1 text-[11px]", finde ? "bg-fondo text-gris/70" : "text-gris")} style={{ width: ANCHO_DIA }}>
                    {dia === 1 || d === rango.desde ? <span className="font-medium text-tinta">{fechaCorta(d).split(" ")[1]}</span> : null}
                    <span className="num">{dia}</span>
                  </div>
                );
              })}
            </div>
            {conFechas.map((f) => {
              const inicio = f.inicio && f.inicio <= f.fin ? f.inicio : f.fin;
              const x = dif(rango.desde, inicio) * ANCHO_DIA;
              const w = (dif(inicio, f.fin) + 1) * ANCHO_DIA;
              return (
                <div key={f.id} className="relative h-12 border-b border-linea-suave">
                  <button type="button" onClick={f.onClick} title={`${f.etiqueta}: ${fechaCorta(inicio)} → ${fechaCorta(f.fin)}`}
                    className={cx("absolute top-2.5 flex h-7 items-center overflow-hidden rounded-md border text-xs font-medium", f.alerta && "ring-2 ring-rojo/60")}
                    style={{ left: x + 2, width: Math.max(w - 4, 10), borderColor: f.color, backgroundColor: f.fondo, color: f.color }}>
                    {f.progreso != null && <span className="absolute inset-y-0 left-0 opacity-25" style={{ width: `${f.progreso}%`, backgroundColor: f.color }} />}
                    <span className="relative truncate px-2">{f.etiqueta}</span>
                  </button>
                </div>
              );
            })}
            <div className="pointer-events-none absolute bottom-0 top-0 w-0.5 bg-rojo/70" style={{ left: xHoy + ANCHO_DIA / 2 }} aria-hidden />
          </div>
        </div>
      </div>
    </div>
  );
}
