// Avisos de tareas que se muestran como alerta emergente en toda la pantalla (los demás quedan en la campanita).
import { AlarmClock, BellRing, ClipboardPlus, Lock, PencilLine, RotateCcw, Timer, Trash2, Undo2, Utensils } from "lucide-react";

// tipo → cómo se presenta. «tono» elige los colores; «insiste» repite el sonido hasta que se atiende.
export const ALERTAS_TAREA = {
  // Recordatorio personal: suena a la hora que la persona eligió y insiste hasta que lo atiende
  MI_RECORDATORIO: { etiqueta: "Tu recordatorio", icono: AlarmClock, tono: "azul", insiste: true, boton: "Ver recordatorios" },
  RECORDATORIO: { etiqueta: "Recordatorio de tu supervisor", icono: BellRing, tono: "rojo", insiste: true, boton: "Ver tarea" },
  ASIGNADA: { etiqueta: "Nueva tarea para ti", icono: ClipboardPlus, tono: "azul", boton: "Ver tarea" },
  DEVUELTA: { etiqueta: "Tu entrega fue devuelta", icono: Undo2, tono: "rojo", insiste: true, boton: "Corregir ahora" },
  REABIERTA: { etiqueta: "Tarea reabierta", icono: RotateCcw, tono: "rojo", boton: "Ver tarea" },
  MODIFICADA: { etiqueta: "Tu tarea cambió", icono: PencilLine, tono: "azul", boton: "Ver cambios" },
  ELIMINADA: { etiqueta: "Se eliminó una de tus tareas", icono: Trash2, tono: "rojo", boton: "Ver mis tareas" },
  BLOQUEADA: { etiqueta: "Tarea bloqueada", icono: Lock, tono: "amarillo", boton: "Ver tarea" },
  VENCE: { etiqueta: "Tarea por vencer", icono: AlarmClock, tono: "rojo", insiste: true, boton: "Ir a la tarea" },
  // Almuerzo: salen igual que las alertas de tareas (con sonido); la de pasarse insiste hasta que marcas tu regreso
  ALMUERZO_HORA: { etiqueta: "Hora de almuerzo", icono: Utensils, tono: "azul" },
  ALMUERZO_FIN: { etiqueta: "Tu almuerzo está por terminar", icono: Timer, tono: "amarillo" },
  ALMUERZO_EXCESO: { etiqueta: "Te pasaste del almuerzo", icono: Utensils, tono: "rojo", insiste: true },
};

export const esAlertaTarea = (aviso) => !aviso.leida && aviso.tipo in ALERTAS_TAREA;
