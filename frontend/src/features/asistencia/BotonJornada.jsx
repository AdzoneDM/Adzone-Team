// Marcar entrada, pausa, regreso y salida desde cualquier pantalla (arriba, junto al buscador).
import { useCallback, useEffect, useRef, useState } from "react";
import { Coffee, LogIn, LogOut, Play } from "lucide-react";
import { estadoJornada, marcarJornada } from "@/lib/api";
import { horaExacta, relojSeg } from "@/lib/formato";
import { datosDeLugar } from "@/lib/ubicacion";
import { Boton, Modal, cx, useAviso } from "@/components/ui";

const TEXTO = { ENTRADA: "Marcar entrada", PAUSA: "Pausa", REGRESO: "Volver", SALIDA: "Salida" };
const ICONO = { ENTRADA: LogIn, PAUSA: Coffee, REGRESO: Play, SALIDA: LogOut };
const MOTIVOS = ["Almuerzo", "Diligencia personal", "Reunión fuera", "Otro"];

export function useJornada() {
  const [estado, setEstado] = useState(null);
  // Se sincroniza con la hora oficial del servidor (la que se estampa al marcar), no con el reloj de la computadora.
  // El punto de referencia es el momento medio de la consulta (compensa la demora de la red) medido con un reloj que no se puede mover.
  const cargar = useCallback(async () => {
    try {
      const antes = performance.now();
      const d = await estadoJornada();
      const despues = performance.now();
      setEstado({ ...d, medio: (antes + despues) / 2, servidorMs: Date.parse(d.ahora) });
    } catch { /* se reintenta en el siguiente ciclo */ }
  }, []);
  useEffect(() => {
    cargar();
    const t = setInterval(() => document.visibilityState === "visible" && cargar(), 60000);
    window.addEventListener("adzone:jornada", cargar);
    return () => { clearInterval(t); window.removeEventListener("adzone:jornada", cargar); };
  }, [cargar]);
  return [estado, cargar];
}

export default function BotonJornada() {
  const avisar = useAviso();
  const [estado, cargar] = useJornada();
  const [abierto, setAbierto] = useState(false);
  const [pidiendoMotivo, setPidiendoMotivo] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const caja = useRef(null);
  const [, setLatido] = useState(0);
  const corriendo = estado?.estado === "TRABAJANDO";
  useEffect(() => {  // el contador y la hora oficial avanzan cada segundo (mientras se trabaja o el panel está abierto)
    if (!corriendo && !abierto) return undefined;
    const t = setInterval(() => setLatido((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, [corriendo, abierto]);
  useEffect(() => {
    if (!abierto) return undefined;
    const fuera = (e) => caja.current && !caja.current.contains(e.target) && setAbierto(false);
    document.addEventListener("mousedown", fuera);
    return () => document.removeEventListener("mousedown", fuera);
  }, [abierto]);
  if (!estado) return null;

  const marcar = async (tipo, motivo = "") => {
    setEnviando(true);
    try {
      const lugar = await datosDeLugar(estado.donde_marca);
      const r = await marcarJornada(tipo, { motivo, movil: window.matchMedia("(max-width: 767px)").matches, ...lugar });
      // La hora que se muestra es la que quedó guardada en el servidor, al segundo
      avisar(`${{ ENTRADA: "Entrada marcada", PAUSA: "Pausa marcada", REGRESO: "Regreso marcado", SALIDA: "Salida marcada" }[tipo]} a las ${horaExacta(r?.momento)}`);
      setAbierto(false);
      setPidiendoMotivo(false);
      await cargar();
      window.dispatchEvent(new Event("adzone:jornada"));
    } catch (e) { avisar(e.message, "rojo"); }
    setEnviando(false);
  };

  const { estado: e, hoy } = estado;
  const color = e === "TRABAJANDO" ? "border-verde/40 bg-verde/10 text-verde" : e === "EN_PAUSA" ? "border-amarillo bg-amarillo-50 text-[#8a5a00]" : "border-linea bg-white text-tinta";
  const punto = e === "TRABAJANDO" ? "bg-verde" : e === "EN_PAUSA" ? "bg-amarillo-600" : "bg-gris";
  // Segundos exactos del servidor + lo transcurrido desde que respondió (así sube de a segundo sin depender del reloj de la PC)
  const transcurrido = (performance.now() - estado.medio) / 1000;
  const segundosHoy = (hoy.trabajados_seg ?? hoy.trabajados * 60) + (e === "TRABAJANDO" ? transcurrido : 0);
  const horaOficial = estado.servidorMs + transcurrido * 1000;
  const etiqueta = e === "TRABAJANDO" ? relojSeg(segundosHoy) : e === "EN_PAUSA" ? "En pausa" : hoy.salida ? "Salida marcada" : "Marcar entrada";

  if (e === "FUERA") {
    return (
      <Boton tam="sm" variante={hoy.salida ? "secundario" : "primario"} icono={LogIn} cargando={enviando} onClick={() => marcar("ENTRADA")}
        className="whitespace-nowrap" aria-label={hoy.salida ? "Volver a marcar entrada" : "Marcar entrada"}>
        <span className="hidden sm:inline">{hoy.salida ? "Entrada" : "Marcar entrada"}</span>
      </Boton>
    );
  }
  return (
    <div className="relative" ref={caja}>
      <button type="button" onClick={() => setAbierto((a) => !a)} aria-expanded={abierto} aria-label={`Jornada: ${etiqueta}`}
        className={cx("flex h-10 items-center gap-2 rounded-lg border px-3 text-sm font-semibold", color)}>
        <span className={cx("size-2 rounded-full", punto)} />
        <span className="num">{etiqueta}</span>
      </button>
      {abierto && (
        <div className="fixed inset-x-4 top-16 z-40 rounded-xl border border-linea bg-white p-3 shadow-xl sm:absolute sm:inset-x-auto sm:right-0 sm:top-12 sm:w-64">
          <p className="text-sm text-gris">Hoy {hoy.entrada ? `entraste a las ${horaExacta(hoy.entrada)}` : ""}
            {hoy.llegada === "TARDE" && <span className="text-rojo"> ({relojSeg(hoy.tardanza_seg)} tarde)</span>}</p>
          <p className="mt-1 text-sm">Trabajado: <strong className="num">{relojSeg(segundosHoy)}</strong>{hoy.pausa_seg ? <> · pausa {relojSeg(hoy.pausa_seg)}</> : null}</p>
          <p className="mt-1 text-xs text-gris">Hora oficial: <span className="num font-medium text-tinta">{horaExacta(horaOficial)}</span></p>
          <div className="mt-3 grid gap-2">
            {estado.siguientes.map((t) => {
              const Icono = ICONO[t];
              return <Boton key={t} variante={t === "SALIDA" ? "secundario" : "primario"} icono={Icono} cargando={enviando}
                onClick={() => (t === "PAUSA" ? setPidiendoMotivo(true) : marcar(t))}>{TEXTO[t]}</Boton>;
            })}
          </div>
          <p className="mt-3 text-xs text-gris">En pausa o fuera de jornada el agente de la computadora no registra nada.</p>
        </div>
      )}
      <Modal abierto={pidiendoMotivo} onCerrar={() => setPidiendoMotivo(false)} titulo="¿Por qué la pausa?" ancho="max-w-sm">
        <div className="grid gap-2">
          {MOTIVOS.map((m) => <Boton key={m} variante="secundario" cargando={enviando} onClick={() => marcar("PAUSA", m)}>{m}</Boton>)}
        </div>
      </Modal>
    </div>
  );
}
