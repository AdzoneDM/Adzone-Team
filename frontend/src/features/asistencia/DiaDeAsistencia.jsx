// Un día de asistencia: la fecha, una línea de tiempo con lo que pasó (trabajo, pausas y almuerzo sobre el turno) y los totales.
import { cx } from "@/components/ui";
import { ZONA, diaSemana, hoyISO, hora, relojSeg } from "@/lib/formato";

const minutosDelDia = (valor) => {
  const p = new Intl.DateTimeFormat("en-GB", { timeZone: ZONA, hour: "2-digit", minute: "2-digit", hour12: false }).formatToParts(new Date(valor));
  return Number(p.find((x) => x.type === "hour").value) % 24 * 60 + Number(p.find((x) => x.type === "minute").value);
};
const aMinutos = (hhmm) => { const [h, m] = String(hhmm).split(":").map(Number); return h * 60 + m; };
/** «17:00» → «5:00 p. m.» */
const hhmm = (t) => { const [h, m] = String(t).split(":").map(Number); return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${h < 12 ? "a. m." : "p. m."}`; };
const hora12 = (min) => { const h = Math.floor(min / 60) % 24; return `${h % 12 || 12} ${h < 12 ? "am" : "pm"}`; };
const dur = (seg) => relojSeg(seg);

/** Trabajo, pausa y almuerzo como tramos [inicio, fin] en minutos del día, a partir de los marcajes. */
function tramos(j) {
  const salida = [];
  let tipo = null, ini = 0;
  const cerrar = (fin, abierto = false) => { if (tipo && fin >= ini) salida.push({ tipo, ini, fin, abierto }); };
  for (const m of j.marcajes) {
    const min = minutosDelDia(m.momento);
    if (m.tipo === "ENTRADA" || m.tipo === "REGRESO") { cerrar(min); tipo = "trabajo"; ini = min; }
    else if (m.tipo === "PAUSA") { cerrar(min); tipo = m.almuerzo ? "almuerzo" : "pausa"; ini = min; }
    else if (m.tipo === "SALIDA") { cerrar(min); tipo = null; }
  }
  if (tipo) cerrar(j.fecha === hoyISO() ? Math.max(ini, minutosDelDia(new Date())) : ini + 1, j.fecha === hoyISO());
  return salida;
}

const COLOR = { trabajo: "bg-verde", pausa: "bg-[#e0a400]", almuerzo: "bg-azul" };
const NOMBRE = { trabajo: "Trabajo", pausa: "Pausa", almuerzo: "Pausa - Almuerzo" };

function LineaDeTiempo({ j, segs }) {
  const turno = j.turno ? [aMinutos(j.turno[0]), aMinutos(j.turno[1])] : null;
  const puntos = [...segs.flatMap((s) => [s.ini, s.fin]), ...(turno || [])];
  const lo = Math.floor((Math.min(...puntos) - 20) / 60) * 60, hi = Math.ceil((Math.max(...puntos) + 20) / 60) * 60;
  const span = Math.max(hi - lo, 60), x = (min) => `${((min - lo) / span) * 100}%`, ancho = (a, b) => `${(Math.max(b - a, 3) / span) * 100}%`;
  const paso = span <= 600 ? 60 : 120;
  const marcas = []; for (let t = Math.ceil(lo / paso) * paso; t <= hi; t += paso) marcas.push(t);
  const resumen = segs.map((s) => `${NOMBRE[s.tipo]} de ${hhmm(`${Math.floor(s.ini / 60)}:${s.ini % 60}`)} a ${hhmm(`${Math.floor(s.fin / 60)}:${s.fin % 60}`)}`).join(", ");
  return (
    <div role="img" aria-label={resumen || "Sin actividad"}>
      <div className="relative h-5 rounded-full bg-fondo">
        {turno && <div className="absolute inset-y-0 rounded-full border border-dashed border-azul/40 bg-azul/5" style={{ left: x(turno[0]), width: ancho(turno[0], turno[1]) }} title={`Turno ${hhmm(j.turno[0])} a ${hhmm(j.turno[1])}`} />}
        {segs.map((s, i) => (
          <div key={i} className={cx("absolute inset-y-1 rounded-full", COLOR[s.tipo], s.abierto && "animate-pulse")} style={{ left: x(s.ini), width: ancho(s.ini, s.fin) }}
            title={`${NOMBRE[s.tipo]}${s.abierto ? " (en curso)" : ""}`} />
        ))}
      </div>
      <div className="relative mt-1 h-4 text-[10px] text-gris" aria-hidden>
        {marcas.map((t, i) => <span key={t} className={cx("absolute whitespace-nowrap num", i === marcas.length - 1 && marcas.length > 1 ? "-translate-x-full" : i === 0 ? "" : "-translate-x-1/2")} style={{ left: x(t) }}>{hora12(t)}</span>)}
      </div>
    </div>
  );
}

function Cifra({ etiqueta, valor, alerta, nota }) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-sm">
      <dt className="text-gris">{etiqueta}</dt>
      <dd className={cx("num text-right", alerta ? "font-semibold text-rojo" : "text-tinta")}>{valor}{nota && <span className="block text-xs font-normal text-rojo">{nota}</span>}</dd>
    </div>
  );
}

export default function DiaDeAsistencia({ j, estado, marcajes }) {
  const [anio, mes, dia] = j.fecha.split("-");
  const mesCorto = new Date(Number(anio), Number(mes) - 1, 1).toLocaleDateString("es-DO", { month: "short" }).replace(".", "");
  const segs = tramos(j);
  const conDatos = segs.length > 0;
  const almExceso = j.pausas.some((p) => p.almuerzo && p.excedida), pausaExceso = j.pausas.some((p) => !p.almuerzo && p.excedida);
  return (
    <li className="grid gap-x-5 gap-y-3 px-4 py-4 sm:px-5 md:grid-cols-[5.5rem_minmax(0,1fr)_13rem]">
      {/* Fecha y estado */}
      <div className="flex items-center gap-3 md:block">
        <div className="flex size-14 shrink-0 flex-col items-center justify-center rounded-xl bg-fondo md:mb-2">
          <span className="text-xl font-semibold leading-none text-noche num">{Number(dia)}</span>
          <span className="mt-0.5 text-[11px] font-medium uppercase text-gris">{diaSemana(j.fecha).slice(0, 3)} · {mesCorto}</span>
        </div>
        <div className="flex flex-wrap items-center gap-1">{estado}</div>
      </div>

      {/* Lo que pasó */}
      <div className="min-w-0">
        {conDatos ? (
          <>
            <p className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-[15px]">
              <span><span className="text-gris">Entró </span><strong className="num font-semibold text-noche">{hora(j.entrada)}</strong>{j.turno && <span className="text-xs text-gris"> (turno {hhmm(j.turno[0])})</span>}</span>
              <span className="hidden text-gris sm:inline" aria-hidden>→</span>
              <span><span className="text-gris">Salió </span><strong className="num font-semibold text-noche">{j.salida ? hora(j.salida) : "—"}</strong>{j.turno && <span className="text-xs text-gris"> ({j.salida ? "turno" : "programada"} {hhmm(j.turno[1])})</span>}</span>
            </p>
            {(j.tardanza > 0 || j.salida_temprana > 0) && (
              <p className="mt-1 flex flex-wrap gap-1.5">
                {j.tardanza > 0 && <span className="rounded-md bg-red-50 px-1.5 py-0.5 text-xs font-medium text-rojo">Llegó {j.tardanza} min tarde</span>}
                {j.salida_temprana > 0 && <span className="rounded-md bg-red-50 px-1.5 py-0.5 text-xs font-medium text-rojo">Salió {j.salida_temprana} min antes</span>}
              </p>
            )}
            <div className="mt-3"><LineaDeTiempo j={j} segs={segs} /></div>
            <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gris">
              {Object.entries(NOMBRE).filter(([k]) => segs.some((s) => s.tipo === k)).map(([k, n]) => (
                <span key={k} className="inline-flex items-center gap-1.5"><span className={cx("size-2 rounded-full", COLOR[k])} />{n}</span>
              ))}
            </div>
          </>
        ) : (
          <p className="text-sm text-gris">{j.turno ? `Turno ${hhmm(j.turno[0])} a ${hhmm(j.turno[1])}` : "Día libre"}{j.ausencia ? ` · ${j.ausencia}` : ""}{j.feriado ? " · Feriado" : ""}</p>
        )}
        <div className="mt-2">{marcajes}</div>
      </div>

      {/* Totales */}
      {conDatos && (
        <dl className="space-y-1.5 rounded-xl bg-fondo px-3.5 py-3 md:self-start">
          <div className="flex items-baseline justify-between gap-3 border-b border-linea pb-1.5">
            <dt className="text-sm font-medium text-noche">Trabajado</dt>
            <dd className="num text-lg font-semibold text-noche">{j.trabajados_seg ? dur(j.trabajados_seg) : "—"}</dd>
          </div>
          <Cifra etiqueta="Pausa - Almuerzo" valor={j.almuerzo_seg ? dur(j.almuerzo_seg) : "—"} alerta={almExceso} />
          <Cifra etiqueta="Pausas" valor={j.pausas_seg ? dur(j.pausas_seg) : "—"} alerta={pausaExceso} nota={j.excesos > 0 ? `+${dur(j.exceso_seg)} sobre el límite` : null} />
          {j.extra_seg > 0 && <Cifra etiqueta="Extra" valor={dur(j.extra_seg)} />}
        </dl>
      )}
    </li>
  );
}
