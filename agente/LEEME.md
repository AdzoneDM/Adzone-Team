# Agente de escritorio de Adzone Team

Mide la actividad de la computadora **solo en jornada** (desde que la persona marca entrada hasta que marca pausa o
salida) y la envía a Adzone Team cada minuto. Siempre está visible en la barra de tareas.

## Qué registra y qué no

| Registra (por minuto) | Nunca registra |
|---|---|
| Aplicación y título de la ventana en uso | Teclas o lo que se escribe |
| Sitio web cuando aparece en el título | Contraseñas |
| Segundos con actividad (teclado/ratón) e inactivos | Contenido de mensajes o correos |
| Nivel de actividad y cambios de ventana | Audio, cámara |
| Capturas de pantalla, **solo si la administración las activa** (se desenfocan) | Nada fuera de la jornada |

## Instalar en una computadora (Windows)

1. En Adzone Team, la persona entra a **Monitoreo → Mi actividad**, acepta la política y pulsa **Vincular esta computadora**.
   Copia el **código del equipo** (sale una sola vez).
2. Copia `AdzoneAgente.exe` a la PC y ábrelo. La primera vez pide la dirección de Adzone Team y el código.
3. Para que arranque con Windows: `Win + R` → `shell:startup` → pega ahí un acceso directo a `AdzoneAgente.exe`.

El ícono es **verde** cuando está midiendo y **amarillo** cuando la persona está fuera de jornada o en pausa. Desde el
ícono se marca entrada, pausa, regreso y salida.

## Construir el .exe

En una PC con Windows y Python 3.10+: doble clic en `construir_windows.bat`. Sale `dist\AdzoneAgente.exe`.

## macOS

`pip3 install pystray pillow` y `python3 adzone_agente.py`. macOS pide permiso de **Accesibilidad** (para leer la
ventana activa) y de **Grabación de pantalla** solo si se usan capturas.

## Sin ícono (pruebas)

`python adzone_agente.py --consola` · Cambiar dirección o código: `python adzone_agente.py --configurar`.
