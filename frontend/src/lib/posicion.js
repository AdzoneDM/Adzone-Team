// Recuerda dónde ibas: al recargar la página o volver atrás, la pantalla vuelve al mismo punto (no al inicio).
// Al entrar a una pantalla nueva desde un enlace, empieza arriba como siempre.
import { useEffect } from "react";
import { useLocation, useNavigationType } from "react-router-dom";

const LLAVE = "adzone:posiciones";
const leer = () => { try { return JSON.parse(sessionStorage.getItem(LLAVE) || "{}"); } catch { return {}; } };
const guardar = (clave, y) => { try { const m = leer(); m[clave] = y; sessionStorage.setItem(LLAVE, JSON.stringify(m)); } catch { /* sin almacenamiento */ } };

export function useRecordarPosicion() {
  const { pathname, search } = useLocation();
  const tipo = useNavigationType(); // POP = recarga o botón atrás/adelante; PUSH = se tocó un enlace
  const clave = pathname + search;

  // Guarda la posición mientras te desplazas (y al cerrar o recargar)
  useEffect(() => {
    let espera = null;
    const ahora = () => guardar(clave, Math.round(window.scrollY));
    const alDesplazar = () => { clearTimeout(espera); espera = setTimeout(ahora, 150); };
    window.addEventListener("scroll", alDesplazar, { passive: true });
    window.addEventListener("pagehide", ahora);
    return () => { clearTimeout(espera); window.removeEventListener("scroll", alDesplazar); window.removeEventListener("pagehide", ahora); };
  }, [clave]);

  // Al llegar: recarga o atrás → vuelve a donde estaba (espera a que la pantalla termine de cargar); enlace nuevo → arriba
  useEffect(() => {
    if (tipo !== "POP") { window.scrollTo(0, 0); return undefined; }
    const y = Number(leer()[clave] || 0);
    if (!y) return undefined;
    let intentos = 0;
    const t = setInterval(() => {
      intentos += 1;
      // La pantalla carga sus datos poco a poco: se espera a que tenga la altura suficiente (hasta ~4 s)
      if (document.documentElement.scrollHeight - window.innerHeight >= y || intentos >= 40) { window.scrollTo(0, y); clearInterval(t); }
    }, 100);
    return () => clearInterval(t);
  }, [clave, tipo]);
}
