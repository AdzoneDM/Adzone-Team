// Avisos de tareas que se muestran como alerta emergente en toda la pantalla (los demás quedan en la campanita).
import { AlarmClock, BellRing, ClipboardPlus, Lock, PencilLine, RotateCcw, Undo2 } from "lucide-react";

// tipo → cómo se presenta. «tono» elige los colores; «insiste» repite el sonido hasta que se atiende.
export const ALERTAS_TAREA = {
  RECORDATORIO: { etiqueta: "Recordatorio de tu supervisor", icono: BellRing, tono: "rojo", insiste: true, boton: "Ver tarea" },
  ASIGNADA: { etiqueta: "Nueva tarea para ti", icono: ClipboardPlus, tono: "azul", boton: "Ver tarea" },
  DEVUELTA: { etiqueta: "Tu entrega fue devuelta", icono: Undo2, tono: "rojo", insiste: true, boton: "Corregir ahora" },
  REABIERTA: { etiqueta: "Tarea reabierta", icono: RotateCcw, tono: "rojo", boton: "Ver tarea" },
  MODIFICADA: { etiqueta: "Tu tarea cambió", icono: PencilLine, tono: "azul", boton: "Ver cambios" },
  BLOQUEADA: { etiqueta: "Tarea bloqueada", icono: Lock, tono: "amarillo", boton: "Ver tarea" },
  VENCE: { etiqueta: "Tarea por vencer", icono: AlarmClock, tono: "rojo", insiste: true, boton: "Ir a la tarea" },
};

export const esAlertaTarea = (aviso) => !aviso.leida && aviso.tipo in ALERTAS_TAREA;
