// Sonidos de la plataforma. El navegador solo deja sonar después de que la persona toca la pantalla una vez,
// así que se desbloquea el audio con el primer toque o tecla.
let contexto = null;

function ctx() {
  if (contexto) return contexto;
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (!Ctx) return null;
  contexto = new Ctx();
  return contexto;
}

if (typeof window !== "undefined") {
  const desbloquear = () => { try { ctx()?.resume(); } catch { /* sin audio */ } };
  for (const ev of ["pointerdown", "keydown", "touchstart"]) window.addEventListener(ev, desbloquear, { once: true, passive: true, capture: true });
}

function tonos(lista, volumen) {
  try {
    const c = ctx();
    if (!c) return;
    if (c.state === "suspended") c.resume().catch(() => {});
    lista.forEach(([hz, t, dur = 0.16]) => {
      const o = c.createOscillator();
      const g = c.createGain();
      o.frequency.value = hz;
      o.type = "sine";
      g.gain.setValueAtTime(0.0001, c.currentTime + t);
      g.gain.exponentialRampToValueAtTime(volumen, c.currentTime + t + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, c.currentTime + t + dur);
      o.connect(g).connect(c.destination);
      o.start(c.currentTime + t);
      o.stop(c.currentTime + t + dur + 0.05);
    });
  } catch { /* el navegador no deja sonar sin tocar la pantalla primero */ }
}

/** Alerta de tarea (recordatorio, devolución…): tres tonos ascendentes y vibración, para que no pase desapercibida. */
export function sonarAlerta() {
  tonos([[880, 0], [1175, 0.18], [1480, 0.36]], 0.4);
  try { navigator.vibrate?.([200, 100, 200, 100, 200]); } catch { /* sin vibración */ }
}

/** Notificación normal (un aviso nuevo en la campanita): dos tonos suaves. */
export function sonarNotificacion() {
  tonos([[988, 0, 0.14], [1319, 0.13, 0.22]], 0.22);
  try { navigator.vibrate?.(80); } catch { /* sin vibración */ }
}

/** Mensaje nuevo del chat: un «pop» corto y suave, distinto del de las notificaciones. */
export function sonarMensaje() {
  tonos([[740, 0, 0.09], [988, 0.08, 0.15]], 0.18);
  try { navigator.vibrate?.(40); } catch { /* sin vibración */ }
}
