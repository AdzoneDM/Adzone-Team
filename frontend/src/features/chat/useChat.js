// Sincronización del chat. Sin websockets: consulta cada pocos segundos y solo con la pestaña visible.
// Con el chat cerrado hace una consulta mínima (el contador de no leídos).
import { useCallback, useEffect, useRef, useState } from "react";
import { chatBorrar, chatConversaciones, chatEditar, chatReaccion, chatEnviar, chatLeido, chatMensajes, chatResumen } from "@/lib/api";
import { mostrarAvisoLocal } from "@/lib/notificaciones";
import { sonarMensaje } from "@/lib/sonido";

const CADA_MENSAJES_MS = 3000;
const CADA_LISTA_MS = 5000;
const CADA_CERRADO_MS = 15000;

/** Repite `tarea` cada `ms` mientras la pestaña esté visible, y al volver a ella.
 *  Con `ocultoCada` (n > 0) también sigue con la pestaña oculta, una de cada n veces: así un mensaje nuevo suena aunque estés en otra ventana. */
function useLatido(tarea, ms, activo = true, ocultoCada = 0) {
  const ref = useRef(tarea);
  useEffect(() => { ref.current = tarea; });
  useEffect(() => {
    if (!activo) return undefined;
    let ciclo = 0;
    const tic = () => { if (document.visibilityState === "visible") ref.current(); };
    const latido = () => { ciclo += 1; if (document.visibilityState === "visible" || (ocultoCada && ciclo % ocultoCada === 0)) ref.current(); };
    tic();
    const t = setInterval(latido, ms);
    document.addEventListener("visibilitychange", tic);
    return () => { clearInterval(t); document.removeEventListener("visibilitychange", tic); };
  }, [ms, activo, ocultoCada]);
}

/** Lista de conversaciones y total de no leídos (abierto: la lista completa; cerrado: solo el contador).
 *  Cuando llega un mensaje nuevo de otra persona suena (y, con la pestaña oculta, sale un aviso del sistema). */
export function useConversaciones({ abierto, activo, usuarioId, activaId }) {
  const [conversaciones, setConversaciones] = useState([]);
  const [noLeidos, setNoLeidos] = useState(0);
  const [grupos, setGrupos] = useState({ puedeCrear: false, departamentos: [] }); // lo que puede hacer con grupos (lo decide el servidor)
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const previo = useRef(null);   // no leídos de la medición anterior (null = aún no hay)
  const activa = useRef(activaId);
  useEffect(() => { activa.current = activaId; });

  /** Compara con la medición anterior: si subió, hay un mensaje nuevo. `lista` sirve para decir de quién es. */
  const medir = useCallback((total, lista) => {
    const antes = previo.current;
    previo.current = total;
    if (antes === null || total <= antes) return;
    sonarMensaje();
    if (document.visibilityState === "hidden" && lista) {
      const c = lista.filter((x) => x.no_leidos > 0 && x.ultimo_autor !== usuarioId)
        .sort((a, b) => String(b.ultima_actividad).localeCompare(String(a.ultima_actividad)))[0];
      if (c) mostrarAvisoLocal({ id: `chat-${c.id}-${c.ultima_actividad}`, titulo: c.titulo, mensaje: c.ultimo_texto || "Nuevo mensaje", enlace: "/" }, false);
    }
  }, [usuarioId]);

  const refrescar = useCallback(async () => {
    try {
      const r = await chatConversaciones();
      setConversaciones(r.conversaciones);
      setNoLeidos(r.no_leidos);
      setGrupos({ puedeCrear: !!r.puede_crear_grupos, departamentos: r.departamentos || [] });
      // A la vista, la conversación abierta se lee en el acto (ya suena en su propia pantalla): no se cuenta aquí
      const propios = document.visibilityState === "visible" ? r.conversaciones.filter((c) => c.id !== activa.current) : r.conversaciones;
      medir(propios.reduce((n, c) => n + c.no_leidos, 0), r.conversaciones);
      setError("");
    } catch (e) {
      setError(e.message || "No se pudo cargar el chat.");
    } finally {
      setCargando(false);
    }
  }, [medir]);

  useEffect(() => { previo.current = null; }, [abierto]); // al abrir o cerrar se vuelve a medir desde cero

  useLatido(refrescar, CADA_LISTA_MS, activo && abierto, 6);
  useLatido(async () => {
    try {
      if (document.visibilityState === "hidden") { await refrescar(); return; } // oculta: se trae la lista para poder avisar de quién es
      const total = (await chatResumen()).no_leidos;
      setNoLeidos(total);
      medir(total, null);
    } catch { /* sin conexión: se reintenta */ }
  }, CADA_CERRADO_MS, activo && !abierto, 2);

  return { conversaciones, noLeidos, cargando, error, refrescar, grupos };
}

/** Mezcla por id (sin duplicar) y deja todo en orden. Un mensaje con el mismo id reemplaza al anterior (p. ej. al borrarse). */
function mezclar(actuales, nuevos) {
  const porId = new Map(actuales.map((m) => [m.id, m]));
  nuevos.forEach((m) => porId.set(m.id, m));
  return [...porId.values()].sort((a, b) => a.id - b.id);
}

/** Mensajes de una conversación. Se monta al abrirla y se desmonta al salir (con `key` por conversación). */
export function useMensajes(conversacion, { alLeer, usuarioId } = {}) {
  const [mensajes, setMensajes] = useState([]);
  const [hayMas, setHayMas] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [cargado, setCargado] = useState(false);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [progreso, setProgreso] = useState(null); // {actual, total, nombre, pct}: avance de la subida de archivos
  const [lectores, setLectores] = useState({ lista: [], total: 0 }); // quién leyó hasta dónde: el «visto» de tus mensajes
  const ultimoId = useRef(0);

  const aplicar = useCallback((lista) => {
    if (!lista.length) return;
    setMensajes((prev) => mezclar(prev, lista));
    ultimoId.current = Math.max(ultimoId.current, ...lista.map((m) => m.id));
  }, []);

  const cargarInicial = useCallback(async () => {
    setCargando(true);
    setError("");
    try {
      const r = await chatMensajes(conversacion);
      setMensajes(r.mensajes);
      setHayMas(r.hay_mas);
      setLectores({ lista: r.lectores || [], total: r.participantes || 0 });
      ultimoId.current = Math.max(0, ...r.mensajes.map((m) => m.id));
      setCargado(true);
    } catch (e) {
      setError(e.message || "No se pudo cargar la conversación.");
    } finally {
      setCargando(false);
    }
  }, [conversacion]);

  useEffect(() => { cargarInicial(); }, [cargarInicial]);

  useLatido(async () => {
    try {
      const r = await chatMensajes(conversacion, { despues: ultimoId.current });
      // Mensaje nuevo de la otra persona en la conversación que tienes abierta: suena
      if (r.mensajes.some((m) => m.autor !== usuarioId && !m.eliminado)) sonarMensaje();
      aplicar(r.mensajes);
      setLectores({ lista: r.lectores || [], total: r.participantes || 0 });
      setError("");
    } catch { setError("Sin conexión. Reintentando…"); }
  }, CADA_MENSAJES_MS, cargado);

  // Visto real: solo cuenta lo que llega mientras la conversación está abierta y a la vista (pestaña visible y ventana activa).
  // Si la persona está en otra ventana, se marca cuando vuelve.
  const ultimo = mensajes.length ? mensajes[mensajes.length - 1].id : 0;
  useEffect(() => {
    if (!ultimo) return undefined;
    const marcar = () => {
      if (document.visibilityState !== "visible" || !document.hasFocus()) return;
      chatLeido(conversacion, ultimo).then(() => alLeer?.()).catch(() => {});
    };
    marcar();
    document.addEventListener("visibilitychange", marcar);
    window.addEventListener("focus", marcar);
    return () => { document.removeEventListener("visibilitychange", marcar); window.removeEventListener("focus", marcar); };
  }, [conversacion, ultimo, alLeer]);

  const cargarAnteriores = useCallback(async () => {
    if (!mensajes.length) return;
    try {
      const r = await chatMensajes(conversacion, { antes: mensajes[0].id });
      setMensajes((prev) => mezclar(prev, r.mensajes));
      setHayMas(r.hay_mas);
    } catch (e) {
      setError(e.message || "No se pudieron cargar los mensajes anteriores.");
    }
  }, [conversacion, mensajes]);

  // Varios archivos a la vez: el servidor guarda un archivo por mensaje, así que se envían en orden (el texto va con el primero).
  // Devuelve cuántos alcanzó a enviar para que, si falla uno, la persona no pierda lo que falta.
  const enviar = useCallback(async (texto, archivos = [], respondeA = null) => {
    setEnviando(true);
    const lista = archivos.length ? archivos : [null];
    let hechos = 0;
    try {
      for (const a of lista) {
        if (a) setProgreso({ actual: hechos + 1, total: lista.length, nombre: a.name, pct: 0 });
        aplicar([await chatEnviar(conversacion, hechos === 0 ? texto : "", a, (p) => setProgreso((x) => (x ? { ...x, pct: Math.round(p * 100) } : x)),
          hechos === 0 ? respondeA : null)]);
        hechos += 1;
      }
      return { ok: true, hechos };
    } catch (e) {
      setError(e.message);
      return { ok: false, hechos, mensaje: e.message };
    } finally {
      setEnviando(false);
      setProgreso(null);
    }
  }, [conversacion, aplicar]);

  const borrar = useCallback(async (id) => {
    try {
      aplicar([await chatBorrar(id)]);
    } catch (e) {
      setError(e.message);
    }
  }, [aplicar]);

  // Devuelve true si se guardó (para cerrar el modo edición); si pasó el tiempo, muestra el motivo
  const editar = useCallback(async (id, texto) => {
    try {
      aplicar([await chatEditar(id, texto)]);
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    }
  }, [aplicar]);

  const reaccionar = useCallback(async (id, emoji) => {
    try {
      aplicar([await chatReaccion(id, emoji)]);
    } catch (e) {
      setError(e.message);
    }
  }, [aplicar]);

  return { mensajes, lectores, progreso, hayMas, cargando, error, enviando, enviar, borrar, editar, reaccionar, cargarAnteriores, reintentar: cargarInicial, limpiarError: () => setError("") };
}
