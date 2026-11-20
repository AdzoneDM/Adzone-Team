// Estado y sincronización del chat global. Sin websockets: consulta cada pocos segundos, solo con la pestaña visible,
// y con el chat cerrado hace una consulta mínima (el contador de no leídos).
import { useCallback, useEffect, useRef, useState } from "react";
import { chatBorrar, chatEnviar, chatLeido, chatMensajes, chatResumen } from "@/lib/api";

const CADA_ABIERTO_MS = 3000;
const CADA_CERRADO_MS = 15000;

/** Mezcla por id (sin duplicar) y deja todo en orden. Un mensaje nuevo con el mismo id reemplaza al anterior (p. ej. al borrarse). */
function mezclar(actuales, nuevos) {
  const porId = new Map(actuales.map((m) => [m.id, m]));
  nuevos.forEach((m) => porId.set(m.id, m));
  return [...porId.values()].sort((a, b) => a.id - b.id);
}

export function useChat({ abierto, usuarioId }) {
  const [mensajes, setMensajes] = useState([]);
  const [hayMas, setHayMas] = useState(false);
  const [noLeidos, setNoLeidos] = useState(0);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const ultimoId = useRef(0);
  const inicial = useRef(false);

  const aplicar = useCallback((lista) => {
    if (!lista.length) return;
    setMensajes((prev) => mezclar(prev, lista));
    ultimoId.current = Math.max(ultimoId.current, ...lista.map((m) => m.id));
  }, []);

  const cargarInicial = useCallback(async () => {
    setCargando(true);
    setError("");
    try {
      const r = await chatMensajes();
      setMensajes(r.mensajes);
      setHayMas(r.hay_mas);
      ultimoId.current = Math.max(0, ...r.mensajes.map((m) => m.id));
      inicial.current = true;
    } catch (e) {
      setError(e.message || "No se pudo cargar el chat.");
    } finally {
      setCargando(false);
    }
  }, []);

  const cargarAnteriores = useCallback(async () => {
    if (!mensajes.length) return;
    try {
      const r = await chatMensajes({ antes: mensajes[0].id });
      setMensajes((prev) => mezclar(prev, r.mensajes));
      setHayMas(r.hay_mas);
    } catch (e) {
      setError(e.message || "No se pudieron cargar los mensajes anteriores.");
    }
  }, [mensajes]);

  // Al abrir el chat: primera carga (una sola vez)
  useEffect(() => {
    if (abierto && !inicial.current) cargarInicial();
  }, [abierto, cargarInicial]);

  // Sincronización periódica
  useEffect(() => {
    if (!usuarioId) return undefined;
    let activo = true;
    let controlador = null;
    const tic = async () => {
      if (document.visibilityState !== "visible") return;
      controlador?.abort();
      controlador = new AbortController();
      try {
        if (abierto && inicial.current) {
          const r = await chatMensajes({ despues: ultimoId.current }, controlador.signal);
          if (activo) { aplicar(r.mensajes); setError(""); }
        } else if (!abierto) {
          const r = await chatResumen();
          if (activo) setNoLeidos(r.no_leidos);
        }
      } catch (e) {
        if (e.name !== "AbortError" && activo && abierto) setError("Sin conexión. Reintentando…");
      }
    };
    tic();
    const t = setInterval(tic, abierto ? CADA_ABIERTO_MS : CADA_CERRADO_MS);
    document.addEventListener("visibilitychange", tic);
    return () => { activo = false; controlador?.abort(); clearInterval(t); document.removeEventListener("visibilitychange", tic); };
  }, [abierto, usuarioId, aplicar]);

  // Con el chat abierto, lo que llega se da por leído
  useEffect(() => {
    if (!abierto || !mensajes.length) return;
    const ultimo = mensajes[mensajes.length - 1].id;
    chatLeido(ultimo).then((r) => setNoLeidos(r.no_leidos)).catch(() => {});
  }, [abierto, mensajes]);

  const enviar = useCallback(async (texto) => {
    setEnviando(true);
    try {
      const m = await chatEnviar(texto);
      aplicar([m]);
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    } finally {
      setEnviando(false);
    }
  }, [aplicar]);

  const borrar = useCallback(async (id) => {
    try {
      aplicar([await chatBorrar(id)]);
    } catch (e) {
      setError(e.message);
    }
  }, [aplicar]);

  return { mensajes, hayMas, noLeidos, cargando, error, enviando, enviar, borrar, cargarAnteriores, reintentar: cargarInicial, limpiarError: () => setError("") };
}
