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
