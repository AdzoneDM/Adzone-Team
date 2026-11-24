"""Requerimiento #8, etapa 1: documentos en evidencias, «asignadas por mí», aviso de vencidas y panel de estados."""
import io
import zipfile
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone

from apps.chat import antivirus
from . import servicios
from .models import EvidenciaArchivo, Notificacion, Tarea
from .tests_mejoras import MEDIA, Base, foto

T = '/api/desempeno/tareas/'
LIMPIO = mock.patch('apps.chat.antivirus.escanear', return_value=(antivirus.LIMPIO, ''))


def docx(nombre='informe.docx', extra=b''):
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w') as z:
        z.writestr('[Content_Types].xml', '<xml/>')
        z.writestr('word/document.xml', '<w/>' + extra.decode())
    return SimpleUploadedFile(nombre, b.getvalue(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')


def lista(r):
    j = r.json()
    return j['results'] if isinstance(j, dict) and 'results' in j else j


@override_settings(MEDIA_ROOT=MEDIA, CHAT_ANTIVIRUS='exigir')
class DocumentosEnEvidenciasTests(Base):
    def entregar(self, tarea, *archivos, quien=None):
        self.como(quien or self.erlin)
        return self.c.post(f'{T}{tarea.id}/entregar/', {'evidencia_nota': 'listo', 'archivos': list(archivos)}, format='multipart')

    def test_word_excel_powerpoint_csv_y_texto_se_aceptan(self):
        t = self.tarea(self.erlin)
        archivos = [docx(), docx('cuentas.xlsx'), docx('charla.pptx'), SimpleUploadedFile('datos.csv', b'a,b\n1,2', content_type='text/csv'),
                    SimpleUploadedFile('notas.txt', b'hola', content_type='text/plain'),
                    SimpleUploadedFile('viejo.doc', b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' + b'0' * 50, content_type='application/msword')]
        r = self.entregar(t, *archivos)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.json()['evidencias']), 6)

    def test_quien_la_adjunto_y_cuando_se_ve_en_cada_evidencia(self):
        t = self.tarea(self.erlin)
        ev = self.entregar(t, docx()).json()['evidencias'][0]
        self.assertEqual(ev['subido_por_nombre'], 'Erlin Pérez')
        self.assertTrue(ev['fecha'])

    def test_un_documento_falso_se_rechaza(self):
        t = self.tarea(self.erlin)
        falso = SimpleUploadedFile('virus.docx', b'MZ\x90\x00 ejecutable disfrazado', content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        r = self.entregar(t, falso)
        self.assertEqual(r.status_code, 400)
        self.assertIn('no es un archivo DOCX válido', str(r.json()))
        self.assertFalse(EvidenciaArchivo.objects.exists())
        self.assertEqual(self.entregar(t, SimpleUploadedFile('macro.exe', b'MZ')).status_code, 400)               # lo ejecutable sigue prohibido

    def test_peso_maximo_de_un_documento(self):
        t = self.tarea(self.erlin)
        grande = SimpleUploadedFile('enorme.xlsx', b'PK\x03\x04' + b'0' * (16 * 1024 * 1024))
        self.assertEqual(self.entregar(t, grande).status_code, 400)
        self.assertEqual(self.entregar(t, self.tarea_docx_tamano(14)).status_code, 200)

    def tarea_docx_tamano(self, mb):
        return SimpleUploadedFile('casi.xlsx', b'PK\x03\x04' + b'0' * (mb * 1024 * 1024))

    def test_un_zip_se_revisa_como_en_el_chat(self):
        t = self.tarea(self.erlin)
        b = io.BytesIO()
        with zipfile.ZipFile(b, 'w') as z:
            z.writestr('leeme.txt', 'hola')
        bueno = SimpleUploadedFile('entrega.zip', b.getvalue())
        with LIMPIO:
            self.assertEqual(self.entregar(t, bueno).status_code, 200)
        t2 = self.tarea(self.erlin)
        b2 = io.BytesIO()
        with zipfile.ZipFile(b2, 'w') as z:
            z.writestr('instalar.exe', 'MZ')
        with LIMPIO:
            r = self.entregar(t2, SimpleUploadedFile('malo.zip', b2.getvalue()))
        self.assertEqual(r.status_code, 400)
        self.assertIn('ejecutables', str(r.json()))
        with mock.patch('apps.chat.antivirus.escanear', return_value=(antivirus.INFECTADO, 'Eicar')):
            t3 = self.tarea(self.erlin)
            self.assertEqual(self.entregar(t3, SimpleUploadedFile('virus.zip', b.getvalue())).status_code, 400)

    def test_los_documentos_se_entregan_como_descarga_y_solo_a_quien_corresponde(self):
        t = self.tarea(self.erlin)
        ev = self.entregar(t, docx()).json()['evidencias'][0]
        self.como(self.vladi)                                                                                   # su supervisora
        r = self.c.get(ev['url'])
        self.assertEqual(r.status_code, 200)
        self.assertIn('attachment', r['Content-Disposition'])
        self.assertEqual(r['X-Content-Type-Options'], 'nosniff')
        self.como(self.dev)                                                                                     # otra área: no la ve
        self.assertEqual(self.c.get(ev['url']).status_code, 404)

    def test_lo_de_siempre_sigue_igual(self):
        t = self.tarea(self.erlin)
        self.assertEqual(self.entregar(t, foto('a.jpg'), SimpleUploadedFile('guia.pdf', b'%PDF-1.4 x', content_type='application/pdf')).status_code, 200)
        t2 = self.tarea(self.erlin)
        self.assertEqual(self.entregar(t2, *[foto(f'{i}.jpg') for i in range(11)]).status_code, 400)              # el tope de 10 archivos

    def test_las_referencias_tambien_aceptan_documentos(self):
        self.vladi.groups.add(Group.objects.get(name='Gerente de Departamento'))
        t = self.tarea(self.erlin)
        self.como(self.vladi)
        r = self.c.post(f'{T}{t.id}/referencias/', {'archivos': [docx('brief.docx')]}, format='multipart')
        self.assertEqual(r.status_code, 200, r.content)


class AsignadasPorMiTests(Base):
    def test_filtra_lo_que_asigne_a_otras_personas(self):
        mia_para_erlin = self.tarea(self.erlin, asignada_por=self.vladi)
        para_si = self.tarea(self.vladi, asignada_por=self.vladi)
        de_otro = self.tarea(self.ashley, asignada_por=self.osiris)
        self.como(self.vladi)
        ids = {t['id'] for t in lista(self.c.get(T + '?ambito=equipo&asignadas=1'))}
        self.assertEqual(ids, {mia_para_erlin.id})
        self.assertNotIn(para_si.id, ids)
        self.assertNotIn(de_otro.id, ids)
        self.assertIn(de_otro.id, {t['id'] for t in lista(self.c.get(T + '?ambito=equipo'))})                    # sin el filtro todo sigue igual


class AvisoDeVencidasTests(Base):
    def vencida(self, quien, dias=2, **kw):
        return Tarea.objects.create(titulo='Vencida de prueba', colaborador=quien, asignada_por=self.vladi,
                                    fecha_limite=timezone.localdate() - timedelta(days=dias), **kw)

    def test_avisa_a_quien_la_tiene_y_a_su_supervisor_una_sola_vez(self):
        t = self.vencida(self.erlin)
        self.assertEqual(servicios.avisar_vencidas(), 1)
        self.assertTrue(Notificacion.objects.filter(destinatario=self.erlin, tarea=t, titulo__startswith='Venció').exists())
        self.assertTrue(Notificacion.objects.filter(destinatario=self.vladi, tarea=t, titulo__startswith='Vencida').exists())
        self.assertEqual(servicios.avisar_vencidas(), 0)                                                         # no se repite cada día

    def test_no_avisa_de_lo_entregado_terminado_ni_de_lo_muy_viejo_ni_de_lo_que_no_vencio(self):
        self.vencida(self.erlin, estado='EN_REVISION')
        self.vencida(self.erlin, estado='COMPLETADA')
        self.vencida(self.erlin, dias=60)
        self.tarea(self.erlin, dias=1)
        self.assertEqual(servicios.avisar_vencidas(), 0)

    def test_las_compañeras_tambien_se_enteran(self):
        t = self.vencida(self.erlin)
        t.companeros.add(self.ashley)
        servicios.avisar_vencidas()
        self.assertTrue(Notificacion.objects.filter(destinatario=self.ashley, tarea=t).exists())

    def test_el_cron_diario_lo_ejecuta(self):
        from django.core.management import call_command
        self.vencida(self.erlin)
        call_command('tareas_diarias', stdout=io.StringIO())
        self.assertTrue(Notificacion.objects.filter(destinatario=self.erlin, titulo__startswith='Venció').exists())


class PanelDeEstadosTests(Base):
    RES = '/api/desempeno/resumen-tareas/'

    def setUp(self):
        super().setUp()
        hoy = timezone.localdate()
        mk = lambda quien, **kw: Tarea.objects.create(titulo='t', colaborador=quien, asignada_por=self.vladi, fecha_limite=kw.pop('limite', hoy + timedelta(days=3)), **kw)  # noqa: E731
        mk(self.erlin)                                                              # pendiente
        mk(self.erlin, estado='EN_PROGRESO')                                        # en proceso
        mk(self.erlin, estado='EN_PROGRESO', rondas_revision=1)                     # devuelta
        mk(self.erlin, estado='EN_REVISION')                                        # por validar
        mk(self.erlin, estado='COMPLETADA', fecha_completada=hoy, limite=hoy + timedelta(days=1))                        # aprobada a tiempo
        mk(self.erlin, estado='COMPLETADA', fecha_completada=hoy, limite=hoy - timedelta(days=1))                        # aprobada tarde
        mk(self.erlin, estado='PENDIENTE', limite=hoy - timedelta(days=2))          # vencida
        mk(self.erlin, estado='BLOQUEADA')
        mk(self.erlin, estado='CANCELADA')
        Tarea.objects.create(titulo='t', colaborador=self.dev, asignada_por=self.osiris, prioridad='ALTA', fecha_limite=hoy + timedelta(days=3))   # de otra área, la asignó Dirección

    def datos(self, quien, **params):
        self.como(quien)
        r = self.c.get(self.RES, params)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def test_cuenta_cada_estado(self):
        c = self.datos(self.osiris)['conteos']
        self.assertEqual((c['total'], c['pendientes'], c['en_proceso'], c['devueltas'], c['por_validar'], c['aprobadas'], c['bloqueadas'], c['canceladas']),
                         (10, 3, 1, 1, 1, 2, 1, 1))
        self.assertEqual((c['vencidas'], c['a_tiempo'], c['fuera_de_plazo']), (1, 1, 1))                        # la vencida se cuenta además de su estado

    def test_cada_quien_ve_solo_sus_estadisticas(self):
        self.assertEqual(self.datos(self.erlin)['conteos']['total'], 9)              # solo las suyas
        self.assertEqual(self.datos(self.dev)['conteos']['total'], 1)
        self.assertEqual(self.datos(self.vladi)['conteos']['total'], 9)              # su equipo, no Tecnología
        self.assertEqual(self.datos(self.osiris)['conteos']['total'], 10)

    def test_filtros(self):
        self.assertEqual(self.datos(self.osiris, estado='vencidas')['conteos']['total'], 1)
        self.assertEqual(self.datos(self.osiris, estado='por_validar')['conteos']['total'], 1)
        self.assertEqual(self.datos(self.osiris, prioridad='ALTA')['conteos']['total'], 1)
        self.assertEqual(self.datos(self.osiris, persona=self.dev.id)['conteos']['total'], 1)
        self.assertEqual(self.datos(self.osiris, departamento=self.tec.id)['conteos']['total'], 1)
        self.assertEqual(self.datos(self.osiris, asignador=self.vladi.id)['conteos']['total'], 9)
        hoy = timezone.localdate()
        self.assertEqual(self.datos(self.osiris, desde=str(hoy - timedelta(days=3)), hasta=str(hoy - timedelta(days=1)))['conteos']['total'], 2)

    def test_por_departamento_y_prioridad(self):
        j = self.datos(self.osiris)
        marketing = next(d for d in j['por_departamento'] if d['departamento'] == 'Marketing')
        self.assertEqual((marketing['total'], marketing['por_validar'], marketing['aprobadas'], marketing['vencidas']), (9, 1, 2, 1))
        self.assertEqual(j['por_prioridad'].get('ALTA'), 1)

    def test_exige_sesion(self):
        self.c.force_authenticate(None)
        self.assertIn(self.c.get(self.RES).status_code, (401, 403))
