// Piezas de los casos operativos: estados, prioridad y el formulario para reportar.
import { useRef, useState } from "react";
import { Paperclip, X } from "lucide-react";
import { reportarCaso } from "@/lib/api";
import { Alerta, Boton, Campo, Modal, cx } from "@/components/ui";

export const ESTADO = {
  RECIBIDO: { texto: "Recibido", clase: "bg-[#eef1f7] text-[#3d4a63]" },
  EN_ATENCION: { texto: "En atención", clase: "bg-azul/10 text-azul" },
  PENDIENTE_VALIDACION: { texto: "Pendiente de validación", clase: "bg-[#f0ebfb] text-[#6d4ac8]" },
  CERRADO: { texto: "Cerrado", clase: "bg-verde-50 text-verde" },
};
export const PRIORIDAD = {
  ALTA: { texto: "Alta", clase: "bg-rojo-50 text-rojo", punto: "bg-rojo" },
  MEDIA: { texto: "Media", clase: "bg-amarillo-50 text-[#8a5a00]", punto: "bg-amarillo-600" },
  BAJA: { texto: "Baja", clase: "bg-fondo text-gris", punto: "bg-gris/60" },
};

export const Chip = ({ clase, children }) => <span className={cx("inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[11.5px] font-semibold", clase)}>{children}</span>;
export const EstadoCaso = ({ c }) => <Chip clase={(ESTADO[c.estado] || ESTADO.RECIBIDO).clase}>{(ESTADO[c.estado] || {}).texto || c.estado}</Chip>;
export const PrioridadCaso = ({ p }) => (p ? <Chip clase={PRIORIDAD[p].clase}><span className={cx("size-1.5 rounded-full", PRIORIDAD[p].punto)} />{PRIORIDAD[p].texto}</Chip>
  : <Chip clase="border border-dashed border-linea text-gris">Sin prioridad</Chip>);

export function Archivos({ archivos, setArchivos, max = 5 }) {
  const entrada = useRef(null);
  return (
    <div>
      <input ref={entrada} type="file" multiple hidden accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.txt,.csv"
        onChange={(e) => { setArchivos((l) => [...l, ...Array.from(e.target.files || [])].slice(0, max)); e.target.value = ""; }} />
      <button type="button" onClick={() => entrada.current?.click()} disabled={archivos.length >= max}
        className="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-linea px-3 py-2 text-sm text-gris hover:border-azul hover:text-azul disabled:opacity-50">
        <Paperclip className="size-4" aria-hidden />Adjuntar evidencia (capturas, PDF…)
      </button>
      {archivos.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {archivos.map((a, i) => (
            <li key={`${a.name}-${i}`} className="inline-flex max-w-full items-center gap-1 rounded-full bg-fondo py-1 pl-2.5 pr-1 text-xs">
              <span className="truncate">{a.name}</span>
              <button type="button" onClick={() => setArchivos((l) => l.filter((_, j) => j !== i))} aria-label={`Quitar ${a.name}`} className="rounded-full p-0.5 hover:bg-linea"><X className="size-3" /></button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Reportar un caso: lo puede hacer cualquier persona. Lo recibe Operaciones. */
export function ModalReportar({ abierto, opciones, onCerrar, onCreado }) {
  const vacio = { tipo: "INCIDENCIA", categoria: "OTRO", impacto: "MEDIO", titulo: "", descripcion: "", referencia: "" };
  const [f, setF] = useState(vacio);
  const [archivos, setArchivos] = useState([]);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const poner = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }));
  const enviar = async () => {
    setEnviando(true); setError("");
    try {
      const c = await reportarCaso(f, archivos);
      setF(vacio); setArchivos([]);
      onCreado(c);
    } catch (e) { setError(e.message); }
    setEnviando(false);
  };
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo="Reportar un caso" descripcion="Lo recibe la Dirección de Operaciones: lo registra, lo prioriza y lo deriva al área que corresponde."
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton><Boton onClick={enviar} cargando={enviando} disabled={!f.titulo.trim() || f.descripcion.trim().length < 10}>Enviar reporte</Boton></>}>
      <div className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        <div role="radiogroup" aria-label="Tipo de caso" className="grid grid-cols-3 gap-2">
          {(opciones?.tipos || []).map(([v, t]) => (
            <button key={v} type="button" role="radio" aria-checked={f.tipo === v} onClick={() => setF((x) => ({ ...x, tipo: v }))}
              className={cx("rounded-xl border px-2 py-2.5 text-sm font-medium transition", f.tipo === v ? "border-azul bg-azul/5 text-azul ring-2 ring-azul/15" : "border-linea text-tinta hover:bg-fondo")}>{t}</button>
          ))}
        </div>
        <Campo etiqueta="Título">{(id) => <input id={id} className="campo" maxLength={160} value={f.titulo} onChange={poner("titulo")} placeholder="Ej.: La impresora grande se atasca con vinil" />}</Campo>
        <Campo etiqueta="¿Qué pasa?" ayuda="Qué ocurre, desde cuándo y a quién afecta. Solo los datos necesarios.">{(id) => <textarea id={id} rows={4} className="campo" maxLength={4000} value={f.descripcion} onChange={poner("descripcion")} />}</Campo>
        <div className="grid gap-3 sm:grid-cols-2">
          <Campo etiqueta="Tema">{(id) => <select id={id} className="campo" value={f.categoria} onChange={poner("categoria")}>{(opciones?.categorias || []).map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select>}</Campo>
          <Campo etiqueta="Impacto">{(id) => <select id={id} className="campo" value={f.impacto} onChange={poner("impacto")}>{(opciones?.impactos || []).map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select>}</Campo>
        </div>
        <Campo etiqueta="Referencia (opcional)" ayuda="El código de lo que se reporta, si existe: «OT-26-0012», «tarea 381», el nombre del cliente…">{(id) => <input id={id} className="campo" maxLength={160} value={f.referencia} onChange={poner("referencia")} />}</Campo>
        <Archivos archivos={archivos} setArchivos={setArchivos} />
      </div>
    </Modal>
  );
}
