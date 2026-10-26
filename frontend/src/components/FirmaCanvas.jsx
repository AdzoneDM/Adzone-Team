// Firma en pantalla (dedo o mouse). Devuelve un PNG como data URL.
import { useEffect, useRef, useState } from "react";
import { Eraser } from "lucide-react";

export default function FirmaCanvas({ onCambio, etiqueta = "Firma del cliente" }) {
  const ref = useRef(null);
  const dibujando = useRef(false);
  const [vacia, setVacia] = useState(true);

  // El lienzo toma su tamaño real al primer trazo (dentro de una ventana que se anima, al montar mide cero).
  const preparar = () => {
    const c = ref.current;
    const escala = window.devicePixelRatio || 1;
    const { width, height } = c.getBoundingClientRect();
    if (c.width === Math.round(width * escala) && c.height === Math.round(height * escala)) return;
    c.width = Math.round(width * escala);
    c.height = Math.round(height * escala);
    const ctx = c.getContext("2d");
    ctx.scale(escala, escala);
    ctx.lineWidth = 2.2;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.strokeStyle = "#16336b";
  };
  useEffect(() => { preparar(); }, []);

  const punto = (e) => {
    const r = ref.current.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  };
  const empezar = (e) => {
    e.preventDefault();
    if (vacia) preparar();
    ref.current.setPointerCapture(e.pointerId);
    dibujando.current = true;
    const ctx = ref.current.getContext("2d");
    ctx.beginPath();
    ctx.moveTo(...punto(e));
  };
  const mover = (e) => {
    if (!dibujando.current) return;
    const ctx = ref.current.getContext("2d");
    ctx.lineTo(...punto(e));
    ctx.stroke();
  };
  const terminar = () => {
    if (!dibujando.current) return;
    dibujando.current = false;
    setVacia(false);
    onCambio(ref.current.toDataURL("image/png"));
  };
  const borrar = () => {
    const c = ref.current;
    c.getContext("2d").clearRect(0, 0, c.width, c.height);
    setVacia(true);
    onCambio("");
  };

  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <span className="etiqueta mb-0">{etiqueta}</span>
        <button type="button" onClick={borrar} className="inline-flex items-center gap-1 text-sm font-medium text-azul"><Eraser className="size-4" />Borrar</button>
      </div>
      <canvas ref={ref} aria-label={etiqueta} role="img" onPointerDown={empezar} onPointerMove={mover} onPointerUp={terminar} onPointerLeave={terminar}
        className="h-40 w-full touch-none rounded-lg border-2 border-dashed border-linea bg-white" />
      {vacia && <p className="mt-1 text-xs text-gris">Que el cliente firme con el dedo. Si no puede, sube fotos de la entrega y anota su nombre.</p>}
    </div>
  );
}
