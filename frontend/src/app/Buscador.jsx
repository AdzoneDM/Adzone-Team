// Buscador global (Ctrl+K o /): órdenes, proyectos, clientes, tareas y, para Finanzas, facturas.
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Building2, ClipboardList, FileText, FolderKanban, ListChecks, Receipt, Search } from "lucide-react";
import { buscar } from "@/lib/api";
import { cx } from "@/components/ui";

const ICONO = { orden: ClipboardList, proyecto: FolderKanban, cliente: Building2, tarea: ListChecks, factura: Receipt, cotizacion: FileText };
const NOMBRE = { orden: "Orden", proyecto: "Proyecto", cliente: "Cliente", tarea: "Tarea", factura: "Factura", cotizacion: "Cotización" };

export default function Buscador({ abierto, onCerrar }) {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [res, setRes] = useState([]);
  const [i, setI] = useState(0);
  const [cargando, setCargando] = useState(false);
  const ref = useRef(null);
  const input = useRef(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (abierto && !d.open) { d.showModal(); setQ(""); setRes([]); setTimeout(() => input.current?.focus(), 10); }
    if (!abierto && d.open) d.close();
  }, [abierto]);
  useEffect(() => {
    if (q.trim().length < 2) { setRes([]); return undefined; }
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      setCargando(true);
      buscar(q.trim(), ctrl.signal).then((r) => { setRes(r); setI(0); }).catch(() => {}).finally(() => setCargando(false));
    }, 200);
    return () => { clearTimeout(t); ctrl.abort(); };
  }, [q]);
  const ir = (r) => { onCerrar(); navigate(r.enlace); };
  return (
    <dialog ref={ref} onCancel={(e) => { e.preventDefault(); onCerrar(); }} onClick={(e) => { if (e.target === ref.current) onCerrar(); }}
      className="m-0 mx-auto mt-[8vh] w-[min(40rem,calc(100vw-1.5rem))] max-w-none rounded-2xl bg-white p-0 text-tinta shadow-2xl backdrop:bg-noche-900/50" aria-label="Buscar">
      <div className="flex items-center gap-3 border-b border-linea-suave px-4">
        <Search className="size-5 text-gris" aria-hidden />
        <input ref={input} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Busca una orden, proyecto, cliente, tarea o factura…"
          className="h-14 flex-1 bg-transparent text-base focus:outline-none" aria-label="Buscar"
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setI((x) => Math.min(x + 1, res.length - 1)); }
            if (e.key === "ArrowUp") { e.preventDefault(); setI((x) => Math.max(x - 1, 0)); }
            if (e.key === "Enter" && res[i]) ir(res[i]);
          }} />
        <kbd className="hidden rounded border border-linea px-1.5 text-xs text-gris md:inline">Esc</kbd>
      </div>
      <ul className="max-h-[60vh] overflow-y-auto p-2" role="listbox">
        {q.trim().length < 2 && <li className="px-3 py-6 text-center text-sm text-gris">Escribe al menos dos letras. Ej.: «OT-2026-0012», «Merengue», «lona».</li>}
        {q.trim().length >= 2 && !cargando && !res.length && <li className="px-3 py-6 text-center text-sm text-gris">Nada encontrado.</li>}
        {res.map((r, j) => {
          const I = ICONO[r.tipo];
          return (
            <li key={`${r.tipo}-${r.id}`} role="option" aria-selected={j === i}>
              <button type="button" onClick={() => ir(r)} onMouseEnter={() => setI(j)}
                className={cx("flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left", j === i && "bg-azul/8")}>
                <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-fondo text-azul"><I className="size-4" /></span>
                <span className="min-w-0 flex-1"><span className="block truncate font-medium">{r.titulo}</span><span className="block truncate text-sm text-gris">{r.sub}</span></span>
                <span className="text-xs text-gris">{NOMBRE[r.tipo]}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </dialog>
  );
}
