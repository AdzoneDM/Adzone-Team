"""Reacciones rápidas y reenviar mensajes (como en WhatsApp), siempre dentro de las conversaciones de cada persona."""
from django.core.files.uploadedfile import SimpleUploadedFile

from .models import Conversacion, Mensaje, Reaccion
from .tests import BASE, Base


class ReaccionesTests(Base):
    def setUp(self):
        super().setUp()
        self.grupo = Conversacion.objects.create(tipo=Conversacion.GRUPO, nombre='Marketing', creado_por=self.ana)
        self.grupo.miembros.set([self.ana, self.luis])
        self.otro = Conversacion.objects.create(tipo=Conversacion.GRUPO, nombre='Ventas', creado_por=self.eva)
        self.otro.miembros.set([self.eva, self.luis])
        self.mio = Conversacion.objects.create(tipo=Conversacion.GRUPO, nombre='Diseño', creado_por=self.ana)
        self.mio.miembros.set([self.ana, self.eva])

    def enviar(self, quien, conv, texto, **extra):
        return self.como(quien).post(f'{BASE}/conversaciones/{conv.pk}/mensajes/', {'texto': texto, **extra}, format='json').data

    def reaccionar(self, quien, mensaje, emoji):
        return self.como(quien).post(f'{BASE}/mensajes/{mensaje}/reaccion/', {'emoji': emoji}, format='json')

    def test_poner_cambiar_y_quitar_reaccion(self):
        m = self.enviar(self.ana, self.grupo, 'Arte listo para revisión')['id']
        r = self.reaccionar(self.luis, m, '👍')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['reacciones'], [{'emoji': '👍', 'n': 1, 'mia': True, 'nombres': ['Tú']}])
        self.reaccionar(self.ana, m, '👍')
        self.reaccionar(self.luis, m, '✅')   # cambia la suya: una por persona
        self.assertEqual(Reaccion.objects.filter(mensaje_id=m).count(), 2)
        self.reaccionar(self.luis, m, '✅')   # el mismo emoji la quita
        self.assertEqual(list(Reaccion.objects.filter(mensaje_id=m).values_list('usuario_id', flat=True)), [self.ana.id])

    def test_la_reaccion_llega_en_la_consulta_periodica(self):
        m = self.enviar(self.ana, self.grupo, 'Hola')['id']
        self.enviar(self.ana, self.grupo, 'Otro')
        ultimo = Mensaje.objects.filter(conversacion=self.grupo).latest('id').id
        self.reaccionar(self.luis, m, '🙏')
        nuevos = self.como(self.ana).get(f'{BASE}/conversaciones/{self.grupo.pk}/mensajes/?despues={ultimo}').data['mensajes']
        self.assertEqual([x['id'] for x in nuevos], [m])
        self.assertEqual(nuevos[0]['reacciones'][0]['nombres'], [self.luis.get_full_name() or self.luis.username])

    def test_no_se_reacciona_fuera_de_tus_conversaciones_ni_con_cualquier_cosa(self):
        ajeno = self.enviar(self.eva, self.otro, 'Solo Ventas')['id']
        self.assertEqual(self.reaccionar(self.ana, ajeno, '👍').status_code, 404)
        m = self.enviar(self.ana, self.grupo, 'x')['id']
        self.assertEqual(self.reaccionar(self.luis, m, '<b>').status_code, 400)

    def test_reenviar_texto_y_archivo(self):
        archivo = SimpleUploadedFile('brief.txt', b'contenido', content_type='text/plain')
        orig = self.como(self.ana).post(f'{BASE}/conversaciones/{self.grupo.pk}/mensajes/', {'texto': 'Brief', 'archivo': archivo}, format='multipart').data
        r = self.como(self.ana).post(f'{BASE}/mensajes/{orig["id"]}/reenviar/', {'conversaciones': [self.mio.pk]}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        copia = Mensaje.objects.get(conversacion=self.mio)
        self.assertTrue(copia.reenviado)
        self.assertEqual((copia.texto, copia.archivo_nombre), ('Brief', 'brief.txt'))
        self.assertNotEqual(copia.archivo.name, Mensaje.objects.get(pk=orig['id']).archivo.name)   # cada uno con su archivo
        with copia.archivo.open('rb') as f:
            self.assertEqual(f.read(), b'contenido')
        self.assertTrue(self.como(self.eva).get(f'{BASE}/conversaciones/{self.mio.pk}/mensajes/').data['mensajes'][0]['reenviado'])

    def test_no_se_reenvia_a_una_conversacion_ajena(self):
        m = self.enviar(self.ana, self.grupo, 'Interno')['id']
        r = self.como(self.ana).post(f'{BASE}/mensajes/{m}/reenviar/', {'conversaciones': [self.otro.pk]}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Mensaje.objects.filter(conversacion=self.otro, texto='Interno').exists())
        ajeno = self.enviar(self.eva, self.otro, 'Secreto')['id']
        self.assertEqual(self.como(self.ana).post(f'{BASE}/mensajes/{ajeno}/reenviar/', {'conversaciones': [self.mio.pk]}, format='json').status_code, 404)

    def test_el_borrado_tambien_llega_en_la_consulta_periodica(self):
        m = self.enviar(self.ana, self.grupo, 'Me equivoqué')['id']
        ultimo = self.enviar(self.ana, self.grupo, 'otro')['id']
        self.como(self.ana).delete(f'{BASE}/mensajes/{m}/')
        nuevos = self.como(self.luis).get(f'{BASE}/conversaciones/{self.grupo.pk}/mensajes/?despues={ultimo}').data['mensajes']
        self.assertTrue(next(x for x in nuevos if x['id'] == m)['eliminado'])
