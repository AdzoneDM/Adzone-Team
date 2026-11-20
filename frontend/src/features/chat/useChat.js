// Sincronización del chat. Sin websockets: consulta cada pocos segundos y solo con la pestaña visible.
// Con el chat cerrado hace una consulta mínima (el contador de no leídos).
import { useCallback, useEffect, useRef, useState } from "react";
import { chatBorrar, chatConversaciones, chatEnviar, chatLeido, chatMensajes, chatResumen } from "@/lib/api";

const CADA_MENSAJES_MS = 3000;
const CADA_LISTA_MS = 5000;
const CADA_CERRADO_MS = 15000;

/** Repite `tarea` cada `ms` mientras la pestaña esté visible, y al volver a ella. */
function useLatido(tarea, ms, activo = true) {
  const ref = useRef(tarea);
  useEffect(() => { ref.current = tarea; });
  useEffect(() => {
    if (!activo) return undefined;
    const tic = () => { if (document.visibilityState === "visible") ref.current(); };
    tic();
    const t = setInterval(tic, ms);
    document.addEventListener("visibilitychange", tic);
    return () => { clearInterval(t); document.removeEventListener("visibilitychange", tic); };
  }, [ms, activo]);
}

/** Lista de conversaciones y total de no leídos (abierto: la lista completa; cerrado: solo el contador). */
export function useConversaciones({ abierto, activo }) {
  const [conversaciones, setConversaciones] = useState([]);
  const [noLeidos, setNoLeidos] = useState(0);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  const refrescar = useCallback(async () => {
    try {
      const r = await chatConversaciones();
      setConversaciones(r.conversaciones);
      setNoLeidos(r.no_leidos);
      setError("");
    } catch (e) {
      setError(e.message || "No se pudo cargar el chat.");
    } finally {
      setCargando(false);
    }
  }, []);

  useLatido(refrescar, CADA_LISTA_MS, activo && abierto);
  useLatido(async () => { try { setNoLeidos((await chatResumen()).no_leidos); } catch { /* sin conexión: se reintenta */ } }, CADA_CERRADO_MS, activo && !abierto);

  return { conversaciones, noLeidos, cargando, error, refrescar };
}

/** Mezcla por id (sin duplicar) y deja todo en orden. Un mensaje con el mismo id reemplaza al anterior (p. ej. al borrarse). */
function mezclar(actuales, nuevos) {
  const porId = new Map(actuales.map((m) => [m.id, m]));
  nuevos.forEach((m) => porId.set(m.id, m));
  return [...porId.values()].sort((a, b) => a.id - b.id);
}

/** Mensajes de una conversación. Se monta al abrirla y se desmonta al salir (con `key` por conversación). */
export function useMensajes(conversacion, { alLeer } = {}) {
  const [mensajes, setMensajes] = useState([]);
  const [hayMas, setHayMas] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [cargado, setCargado] = useState(false);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
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
      aplicar(r.mensajes);
      setError("");
    } catch { setError("Sin conexión. Reintentando…"); }
  }, CADA_MENSAJES_MS, cargado);

  // Mientras la conversación está abierta, lo que llega se da por leído
  const ultimo = mensajes.length ? mensajes[mensajes.length - 1].id : 0;
  useEffect(() => {
    if (ultimo) chatLeido(conversacion, ultimo).then(() => alLeer?.()).catch(() => {});
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

  const enviar = useCallback(async (texto) => {
    setEnviando(true);
    try {
      aplicar([await chatEnviar(conversacion, texto)]);
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    } finally {
      setEnviando(false);
    }
  }, [conversacion, aplicar]);

  const borrar = useCallback(async (id) => {
    try {
      aplicar([await chatBorrar(id)]);
    } catch (e) {
      setError(e.message);
    }
  }, [aplicar]);

  return { mensajes, hayMas, cargando, error, enviando, enviar, borrar, cargarAnteriores, reintentar: cargarInicial, limpiarError: () => setError("") };
}
