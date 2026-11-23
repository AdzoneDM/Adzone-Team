# Adzone Team como aplicación instalable (evaluación)

**Conclusión: ya es una PWA instalable y la recomendación es seguir con la PWA** (no hacer una app nativa aparte).
Una sola base de código, se actualiza sola al desplegar, sin tiendas de apps, y cubre Windows, Mac, Linux, Android y iPhone.

## Qué tiene hoy
- `manifest.webmanifest`: nombre, íconos (192, 512 y «maskable»), pantalla completa (`standalone`), color de marca, accesos directos («Mis tareas», «Por validar»).
- `sw.js` (service worker): permite instalar y abrir la app con mala señal (red primero; nunca guarda `/api` ni `/media`, así los datos siempre son los actuales) y recibe los **avisos push** con la app cerrada.
- Avisos push (Web Push, claves VAPID en el servidor): campanita + notificación del sistema; las importantes (tareas devueltas, vencimientos, **alertas de almuerzo**…) se quedan en pantalla hasta atenderlas.
- Invitación a instalar en la propia app (`beforeinstallprompt`) y guía paso a paso en «Mi cuenta → Avisos en el celular».

## Compatibilidad
| Sistema | Instalar | Avisos con la app cerrada | Notas |
|---|---|---|---|
| Windows / Mac / Linux (Chrome o Edge) | Sí: ícono «Instalar» en la barra de direcciones | Sí | Se abre en su propia ventana, con ícono en la barra de tareas |
| Android (Chrome) | Sí: ⋮ → «Instalar app» | Sí | Funciona como una app más |
| iPhone / iPad (Safari) | Sí, manual: Compartir → «Agregar a inicio» | Sí, **solo con la app instalada** (iOS 16.4 o más) | Apple no deja instalar con un botón; la app explica los pasos |

## Sincronización y funciones
Es la misma web: tareas, validación, chat, asistencia, videos, etc. funcionan igual y siempre muestran los datos del servidor.
Sin internet abre la pantalla de inicio guardada, pero **no** permite trabajar sin conexión (a propósito: evita datos viejos o marcajes falsos).

## Límites y qué sigue
- iPhone no muestra el globo de notificaciones si la persona no instaló la app: hay que pedírselo al equipo.
- Cámara y grabación de video usan el selector del teléfono (funcionan instalada o no).
- Posibles mejoras (no urgentes): contador en el ícono (badge) con las tareas por validar; compartir una foto o video desde la galería del celular directo a Adzone Team («compartir con…»).
- Una app nativa (tiendas) solo valdría la pena si se necesitara algo que la web no da (por ejemplo, rastreo en segundo plano); hoy no hace falta.
