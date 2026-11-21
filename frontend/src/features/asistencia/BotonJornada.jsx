// Marcar entrada, pausa, regreso y salida desde cualquier pantalla (arriba, junto al buscador).
import { useCallback, useEffect, useRef, useState } from "react";
import { Coffee, LogIn, LogOut, Play, Utensils } from "lucide-react";
import { estadoJornada, marcarJornada } from "@/lib/api";
import { horaExacta, relojSeg } from "@/lib/formato";
import { datosDeLugar } from "@/lib/ubicacion";
import { Boton, Modal, cx, useAviso } from "@/components/ui";

const TEXTO = { ENTRADA: "Marcar entrada", PAUSA: "Iniciar pausa", REGRESO: "Terminar pausa", SALIDA: "Salida" };
const ICONO = { ENTRADA: LogIn, PAUSA: Coffee, REGRESO: Play, SALIDA: LogOut };
const MOTIVOS = ["Diligencia personal", "Reunión fuera", "Descanso", "Otro"]; // el almuerzo tiene su propio botón

/** «17:00» → «5:00 p. m.» */
const hhmm = (t) => { const [h, m] = String(t).split(":").map(Number); return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${h < 12 ? "a. m." : "p. m."}`; };

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
  const corriendo = estado?.estado === "TRABAJANDO" || estado?.estado === "EN_PAUSA"; // el contador de la pausa también corre
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
      const dicho = { ENTRADA: "Entrada marcada", PAUSA: "Pausa iniciada", ALMUERZO: "Almuerzo iniciado", REGRESO: estado.en_almuerzo ? "Almuerzo terminado" : "Pausa terminada", FIN_ALMUERZO: "Almuerzo terminado", SALIDA: "Salida marcada" }[tipo];
      avisar(`${dicho} a las ${horaExacta(r?.momento)}`);
      setAbierto(false);
      setPidiendoMotivo(false);
      await cargar();
      window.dispatchEvent(new Event("adzone:jornada"));
    } catch (e) { avisar(e.message, "rojo"); }
    setEnviando(false);
  };

  const { estado: e, hoy } = estado;
  // Segundos exactos del servidor + lo transcurrido desde que respondió (así sube de a segundo sin depender del reloj de la PC)
  const transcurrido = (performance.now() - estado.medio) / 1000;
  const segundosHoy = (hoy.trabajados_seg ?? hoy.trabajados * 60) + (e === "TRABAJANDO" ? transcurrido : 0);
  const horaOficial = estado.servidorMs + transcurrido * 1000;
  // Contador de la pausa: desde que la inició (hora del servidor) y contra su límite (60 min por defecto; el almuerzo, el suyo)
  const enAlmuerzo = !!estado.en_almuerzo;
  const segundosPausa = e === "EN_PAUSA" && estado.ultimo ? Math.max(0, (horaOficial - Date.parse(estado.ultimo.momento)) / 1000) : 0;
  const limitePausa = (enAlmuerzo ? estado.limites?.almuerzo_min : estado.limites?.pausa_min) * 60 || 0;
  const pasada = e === "EN_PAUSA" && limitePausa > 0 && segundosPausa >= limitePausa;
  const color = e === "TRABAJANDO" ? "border-verde/40 bg-verde/10 text-verde" : e === "EN_PAUSA" ? (pasada ? "border-rojo/50 bg-rojo/10 text-rojo" : "border-amarillo bg-amarillo-50 text-[#8a5a00]") : "border-linea bg-white text-tinta";
  const punto = e === "TRABAJANDO" ? "bg-verde" : e === "EN_PAUSA" ? (pasada ? "bg-rojo animate-pulse" : "bg-amarillo-600") : "bg-gris";
  const etiqueta = e === "TRABAJANDO" ? relojSeg(segundosHoy) : e === "EN_PAUSA" ? `${enAlmuerzo ? "Almuerzo" : "Pausa"} ${relojSeg(segundosPausa)}` : hoy.salida ? "Salida marcada" : "Marcar entrada";

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
          <p className="mt-1 text-sm">Trabajado: <strong className="num">{relojSeg(segundosHoy)}</strong>{hoy.almuerzo_seg ? <> · almuerzo {relojSeg(hoy.almuerzo_seg)}</> : null}{hoy.pausas_seg ? <> · pausas {relojSeg(hoy.pausas_seg)}</> : null}</p>
          {hoy.turno && <p className="mt-1 text-sm">Salida programada: <strong className="num">{hhmm(hoy.turno[1])}</strong>{hoy.salida ? <span className="text-gris"> · ya marcaste a las {horaExacta(hoy.salida)}</span> : null}</p>}
          <p className="mt-1 text-xs text-gris">Hora oficial: <span className="num font-medium text-tinta">{horaExacta(horaOficial)}</span></p>
          {e === "EN_PAUSA" && limitePausa > 0 && (
            <p className={cx("mt-2 rounded-md px-2 py-1 text-sm", pasada ? "bg-rojo/10 font-semibold text-rojo" : "bg-amarillo-50 text-[#8a5a00]")}>
              {pasada ? `Pasaste el límite de ${Math.round(limitePausa / 60)} min: marca tu regreso.` : `${enAlmuerzo ? "Almuerzo" : "Pausa"}: límite ${Math.round(limitePausa / 60)} min.`}
            </p>
          )}
          <div className="mt-3 grid gap-2">
            {estado.siguientes.map((t) => {
              if (t === "PAUSA") {
                return (
                  <div key={t} className="grid gap-2">
                    <Boton variante="primario" icono={Utensils} cargando={enviando} onClick={() => marcar("ALMUERZO", "Almuerzo")}>Iniciar almuerzo</Boton>
                    <Boton variante="secundario" icono={Coffee} cargando={enviando} onClick={() => setPidiendoMotivo(true)}>Iniciar pausa</Boton>
                  </div>
                );
              }
              const Icono = ICONO[t];
              const texto = t === "REGRESO" && enAlmuerzo ? "Terminar almuerzo" : TEXTO[t];
              return <Boton key={t} variante={t === "SALIDA" ? "secundario" : "primario"} icono={Icono} cargando={enviando}
                onClick={() => marcar(t === "REGRESO" && enAlmuerzo ? "FIN_ALMUERZO" : t)}>{texto}</Boton>;
            })}
          </div>
        </div>
      )}
      <Modal abierto={pidiendoMotivo} onCerrar={() => setPidiendoMotivo(false)} titulo="¿Por qué la pausa?" descripcion={`Si pasa de ${estado.limites?.pausa_min ?? 60} minutos sin que marques el regreso, se avisa a tu supervisor.`} ancho="max-w-sm">
        <div className="grid gap-2">
          {MOTIVOS.map((m) => <Boton key={m} variante="secundario" cargando={enviando} onClick={() => marcar("PAUSA", m)}>{m}</Boton>)}
        </div>
      </Modal>
    </div>
  );
}
