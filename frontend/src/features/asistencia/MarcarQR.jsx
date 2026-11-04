// /marcar?s=…&t=… : lo que abre la cámara del celular al escanear el QR de la pantalla de la oficina.
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, QrCode } from "lucide-react";
import { estadoJornada, marcarJornada } from "@/lib/api";
import { Alerta, Boton, Cargando } from "@/components/ui";

const TEXTO = { ENTRADA: "Marcar entrada", PAUSA: "Iniciar pausa", REGRESO: "Volver de la pausa", SALIDA: "Marcar salida" };

export default function MarcarQR() {
  const [params] = useSearchParams();
  const qr = { sitio: params.get("s"), token: params.get("t") };
  const [estado, setEstado] = useState(null);
  const [hecho, setHecho] = useState(null);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState("");
  useEffect(() => { estadoJornada().then(setEstado).catch((e) => setError(e.message)); }, []);
  const marcar = async (tipo) => {
    setEnviando(tipo); setError("");
    try {
      const r = await marcarJornada(tipo, { qr, movil: true, motivo: tipo === "PAUSA" ? "Almuerzo" : "" });
      setHecho({ tipo, sitio: r.sitio });
      window.dispatchEvent(new Event("adzone:jornada"));
    } catch (e) { setError(e.message); }
    setEnviando("");
  };
  return (
    <div className="mx-auto max-w-sm space-y-5 py-6 text-center">
      {hecho ? (
        <>
          <CheckCircle2 className="mx-auto size-16 text-verde" />
          <h1 className="text-2xl font-semibold">{{ ENTRADA: "¡Entrada marcada!", PAUSA: "Pausa marcada", REGRESO: "De vuelta", SALIDA: "¡Salida marcada!" }[hecho.tipo]}</h1>
          <p className="text-gris">{hecho.sitio ? `En ${hecho.sitio}, ` : ""}{new Date().toLocaleTimeString("es-DO", { hour: "numeric", minute: "2-digit" })}</p>
          <Link to="/" className="inline-block text-azul hover:underline">Ir al inicio</Link>
        </>
      ) : (
        <>
          <QrCode className="mx-auto size-12 text-azul" />
          <h1 className="text-2xl font-semibold">Marcar con el QR de la oficina</h1>
          {error && <Alerta>{error}</Alerta>}
          {!qr.sitio || !qr.token ? <Alerta>Este enlace no trae el código. Escanea el QR de la pantalla otra vez.</Alerta>
            : !estado ? !error && <Cargando />
              : <div className="space-y-3">{estado.siguientes.map((t) => (
                  <Boton key={t} tam="lg" className="w-full" variante={t === "ENTRADA" || t === "REGRESO" ? "primario" : "secundario"} cargando={enviando === t}
                    disabled={!!enviando} onClick={() => marcar(t)}>{TEXTO[t]}</Boton>
                ))}</div>}
          <p className="text-sm text-gris">El código cambia cada 30 segundos: si tardas, vuelve a escanearlo.</p>
        </>
      )}
    </div>
  );
}
