"""Quién vio cada mensaje (con fecha y hora), quién lo tiene pendiente y quién abrió el archivo, como en WhatsApp pero con nombres."""
import shutil
import tempfile

from django.contrib.auth.models import Group, User
from django.test import override_settings

from .models import Conversacion, Mensaje, VistaMensaje
from .tests import BASE, Base
from .tests_grupos import pdf

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA)
class VistosTests(Base):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        super().setUp()
        self.jefa = User.objects.create_user('jefa', password='x', first_name='Jefa')
        self.jefa.groups.add(Group.objects.get(name='Gerente de Departamento'))
        r = self.como(self.jefa).post(f'{BASE}/grupos/', {'nombre': 'Campaña', 'miembros': [self.ana.id, self.luis.id, self.eva.id]}, format='json')
        self.grupo = r.data['id']

    def vistos(self, quien, mid):
        return self.como(quien).get(f'{BASE}/mensajes/{mid}/vistos/')

    def test_entregado_visto_y_pendiente_con_nombres_y_porcentaje(self):
        mid = self.enviar(self.jefa, self.grupo, 'Instrucciones del lunes').data['id']
        # Luis abre la app: le llega (entregado) pero no lo ha visto
        self.como(self.luis).get(f'{BASE}/conversaciones/{self.grupo}/mensajes/')
        # Ana lo ve
        self.como(self.ana).post(f'{BASE}/conversaciones/{self.grupo}/leido/', {'hasta': mid}, format='json')
        d = self.vistos(self.jefa, mid).data
        self.assertEqual((d['integrantes'], len(d['vistos']), len(d['pendientes']), d['porcentaje']), (3, 1, 2, 33))
        self.assertEqual(d['vistos'][0]['nombre'], 'Ana Pérez')
        self.assertIsNotNone(d['vistos'][0]['visto'])
        estados = {p['nombre']: p['estado'] for p in d['pendientes']}
        self.assertEqual(estados, {'Luis': 'ENTREGADO', 'Eva': 'ENVIADO'})
        # Volver a leer no duplica ni cambia la hora
        hora = VistaMensaje.objects.get(mensaje_id=mid, usuario=self.ana).visto
        self.como(self.ana).post(f'{BASE}/conversaciones/{self.grupo}/leido/', {'hasta': mid}, format='json')
        self.assertEqual(VistaMensaje.objects.filter(mensaje_id=mid, usuario=self.ana).count(), 1)
        self.assertEqual(VistaMensaje.objects.get(mensaje_id=mid, usuario=self.ana).visto, hora)

    def test_archivo_abierto(self):
        r = self.como(self.jefa).post(f'{BASE}/conversaciones/{self.grupo}/mensajes/', {'archivo': pdf()}, format='multipart')
        mid = r.data['id']
        self.como(self.luis).post(f'{BASE}/mensajes/{mid}/abierto/')
        self.como(self.eva).get(f'{BASE}/mensajes/{mid}/archivo/?descargar=1')
        d = self.vistos(self.jefa, mid).data
        self.assertTrue(d['tiene_archivo'])
        self.assertEqual(d['abiertos'], 2)
        self.assertEqual({v['nombre'] for v in d['vistos'] if v['estado'] == 'ABIERTO'}, {'Luis', 'Eva'})

    def test_solo_quien_lo_envio_quien_administra_el_grupo_o_direccion(self):
        mid = self.enviar(self.ana, self.grupo, 'Listo el arte').data['id']
        self.assertEqual(self.vistos(self.ana, mid).status_code, 200)
        self.assertEqual(self.vistos(self.jefa, mid).status_code, 200)     # administra el grupo
        self.assertEqual(self.vistos(self.luis, mid).status_code, 403)
        self.assertIn(self.vistos(self.vende_o_dir(), mid).status_code, (200, 404))
        r = self.como(self.ana).get(f'{BASE}/conversaciones/{self.grupo}/mensajes/')
        self.assertTrue(r.data['mensajes'][-1]['puede_ver_vistos'])
        self.assertFalse(self.como(self.luis).get(f'{BASE}/conversaciones/{self.grupo}/mensajes/').data['mensajes'][-1]['puede_ver_vistos'])

    def vende_o_dir(self):
        return self.dir

    def test_mensajes_viejos_cuentan_como_vistos_sin_hora(self):
        mid = self.enviar(self.jefa, self.grupo, 'Viejo').data['id']
        VistaMensaje.objects.all().delete()
        from .models import Lectura
        Lectura.objects.update_or_create(usuario=self.eva, conversacion=Conversacion.objects.get(pk=self.grupo), defaults={'ultimo_leido': mid})
        d = self.vistos(self.jefa, mid).data
        self.assertEqual([(v['nombre'], v['sin_hora']) for v in d['vistos']], [('Eva', True)])
        self.assertEqual(Mensaje.objects.get(pk=mid).vistas.count(), 0)
