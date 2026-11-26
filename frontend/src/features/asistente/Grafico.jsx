// Gráfico de las respuestas del asistente (```grafico {...}```). Barras horizontales (los nombres se leen en el celular) o líneas.
// Paleta validada (scripts/validate_palette.js, modo claro): azul, ámbar oscuro, violeta. Rojo y verde quedan para estados.
import { useState } from "react";
import { cx } from "@/components/ui";

const COLORES = ["#224b9a", "#c27c00", "#8a5cc7"];
const fmt = (v) => (v == null || Number.isNaN(Number(v)) ? "—" : Number(v).toLocaleString("es-DO", { maximumFractionDigits: 1 }));

export function leerGrafico(texto) {
  try {
    const g = JSON.parse(texto);
    const etiquetas = (g.etiquetas || []).slice(0, 12).map(String);
    const series = (g.series || []).slice(0, 3).map((s) => ({ nombre: String(s.nombre || ""), valores: etiquetas.map((_, i) => Number(s.valores?.[i]) || 0) }));
    if (!etiquetas.length || !series.length) return null;
    return { tipo: g.tipo === "lineas" ? "lineas" : "barras", titulo: String(g.titulo || ""), etiquetas, series };
  } catch { return null; }
}

function Leyenda({ series }) {
  if (series.length < 2) return null;
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gris">
      {series.map((s, i) => <span key={s.nombre} className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-sm" style={{ background: COLORES[i] }} />{s.nombre}</span>)}
    </div>
  );
}

function Barras({ g }) {
  const [hover, setHover] = useState(null);
  const max = Math.max(1, ...g.series.flatMap((s) => s.valores));
  const alto = g.series.length > 1 ? 10 : 14;
  return (
    <ul className="space-y-2">
      {g.etiquetas.map((et, i) => (
        <li key={et} className="grid grid-cols-[minmax(5rem,9rem)_1fr] items-center gap-2 text-xs" onMouseLeave={() => setHover(null)}>
          <span className="truncate text-tinta" title={et}>{et}</span>
          <span className="space-y-0.5">
            {g.series.map((s, j) => (
              <span key={s.nombre} className="relative flex items-center gap-1.5" onMouseEnter={() => setHover(`${i}-${j}`)}>
                <span className="block rounded-r-[4px]" style={{ width: `${Math.max(1, (s.valores[i] / max) * 100)}%`, height: alto, background: COLORES[j], minWidth: 2 }} />
                <span className="num shrink-0 text-gris">{fmt(s.valores[i])}</span>
                {hover === `${i}-${j}` && g.series.length > 1 && (
                  <span className="absolute -top-7 left-0 z-10 whitespace-nowrap rounded-md bg-noche px-2 py-1 text-[11px] text-white shadow">{et} · {s.nombre}: {fmt(s.valores[i])}</span>
                )}
              </span>
            ))}
          </span>
        </li>
      ))}
    </ul>
  );
}

function Lineas({ g }) {
  const [hover, setHover] = useState(null);
  const W = 320, H = 150, PX = 30, PY = 12;
  const max = Math.max(1, ...g.series.flatMap((s) => s.valores));
  const n = g.etiquetas.length;
  const x = (i) => PX + (n === 1 ? (W - PX * 2) / 2 : (i * (W - PX * 2)) / (n - 1));
  const y = (v) => H - PY - (v / max) * (H - PY * 2);
  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H + 18}`} className="w-full" role="img" aria-label={g.titulo}>
        {[0, 0.5, 1].map((f) => <g key={f}><line x1={PX} x2={W - PX} y1={y(max * f)} y2={y(max * f)} stroke="#eef1f7" strokeWidth="1" />
          <text x={PX - 4} y={y(max * f) + 3} textAnchor="end" fontSize="9" fill="#5b6475">{fmt(max * f)}</text></g>)}
        {g.series.map((s, j) => (
          <g key={s.nombre}>
            <polyline fill="none" stroke={COLORES[j]} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" points={s.valores.map((v, i) => `${x(i)},${y(v)}`).join(" ")} />
            {s.valores.map((v, i) => <circle key={i} cx={x(i)} cy={y(v)} r={hover === i ? 4.5 : 3} fill={COLORES[j]} stroke="#fff" strokeWidth="2" />)}
          </g>
        ))}
        {hover != null && <line x1={x(hover)} x2={x(hover)} y1={PY} y2={H - PY} stroke="#5b6475" strokeWidth="1" strokeDasharray="2 3" />}
        {g.etiquetas.map((et, i) => (n <= 8 || i % Math.ceil(n / 6) === 0) && <text key={et} x={x(i)} y={H + 12} textAnchor="middle" fontSize="9" fill="#5b6475">{et.length > 10 ? `${et.slice(0, 9)}…` : et}</text>)}
        {g.etiquetas.map((et, i) => <rect key={`h${et}`} x={x(i) - (W - PX * 2) / Math.max(1, n - 1) / 2} y={0} width={(W - PX * 2) / Math.max(1, n - 1)} height={H} fill="transparent" onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} />)}
      </svg>
      {hover != null && (
        <div className="pointer-events-none absolute left-1/2 top-0 -translate-x-1/2 rounded-md bg-noche px-2 py-1 text-[11px] text-white shadow">
          <b>{g.etiquetas[hover]}</b>{g.series.map((s) => <span key={s.nombre}> · {g.series.length > 1 ? `${s.nombre}: ` : ""}{fmt(s.valores[hover])}</span>)}
        </div>
      )}
    </div>
  );
}

export default function Grafico({ g }) {
  const [tabla, setTabla] = useState(false);
  return (
    <figure className="my-2 space-y-2 rounded-xl border border-linea bg-white p-3 text-tinta">
      <figcaption className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold">{g.titulo}</span>
        <button type="button" onClick={() => setTabla((t) => !t)} className="shrink-0 text-xs font-medium text-azul hover:underline">{tabla ? "Ver gráfico" : "Ver datos"}</button>
      </figcaption>
      <Leyenda series={g.series} />
      {tabla ? (
        <div className="overflow-x-auto"><table className="w-full text-xs"><thead><tr><th className="py-1 text-left font-medium text-gris" />
          {g.series.map((s) => <th key={s.nombre} className="py-1 text-right font-medium text-gris">{s.nombre || "Valor"}</th>)}</tr></thead>
          <tbody>{g.etiquetas.map((et, i) => <tr key={et} className="border-t border-linea-suave"><td className="py-1">{et}</td>
            {g.series.map((s) => <td key={s.nombre} className={cx("py-1 text-right num")}>{fmt(s.valores[i])}</td>)}</tr>)}</tbody></table></div>
      ) : g.tipo === "lineas" ? <Lineas g={g} /> : <Barras g={g} />}
    </figure>
  );
}
