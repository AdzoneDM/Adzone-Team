// Al entrar a la plataforma, si hoy todavía no marcaste tu entrada, aparece esta pantalla para hacerlo con un toque.
import { useCallback, useEffect, useState } from "react";
import { Play } from "lucide-react";
import { estadoJornada, marcarJornada } from "@/lib/api";
import { ZONA, horaExacta, primerNombre } from "@/lib/formato";
import { datosDeLugar } from "@/lib/ubicacion";
import { useSesion } from "@/lib/sesion";
import { Boton, useAviso } from "@/components/ui";

const LLAVE = "adzone:entrada-despues";
const ESPERA_MS = 30 * 60 * 1000; // si no se pudo iniciar, «Cerrar por ahora» la oculta media hora

const leerPosposicion = (uid) => {
  try { const v = JSON.parse(sessionStorage.getItem(LLAVE) || "null"); return v && v.uid === uid && v.hasta > Date.now(); } catch { return false; }
};

export default function PantallaEntrada() {
  const { usuario } = useSesion();
  const avisar = useAviso();
  const [estado, setEstado] = useState(null);
  const [oculta, setOculta] = useState(() => leerPosposicion(usuario?.id));
  const [enviando, setEnviando] = useState(false);
  const [fallo, setFallo] = useState(""); // por qué no se pudo iniciar (p. ej. ubicación): solo entonces se ofrece cerrar la pantalla
  const [, setLatido] = useState(0);

  const cargar = useCallback(async () => {
    try {
      const antes = performance.now();
      const d = await estadoJornada();
      setEstado({ ...d, medio: (antes + performance.now()) / 2, servidorMs: Date.parse(d.ahora) });
    } catch { /* si no se puede consultar, no estorba */ }
  }, []);

  useEffect(() => {
    cargar();
    window.addEventListener("adzone:jornada", cargar);
    return () => window.removeEventListener("adzone:jornada", cargar);
  }, [cargar]);

  // Falta marcar: es día de trabajo, marcar es obligatorio para esta persona y todavía no hay ninguna marca hoy.
  // «SIN_CONTROL» es quien aún no ha usado el control de horario: justo a esa persona hay que pedirle que empiece.
  const falta = !!estado && estado.estado === "FUERA" && estado.marca_obligatoria !== false && estado.hoy?.laborable
    && ["PENDIENTE", "TARDE_SIN_MARCAR", "SIN_CONTROL"].includes(estado.hoy?.estado);
  const visible = falta && !oculta;

  useEffect(() => {
    if (!visible) return undefined;
    const t = setInterval(() => setLatido((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, [visible]);

  // «Comenzar» inicia la jornada: marca la entrada y arranca el contador de tiempo
  const marcar = async () => {
    setEnviando(true);
    setFallo("");
    try {
      const lugar = await datosDeLugar(estado.donde_marca);
      const r = await marcarJornada("ENTRADA", { movil: window.matchMedia("(max-width: 767px)").matches, ...lugar });
      avisar(`Jornada iniciada a las ${horaExacta(r?.momento)}. ¡Buen día!`);
      window.dispatchEvent(new Event("adzone:jornada"));
    } catch (e) { setFallo(e.message); }
    setEnviando(false);
  };

  const despues = () => {
    try { sessionStorage.setItem(LLAVE, JSON.stringify({ uid: usuario?.id, hasta: Date.now() + ESPERA_MS })); } catch { /* sin almacenamiento */ }
    setOculta(true);
  };

  if (!visible) return null;
  const ahora = estado.servidorMs + (performance.now() - estado.medio);
  const tarde = estado.hoy.estado === "TARDE_SIN_MARCAR";
  const dia = new Date(ahora).toLocaleDateString("es-DO", { timeZone: ZONA, weekday: "long", day: "numeric", month: "long" });
  const horaDelDia = Number(new Date(ahora).toLocaleTimeString("en-GB", { timeZone: ZONA, hour: "2-digit", hour12: false }).slice(0, 2));
  const saludo = horaDelDia < 12 ? "Buen día" : horaDelDia < 19 ? "Buenas tardes" : "Buenas noches";
  return (
    <div className="fixed inset-0 z-[75] flex items-center justify-center bg-noche-900/85 p-4 backdrop-blur-md" role="dialog" aria-modal="true" aria-labelledby="entrada-titulo">
      <div className="w-full max-w-md animate-[entrar-alerta_0.35s_cubic-bezier(0.2,0.9,0.3,1.15)] overflow-hidden rounded-3xl bg-white text-center shadow-[0_30px_90px_-20px_rgba(0,0,0,0.6)] motion-reduce:animate-none">
        <div className="h-2 bg-amarillo" />
        <div className="px-6 pb-6 pt-8 sm:px-8">
          <p className="text-sm font-medium text-gris first-letter:uppercase">{dia}</p>
          <p className="mt-2 font-display text-5xl font-semibold tabular-nums text-noche sm:text-6xl" aria-label="Hora oficial">{horaExacta(ahora)}</p>
          <h2 id="entrada-titulo" className="mt-5 text-2xl font-semibold text-tinta">{saludo}, {primerNombre(usuario?.nombre || "")}</h2>
          <p className="mt-2 text-[15px] text-gris">
            {tarde
              ? "Ya pasó tu hora de entrada. Toca Comenzar para iniciar tu jornada y tu contador de tiempo ahora."
              : `Tu turno empieza a las ${estado.hoy.turno?.[0] || "—"}. Toca Comenzar para iniciar tu jornada y tu contador de tiempo.`}
          </p>
          {fallo && <p role="alert" className="mt-4 rounded-lg bg-rojo-50 px-3 py-2 text-sm text-rojo">{fallo}</p>}
          <Boton icono={Play} onClick={marcar} cargando={enviando} className="mt-6 !h-14 w-full !text-base" autoFocus>Comenzar</Boton>
          {fallo && <button type="button" onClick={despues} className="mt-3 rounded-lg px-3 py-2 text-sm font-medium text-gris hover:bg-fondo hover:text-tinta">Cerrar por ahora</button>}
        </div>
      </div>
    </div>
  );
}
