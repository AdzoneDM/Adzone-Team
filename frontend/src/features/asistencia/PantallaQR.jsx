// Pantalla de la recepción (una tablet o un monitor): muestra el QR para marcar, que cambia cada 30 segundos.
// Se abre con su enlace secreto, sin entrar con usuario. Si el enlace se comparte por error, se genera otro en Asistencia → Horarios.
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import Marca from "@/components/Marca";
import { pantallaQR } from "@/lib/api";

export default function PantallaQR() {
  const { clave } = useParams();
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [hora, setHora] = useState(new Date());
  useEffect(() => {
    let t;
    const traer = () => pantallaQR(clave)
      .then((x) => { setD(x); setError(""); t = setTimeout(traer, (x.cambia_en + 1) * 1000); })
      .catch((e) => { setError(e.status === 404 ? "Este enlace ya no sirve. Pide el nuevo en Asistencia → Horarios." : "Sin conexión: reintentando…"); t = setTimeout(traer, 10000); });
    traer();
    const r = setInterval(() => setHora(new Date()), 1000);
    return () => { clearTimeout(t); clearInterval(r); };
  }, [clave]);
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-6 bg-noche p-6 text-center text-white">
      <Marca className="text-2xl" />
      <p className="font-display text-5xl font-semibold tabular-nums">{hora.toLocaleTimeString("es-DO", { hour: "numeric", minute: "2-digit", second: "2-digit" })}</p>
      {error ? <p className="text-xl text-amarillo">{error}</p> : d && (
        <>
          <div className="size-[min(70vw,60vh)] rounded-2xl bg-white p-4 [&_svg]:size-full" dangerouslySetInnerHTML={{ __html: d.qr }} />
          <p className="text-2xl">Escanea con la cámara de tu celular para marcar · <b>{d.sitio}</b></p>
        </>
      )}
    </div>
  );
}
