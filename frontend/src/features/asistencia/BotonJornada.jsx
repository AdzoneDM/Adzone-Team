// Marcar entrada, pausa, regreso y salida desde cualquier pantalla (arriba, junto al buscador).
import { useCallback, useEffect, useRef, useState } from "react";
import { Coffee, LogIn, LogOut, Play } from "lucide-react";
import { estadoJornada, marcarJornada } from "@/lib/api";
import { reloj } from "@/lib/formato";
import { Boton, Modal, cx, useAviso } from "@/components/ui";

const TEXTO = { ENTRADA: "Marcar entrada", PAUSA: "Pausa", REGRESO: "Volver", SALIDA: "Salida" };
const ICONO = { ENTRADA: LogIn, PAUSA: Coffee, REGRESO: Play, SALIDA: LogOut };
const MOTIVOS = ["Almuerzo", "Diligencia personal", "Reunión fuera", "Otro"];

export function useJornada() {
  const [estado, setEstado] = useState(null);
  const cargar = useCallback(() => estadoJornada().then(setEstado).catch(() => {}), []);
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
      await marcarJornada(tipo, { motivo, movil: window.matchMedia("(max-width: 767px)").matches });
      avisar({ ENTRADA: "Entrada marcada. ¡Buen día!", PAUSA: "Pausa marcada.", REGRESO: "De vuelta.", SALIDA: "Salida marcada. ¡Hasta mañana!" }[tipo]);
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
  const etiqueta = e === "TRABAJANDO" ? reloj(hoy.trabajados) : e === "EN_PAUSA" ? "En pausa" : hoy.salida ? "Salida marcada" : "Marcar entrada";

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
          <p className="text-sm text-gris">Hoy {hoy.entrada ? `entraste a las ${new Date(hoy.entrada).toLocaleTimeString("es-DO", { hour: "numeric", minute: "2-digit" })}` : ""}
            {hoy.llegada === "TARDE" && <span className="text-rojo"> ({hoy.tardanza} min tarde)</span>}</p>
          <p className="mt-1 text-sm">Trabajado: <strong className="num">{reloj(hoy.trabajados)}</strong>{hoy.pausa ? <> · pausa {reloj(hoy.pausa)}</> : null}</p>
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
