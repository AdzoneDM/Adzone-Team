// Crear, ver y administrar un grupo de chat. Crear y cambiar grupos es de las jefaturas (el servidor lo vuelve a comprobar);
// el resto de las personas solo ve quiénes participan.
import { useEffect, useState } from "react";
import { Search, Trash2, Users, X } from "lucide-react";
import { chatGrupo, chatGrupoCrear, chatGrupoEditar, chatGrupoEliminar, chatPersonas } from "@/lib/api";
import { Alerta, Avatar, Boton, Campo, Modal, useConfirmar } from "@/components/ui";

/** `grupo`: la conversación del grupo (para ver o editar) o null (para crear uno nuevo). */
export default function GrupoModal({ abierto, grupo, departamentos, usuarioId, onCerrar, onGuardado, onEliminado }) {
  const confirmar = useConfirmar();
  const nuevo = !grupo;
  const [nombre, setNombre] = useState("");
  const [area, setArea] = useState("");
  const [miembros, setMiembros] = useState([]); // [{ id, nombre, puesto }]
  const [puedeGestionar, setPuedeGestionar] = useState(true);
  const [texto, setTexto] = useState("");
  const [resultados, setResultados] = useState([]);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    if (!abierto) return;
    setError(""); setTexto(""); setResultados([]);
    if (nuevo) { setNombre(""); setArea(""); setMiembros([]); setPuedeGestionar(true); return; }
    setNombre(grupo.titulo); setArea(grupo.grupo?.departamento_id ? String(grupo.grupo.departamento_id) : ""); setPuedeGestionar(!!grupo.grupo?.puede_gestionar);
    chatGrupo(grupo.id).then((d) => { setMiembros(d.grupo.miembros || []); setPuedeGestionar(!!d.grupo.puede_gestionar); }).catch((e) => setError(e.message));
  }, [abierto, grupo, nuevo]);

  // Buscar personas para agregar (con una pausa corta)
  useEffect(() => {
    if (!abierto || !puedeGestionar || texto.trim().length < 2) { setResultados([]); return undefined; }
    const t = setTimeout(() => chatPersonas(texto.trim()).then(setResultados).catch(() => setResultados([])), 250);
    return () => clearTimeout(t);
  }, [texto, abierto, puedeGestionar]);

  const agregar = (p) => { setMiembros((m) => (m.some((x) => x.id === p.id) ? m : [...m, p])); setTexto(""); setResultados([]); };
  const quitar = (id) => setMiembros((m) => m.filter((x) => x.id !== id));

  const guardar = async () => {
    setError("");
    if (nombre.trim().length < 3) return setError("Ponle un nombre al grupo (mínimo 3 letras).");
    setGuardando(true);
    try {
      const ids = miembros.map((m) => m.id);
      const datos = { nombre: nombre.trim(), departamento: area ? Number(area) : null, miembros: nuevo ? ids.filter((id) => id !== usuarioId) : ids };
      const r = nuevo ? await chatGrupoCrear(datos) : await chatGrupoEditar(grupo.id, datos);
      onGuardado(r);
    } catch (e) { setError(e.message); }
    setGuardando(false);
  };

  const eliminar = async () => {
    if (!(await confirmar({ titulo: `¿Eliminar el grupo «${grupo.titulo}»?`, mensaje: "Se borran sus mensajes y archivos para todas las personas. No se puede deshacer.", boton: "Eliminar grupo", peligro: true }))) return;
    try { await chatGrupoEliminar(grupo.id); onEliminado(grupo.id); } catch (e) { setError(e.message); }
  };

  return (
    <Modal abierto={abierto} onCerrar={onCerrar} ancho="md:max-w-lg" titulo={nuevo ? "Nuevo grupo" : puedeGestionar ? "Administrar el grupo" : grupo.titulo}
      descripcion={nuevo ? "Para una conversación de un área o de las personas que elijas." : puedeGestionar ? "Cambia el nombre o quién participa." : `${miembros.length || grupo.grupo?.n_miembros || ""} personas${grupo.grupo?.departamento ? ` · ${grupo.grupo.departamento}` : ""}`}
      pie={puedeGestionar ? (
        <>
          {!nuevo && <Boton variante="fantasma" icono={Trash2} className="mr-auto text-rojo" onClick={eliminar}>Eliminar grupo</Boton>}
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton cargando={guardando} onClick={guardar}>{nuevo ? "Crear grupo" : "Guardar cambios"}</Boton>
        </>
      ) : <Boton variante="secundario" onClick={onCerrar}>Cerrar</Boton>}>
      <div className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        {puedeGestionar && (
          <>
            <Campo etiqueta="Nombre del grupo">{(id) => <input id={id} className="campo" value={nombre} maxLength={80} onChange={(e) => setNombre(e.target.value)} placeholder="Tecnología, Marketing, Gerencia…" autoComplete="off" />}</Campo>
            <Campo etiqueta="Área" ayuda={nuevo ? "Si eliges un área, entra todo su personal activo. Además puedes sumar a otras personas." : "El área solo sirve para identificar el grupo; las personas se cambian abajo."}>
              {(id) => (
                <select id={id} className="campo" value={area} onChange={(e) => setArea(e.target.value)}>
                  <option value="">Sin área: solo las personas que elija</option>
                  {departamentos.map((d) => <option key={d.id} value={d.id}>{d.nombre}</option>)}
                </select>
              )}
            </Campo>
            <div>
              <label htmlFor="grupo-buscar" className="etiqueta">Agregar personas</label>
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" aria-hidden />
                <input id="grupo-buscar" className="campo pl-9" value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Busca por nombre, cargo o área…" autoComplete="off" />
              </div>
              {resultados.length > 0 && (
                <ul className="mt-1 max-h-44 overflow-y-auto rounded-xl border border-linea bg-white shadow-sm">
                  {resultados.map((p) => (
                    <li key={p.id}>
                      <button type="button" onClick={() => agregar(p)} className="flex w-full items-center gap-2.5 px-3 py-2 text-left hover:bg-fondo">
                        <Avatar nombre={p.nombre} tam="sm" />
                        <span className="min-w-0"><span className="block truncate text-sm font-medium">{p.nombre}</span><span className="block truncate text-xs text-gris">{[p.puesto, p.departamento].filter(Boolean).join(" · ")}</span></span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        )}
        <div>
          <p className="etiqueta flex items-center gap-1.5"><Users className="size-4" aria-hidden />Participantes {miembros.length > 0 && <span className="font-normal text-gris">({miembros.length}{nuevo ? " + tú" : ""})</span>}</p>
          {miembros.length === 0 ? (
            <p className="mt-1 text-sm text-gris">{nuevo ? "Aún no agregas a nadie. Tú entras automáticamente." : "Cargando…"}</p>
          ) : (
            <ul className="mt-1.5 flex flex-wrap gap-1.5">
              {miembros.map((m) => (
                <li key={m.id} className="flex items-center gap-1.5 rounded-full border border-linea bg-fondo py-1 pl-1 pr-2.5 text-sm">
                  <Avatar nombre={m.nombre} tam="sm" className="!size-6 !text-[10px]" />
                  <span title={[m.puesto, m.departamento].filter(Boolean).join(" · ")}>{m.nombre}{m.id === usuarioId ? " (tú)" : ""}</span>
                  {puedeGestionar && m.id !== usuarioId && <button type="button" onClick={() => quitar(m.id)} aria-label={`Quitar a ${m.nombre}`} className="rounded-full p-0.5 text-gris hover:text-rojo"><X className="size-3.5" /></button>}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </Modal>
  );
}
