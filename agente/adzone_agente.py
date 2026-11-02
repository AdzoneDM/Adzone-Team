"""
Agente de escritorio de Adzone Team (Windows y macOS).

Qué hace, solo mientras la persona está en jornada (marcó entrada y no está en pausa) y aceptó la política:
- Cada 5 segundos mira la ventana activa (aplicación y título) y si hubo teclado o ratón recientemente
  (solo el tiempo desde la última entrada: no lee ni guarda teclas).
- Cada minuto arma un resumen (aplicación más usada, segundos activos e inactivos, nivel de actividad, cambios de
  ventana) y lo envía a Adzone Team. Si no hay internet, lo guarda y lo reenvía después.
- Si la administración activó las capturas, toma una cada cierto tiempo (se desenfoca en el servidor).
- Siempre visible: ícono en la barra de tareas con el estado y botones para marcar entrada, pausa, regreso y salida.

Configuración: la primera vez pide la dirección de Adzone Team y el código del equipo (Monitoreo → Mis equipos →
Vincular esta computadora). Se guarda en ~/.adzone_agente.json.

Uso:  python adzone_agente.py            (con ícono, si están instalados pystray y Pillow)
      python adzone_agente.py --consola  (sin ícono, muestra el estado en la terminal)
"""
import json
import os
import platform
import queue
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import webbrowser
from collections import Counter
from datetime import datetime, timezone

VERSION = '1.0.0'
CONFIG = os.path.join(os.path.expanduser('~'), '.adzone_agente.json')
PENDIENTES = os.path.join(os.path.expanduser('~'), '.adzone_agente_pendientes.json')
MUESTRA_SEG = 5
SISTEMA = platform.system()
DOMINIO = re.compile(r'\b((?:[a-z0-9-]+\.)+(?:com|net|org|do|io|ai|tv|marketing|app|dev|co|es|us|gob\.do|edu\.do))\b', re.I)


# ------------------------------------------------------------------ Sistema operativo
def _ventana_windows():
    import ctypes
    from ctypes import wintypes
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    hwnd = user32.GetForegroundWindow()
    largo = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(largo + 1)
    user32.GetWindowTextW(hwnd, buf, largo + 1)
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    app = ''
    h = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if h:
        ruta = ctypes.create_unicode_buffer(512)
        tam = wintypes.DWORD(512)
        if kernel32.QueryFullProcessImageNameW(h, 0, ruta, ctypes.byref(tam)):
            app = os.path.basename(ruta.value)
        kernel32.CloseHandle(h)
    return app, buf.value


def _inactivo_windows():
    import ctypes

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [('cbSize', ctypes.c_uint), ('dwTime', ctypes.c_uint)]
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info))
    return (ctypes.windll.kernel32.GetTickCount() - info.dwTime) / 1000.0


def _ventana_mac():
    guion = ('tell application "System Events" to set p to first application process whose frontmost is true\n'
             'set n to name of p\nset t to ""\ntry\nset t to name of front window of p\nend try\nreturn n & "\\n" & t')
    salida = subprocess.run(['osascript', '-e', guion], capture_output=True, text=True, timeout=3).stdout.strip().split('\n', 1)
    return salida[0], salida[1] if len(salida) > 1 else ''


def _inactivo_mac():
    salida = subprocess.run(['ioreg', '-c', 'IOHIDSystem'], capture_output=True, text=True, timeout=3).stdout
    m = re.search(r'"HIDIdleTime" = (\d+)', salida)
    return int(m.group(1)) / 1e9 if m else 0.0


def ventana_activa():
    try:
        return _ventana_windows() if SISTEMA == 'Windows' else _ventana_mac() if SISTEMA == 'Darwin' else ('', '')
    except Exception:
        return '', ''


def segundos_inactivo():
    try:
        return _inactivo_windows() if SISTEMA == 'Windows' else _inactivo_mac() if SISTEMA == 'Darwin' else 0.0
    except Exception:
        return 0.0


def captura_jpeg():
    try:
        from PIL import ImageGrab
        import io
        img = ImageGrab.grab(all_screens=True)
        img.thumbnail((1600, 1600))
        buf = io.BytesIO()
        img.convert('RGB').save(buf, 'JPEG', quality=55)
        return buf.getvalue()
    except Exception:
        return None


# ------------------------------------------------------------------ Conexión con Adzone Team
class Cliente:
    def __init__(self, servidor, token):
        self.servidor, self.token = servidor.rstrip('/'), token

    def _pedir(self, metodo, ruta, datos=None, cuerpo=None, tipo='application/json'):
        url = f'{self.servidor}/api/monitoreo/{ruta}'
        if metodo == 'GET':
            url += f'?version={VERSION}&sistema={platform.system()}+{platform.release()}'
        req = urllib.request.Request(url, method=metodo, data=cuerpo if cuerpo is not None else (json.dumps(datos).encode() if datos is not None else None))
        req.add_header('Authorization', f'Dispositivo {self.token}')
        req.add_header('Content-Type', tipo)
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode() or '{}')

    def estado(self):
        return self._pedir('GET', 'agente/estado/')

    def enviar(self, minutos):
        return self._pedir('POST', 'agente/actividad/', {'minutos': minutos, 'version': VERSION})

    def marcar(self, tipo):
        return self._pedir('POST', 'agente/marcar/', {'tipo': tipo})

    def captura(self, jpeg, app):
        limite = uuid.uuid4().hex
        partes = [f'--{limite}\r\nContent-Disposition: form-data; name="app"\r\n\r\n{app}\r\n'.encode(),
                  f'--{limite}\r\nContent-Disposition: form-data; name="archivo"; filename="c.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'.encode(),
                  jpeg, f'\r\n--{limite}--\r\n'.encode()]
        return self._pedir('POST', 'agente/captura/', cuerpo=b''.join(partes), tipo=f'multipart/form-data; boundary={limite}')


# ------------------------------------------------------------------ Agente
class Agente:
    def __init__(self, cliente):
        self.cliente = cliente
        self.estado = {'registrar': False, 'motivo': 'Conectando…', 'jornada': 'FUERA', 'umbral_inactivo_seg': 180}
        self.muestras = []
        self.minuto_actual = None
        self.cola = self._leer_pendientes()
        self.ultima_captura = 0
        self.app_anterior = None
        self.cambios = 0
        self.alto = threading.Event()
        self.fallos = 0
        self.avisos = queue.Queue()

    def _leer_pendientes(self):
        try:
            with open(PENDIENTES, encoding='utf-8') as f:
                return json.load(f)[-720:]
        except (OSError, ValueError):
            return []

    def _guardar_pendientes(self):
        try:
            with open(PENDIENTES, 'w', encoding='utf-8') as f:
                json.dump(self.cola[-720:], f)
        except OSError:
            pass

    def refrescar(self):
        try:
            self.estado = self.cliente.estado()
            self.fallos = 0
        except urllib.error.HTTPError as e:
            self.estado = {**self.estado, 'registrar': False, 'motivo': 'Equipo no vinculado: revisa el código.' if e.code == 401 else f'Error {e.code}'}
        except Exception:
            # Sin conexión: se sigue un par de minutos con lo último que dijo la plataforma (lo medido se guarda y
            # se envía al volver). Si no se puede confirmar que la persona sigue en jornada, se deja de registrar.
            self.fallos += 1
            seguir = self.estado.get('registrar') and self.fallos <= 2
            self.estado = {**self.estado, 'registrar': seguir,
                           'motivo': 'Sin conexión: se guarda y se envía al volver.' if seguir else 'Sin conexión: no se registra hasta confirmar la jornada.'}
        return self.estado

    def _cerrar_minuto(self):
        if not self.muestras or self.minuto_actual is None:
            return
        umbral = self.estado.get('umbral_inactivo_seg', 180)
        activos = sum(MUESTRA_SEG for m in self.muestras if m['inactivo'] < umbral)
        total = len(self.muestras) * MUESTRA_SEG
        con_entrada = sum(1 for m in self.muestras if m['inactivo'] < MUESTRA_SEG + 1)
        app, titulo = Counter((m['app'], m['titulo']) for m in self.muestras).most_common(1)[0][0]
        dominio = DOMINIO.search(titulo or '')
        self.cola.append({'minuto': self.minuto_actual.isoformat(), 'activos': min(activos, 60), 'inactivos': max(0, min(total, 60) - min(activos, 60)),
                          'intensidad': round(con_entrada / len(self.muestras) * 100), 'cambios': self.cambios,
                          'app': app[:100], 'titulo': titulo[:255], 'dominio': dominio.group(1).lower() if dominio else ''})
        self.muestras, self.cambios = [], 0

    def enviar_cola(self):
        if not self.cola:
            return
        lote = self.cola[:120]
        try:
            r = self.cliente.enviar(lote)
            self.cola = self.cola[len(lote):]
            if r.get('estado'):
                self.estado = r['estado']
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500:
                self.cola = self.cola[len(lote):]  # la plataforma no lo acepta: no se reintenta para siempre
        except Exception:
            pass
        self._guardar_pendientes()

    def bucle(self):
        self.refrescar()
        ultimo_estado = time.time()
        while not self.alto.is_set():
            ahora = datetime.now(timezone.utc).replace(second=0, microsecond=0)
            if self.minuto_actual and ahora != self.minuto_actual:
                if self.estado.get('registrar'):
                    self._cerrar_minuto()
                self.muestras, self.cambios = [], 0
                self.enviar_cola()
            self.minuto_actual = ahora
            if time.time() - ultimo_estado >= 60:
                self.refrescar()
                ultimo_estado = time.time()
            if self.estado.get('registrar'):
                app, titulo = ventana_activa()
                if (app, titulo) != self.app_anterior and self.app_anterior is not None:
                    self.cambios += 1
                self.app_anterior = (app, titulo)
                self.muestras.append({'app': app, 'titulo': titulo, 'inactivo': segundos_inactivo()})
                cada = self.estado.get('capturas_cada_min', 10) * 60
                if self.estado.get('capturas') and time.time() - self.ultima_captura >= cada:
                    jpeg = captura_jpeg()
                    if jpeg:
                        try:
                            self.cliente.captura(jpeg, app)
                        except Exception:
                            pass
                    self.ultima_captura = time.time()
            self.alto.wait(MUESTRA_SEG)

    def marcar(self, tipo):
        try:
            self.estado = self.cliente.marcar(tipo)
            return None
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read().decode()).get('detail', 'No se pudo marcar.')
            except Exception:
                return 'No se pudo marcar.'
        except Exception:
            return 'Sin conexión.'

    def texto_estado(self):
        e = self.estado
        quien = e.get('usuario', '')
        return f"{quien} · {'Midiendo' if e.get('registrar') else 'En pausa / fuera de jornada'} — {e.get('motivo', '')}"


# ------------------------------------------------------------------ Configuración y ventana
def cargar_config():
    try:
        with open(CONFIG, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def pedir_config():
    datos = cargar_config()
    try:
        import tkinter as tk
        from tkinter import simpledialog
        raiz = tk.Tk()
        raiz.withdraw()
        servidor = simpledialog.askstring('Adzone Team', 'Dirección de Adzone Team (ej. https://team.adzone.marketing):',
                                          initialvalue=datos.get('servidor', 'https://'))
        token = simpledialog.askstring('Adzone Team', 'Código del equipo (Monitoreo → Mis equipos → Vincular):', initialvalue='')
        raiz.destroy()
    except Exception:
        servidor = input('Dirección de Adzone Team: ').strip()
        token = input('Código del equipo: ').strip()
    if not servidor or not token:
        sys.exit('Falta la dirección o el código del equipo.')
    datos = {'servidor': servidor.strip(), 'token': token.strip()}
    with open(CONFIG, 'w', encoding='utf-8') as f:
        json.dump(datos, f)
    return datos


def con_icono(agente, servidor):
    import pystray
    from PIL import Image, ImageDraw

    def icono(color):
        img = Image.new('RGB', (64, 64), (31, 58, 95))
        ImageDraw.Draw(img).ellipse((16, 16, 48, 48), fill=color)
        return img

    def accion(tipo):
        def hacer(icon, item):
            error = agente.marcar(tipo)
            if error:
                icon.notify(error, 'Adzone Team')
            actualizar(icon)
        return hacer

    def actualizar(icon):
        icon.icon = icono((46, 160, 67) if agente.estado.get('registrar') else (200, 160, 40))
        icon.title = agente.texto_estado()[:120]

    menu = pystray.Menu(
        pystray.MenuItem(lambda item: agente.texto_estado()[:90], None, enabled=False),
        pystray.MenuItem('Marcar entrada', accion('ENTRADA')),
        pystray.MenuItem('Iniciar pausa', accion('PAUSA')),
        pystray.MenuItem('Volver de la pausa', accion('REGRESO')),
        pystray.MenuItem('Marcar salida', accion('SALIDA')),
        pystray.MenuItem('Ver mi actividad', lambda *_: webbrowser.open(f'{servidor}/monitoreo')),
        pystray.MenuItem('Salir del agente', lambda icon, item: (agente.alto.set(), icon.stop())),
    )
    icon = pystray.Icon('adzone', icono((200, 160, 40)), 'Adzone Team', menu)

    def refrescar_icono():
        while not agente.alto.is_set():
            actualizar(icon)
            agente.alto.wait(15)
    threading.Thread(target=refrescar_icono, daemon=True).start()
    icon.run()


def main():
    datos = cargar_config()
    if '--configurar' in sys.argv or not datos.get('token'):
        datos = pedir_config()
    agente = Agente(Cliente(datos['servidor'], datos['token']))
    hilo = threading.Thread(target=agente.bucle, daemon=True)
    hilo.start()
    if '--consola' not in sys.argv:
        try:
            con_icono(agente, datos['servidor'])
            return
        except ImportError:
            print('Sin pystray/Pillow: modo consola.')
    try:
        while True:
            print(time.strftime('%H:%M'), agente.texto_estado(), f'· pendientes: {len(agente.cola)}', flush=True)
            time.sleep(60)
    except KeyboardInterrupt:
        agente.alto.set()


if __name__ == '__main__':
    main()
