// Administración → Respaldos: copias cifradas que el servidor hace cada noche (base, archivos privados y configuración).
import { useEffect, useState } from "react";
import { Download, Lock } from "lucide-react";
import { respaldos as cargar } from "@/lib/api";
import { Alerta, Cabecera, Cargando, Insignia, Panel, Vacio } from "@/components/ui";

const tamano = (b) => (b > 1e9 ? `${(b / 1e9).toFixed(1)} GB` : b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1e3))} KB`);

export default function Respaldos() {
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { cargar().then(setD).catch((e) => setError(e.message)); }, []);
  const porDia = {};
  (d?.respaldos || []).forEach((r) => { (porDia[r.fecha] ||= []).push(r); });
  return (
    <div className="max-w-3xl space-y-5">
      <Cabecera titulo="Respaldos" descripcion="El servidor guarda cada noche una copia cifrada de la base de datos, los archivos privados y la configuración, durante 30 días. Descarga la de la semana y guárdala fuera del servidor." />
      {error && <Alerta>{error}</Alerta>}
      {!d ? !error && <Cargando /> : <>
        {d.atrasado && <Alerta>{d.ultimo ? `El último respaldo es del ${d.ultimo}.` : "Todavía no hay respaldos."} Revisa la tarea programada de las 2:30 en Plesk (servidor/respaldo.sh).</Alerta>}
        <Alerta tono="amarillo"><Lock className="mr-1 inline size-4" />Están cifrados: se abren con la clave de respaldos (RESPALDO_CLAVE), que debe estar guardada también fuera del servidor. Las instrucciones para abrirlos están en la guía de despliegue.</Alerta>
        {Object.keys(porDia).length === 0 ? <Vacio titulo="Sin respaldos todavía" /> : Object.entries(porDia).map(([fecha, lista], i) => (
          <Panel key={fecha} titulo={fecha} accion={i === 0 ? <Insignia tono="verde">Más reciente</Insignia> : null} cuerpo="p-0">
            <ul className="divide-y divide-linea-suave">
              {lista.map((r) => (
                <li key={r.nombre} className="flex items-center gap-3 px-5 py-3">
                  <span className="min-w-0 flex-1"><span className="block font-medium">{r.tipo}</span><span className="block truncate text-sm text-gris">{r.hora} · {tamano(r.tamano)}</span></span>
                  <a className="inline-flex items-center gap-1.5 rounded-lg border border-linea px-3 py-1.5 text-sm font-medium hover:bg-niebla" href={`/api/respaldos/${encodeURIComponent(r.nombre)}/`} download>
                    <Download className="size-4" />Descargar
                  </a>
                </li>
              ))}
            </ul>
          </Panel>
        ))}
      </>}
    </div>
  );
}
