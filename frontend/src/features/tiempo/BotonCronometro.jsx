import { Play, Square } from "lucide-react";
import { reloj } from "@/lib/formato";
import { Boton } from "@/components/ui";
import { useCronometro } from "./cronometro";

/** «Iniciar cronómetro» en una tarea u orden. Si ya corre en eso mismo, muestra el tiempo y permite detenerlo. */
export default function BotonCronometro({ tarea, orden, proyecto, tam = "md", className }) {
  const { activo, minutos, iniciar, detener } = useCronometro() || {};
  if (!iniciar) return null;
  const aqui = activo && ((tarea && activo.tarea === tarea) || (!tarea && orden && activo.orden === orden && !activo.tarea) || (!tarea && !orden && proyecto && activo.proyecto === proyecto));
  if (aqui) {
    return <Boton variante="secundario" tam={tam} icono={Square} onClick={detener} className={className}><span className="num">{reloj(minutos)}</span> Detener</Boton>;
  }
  return <Boton variante="secundario" tam={tam} icono={Play} onClick={() => iniciar({ tarea, orden, proyecto })} className={className}>Cronómetro</Boton>;
}
