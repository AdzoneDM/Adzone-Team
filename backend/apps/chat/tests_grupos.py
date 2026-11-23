"""Grupos de chat por área (solo las jefaturas los administran) y archivos adjuntos."""
import io
import shutil
import tempfile

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image

from apps.core.models import Departamento
from apps.organizacion.models import PuestoDeTrabajo

from . import servicios
from .models import Conversacion, Mensaje
from .tests import BASE, Base

MEDIA = tempfile.mkdtemp()


def imagen(nombre='foto.png'):
    b = io.BytesIO()
    Image.new('RGB', (12, 12), 'blue').save(b, 'PNG')
    return SimpleUploadedFile(nombre, b.getvalue(), content_type='image/png')


def pdf(nombre='informe.pdf', tam=100):
    return SimpleUploadedFile(nombre, b'%PDF-1.4 ' + b'0' * tam, content_type='application/pdf')


@override_settings(MEDIA_ROOT=MEDIA)
class GruposTests(Base):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        super().setUp()
        self.gerente = User.objects.create_user('gerente', password='x', first_name='Gerente')
        self.gerente.groups.add(Group.objects.get(name='Gerente de Departamento'))
        self.jefe2 = User.objects.create_user('jefe2', password='x', first_name='Jefa')
        self.jefe2.groups.add(Group.objects.get(name='Gerente de Departamento'))
        self.depto = Departamento.objects.get(nombre='Diseño')
        self.otro_depto = Departamento.objects.create(nombre='Ventas')
        self.vende = User.objects.create_user('vende', password='x', first_name='Vende')
        self.vende.perfil.puesto_trabajo = PuestoDeTrabajo.objects.create(nombre='Vendedor', departamento=self.otro_depto)
        self.vende.perfil.save()

    def crear(self, quien, **datos):
        return self.como(quien).post(f'{BASE}/grupos/', datos, format='json')

    # ---- crear: solo jefaturas
    def test_una_jefatura_crea_un_grupo_con_las_personas_que_elige(self):
        r = self.crear(self.gerente, nombre='Equipo de campaña', miembros=[self.ana.id, self.luis.id])
        self.assertEqual(r.status_code, 201, r.content)
        c = Conversacion.objects.get(pk=r.data['id'])
        self.assertEqual({u.pk for u in c.miembros.all()}, {self.gerente.id, self.ana.id, self.luis.id})
        self.assertEqual(r.data['titulo'], 'Equipo de campaña')
        self.assertTrue(r.data['grupo']['puede_gestionar'])

    def test_un_grupo_por_area_incluye_a_todo_su_personal(self):
        r = self.crear(self.gerente, nombre='Diseño', departamento=self.depto.id)
        c = Conversacion.objects.get(pk=r.data['id'])
        self.assertIn(self.ana, c.miembros.all())            # Ana es de Diseño
        self.assertNotIn(self.vende, c.miembros.all())       # Vende es de Ventas
        self.assertEqual(c.departamento, self.depto)

    def test_el_personal_comun_no_puede_crear_grupos_ni_forzando_la_ruta(self):
        for quien in (self.ana, self.luis, self.vende):
            self.assertEqual(self.crear(quien, nombre='Mi grupo', miembros=[self.luis.id]).status_code, 403)
        self.assertEqual(Conversacion.objects.filter(tipo='GRUPO').count(), 0)
        self.assertFalse(self.como(self.ana).get(f'{BASE}/conversaciones/').data['puede_crear_grupos'])
        self.assertTrue(self.como(self.gerente).get(f'{BASE}/conversaciones/').data['puede_crear_grupos'])
        self.assertTrue(self.como(self.dir).get(f'{BASE}/conversaciones/').data['puede_crear_grupos'])

    def test_validaciones_al_crear(self):
        self.assertEqual(self.crear(self.gerente, nombre='ab', miembros=[self.ana.id]).status_code, 400)
        self.assertEqual(self.crear(self.gerente, nombre='Solo yo', miembros=[]).status_code, 400)
        self.eva.is_active = False
        self.eva.save()
        self.assertEqual(self.crear(self.gerente, nombre='Con inactiva', miembros=[self.eva.id]).status_code, 400)

    # ---- ver y escribir: solo participantes
    def grupo(self, miembros=None):
        return self.crear(self.gerente, nombre='Tecnología', miembros=miembros or [self.ana.id, self.luis.id]).data['id']

    def test_solo_los_participantes_ven_y_escriben(self):
        g = self.grupo()
        self.assertEqual(self.enviar(self.ana, g, 'hola grupo').status_code, 201)
        self.assertIn(g, [x['id'] for x in self.como(self.luis).get(f'{BASE}/conversaciones/').data['conversaciones']])
        for fuera in (self.eva, self.vende, self.dir):
            c = self.como(fuera)
            self.assertEqual(c.get(f'{BASE}/conversaciones/{g}/mensajes/').status_code, 404)
            self.assertEqual(self.enviar(fuera, g, 'me cuelo').status_code, 404)
            self.assertNotIn(g, [x['id'] for x in c.get(f'{BASE}/conversaciones/').data['conversaciones']])

    def test_un_participante_comun_ve_los_datos_pero_no_puede_editar_ni_borrar(self):
        g = self.grupo()
        c = self.como(self.ana)
        datos = c.get(f'{BASE}/grupos/{g}/').data['grupo']
        self.assertEqual((datos['nombre'], datos['puede_gestionar'], datos['n_miembros']), ('Tecnología', False, 3))
        self.assertEqual(c.patch(f'{BASE}/grupos/{g}/', {'nombre': 'Otro nombre'}, format='json').status_code, 403)
        self.assertEqual(c.patch(f'{BASE}/grupos/{g}/', {'miembros': [self.ana.id]}, format='json').status_code, 403)
        self.assertEqual(c.delete(f'{BASE}/grupos/{g}/').status_code, 403)
        self.assertTrue(Conversacion.objects.filter(pk=g, nombre='Tecnología').exists())

    def test_otra_jefatura_no_toca_el_grupo_de_su_colega_pero_direccion_si(self):
        g = self.grupo(miembros=[self.ana.id, self.jefe2.id])
        c = self.como(self.jefe2)                         # participa y tiene el permiso, pero no lo creó
        self.assertEqual(c.patch(f'{BASE}/grupos/{g}/', {'nombre': 'Renombrado'}, format='json').status_code, 403)
        self.assertEqual(c.delete(f'{BASE}/grupos/{g}/').status_code, 403)
        d = self.como(self.dir)                           # Dirección administra todos, aunque no participe
        self.assertEqual(d.patch(f'{BASE}/grupos/{g}/', {'nombre': 'Por Dirección'}, format='json').status_code, 200)
        self.assertEqual(Conversacion.objects.get(pk=g).nombre, 'Por Dirección')

    def test_la_jefatura_edita_agrega_y_quita_personas(self):
        g = self.grupo()
        c = self.como(self.gerente)
        r = c.patch(f'{BASE}/grupos/{g}/', {'nombre': 'Tecnología y soporte', 'miembros': [self.ana.id, self.eva.id]}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual({u.pk for u in Conversacion.objects.get(pk=g).miembros.all()}, {self.gerente.id, self.ana.id, self.eva.id})
        self.assertEqual(self.como(self.luis).get(f'{BASE}/conversaciones/{g}/mensajes/').status_code, 404)    # quien se quitó ya no entra
        self.assertEqual(self.como(self.eva).get(f'{BASE}/conversaciones/{g}/mensajes/').status_code, 200)
        self.assertEqual(c.patch(f'{BASE}/grupos/{g}/', {'miembros': []}, format='json').status_code, 400)

    def test_eliminar_un_grupo_borra_sus_mensajes_y_archivos(self):
        g = self.grupo()
        self.como(self.ana).post(f'{BASE}/conversaciones/{g}/mensajes/', {'texto': 'adjunto', 'archivo': pdf()}, format='multipart')
        m = Mensaje.objects.get(conversacion_id=g)
        ruta = m.archivo.path
        self.assertEqual(self.como(self.gerente).delete(f'{BASE}/grupos/{g}/').status_code, 204)
        self.assertFalse(Conversacion.objects.filter(pk=g).exists())
        self.assertFalse(Mensaje.objects.filter(pk=m.pk).exists())
        import os
        self.assertFalse(os.path.exists(ruta))

    def test_quien_administra_el_grupo_modera_sus_mensajes(self):
        g = self.grupo()
        mid = self.enviar(self.ana, g, 'inapropiado').data['id']
        self.assertEqual(self.como(self.luis).delete(f'{BASE}/mensajes/{mid}/').status_code, 403)
        self.assertEqual(self.como(self.gerente).delete(f'{BASE}/mensajes/{mid}/').status_code, 200)

    # ---- archivos adjuntos
    def test_envia_imagen_y_documento_en_un_privado_y_en_un_grupo(self):
        priv, g = self.privado(self.ana, self.luis), self.grupo()
        c = self.como(self.ana)
        for conv in (priv, g):
            r = c.post(f'{BASE}/conversaciones/{conv}/mensajes/', {'archivo': imagen()}, format='multipart')
            self.assertEqual(r.status_code, 201, r.content)
            self.assertEqual((r.data['archivo']['nombre'], r.data['archivo']['es_imagen'], r.data['texto']), ('foto.png', True, ''))
            r = c.post(f'{BASE}/conversaciones/{conv}/mensajes/', {'texto': 'el informe', 'archivo': pdf()}, format='multipart')
            self.assertEqual((r.status_code, r.data['archivo']['es_imagen'], r.data['texto']), (201, False, 'el informe'))
        fila = next(x for x in self.como(self.luis).get(f'{BASE}/conversaciones/').data['conversaciones'] if x['id'] == priv)
        self.assertEqual(fila['ultimo_texto'], 'el informe')

    def test_un_mensaje_sin_texto_ni_archivo_se_rechaza(self):
        self.assertEqual(self.enviar(self.ana, self.sala.id, '').status_code, 400)

    def test_rechaza_ejecutables_imagenes_falsas_y_archivos_enormes(self):
        c = self.como(self.ana)
        url = f'{BASE}/conversaciones/{self.sala.id}/mensajes/'
        malo = SimpleUploadedFile('programa.exe', b'MZ', content_type='application/octet-stream')
        falsa = SimpleUploadedFile('rota.png', b'no soy imagen', content_type='image/png')
        grande = SimpleUploadedFile('enorme.pdf', b'0' * (15 * 1024 * 1024 + 1), content_type='application/pdf')
        for f in (malo, falsa, grande):
            self.assertEqual(c.post(url, {'texto': 'x', 'archivo': f}, format='multipart').status_code, 400)
        self.assertEqual(Mensaje.objects.count(), 0)

    def test_solo_los_participantes_descargan_y_borrar_el_mensaje_borra_el_archivo(self):
        g = self.grupo()
        mid = self.como(self.ana).post(f'{BASE}/conversaciones/{g}/mensajes/', {'archivo': pdf('plan.pdf')}, format='multipart').data['id']
        self.assertEqual(self.como(self.luis).get(f'{BASE}/mensajes/{mid}/archivo/').status_code, 200)
        self.assertIn('attachment', self.como(self.luis).get(f'{BASE}/mensajes/{mid}/archivo/?descargar=1')['Content-Disposition'])
        for fuera in (self.eva, self.dir):
            self.assertEqual(self.como(fuera).get(f'{BASE}/mensajes/{mid}/archivo/').status_code, 404)
        import os
        ruta = Mensaje.objects.get(pk=mid).archivo.path
        self.como(self.ana).delete(f'{BASE}/mensajes/{mid}/')
        self.assertFalse(os.path.exists(ruta))
        self.assertEqual(self.como(self.luis).get(f'{BASE}/mensajes/{mid}/archivo/').status_code, 404)


def video(nombre='clip.mp4', tam=1500):
    return SimpleUploadedFile(nombre, b'\x00\x00\x00\x18ftypmp42' + bytes(range(256)) * (tam // 256), content_type='video/mp4')


@override_settings(MEDIA_ROOT=MEDIA)
class VideosEnElChatTests(Base):
    def setUp(self):
        super().setUp()
        self.priv = self.privado(self.ana, self.luis)

    def enviar_video(self, quien, conv, archivo=None, texto=''):
        return self.como(quien).post(f'{BASE}/conversaciones/{conv}/mensajes/', {'texto': texto, 'archivo': archivo or video()}, format='multipart')

    def test_se_envia_un_video_por_un_chat_privado_y_por_la_sala(self):
        for conv in (self.priv, self.sala.id):
            r = self.enviar_video(self.ana, conv, texto='mira')
            self.assertEqual(r.status_code, 201, r.content)
            self.assertEqual((r.data['archivo']['es_video'], r.data['archivo']['es_imagen'], r.data['texto']), (True, False, 'mira'))

    def test_formatos_del_celular(self):
        for nombre in ('a.mov', 'b.webm', 'c.m4v', 'd.3gp'):
            self.assertEqual(self.enviar_video(self.ana, self.sala.id, video(nombre)).status_code, 201, nombre)

    @override_settings(EVIDENCIA_VIDEO_MAX_MB=1)
    def test_un_video_pesado_se_rechaza_con_el_limite_de_videos(self):
        r = self.enviar_video(self.ana, self.sala.id, video('largo.mp4', 2 * 1024 * 1024))
        self.assertEqual(r.status_code, 400)
        self.assertIn('1 MB', str(r.json()))
        self.assertEqual(Mensaje.objects.count(), 0)

    def test_el_video_se_reproduce_por_tramos_y_solo_lo_ven_los_participantes(self):
        mid = self.enviar_video(self.ana, self.priv).data['id']
        c = self.como(self.luis)
        total = int(c.get(f'{BASE}/mensajes/{mid}/archivo/')['Content-Length'])
        parte = c.get(f'{BASE}/mensajes/{mid}/archivo/', HTTP_RANGE='bytes=0-9')
        self.assertEqual((parte.status_code, parte['Content-Range']), (206, f'bytes 0-9/{total}'))
        self.assertEqual(self.como(self.eva).get(f'{BASE}/mensajes/{mid}/archivo/').status_code, 404)

    def test_los_videos_viejos_se_borran_solos_y_lo_demas_se_queda(self):
        from datetime import timedelta
        from django.utils import timezone
        mv = Mensaje.objects.get(pk=self.enviar_video(self.ana, self.priv).data['id'])
        mf = Mensaje.objects.get(pk=self.como(self.ana).post(f'{BASE}/conversaciones/{self.priv}/mensajes/', {'archivo': pdf()}, format='multipart').data['id'])
        import os
        ruta = mv.archivo.path
        Mensaje.objects.filter(pk__in=[mv.pk, mf.pk]).update(creado=timezone.now() - timedelta(days=30))
        self.assertEqual(servicios.purgar_videos_del_chat()[0], 1)
        mv.refresh_from_db(), mf.refresh_from_db()
        self.assertTrue(mv.archivo_purgado)
        self.assertFalse(os.path.exists(ruta))
        self.assertFalse(mf.archivo_purgado)                                           # los documentos no se borran
        visto = next(m for m in self.como(self.luis).get(f'{BASE}/conversaciones/{self.priv}/mensajes/').data['mensajes'] if m['id'] == mv.pk)
        self.assertTrue(visto['archivo']['purgado'])
        self.assertEqual(self.como(self.luis).get(f'{BASE}/mensajes/{mv.pk}/archivo/').status_code, 410)

    def test_un_video_reciente_no_se_borra(self):
        self.enviar_video(self.ana, self.priv)
        self.assertEqual(servicios.purgar_videos_del_chat(), (0, 0))
