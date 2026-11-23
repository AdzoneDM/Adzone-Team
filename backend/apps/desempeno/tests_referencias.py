"""Bocetos e imágenes de referencia que adjunta el supervisor: al asignar y al devolver una tarea."""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from .models import Notificacion, ReferenciaArchivo
from .tests_mejoras import MEDIA, Base, foto

T = '/api/desempeno/tareas/'


@override_settings(MEDIA_ROOT=MEDIA)
class ReferenciasTests(Base):
    def subir(self, quien, tarea, *archivos, **extra):
        self.como(quien)
        return self.c.post(f'{T}{tarea.id}/referencias/', {'archivos': list(archivos), **extra}, format='multipart')

    def test_el_supervisor_adjunta_un_boceto_al_asignar_y_la_persona_lo_ve(self):
        t = self.tarea(self.erlin)
        r = self.subir(self.vladi, t, foto('boceto.jpg'), nota='Así quiero el layout')
        self.assertEqual(r.status_code, 200, r.content)
        ref = r.json()['referencias'][0]
        self.assertEqual((ref['nombre_original'], ref['momento'], ref['es_imagen'], ref['nota']), ('boceto.jpg', 'ASIGNACION', True, 'Así quiero el layout'))
        self.assertEqual(ref['subido_por_nombre'], 'Vladimir Gómez')
        # Le llega el aviso a quien tiene la tarea
        self.assertTrue(Notificacion.objects.filter(destinatario=self.erlin, tipo='MODIFICADA', titulo__startswith='Nueva referencia').exists())
        # Quien tiene la tarea ve la referencia y descarga el archivo
        self.como(self.erlin)
        self.assertEqual(self.c.get(f'{T}{t.id}/').json()['referencias'][0]['id'], ref['id'])
        self.assertEqual(self.c.get(ref['url']).status_code, 200)

    def test_quien_no_tiene_que_ver_no_la_ve_ni_la_sube(self):
        t = self.tarea(self.erlin)
        ref = self.subir(self.vladi, t, foto()).json()['referencias'][0]
        self.assertEqual(self.subir(self.erlin, t, foto()).status_code, 403)          # quien trabaja la tarea no pone referencias
        for otro in (self.ashley, self.dev):
            self.como(otro)
            self.assertEqual(self.c.get(ref['url']).status_code, 404)
        self.como(self.osiris)
        self.assertEqual(self.c.get(ref['url']).status_code, 200)                      # Dirección sí

    def test_solo_imagenes_y_pdf_y_con_limite(self):
        t = self.tarea(self.erlin)
        malo = SimpleUploadedFile('virus.exe', b'MZ', content_type='application/octet-stream')
        self.assertEqual(self.subir(self.vladi, t, malo).status_code, 400)
        self.assertEqual(self.subir(self.vladi, t, *[foto(f'{i}.jpg') for i in range(11)]).status_code, 400)
        pdf = SimpleUploadedFile('guia.pdf', b'%PDF-1.4', content_type='application/pdf')
        self.assertEqual(self.subir(self.vladi, t, pdf).status_code, 200)
        self.assertEqual(ReferenciaArchivo.objects.filter(tarea=t).count(), 1)

    def test_devolver_con_boceto_de_correccion(self):
        t = self.tarea(self.erlin, estado='EN_REVISION', evidencia_nota='listo')
        self.como(self.vladi)
        r = self.c.post(f'{T}{t.id}/rechazar/', {'comentario_revision': 'Mueve el logo arriba', 'archivos': [foto('correccion.jpg')]}, format='multipart')
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        self.assertEqual((d['estado'], d['rondas_revision']), ('EN_PROGRESO', 1))
        self.assertEqual([(x['momento'], x['ronda']) for x in d['referencias']], [('CORRECCION', 1)])
        aviso = Notificacion.objects.get(destinatario=self.erlin, tipo='DEVUELTA')
        self.assertIn('Mueve el logo arriba', aviso.mensaje)
        self.assertIn('1 archivo de referencia', aviso.mensaje)
        # Devolver sin archivos sigue funcionando como siempre
        t2 = self.tarea(self.ashley, estado='EN_REVISION', evidencia_nota='listo')
        self.assertEqual(self.c.post(f'{T}{t2.id}/rechazar/', {'comentario_revision': 'Falta el CTA'}, format='json').status_code, 200)

    def test_devolver_con_archivo_invalido_no_devuelve_la_tarea(self):
        t = self.tarea(self.erlin, estado='EN_REVISION', evidencia_nota='listo')
        self.como(self.vladi)
        malo = SimpleUploadedFile('x.exe', b'MZ')
        r = self.c.post(f'{T}{t.id}/rechazar/', {'comentario_revision': 'Corrige esto', 'archivos': [malo]}, format='multipart')
        self.assertEqual(r.status_code, 400)
        t.refresh_from_db()
        self.assertEqual((t.estado, t.rondas_revision), ('EN_REVISION', 0))

    def test_quitar_una_referencia(self):
        t = self.tarea(self.erlin)
        ref = self.subir(self.vladi, t, foto()).json()['referencias'][0]
        self.assertTrue(ref['puede_borrar'])
        self.como(self.erlin)
        self.assertEqual(self.c.delete(ref['url']).status_code, 403)
        self.como(self.ashley)
        self.assertEqual(self.c.delete(ref['url']).status_code, 404)
        self.como(self.vladi)
        self.assertEqual(self.c.delete(ref['url']).status_code, 204)
        self.assertFalse(ReferenciaArchivo.objects.exists())

    def test_si_se_acaba_de_asignar_la_referencia_se_suma_al_mismo_aviso(self):
        # El supervisor asigna (aviso «Nueva tarea») y enseguida adjunta el boceto: la persona recibe UNA sola alerta
        self.como(self.vladi)
        from datetime import timedelta
        from django.utils import timezone
        r = self.c.post(T, {'titulo': 'Logo', 'colaborador': self.erlin.id, 'fecha_limite': str(timezone.localdate() + timedelta(days=3)), 'prioridad': 'MEDIA'}, format='json')
        tid = r.json()['id']
        self.assertEqual(Notificacion.objects.filter(destinatario=self.erlin, tarea_id=tid).count(), 1)
        self.subir(self.vladi, self.tarea_de(tid), foto())
        avisos = Notificacion.objects.filter(destinatario=self.erlin, tarea_id=tid)
        self.assertEqual(avisos.count(), 1)
        self.assertEqual(avisos[0].tipo, 'ASIGNADA')
        self.assertIn('1 archivo de referencia', avisos[0].mensaje)

    def tarea_de(self, tid):
        from .models import Tarea
        return Tarea.objects.get(pk=tid)
