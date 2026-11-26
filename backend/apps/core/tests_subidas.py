"""Subida por partes de archivos grandes (ZIP y videos) y su uso en las tareas: referencias, entregas y devoluciones."""
import io
import os
import zipfile
from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from apps.desempeno.models import EvidenciaArchivo, ReferenciaArchivo
from apps.desempeno.tests_mejoras import MEDIA, Base
from .models import SubidaPorPartes
from .subidas import CARPETA, limpiar_vencidas

PARTE = 256 * 1024
S = '/api/subidas/'
T = '/api/desempeno/tareas/'


def zip_de(mb=3, adentro='fotos/plano.png'):
    """Un ZIP de varios MB (contenido aleatorio: no se comprime, así pesa lo que dice)."""
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w', zipfile.ZIP_STORED) as z:
        z.writestr(adentro, os.urandom(int(mb * 1024 * 1024)))
    return b.getvalue()


@override_settings(MEDIA_ROOT=MEDIA, SUBIDA_PARTE_BYTES=PARTE, CHAT_ANTIVIRUS='omitir')
class SubidaPorPartesTests(Base):
    def subir(self, quien, nombre, datos, completar=True):
        """Sube `datos` por partes como `quien` y devuelve (id, respuesta de completar)."""
        self.como(quien)
        r = self.c.post(S, {'nombre': nombre, 'tamano': len(datos)}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        inicio = r.json()
        self.assertEqual(inicio['tamano_parte'], PARTE)
        for i in range(inicio['partes']):
            r = self.c.put(f"{S}{inicio['id']}/partes/{i}/", data=datos[i * PARTE:(i + 1) * PARTE], content_type='application/octet-stream')
            self.assertEqual(r.status_code, 200, r.content)
        if not completar:
            return inicio['id'], None
        return inicio['id'], self.c.post(f"{S}{inicio['id']}/completar/")

    def test_zip_de_varios_mb_por_partes_queda_de_referencia_y_se_descarga(self):
        datos = zip_de(3)
        sid, r = self.subir(self.vladi, 'entregables.zip', datos)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['estado'], 'COMPLETA')
        self.assertGreater(r.json()['partes'], 10)
        t = self.tarea(self.erlin)
        with self.captureOnCommitCallbacks(execute=True):
            r = self.c.post(f'{T}{t.id}/referencias/', {'subidas': [sid], 'nota': 'Los archivos fuente'}, format='multipart')
        self.assertEqual(r.status_code, 200, r.content)
        ref = r.json()['referencias'][0]
        self.assertEqual((ref['nombre_original'], ref['tamano']), ('entregables.zip', len(datos)))
        # El archivo se movió a su lugar (la carpeta temporal ya no está) y la subida no se puede usar otra vez
        self.assertFalse(os.path.exists(os.path.join(MEDIA, CARPETA, sid)))
        self.assertEqual(SubidaPorPartes.objects.get(pk=sid).estado, 'USADA')
        self.assertEqual(self.c.post(f'{T}{t.id}/referencias/', {'subidas': [sid]}, format='multipart').status_code, 400)
        # Quien tiene la tarea la descarga entera
        self.como(self.erlin)
        descarga = self.c.get(ref['url'])
        self.assertEqual(descarga.status_code, 200)
        self.assertEqual(b''.join(descarga.streaming_content), datos)

    def test_entregar_con_un_video_grande_y_un_archivo_chico(self):
        video = b'\x00\x00\x00\x18ftypmp42' + os.urandom(PARTE * 2 + 1234)
        sid, r = self.subir(self.erlin, 'grabacion.mp4', video)
        self.assertEqual(r.status_code, 200, r.content)
        t = self.tarea(self.erlin)
        with self.captureOnCommitCallbacks(execute=True):
            r = self.c.post(f'{T}{t.id}/entregar/', {'evidencia_nota': 'Listo', 'subidas': [sid]}, format='multipart')
        self.assertEqual(r.status_code, 200, r.content)
        ev = EvidenciaArchivo.objects.get(tarea=t)
        self.assertEqual((ev.nombre_original, ev.tamano, ev.es_video), ('grabacion.mp4', len(video), True))
        self.assertEqual(self.c.get(f'/api/desempeno/evidencias/{ev.id}/archivo/?descargar=1').status_code, 200)

    def test_devolver_con_zip_grande(self):
        sid, _ = self.subir(self.vladi, 'correcciones.zip', zip_de(1))
        t = self.tarea(self.erlin, estado='EN_REVISION', evidencia_nota='listo')
        r = self.c.post(f'{T}{t.id}/rechazar/', {'comentario_revision': 'Usa estos archivos', 'subidas': [sid]}, format='multipart')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual([(x['nombre_original'], x['momento']) for x in r.json()['referencias']], [('correcciones.zip', 'CORRECCION')])

    @override_settings(ADJUNTO_GRANDE_MAX_MB=400)
    def test_rechaza_lo_que_pasa_del_limite(self):
        self.como(self.vladi)
        r = self.c.post(S, {'nombre': 'enorme.zip', 'tamano': 401 * 1024 * 1024}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('Máximo 400 MB', r.json()['detail'])
        self.assertEqual(self.c.post(S, {'nombre': 'justo.zip', 'tamano': 400 * 1024 * 1024}, format='json').status_code, 201)
        # Una foto sigue con su tope de siempre
        self.assertEqual(self.c.post(S, {'nombre': 'foto.jpg', 'tamano': 50 * 1024 * 1024}, format='json').status_code, 400)

    def test_parte_de_mas_o_fuera_de_orden_no_se_acepta(self):
        datos = zip_de(1)
        self.como(self.vladi)
        sid = self.c.post(S, {'nombre': 'a.zip', 'tamano': len(datos)}, format='json').json()['id']
        self.assertEqual(self.c.put(f'{S}{sid}/partes/1/', data=datos[PARTE:2 * PARTE], content_type='application/octet-stream').status_code, 409)
        self.assertEqual(self.c.put(f'{S}{sid}/partes/0/', data=datos[:PARTE] + b'x', content_type='application/octet-stream').status_code, 400)
        self.assertEqual(self.c.put(f'{S}{sid}/partes/0/', data=datos[:PARTE], content_type='application/octet-stream').status_code, 200)
        # Repetir una parte ya recibida (reintento) no la escribe dos veces
        self.assertEqual(self.c.put(f'{S}{sid}/partes/0/', data=datos[:PARTE], content_type='application/octet-stream').json()['recibidos'], PARTE)
        # Completar con partes faltantes no se puede
        self.assertEqual(self.c.post(f'{S}{sid}/completar/').status_code, 400)

    def test_rechaza_extensiones_y_contenido_peligroso(self):
        self.como(self.vladi)
        for nombre in ('virus.exe', 'script.sh', 'pagina.html', 'sin_extension'):
            self.assertEqual(self.c.post(S, {'nombre': nombre, 'tamano': 1000}, format='json').status_code, 400, nombre)
        # Un programa disfrazado de video
        sid, r = self.subir(self.vladi, 'video.mp4', b'MZ' + os.urandom(PARTE + 10))
        self.assertEqual(r.status_code, 400)
        self.assertIn('ejecutable', r.json()['detail'])
        self.assertEqual(SubidaPorPartes.objects.get(pk=sid).estado, 'RECHAZADA')
        # Un ZIP con un .exe adentro, como en el chat
        _, r = self.subir(self.vladi, 'paquete.zip', zip_de(0.5, adentro='instalar.exe'))
        self.assertEqual(r.status_code, 400)
        self.assertIn('ejecutables', r.json()['detail'])
        # Algo que dice ser ZIP y no lo es
        _, r = self.subir(self.vladi, 'falso.zip', os.urandom(PARTE + 5))
        self.assertEqual(r.status_code, 400)
        # Una subida rechazada no se puede adjuntar
        t = self.tarea(self.erlin)
        self.assertEqual(self.c.post(f'{T}{t.id}/referencias/', {'subidas': [sid]}, format='multipart').status_code, 400)

    def test_nadie_usa_la_subida_de_otra_persona(self):
        datos = zip_de(1)
        sid, _ = self.subir(self.erlin, 'mio.zip', datos, completar=False)
        self.como(self.ashley)
        self.assertEqual(self.c.get(f'{S}{sid}/').status_code, 404)
        self.assertEqual(self.c.post(f'{S}{sid}/completar/').status_code, 404)
        self.assertEqual(self.c.put(f'{S}{sid}/partes/0/', data=datos[:PARTE], content_type='application/octet-stream').status_code, 404)
        self.assertEqual(self.c.delete(f'{S}{sid}/').status_code, 404)
        self.como(self.erlin)
        self.assertEqual(self.c.post(f'{S}{sid}/completar/').status_code, 200)
        # Otra persona no la adjunta a su tarea aunque conozca el id
        t = self.tarea(self.vladi)
        self.como(self.vladi)
        r = self.c.post(f'{T}{t.id}/entregar/', {'evidencia_nota': 'x', 'subidas': [sid]}, format='multipart')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(EvidenciaArchivo.objects.filter(tarea=t).exists())
        t.refresh_from_db()
        self.assertNotEqual(t.estado, 'EN_REVISION')
        self.assertEqual(SubidaPorPartes.objects.get(pk=sid).estado, 'COMPLETA')

    def test_los_archivos_chicos_siguen_como_siempre_y_la_sesion_trae_el_limite(self):
        from apps.desempeno.tests_mejoras import foto
        t = self.tarea(self.erlin)
        self.como(self.vladi)
        r = self.c.post(f'{T}{t.id}/referencias/', {'archivos': [foto('boceto.jpg')]}, format='multipart')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(ReferenciaArchivo.objects.filter(tarea=t).count(), 1)
        self.assertEqual(self.c.post(f'{T}{t.id}/referencias/', {'nota': 'sin nada'}, format='multipart').status_code, 400)
        self.assertEqual(self.c.get('/api/auth/session/').json()['user']['limite_adjunto_grande_mb'], 400)

    def test_limpieza_de_subidas_viejas(self):
        sid, _ = self.subir(self.vladi, 'olvidado.zip', zip_de(0.5), completar=False)
        nuevo, _ = self.subir(self.vladi, 'reciente.zip', zip_de(0.5), completar=False)
        SubidaPorPartes.objects.filter(pk=sid).update(creada=timezone.now() - timedelta(hours=25))
        self.assertEqual(limpiar_vencidas(), 1)
        self.assertFalse(SubidaPorPartes.objects.filter(pk=sid).exists())
        self.assertFalse(os.path.exists(os.path.join(MEDIA, CARPETA, sid)))
        self.assertTrue(os.path.exists(os.path.join(MEDIA, CARPETA, nuevo)))


@override_settings(MEDIA_ROOT=MEDIA, SUBIDA_PARTE_BYTES=PARTE, CHAT_ANTIVIRUS='exigir', CLAMAV_STREAM_MAX_MB=1)
class AntivirusZipGrandeTests(Base):
    """El antivirus del servidor solo recibe hasta 100 MB por envío: un ZIP más grande se revisa archivo por archivo."""
    def subir_zip(self, datos):
        self.como(self.vladi)
        inicio = self.c.post(S, {'nombre': 'grande.zip', 'tamano': len(datos)}, format='json').json()
        for i in range(inicio['partes']):
            self.c.put(f"{S}{inicio['id']}/partes/{i}/", data=datos[i * PARTE:(i + 1) * PARTE], content_type='application/octet-stream')
        return self.c.post(f"{S}{inicio['id']}/completar/")

    def zip_varios(self, tamanos):
        b = io.BytesIO()
        with zipfile.ZipFile(b, 'w', zipfile.ZIP_STORED) as z:
            for i, mb in enumerate(tamanos):
                z.writestr(f'parte{i}.png', os.urandom(int(mb * 1024 * 1024)))
        return b.getvalue()

    def test_zip_mas_grande_que_el_tope_se_revisa_por_archivo(self):
        from unittest import mock
        from apps.chat import antivirus
        enviados = []
        def falso(f):
            enviados.append(len(f.read()))
            return antivirus.LIMPIO, ''
        with mock.patch.object(antivirus, 'escanear', side_effect=falso):
            r = self.subir_zip(self.zip_varios([0.6, 0.6, 0.6]))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(enviados), 3)                       # uno por archivo, nunca el ZIP entero
        self.assertTrue(all(n <= 1024 * 1024 for n in enviados))

    def test_archivo_interno_mas_grande_que_el_tope_se_rechaza_con_explicacion(self):
        from unittest import mock
        from apps.chat import antivirus
        with mock.patch.object(antivirus, 'escanear', return_value=(antivirus.LIMPIO, '')):
            r = self.subir_zip(self.zip_varios([1.5, 0.2]))
        self.assertEqual(r.status_code, 400)
        self.assertIn('parte0.png', r.content.decode())

    def test_amenaza_dentro_del_zip(self):
        from unittest import mock
        from apps.chat import antivirus
        with mock.patch.object(antivirus, 'escanear', side_effect=[(antivirus.LIMPIO, ''), (antivirus.INFECTADO, 'Eicar-Test')]):
            r = self.subir_zip(self.zip_varios([0.6, 0.6]))
        self.assertEqual(r.status_code, 400)
        self.assertIn('Eicar', r.content.decode())
