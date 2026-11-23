"""Videos como evidencia y referencia de tareas: subida, reproducción por tramos y limpieza después de validada la tarea."""
import os
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone

from . import servicios
from .models import ConfiguracionDesempeno, EvidenciaArchivo, ReferenciaArchivo
from .tests_mejoras import MEDIA, Base, foto

T = '/api/desempeno/tareas/'


def video(nombre='avance.mp4', tam=2000):
    return SimpleUploadedFile(nombre, b'\x00\x00\x00\x18ftypmp42' + bytes(range(256)) * (tam // 256), content_type='video/mp4')


@override_settings(MEDIA_ROOT=MEDIA)
class VideosTests(Base):
    def entregar(self, quien, tarea, *archivos, **extra):
        self.como(quien)
        return self.c.post(f'{T}{tarea.id}/entregar/', {'evidencia_nota': 'listo', 'archivos': list(archivos), **extra}, format='multipart')

    def test_entrega_un_video_como_evidencia(self):
        t = self.tarea(self.erlin)
        r = self.entregar(self.erlin, t, video(), foto('captura.jpg'))
        self.assertEqual(r.status_code, 200, r.content)
        ev = {e['nombre_original']: e for e in r.json()['evidencias']}
        self.assertEqual((ev['avance.mp4']['es_video'], ev['avance.mp4']['es_imagen']), (True, False))
        self.assertEqual((ev['captura.jpg']['es_video'], ev['captura.jpg']['es_imagen']), (False, True))

    def test_se_entregan_varias_imagenes_a_la_vez(self):
        t = self.tarea(self.erlin)
        r = self.entregar(self.erlin, t, *[foto(f'foto{i}.jpg') for i in range(10)])
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.data['evidencias']), 10)
        t2 = self.tarea(self.erlin)
        self.assertEqual(self.entregar(self.erlin, t2, *[foto(f'f{i}.jpg') for i in range(11)]).status_code, 400)   # el tope es 10

    def test_formatos_de_video_del_celular_se_aceptan(self):
        for nombre in ('a.mov', 'b.m4v', 'c.webm', 'd.3gp'):
            self.assertEqual(self.entregar(self.erlin, self.tarea(self.erlin), video(nombre)).status_code, 200, nombre)

    @override_settings(EVIDENCIA_VIDEO_MAX_MB=1, EVIDENCIA_MAX_MB=1)
    def test_un_video_tiene_su_propio_limite_y_el_resto_sigue_igual(self):
        t = self.tarea(self.erlin)
        grande = video('largo.mp4', 2 * 1024 * 1024)
        r = self.entregar(self.erlin, t, grande)
        self.assertEqual(r.status_code, 400)
        self.assertIn('pesa más de 1 MB', str(r.json()))
        self.assertIn('enlace', str(r.json()))                                         # sugiere pegar un enlace si es muy largo
        pesada = SimpleUploadedFile('pesada.png', b'0' * (2 * 1024 * 1024), content_type='image/png')
        self.assertEqual(self.entregar(self.erlin, t, pesada).status_code, 400)

    def test_ejecutables_y_otros_formatos_siguen_rechazados(self):
        t = self.tarea(self.erlin)
        malo = SimpleUploadedFile('virus.exe', b'MZ', content_type='application/octet-stream')
        self.assertEqual(self.entregar(self.erlin, t, malo).status_code, 400)

    def test_el_supervisor_adjunta_un_video_de_referencia(self):
        t = self.tarea(self.erlin)
        self.como(self.vladi)
        r = self.c.post(f'{T}{t.id}/referencias/', {'archivos': [video('ejemplo.mp4')]}, format='multipart')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['referencias'][0]['es_video'])

    def test_el_video_se_reproduce_por_tramos(self):
        t = self.tarea(self.erlin)
        url = self.entregar(self.erlin, t, video(tam=1024)).json()['evidencias'][0]['url']
        self.como(self.erlin)
        completo = self.c.get(url)
        self.assertEqual((completo.status_code, completo['Content-Type'], completo['Accept-Ranges']), (200, 'video/mp4', 'bytes'))
        total = int(completo['Content-Length'])
        self.assertEqual(len(b''.join(completo.streaming_content)), total)
        parte = self.c.get(url, HTTP_RANGE='bytes=0-99')
        self.assertEqual((parte.status_code, parte['Content-Range'], parte['Content-Length']), (206, f'bytes 0-99/{total}', '100'))
        self.assertEqual(len(b''.join(parte.streaming_content)), 100)
        final = self.c.get(url, HTTP_RANGE='bytes=-50')
        self.assertEqual((final.status_code, final['Content-Range']), (206, f'bytes {total - 50}-{total - 1}/{total}'))
        self.assertEqual(self.c.get(url, HTTP_RANGE=f'bytes={total + 10}-').status_code, 416)
        self.assertIn('attachment', self.c.get(url + '?descargar=1')['Content-Disposition'])

    def test_quien_no_tiene_que_ver_con_la_tarea_no_ve_el_video(self):
        t = self.tarea(self.erlin)
        url = self.entregar(self.erlin, t, video()).json()['evidencias'][0]['url']
        for otro in (self.ashley, self.dev):
            self.como(otro)
            self.assertEqual(self.c.get(url).status_code, 404)

    def test_la_sesion_informa_el_limite_de_videos(self):
        self.como(self.erlin)
        self.assertEqual(self.c.get('/api/auth/session/').json()['user']['limite_video_mb'], 60)

    # ---- limpieza
    def _con_video(self, **tarea):
        t = self.tarea(self.erlin, estado='COMPLETADA', **tarea)
        self.como(self.erlin)
        v = EvidenciaArchivo.objects.create(tarea=t, archivo=video(), nombre_original='avance.mp4', tipo='video/mp4', tamano=2000)
        f = EvidenciaArchivo.objects.create(tarea=t, archivo=foto('foto.jpg'), nombre_original='foto.jpg', tipo='image/jpeg', tamano=100)
        return t, v, f

    def test_los_videos_se_borran_pasados_los_dias_de_una_tarea_validada(self):
        hoy = timezone.localdate()
        t, v, f = self._con_video(fecha_completada=hoy - timedelta(days=8))
        ruta = v.archivo.path
        self.assertTrue(os.path.exists(ruta))
        borrados, liberado = servicios.purgar_videos(hoy)
        self.assertEqual((borrados, liberado), (1, 2000))
        v.refresh_from_db(), f.refresh_from_db()
        self.assertTrue(v.purgado)
        self.assertFalse(os.path.exists(ruta))
        self.assertFalse(f.purgado)                                                    # las fotos y los PDF no se tocan
        self.assertTrue(f.archivo)
        self.assertEqual(servicios.purgar_videos(hoy), (0, 0))                         # no repite

    def test_no_se_borra_antes_de_tiempo_ni_si_la_tarea_no_esta_validada(self):
        hoy = timezone.localdate()
        _, reciente, _ = self._con_video(fecha_completada=hoy - timedelta(days=3))
        en_revision = self.tarea(self.ashley, estado='EN_REVISION')
        pendiente = EvidenciaArchivo.objects.create(tarea=en_revision, archivo=video(), nombre_original='x.mp4', tipo='video/mp4', tamano=10)
        self.assertEqual(servicios.purgar_videos(hoy), (0, 0))
        reciente.refresh_from_db(), pendiente.refresh_from_db()
        self.assertFalse(reciente.purgado)
        self.assertFalse(pendiente.purgado)

    def test_los_dias_de_conservacion_se_configuran(self):
        hoy = timezone.localdate()
        _, v, _ = self._con_video(fecha_completada=hoy - timedelta(days=3))
        c = ConfiguracionDesempeno.actual()
        c.dias_conservar_videos = 2
        c.save()
        self.assertEqual(servicios.purgar_videos(hoy)[0], 1)
        # También desde la pantalla de reglas (solo Dirección) y con límites
        self.como(self.osiris)
        self.assertEqual(self.c.patch('/api/desempeno/configuracion/', {'dias_conservar_videos': 14}, format='json').status_code, 200)
        self.assertEqual(ConfiguracionDesempeno.actual().dias_conservar_videos, 14)
        self.assertEqual(self.c.patch('/api/desempeno/configuracion/', {'dias_conservar_videos': 999}, format='json').status_code, 400)

    def test_un_video_borrado_avisa_y_tambien_se_limpian_las_referencias(self):
        hoy = timezone.localdate()
        t, v, _ = self._con_video(fecha_completada=hoy - timedelta(days=30))
        ref = ReferenciaArchivo.objects.create(tarea=t, archivo=video('ref.mp4'), nombre_original='ref.mp4', tipo='video/mp4', tamano=500)
        self.assertEqual(servicios.purgar_videos(hoy)[0], 2)
        self.como(self.erlin)
        r = self.c.get(f'/api/desempeno/evidencias/{v.pk}/archivo/')
        self.assertEqual(r.status_code, 410)
        self.assertIn('se borró', r.json()['detail'])
        self.assertEqual(self.c.get(f'/api/desempeno/referencias/{ref.pk}/archivo/').status_code, 410)
        ficha = self.c.get(f'{T}{t.id}/').json()
        self.assertTrue(all(e['purgado'] for e in ficha['evidencias'] if e['es_video']))


class EquipoVeSuTrabajoTests(Base):
    """«Mi equipo» muestra las tareas de toda la gente a cargo y también las propias del encargado."""

    def test_el_encargado_ve_las_suyas_y_las_de_su_equipo_juntas(self):
        mia = self.tarea(self.vladi)
        de_erlin = self.tarea(self.erlin)
        ajena = self.tarea(self.dev)                                # de otra área: no es de su equipo
        self.como(self.vladi)
        ids = {t['id'] for t in self._lista('/api/desempeno/tareas/?ambito=equipo')}
        self.assertIn(mia.id, ids)
        self.assertIn(de_erlin.id, ids)
        self.assertNotIn(ajena.id, ids)

    def _lista(self, url):
        r = self.c.get(url).json()
        return r['results'] if isinstance(r, dict) else r

    def test_mis_tareas_sigue_mostrando_solo_las_mias(self):
        mia, de_erlin = self.tarea(self.vladi), self.tarea(self.erlin)
        self.como(self.vladi)
        ids = {t['id'] for t in self._lista('/api/desempeno/tareas/?ambito=mias')}
        self.assertEqual(ids, {mia.id})

    def test_un_colaborador_sin_equipo_solo_ve_las_suyas(self):
        mia, otra = self.tarea(self.erlin), self.tarea(self.dev)
        self.como(self.erlin)
        ids = {t['id'] for t in self._lista('/api/desempeno/tareas/?ambito=equipo')}
        self.assertEqual(ids, {mia.id})
