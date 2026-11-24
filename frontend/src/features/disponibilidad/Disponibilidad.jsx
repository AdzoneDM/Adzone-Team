// Quién está libre: tablero público para todos los departamentos, para pedir ayuda a quien no tiene tareas.
// Solo muestra CUÁNTAS tareas tiene cada persona y su próxima entrega; nunca de qué son.
import { useCallback, useEffect, useMemo, useState } from "react";
import { HandHeart, MessageCircle, Plus, RefreshCw, Search, UsersRound } from "lucide-react";
import { crearColaboracion, disponibilidad, equipo } from "@/lib/api";
import { fechaCorta } from "@/lib/formato";
import { useNovedades } from "@/lib/novedades";
import FormTarea from "@/features/tareas/FormTarea";
import { Alerta, Avatar, Boton, Cabecera, Campo, Cargando, Insignia, Modal, Pestanas, Vacio, cx, useAviso } from "@/components/ui";

const ESTADO = {
  LIBRE: { texto: "Libre", tono: "verde", orden: 0 },
  POCA: { texto: "Poca carga", tono: "amarillo", orden: 1 },
  OCUPADO: { texto: "Ocupado/a", tono: "rojo", orden: 2 },
  AUSENTE: { texto: "No disponible hoy", tono: "neutro", orden: 3 },
};
const horas = (h) => (!h ? "" : `~${h % 1 ? h.toFixed(1) : h} h`);

function PedirApoyo({ persona, onCerrar, onHecho }) {
  const avisar = useAviso();
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { setTexto(""); setError(""); }, [persona?.id]);
  if (!persona) return null;
  const enviar = async () => {
    if (texto.trim().length < 5) return setError("Cuéntale en qué necesitas apoyo (unas palabras).");
    setEnviando(true); setError("");
    try {
      await crearColaboracion({ ayudante: persona.id, descripcion: texto.trim() });
      avisar(`Le llegó tu pedido de apoyo a ${persona.nombre}.`);
      onHecho();
    } catch (e) { setError(e.message); }
    setEnviando(false);
  };
  return (
    <Modal abierto onCerrar={onCerrar} titulo={`Pedir apoyo a ${persona.nombre}`} descripcion={`${persona.puesto} · ${persona.departamento}`}
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton icono={HandHeart} cargando={enviando} onClick={enviar}>Pedir apoyo</Boton></>}>
      <div className="space-y-3">
        {error && <Alerta>{error}</Alerta>}
        <Campo etiqueta="¿En qué necesitas apoyo?" ayuda="Le llega un aviso. Si acepta y te ayuda, queda registrado como colaboración (y cuenta para su avance).">
          {(id) => <textarea id={id} className="campo" rows={4} value={texto} onChange={(e) => setTexto(e.target.value)} maxLength={500} placeholder="Ej.: Necesito ayuda editando un video de 1 minuto para mañana" autoFocus />}
        </Campo>
      </div>
    </Modal>
  );
}

function Tarjeta({ p, onApoyo, onAsignar }) {
  const e = ESTADO[p.estado];
  return (
    <article className={cx("flex flex-col gap-3 rounded-xl border bg-white p-4", p.estado === "LIBRE" ? "border-verde/40 ring-1 ring-verde/10" : "border-linea")}>
      <div className="flex items-start gap-3">
        <Avatar nombre={p.nombre} />
        <div className="min-w-0 flex-1">
          <h3 className="truncate !text-[15px] font-semibold !text-noche">{p.nombre}{p.es_yo && <span className="ml-1.5 text-xs font-normal text-gris">(tú)</span>}</h3>
          <p className="truncate text-sm text-gris">{p.puesto}</p>
        </div>
        <Insignia tono={e.tono}>{e.texto}</Insignia>
      </div>
      <p className="text-sm text-gris">
        {p.estado === "AUSENTE" ? "Está de permiso o vacaciones hoy." : p.tareas_abiertas === 0
          ? <>Sin tareas abiertas{p.en_revision > 0 && <> · {p.en_revision} esperando validación</>}.</>
          : <><b className="text-tinta">{p.tareas_abiertas}</b> {p.tareas_abiertas === 1 ? "tarea abierta" : "tareas abiertas"}{horas(p.horas_pendientes) && <> · {horas(p.horas_pendientes)}</>}{p.proxima_entrega && <> · próxima entrega {fechaCorta(p.proxima_entrega)}</>}.</>}
      </p>
      {!p.es_yo && (
        <div className="mt-auto flex flex-wrap gap-2">
          <Boton tam="sm" variante="secundario" icono={MessageCircle} onClick={() => window.dispatchEvent(new CustomEvent("adzone:abrir-chat", { detail: { id: p.id, nombre: p.nombre } }))}>Escribirle</Boton>
          {p.puedo_pedir_apoyo && <Boton tam="sm" variante={p.estado === "LIBRE" ? "primario" : "secundario"} icono={HandHeart} onClick={() => onApoyo(p)}>Pedir apoyo</Boton>}
          {p.puedo_asignar && <Boton tam="sm" variante="secundario" icono={Plus} onClick={() => onAsignar(p)}>Asignar tarea</Boton>}
        </div>
      )}
      {!p.es_yo && !p.puedo_pedir_apoyo && p.departamento_id != null && (
        <p className="-mt-1 text-xs text-gris">De otro departamento: escríbele, o pide el apoyo formal por tu supervisor.</p>
      )}
    </article>
  );
}

export default function Disponibilidad() {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  const [vista, setVista] = useState("libres");
  const [buscar, setBuscar] = useState("");
  const [depto, setDepto] = useState("");
  const [apoyo, setApoyo] = useState(null);
  const [asignando, setAsignando] = useState(null);
  const [gente, setGente] = useState([]);
  const avisar = useAviso();

  const cargar = useCallback(() => disponibilidad().then((d) => { setDatos(d); setError(""); }).catch((e) => setError(e.message)), []);
  useEffect(() => { cargar(); }, [cargar]);
  useNovedades(cargar, 30000);
  const asignar = async (p) => { if (!gente.length) { try { setGente(await equipo()); } catch { /* el formulario avisa */ } } setAsignando(p); };

  const deptos = useMemo(() => [...new Set((datos?.personas || []).map((p) => p.departamento).filter(Boolean))].sort(), [datos]);
  const filtradas = useMemo(() => (datos?.personas || []).filter((p) => {
    if (vista === "libres" && p.estado !== "LIBRE") return false;
    if (vista === "poca" && p.estado !== "POCA") return false;
    if (vista === "ocupados" && p.estado !== "OCUPADO") return false;
    if (depto && p.departamento !== depto) return false;
    const t = buscar.toLowerCase();
    return !t || [p.nombre, p.puesto, p.departamento].some((x) => (x || "").toLowerCase().includes(t));
  }), [datos, vista, buscar, depto]);
  const grupos = useMemo(() => {
    const m = new Map();
    filtradas.forEach((p) => { const k = p.departamento || "Sin departamento"; (m.get(k) || m.set(k, []).get(k)).push(p); });
    return [...m.entries()].map(([k, l]) => [k, l.sort((a, b) => ESTADO[a.estado].orden - ESTADO[b.estado].orden || a.tareas_abiertas - b.tareas_abiertas || a.nombre.localeCompare(b.nombre))])
      .sort((a, b) => b[1].filter((x) => x.estado === "LIBRE").length - a[1].filter((x) => x.estado === "LIBRE").length || a[0].localeCompare(b[0]));
  }, [filtradas]);

  if (error && !datos) return <Alerta>{error}</Alerta>;
  if (!datos) return <Cargando />;
  const r = datos.resumen;

  return (
    <div>
      <Cabecera titulo="Quién está libre" descripcion="Personas sin tareas abiertas, de todos los departamentos: pídeles apoyo o escríbeles. Solo se ve cuántas tareas tiene cada quien, nunca de qué son.">
        <Boton variante="secundario" icono={RefreshCw} onClick={cargar}>Actualizar</Boton>
      </Cabecera>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Pestanas className="max-w-xl" valor={vista} onCambio={setVista} opciones={[
          { valor: "libres", etiqueta: "Libres", cuenta: r.libres }, { valor: "poca", etiqueta: "Poca carga", cuenta: r.poca_carga },
          { valor: "ocupados", etiqueta: "Ocupados", cuenta: r.ocupados }, { valor: "todos", etiqueta: "Todos", cuenta: datos.personas.length }]} />
        <div className="relative min-w-52 flex-1 md:max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" aria-hidden />
          <input className="campo h-11 !pl-9" placeholder="Buscar persona o puesto…" value={buscar} onChange={(e) => setBuscar(e.target.value)} aria-label="Buscar persona" />
        </div>
        <select className="campo h-11 w-auto py-0" value={depto} onChange={(e) => setDepto(e.target.value)} aria-label="Departamento">
          <option value="">Todos los departamentos</option>
          {deptos.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
      </div>
      <p className="mb-4 text-xs text-gris">Libre = sin tareas abiertas · Poca carga = 1 a {datos.poca_carga_max} · Ocupado/a = más. Lo que ya entregó y espera validación no cuenta como carga. Quien está de permiso hoy aparece como no disponible.</p>

      {grupos.length === 0 ? (
        <Vacio icono={UsersRound} titulo={vista === "libres" ? "Hoy nadie está libre" : "Nadie coincide"}>
          {vista === "libres" ? "Todas las personas tienen tareas abiertas. Mira «Poca carga» para quienes tienen menos." : "Prueba con otra búsqueda o departamento."}
        </Vacio>
      ) : (
        <div className="space-y-6">
          {grupos.map(([nombre, lista]) => (
            <section key={nombre} aria-label={nombre}>
              <h2 className="mb-2 flex items-baseline gap-2 !text-base font-semibold !text-noche">{nombre}
                <span className="text-xs font-normal text-gris">{lista.filter((x) => x.estado === "LIBRE").length} libre(s) de {lista.length}</span></h2>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{lista.map((p) => <Tarjeta key={p.id} p={p} onApoyo={setApoyo} onAsignar={asignar} />)}</div>
            </section>
          ))}
        </div>
      )}
      <PedirApoyo persona={apoyo} onCerrar={() => setApoyo(null)} onHecho={() => setApoyo(null)} />
      <FormTarea abierto={!!asignando} onCerrar={() => setAsignando(null)} gente={gente} inicial={asignando ? { colaborador: String(asignando.id) } : null}
        onGuardada={(m) => { setAsignando(null); avisar(m || "Tarea asignada."); cargar(); }} />
    </div>
  );
}
