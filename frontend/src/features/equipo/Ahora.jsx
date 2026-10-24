// «Ahora»: en qué está cada persona del equipo (lo que era el tablero de Adzone Team).
import { useCallback, useEffect, useState } from "react";
import { BellRing, Plus, RefreshCw, Users } from "lucide-react";
import { cargaEquipo, recordarTarea } from "@/lib/api";
import { vencimiento } from "@/lib/formato";
import { Progreso } from "@/features/tareas/componentes";
import { Alerta, Avatar, Boton, Cargando, Vacio, cx, useAviso } from "@/components/ui";

const ESTADOS = {
  vencida: { texto: "Con tarea vencida", punto: "bg-rojo", caja: "border-rojo/40" },
  pide_trabajo: { texto: "Pide más trabajo", punto: "bg-amarillo", caja: "border-amarillo" },
  libre: { texto: "Sin tareas", punto: "bg-gris/50", caja: "border-linea" },
  en_revision: { texto: "Esperando validación", punto: "bg-amarillo", caja: "border-linea" },
  por_empezar: { texto: "Por empezar", punto: "bg-azul/40", caja: "border-linea" },
  trabajando: { texto: "Trabajando", punto: "bg-verde", caja: "border-linea" },
};
const ORDEN = Object.keys(ESTADOS);

function Tarjeta({ p, onAbrirTarea, onAsignar, onRecordar, recordando }) {
  const e = ESTADOS[p.estado];
  const t = p.actual;
  const v = t && t.estado !== "EN_REVISION" ? vencimiento(t.fecha_limite) : null;
  const puedeRecordar = t && ["PENDIENTE", "EN_PROGRESO"].includes(t.estado);
  return (
    <li className={cx("flex flex-col rounded-xl border-2 bg-white", e.caja)}>
      <div className="flex items-start gap-3 p-4 pb-3">
        <Avatar nombre={p.nombre} />
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium">{p.nombre}</p>
          <p className="truncate text-sm text-gris">{p.puesto || "Sin puesto"}</p>
        </div>
        {p.departamento && (
          <span className="shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium" style={{ color: p.color, backgroundColor: p.color_fondo }}>
            {p.departamento}
          </span>
        )}
      </div>
      <div className="flex items-center gap-2 px-4 text-sm font-medium">
        <span className={cx("size-2.5 rounded-full", e.punto)} aria-hidden="true" />
        {e.texto}
        {p.abiertas > 1 && <span className="font-normal text-gris">· {p.abiertas} abiertas</span>}
      </div>
      <div className="flex-1 px-4 py-3">
        {t ? (
          <button type="button" onClick={() => onAbrirTarea(t.id)} className="w-full rounded-lg bg-fondo px-3 py-2.5 text-left hover:bg-linea-suave">
            <span className="line-clamp-2 text-[15px] font-medium leading-snug">{t.titulo}</span>
            <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-gris">
              {t.cliente && <span className="truncate">{t.cliente}</span>}
              {v && <span className={cx(v.tono === "rojo" && "font-medium text-rojo", v.tono === "amarillo" && "font-medium text-[#a86a00]")}>{v.texto}</span>}
              <Progreso progreso={t.progreso} />
            </span>
          </button>
        ) : (
          <p className="text-sm text-gris">{p.pide_trabajo ? "Terminó lo suyo y avisó que puede tomar más." : "No tiene tareas abiertas."}</p>
        )}
      </div>
      <div className="flex gap-2 border-t border-linea-suave px-4 py-3">
        {puedeRecordar && (
          <Boton variante="secundario" tam="sm" icono={BellRing} onClick={() => onRecordar(t)} cargando={recordando === t.id} className="flex-1">Recordar</Boton>
        )}
        <Boton variante={["libre", "pide_trabajo"].includes(p.estado) ? "acento" : "fantasma"} tam="sm" icono={Plus} onClick={() => onAsignar(p)} className="flex-1">
          Asignar tarea
        </Boton>
      </div>
    </li>
  );
}

export default function Ahora({ version, onAbrirTarea, onAsignar }) {
  const avisar = useAviso();
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  const [filtro, setFiltro] = useState("");
  const [recordando, setRecordando] = useState(null);

  const cargar = useCallback(() => { cargaEquipo().then((d) => { setDatos(d); setError(""); }).catch((e) => setError(e.message)); }, []);
  useEffect(() => { cargar(); }, [cargar, version]);
  useEffect(() => {
    const t = setInterval(() => { if (document.visibilityState === "visible") cargar(); }, 60000);
    return () => clearInterval(t);
  }, [cargar]);

  const recordar = async (t) => {
    setRecordando(t.id);
    try { avisar((await recordarTarea(t.id, "")).message); } catch (e) { avisar(e.message, "rojo"); }
    setRecordando(null);
  };

  if (error) return <Alerta>{error}</Alerta>;
  if (!datos) return <Cargando />;
  if (!datos.personas.length) return <Vacio icono={Users} titulo="No tienes personas a cargo">Cuando alguien ocupe un puesto que depende del tuyo, aparece aquí.</Vacio>;

  const lista = datos.personas.filter((p) => !filtro || p.estado === filtro);
  const piden = datos.conteo.pide_trabajo || 0;
  return (
    <div className="space-y-4">
      {piden > 0 && (
        <Alerta tono="amarillo" className="border border-amarillo bg-amarillo-50 text-[#7a5000]">
          <span className="font-medium">{piden === 1 ? "1 persona pide más trabajo." : `${piden} personas piden más trabajo.`} Asígnale algo desde su tarjeta.</span>
        </Alerta>
      )}
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filtrar por estado">
        <button type="button" onClick={() => setFiltro("")} aria-pressed={!filtro}
          className={cx("min-h-10 rounded-full border px-3.5 text-sm font-medium", !filtro ? "border-noche bg-noche text-white" : "border-linea bg-white")}>
          Todos <span className="num opacity-70">{datos.personas.length}</span>
        </button>
        {ORDEN.filter((k) => datos.conteo[k]).map((k) => (
          <button key={k} type="button" onClick={() => setFiltro(filtro === k ? "" : k)} aria-pressed={filtro === k}
            className={cx("inline-flex min-h-10 items-center gap-2 rounded-full border px-3.5 text-sm font-medium",
              filtro === k ? "border-noche bg-noche text-white" : "border-linea bg-white")}>
            <span className={cx("size-2 rounded-full", ESTADOS[k].punto)} aria-hidden="true" />
            {ESTADOS[k].texto} <span className="num opacity-70">{datos.conteo[k]}</span>
          </button>
        ))}
        <Boton variante="fantasma" tam="sm" icono={RefreshCw} onClick={cargar} className="ml-auto" aria-label="Actualizar">Actualizar</Boton>
      </div>
      <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {lista.map((p) => <Tarjeta key={p.id} p={p} onAbrirTarea={onAbrirTarea} onAsignar={onAsignar} onRecordar={recordar} recordando={recordando} />)}
      </ul>
    </div>
  );
}
