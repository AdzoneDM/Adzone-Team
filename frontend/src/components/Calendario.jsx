// Calendario mensual: cada día muestra lo que vence. En el celular, una lista por día.
import { useMemo } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { hoyISO, nombreMes } from "@/lib/formato";
import { cx } from "@/components/ui";

const DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

export function rangoMes(mes) {
  const [a, m] = mes.split("-").map(Number);
  const primero = new Date(a, m - 1, 1);
  const inicio = new Date(primero);
  inicio.setDate(1 - ((primero.getDay() + 6) % 7));
  const dias = [];
  for (let i = 0; i < 42; i++) {
    const d = new Date(inicio);
    d.setDate(inicio.getDate() + i);
    dias.push(d);
  }
  return { dias, desde: iso(dias[0]), hasta: iso(dias[41]) };
}

export function moverMes(mes, delta) {
  const [a, m] = mes.split("-").map(Number);
  const f = new Date(a, m - 1 + delta, 1);
  return `${f.getFullYear()}-${String(f.getMonth() + 1).padStart(2, "0")}`;
}

/**
 * items: [{ id, fecha: "AAAA-MM-DD", titulo, color, fondo, tachado, onClick }]
 */
export default function Calendario({ mes, onMes, items }) {
  const { dias } = useMemo(() => rangoMes(mes), [mes]);
  const porDia = useMemo(() => {
    const m = {};
    for (const it of items) (m[it.fecha] ||= []).push(it);
    return m;
  }, [items]);
  const hoy = hoyISO();
  const delMes = dias.filter((d) => iso(d).startsWith(mes) && porDia[iso(d)]);

  return (
    <div className="rounded-xl border border-linea bg-white">
      <div className="flex items-center justify-between border-b border-linea-suave px-3 py-2">
        <button type="button" onClick={() => onMes(moverMes(mes, -1))} className="rounded-lg p-2 text-gris hover:bg-fondo" aria-label="Mes anterior"><ChevronLeft className="size-5" /></button>
        <p className="font-display text-lg font-semibold first-letter:uppercase">{nombreMes(mes)}</p>
        <button type="button" onClick={() => onMes(moverMes(mes, 1))} className="rounded-lg p-2 text-gris hover:bg-fondo" aria-label="Mes siguiente"><ChevronRight className="size-5" /></button>
      </div>
      {/* PC: cuadrícula */}
      <div className="hidden md:block">
        <div className="grid grid-cols-7 border-b border-linea-suave text-center text-xs font-medium text-gris">
          {DIAS.map((d) => <div key={d} className="py-2">{d}</div>)}
        </div>
        <div className="grid grid-cols-7">
          {dias.map((d) => {
            const clave = iso(d);
            const lista = porDia[clave] || [];
            const fuera = !clave.startsWith(mes);
            return (
              <div key={clave} className={cx("min-h-28 border-b border-r border-linea-suave p-1.5 [&:nth-child(7n)]:border-r-0", fuera && "bg-fondo/60")}>
                <p className={cx("mb-1 inline-flex size-6 items-center justify-center rounded-full text-xs num",
                  clave === hoy ? "bg-azul font-semibold text-white" : fuera ? "text-gris/60" : "text-gris")}>{d.getDate()}</p>
                <ul className="space-y-1">
                  {lista.slice(0, 4).map((it) => (
                    <li key={it.id}>
                      <button type="button" onClick={it.onClick} title={it.titulo}
                        className={cx("block w-full truncate rounded-md border-l-[3px] px-1.5 py-0.5 text-left text-xs font-medium hover:brightness-95", it.tachado && "line-through opacity-60")}
                        style={{ borderColor: it.color, backgroundColor: it.fondo, color: it.color }}>
                        {it.titulo}
                      </button>
                    </li>
                  ))}
                  {lista.length > 4 && <li className="px-1.5 text-xs text-gris">+{lista.length - 4} más</li>}
                </ul>
              </div>
            );
          })}
        </div>
      </div>
      {/* Celular: agenda */}
      <ul className="divide-y divide-linea-suave md:hidden">
        {delMes.length === 0 && <li className="px-4 py-8 text-center text-sm text-gris">Nada programado este mes.</li>}
        {delMes.map((d) => {
          const clave = iso(d);
          return (
            <li key={clave} className="flex gap-3 px-4 py-3">
              <div className={cx("w-11 shrink-0 text-center", clave === hoy && "text-azul")}>
                <p className="text-xs uppercase text-gris">{DIAS[(d.getDay() + 6) % 7]}</p>
                <p className="font-display text-xl font-semibold num">{d.getDate()}</p>
              </div>
              <ul className="min-w-0 flex-1 space-y-1.5">
                {porDia[clave].map((it) => (
                  <li key={it.id}>
                    <button type="button" onClick={it.onClick} className={cx("block w-full truncate rounded-lg border-l-4 px-3 py-2 text-left text-sm font-medium", it.tachado && "line-through opacity-60")}
                      style={{ borderColor: it.color, backgroundColor: it.fondo, color: it.color }}>{it.titulo}</button>
                  </li>
                ))}
              </ul>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
