// Bitácora de accesos: entradas, contraseñas equivocadas, bloqueos, entradas poco habituales, sesiones cerradas y accesos denegados.
import { useEffect, useState } from "react";
import { bitacoraAccesos } from "@/lib/api";
import { Alerta, Cargando, Insignia, Panel } from "@/components/ui";

const TONO = { ENTRADA: "verde", SALIDA: "gris", FALLO: "amarillo", FALLO_CODIGO: "amarillo", BLOQUEO: "rojo", SOSPECHOSO: "rojo",
  SESION_CERRADA: "azul", DENEGADO: "amarillo", IP_BLOQUEADA: "rojo", CLAVE: "azul" };
const FILTROS = [["", "Todo"], ["FALLO,FALLO_CODIGO,BLOQUEO", "Fallos y bloqueos"], ["SOSPECHOSO,IP_BLOQUEADA", "Sospechosos"], ["DENEGADO", "Accesos denegados"],
  ["ENTRADA,SALIDA", "Entradas y salidas"], ["CLAVE,SESION_CERRADA", "Contraseñas y sesiones"]];

export default function Accesos() {
  const [tipo, setTipo] = useState("");
  const [buscar, setBuscar] = useState("");
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const t = setTimeout(() => bitacoraAccesos({ tipo, usuario: buscar.trim(), dias: 30 }).then(setD).catch((e) => setError(e.message)), 300);
    return () => clearTimeout(t);
  }, [tipo, buscar]);
  const r = d?.resumen_24h;
  return (
    <div className="space-y-4">
      {r && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {[["Entradas", r.entradas, ""], ["Contraseñas equivocadas", r.fallos, r.fallos > 20 ? "text-[#a86a00]" : ""], ["Cuentas bloqueadas", r.bloqueos, r.bloqueos ? "text-rojo" : ""],
            ["Entradas poco habituales", r.sospechosos, r.sospechosos ? "text-rojo" : ""], ["Accesos denegados", r.denegados, ""]].map(([e, v, c]) => (
            <div key={e} className="rounded-xl border border-linea bg-white p-3"><p className={`num text-2xl font-semibold ${c}`}>{v}</p><p className="text-xs text-gris">{e} · 24 h</p></div>
          ))}
        </div>
      )}
      {r?.ips_con_mas_fallos?.length > 0 && <p className="text-sm text-gris">IPs con más fallos (24 h): {r.ips_con_mas_fallos.map((x) => `${x.ip} (${x.n})`).join(", ")}</p>}
      <Panel titulo="Bitácora de accesos (30 días)" cuerpo="p-0"
        accion={<div className="flex flex-wrap gap-2">
          <select className="campo !h-9 !w-auto !py-0" value={tipo} onChange={(e) => setTipo(e.target.value)} aria-label="Tipo de evento">{FILTROS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select>
          <input className="campo !h-9 w-full sm:w-48" placeholder="Persona o usuario…" value={buscar} onChange={(e) => setBuscar(e.target.value)} aria-label="Buscar persona" />
        </div>}>
        {error && <Alerta className="m-4">{error}</Alerta>}
        {!d ? <Cargando /> : !d.eventos.length ? <p className="p-5 text-sm text-gris">Sin eventos con ese filtro.</p> : (
          <ul className="divide-y divide-linea-suave">
            {d.eventos.map((e) => (
              <li key={e.id} className="grid gap-x-4 gap-y-1 px-5 py-3 text-sm md:grid-cols-[9rem_minmax(0,12rem)_minmax(0,1fr)]">
                <p className="num whitespace-nowrap text-gris">{new Date(e.fecha).toLocaleString("es-DO", { dateStyle: "short", timeStyle: "short" })}</p>
                <div className="min-w-0"><Insignia tono={TONO[e.tipo] || "gris"}>{e.tipo_texto}</Insignia><p className="mt-0.5 truncate font-medium">{e.nombre || "—"}</p></div>
                <p className="min-w-0 text-gris [overflow-wrap:anywhere]">
                  {[e.ip && `IP ${e.ip}`, e.dispositivo, e.dispositivo_nuevo && !(e.motivo || "").includes("dispositivo nuevo") && "dispositivo nuevo", e.riesgo ? `riesgo ${e.riesgo}` : "", e.motivo, e.tipo === "DENEGADO" && e.ruta].filter(Boolean).join(" · ")}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
