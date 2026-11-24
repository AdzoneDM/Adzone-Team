"""ZIP en el chat: validación real, antivirus, límite configurable, descarga protegida y limpieza a los 30 días."""
import io
import zipfile
from datetime import timedelta
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone

from . import antivirus, servicios
from .models import Mensaje
from .tests import BASE, Base
from .tests_grupos import MEDIA, imagen, pdf

LIMPIO = mock.patch('apps.chat.antivirus.escanear', return_value=(antivirus.LIMPIO, ''))


def zip_de(archivos=None, nombre='proyecto.zip', **kw):
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, datos in (archivos or {'leeme.txt': b'hola', 'src/app.py': b'print(1)'}).items():
            z.writestr(n, datos)
    return SimpleUploadedFile(nombre, b.getvalue(), content_type='application/zip')


@override_settings(MEDIA_ROOT=MEDIA, CHAT_ANTIVIRUS='exigir')
class ZipTests(Base):
    def setUp(self):
        super().setUp()
        self.priv = self.privado(self.ana, self.luis)

    def enviar(self, archivo, quien=None, conv=None, texto=''):
        return self.como(quien or self.ana).post(f'{BASE}/conversaciones/{conv or self.priv}/mensajes/', {'texto': texto, 'archivo': archivo}, format='multipart')

    # ---------------------------------------------------------------- lo que sí entra
    def test_un_zip_real_se_envia_por_privado_y_por_la_sala_con_su_ficha(self):
        with LIMPIO:
            for conv in (self.priv, self.sala.id):
                r = self.enviar(zip_de(), conv=conv)
                self.assertEqual(r.status_code, 201, r.content)
                a = r.data['archivo']
                self.assertEqual((a['nombre'], a['es_zip'], a['items'], a['revisado'], a['es_video'], a['es_imagen']), ('proyecto.zip', True, 2, True, False, False))
                self.assertGreater(a['tamano'], 0)
        m = Mensaje.objects.latest('id')
        self.assertEqual((m.autor, m.archivo_escaneo, m.archivo_items), (self.ana, 'LIMPIO', 2))      # quién, y que fue revisado

    def test_se_pueden_compartir_varios_zip(self):
        with LIMPIO:
            self.assertEqual([self.enviar(zip_de(nombre=f'parte{i}.zip')).status_code for i in range(3)], [201, 201, 201])

    # ---------------------------------------------------------------- lo que se rechaza
    def test_un_archivo_que_solo_se_llama_zip_se_rechaza(self):
        falso = SimpleUploadedFile('virus.zip', b'MZ\x90\x00 esto es un ejecutable', content_type='application/zip')
        with LIMPIO as av:
            r = self.enviar(falso)
        self.assertEqual(r.status_code, 400)
        self.assertIn('no es un ZIP válido', str(r.data))
        self.assertFalse(Mensaje.objects.exists())
        av.assert_not_called()                                                                           # ni siquiera llega al antivirus

    def test_un_zip_corrupto_se_rechaza(self):
        buena = zip_de().read()
        roto = SimpleUploadedFile('roto.zip', buena[:40] + b'\x00' * 10, content_type='application/zip')   # firma buena, índice destruido
        with LIMPIO:
            self.assertEqual(self.enviar(roto).status_code, 400)

    def test_un_zip_con_contrasena_no_se_puede_revisar_y_se_rechaza(self):
        b = io.BytesIO()
        with zipfile.ZipFile(b, 'w') as z:
            z.writestr('secreto.txt', b'x')
        datos = bytearray(b.getvalue())
        datos[6] |= 0x01                                                                                 # bit «cifrado» del archivo local
        i = datos.rfind(b'PK\x01\x02')
        datos[i + 8] |= 0x01                                                                             # y del directorio central
        with LIMPIO:
            r = self.enviar(SimpleUploadedFile('clave.zip', bytes(datos)))
        self.assertEqual(r.status_code, 400)
        self.assertIn('contraseña', str(r.data))

    def test_un_zip_con_ejecutables_se_rechaza(self):
        with LIMPIO:
            r = self.enviar(zip_de({'foto.jpg': b'x', 'instalar.exe': b'MZ'}))
        self.assertEqual(r.status_code, 400)
        self.assertIn('ejecutables', str(r.data))
        with LIMPIO, override_settings(CHAT_ZIP_BLOQUEAR_EJECUTABLES=False):
            self.assertEqual(self.enviar(zip_de({'instalar.exe': b'MZ'})).status_code, 201)             # configurable

    def test_una_bomba_de_compresion_se_rechaza(self):
        bomba = zip_de({'ceros.bin': b'\x00' * (120 * 1024 * 1024)})                                    # 120 MB de ceros en pocos KB
        self.assertLess(bomba.size, 1024 * 1024)
        with LIMPIO:
            r = self.enviar(bomba)
        self.assertEqual(r.status_code, 400)
        self.assertIn('desproporcionado', str(r.data))

    def test_el_limite_de_tamano_es_configurable(self):
        import random
        datos = random.Random(7).randbytes(2 * 1024 * 1024)                                               # ~2 MB incompresibles
        with LIMPIO, override_settings(CHAT_ZIP_MAX_MB=1):
            r = self.enviar(zip_de({'datos.bin': datos}))
        self.assertEqual(r.status_code, 400)
        self.assertIn('más de 1 MB', str(r.data))
        with LIMPIO, override_settings(CHAT_ZIP_MAX_MB=50):
            self.assertEqual(self.enviar(zip_de({'datos.bin': datos})).status_code, 201)

    # ---------------------------------------------------------------- antivirus
    def test_si_el_antivirus_detecta_una_amenaza_no_se_envia(self):
        with mock.patch('apps.chat.antivirus.escanear', return_value=(antivirus.INFECTADO, 'Eicar-Test-Signature')):
            r = self.enviar(zip_de())
        self.assertEqual(r.status_code, 400)
        self.assertIn('Eicar-Test-Signature', str(r.data))
        self.assertFalse(Mensaje.objects.exists())

    def test_si_el_antivirus_no_responde_se_rechaza(self):
        with mock.patch('apps.chat.antivirus.escanear', return_value=(antivirus.NO_DISPONIBLE, 'sin conexión')):
            r = self.enviar(zip_de())
        self.assertEqual(r.status_code, 400)
        self.assertIn('antivirus', str(r.data))
        self.assertFalse(Mensaje.objects.exists())

    def test_sin_clamd_la_conexion_falla_y_queda_como_no_disponible(self):
        with override_settings(CLAMAV_SOCKET='/tmp/no-existe.ctl'):
            self.assertEqual(antivirus.escanear(io.BytesIO(b'x'))[0], antivirus.NO_DISPONIBLE)

    def test_en_desarrollo_se_puede_omitir_y_queda_marcado_sin_revisar(self):
        with override_settings(CHAT_ANTIVIRUS='omitir'):
            r = self.enviar(zip_de())
        self.assertEqual(r.status_code, 201)
        self.assertEqual((r.data['archivo']['revisado'], Mensaje.objects.get().archivo_escaneo), (False, 'NO_REVISADO'))

    # ---------------------------------------------------------------- descarga protegida
    def test_solo_los_participantes_descargan_y_siempre_como_descarga(self):
        with LIMPIO:
            mid = self.enviar(zip_de()).data['id']
        r = self.como(self.luis).get(f'{BASE}/mensajes/{mid}/archivo/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('attachment', r['Content-Disposition'])
        self.assertEqual((r['Content-Type'], r['X-Content-Type-Options']), ('application/zip', 'nosniff'))
        self.assertEqual(self.como(self.eva).get(f'{BASE}/mensajes/{mid}/archivo/').status_code, 404)    # ajena al privado
        self.assertIn(APIClientSinSesion().get(f'{BASE}/mensajes/{mid}/archivo/').status_code, (401, 403))

    def test_se_vuelve_a_validar_antes_de_entregarlo(self):
        with LIMPIO:
            mid = self.enviar(zip_de()).data['id']
        m = Mensaje.objects.get(pk=mid)
        with m.archivo.open('wb') as f:                                                                   # alguien cambió el contenido en disco
            f.write(b'MZ no soy un zip')
        self.assertEqual(self.como(self.luis).get(f'{BASE}/mensajes/{mid}/archivo/').status_code, 422)

    # ---------------------------------------------------------------- limpieza a los 30 días
    def test_los_zip_se_borran_a_los_30_dias_y_el_mensaje_queda(self):
        with LIMPIO:
            viejo = self.enviar(zip_de(nombre='viejo.zip')).data['id']
            reciente = self.enviar(zip_de(nombre='nuevo.zip')).data['id']
            otro = self.enviar(pdf()).data['id']
        Mensaje.objects.filter(pk__in=[viejo, otro]).update(creado=timezone.now() - timedelta(days=31))
        n, liberado = servicios.purgar_videos_del_chat()
        self.assertEqual(n, 1)
        self.assertGreater(liberado, 0)
        m = Mensaje.objects.get(pk=viejo)
        self.assertTrue(m.archivo_purgado)
        self.assertFalse(m.archivo)
        self.assertFalse(Mensaje.objects.get(pk=reciente).archivo_purgado)                                # menos de 30 días: se queda
        self.assertFalse(Mensaje.objects.get(pk=otro).archivo_purgado)                                    # un PDF viejo no se borra
        a = self.como(self.luis).get(f'{BASE}/conversaciones/{self.priv}/mensajes/').data['mensajes']
        purgado = next(x for x in a if x['id'] == viejo)['archivo']
        self.assertEqual((purgado['purgado'], purgado['es_zip'], purgado['es_video']), (True, True, False))
        self.assertEqual(self.como(self.luis).get(f'{BASE}/mensajes/{viejo}/archivo/').status_code, 410)

    def test_los_dias_de_conservacion_son_configurables(self):
        from apps.desempeno.models import ConfiguracionDesempeno
        c = ConfiguracionDesempeno.actual()
        self.assertEqual(c.dias_conservar_zip_chat, 30)
        c.dias_conservar_zip_chat = 5
        c.save()
        with LIMPIO:
            mid = self.enviar(zip_de()).data['id']
        Mensaje.objects.filter(pk=mid).update(creado=timezone.now() - timedelta(days=6))
        self.assertEqual(servicios.purgar_videos_del_chat()[0], 1)

    # ---------------------------------------------------------------- lo existente sigue igual
    def test_los_demas_formatos_no_pasan_por_el_antivirus_ni_cambian(self):
        with mock.patch('apps.chat.antivirus.escanear') as av:
            self.assertEqual(self.enviar(pdf()).status_code, 201)
            self.assertEqual(self.enviar(imagen()).status_code, 201)
            self.assertEqual(self.enviar(SimpleUploadedFile('notas.txt', b'hola', content_type='text/plain')).status_code, 201)
            self.assertEqual(self.enviar(SimpleUploadedFile('virus.exe', b'MZ', content_type='application/octet-stream')).status_code, 400)
            grande = SimpleUploadedFile('enorme.pdf', b'%PDF' + b'0' * (16 * 1024 * 1024), content_type='application/pdf')
            self.assertEqual(self.enviar(grande).status_code, 400)                                       # el tope de 15 MB de documentos sigue igual
        av.assert_not_called()
        m = Mensaje.objects.filter(archivo_nombre='informe.pdf').get()
        self.assertEqual((m.archivo_items, m.archivo_escaneo), (None, ''))

    def test_el_estado_de_la_sesion_trae_el_limite_de_zip(self):
        self.assertEqual(self.como(self.ana).get('/api/auth/session/').json()['user']['limite_zip_mb'], 50)


def APIClientSinSesion():
    from rest_framework.test import APIClient
    return APIClient()
