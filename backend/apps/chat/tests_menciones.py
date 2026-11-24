"""Menciones con @usuario en el chat: solo participantes, aviso a quien se menciona, sin revelar nada a quien no está en la conversación."""
from django.contrib.auth.models import User

from apps.desempeno.models import Notificacion
from . import servicios
from .models import Conversacion, Mensaje
from .tests import BASE, Base


class MencionesTests(Base):
    def setUp(self):
        super().setUp()
        self.grupo = Conversacion.objects.create(tipo=Conversacion.GRUPO, nombre='Marketing', creado_por=self.ana)
        self.grupo.miembros.set([self.ana, self.luis])                                # Eva NO está en el grupo

    def enviar(self, quien, conv, texto):
        return self.como(quien).post(f'{BASE}/conversaciones/{conv}/mensajes/', {'texto': texto}, format='json')

    def avisos(self, quien):
        return Notificacion.objects.filter(destinatario=quien, tipo='MENCION')

    def test_mencionar_a_un_miembro_le_llega_el_aviso_y_el_mensaje_lo_marca(self):
        r = self.enviar(self.ana, self.grupo.id, 'Hola @luis, ¿puedes revisar esto?')
        self.assertEqual(r.status_code, 201)
        self.assertEqual([(m['username'], m['nombre']) for m in r.data['menciones']], [('luis', 'Luis')])
        n = self.avisos(self.luis).get()
        self.assertIn('Ana Pérez te mencionó en Marketing', n.titulo)
        self.assertIn('puedes revisar', n.mensaje)
        self.assertFalse(self.avisos(self.ana).exists())                                # el autor no se avisa a sí mismo

    def test_quien_no_esta_en_el_grupo_no_recibe_aviso_ni_se_revela(self):
        r = self.enviar(self.ana, self.grupo.id, 'cc @eva por si acaso')
        self.assertEqual(r.data['menciones'], [])
        self.assertFalse(self.avisos(self.eva).exists())

    def test_no_distingue_mayusculas_ni_puntuacion_final_y_no_repite(self):
        r = self.enviar(self.ana, self.grupo.id, '@LUIS. @luis, @Luis!')
        self.assertEqual(len(r.data['menciones']), 1)
        self.assertEqual(self.avisos(self.luis).count(), 1)

    def test_un_correo_no_es_una_mencion(self):
        r = self.enviar(self.ana, self.grupo.id, 'escríbeme a ana@luis.com')
        self.assertEqual(r.data['menciones'], [])

    def test_en_la_sala_de_la_empresa_se_puede_mencionar_a_cualquiera(self):
        r = self.enviar(self.ana, self.sala.id, '@eva y @luis, reunión a las 3')
        self.assertEqual(sorted(m['username'] for m in r.data['menciones']), ['eva', 'luis'])
        self.assertTrue(self.avisos(self.eva).exists() and self.avisos(self.luis).exists())

    def test_en_un_chat_privado_solo_cuenta_la_otra_persona(self):
        conv = self.privado(self.ana, self.luis)
        r = self.enviar(self.ana, conv, '@luis @eva')
        self.assertEqual([m['username'] for m in r.data['menciones']], ['luis'])

    def test_un_mensaje_borrado_no_muestra_a_quien_mencionaba(self):
        mid = self.enviar(self.ana, self.grupo.id, '@luis hola').data['id']
        self.como(self.ana).delete(f'{BASE}/mensajes/{mid}/')
        lista = self.como(self.luis).get(f'{BASE}/conversaciones/{self.grupo.id}/mensajes/').data['mensajes']
        self.assertEqual(next(m for m in lista if m['id'] == mid)['menciones'], [])

    def test_los_mensajes_sin_menciones_siguen_igual(self):
        r = self.enviar(self.ana, self.grupo.id, 'hola a todos')
        self.assertEqual((r.status_code, r.data['menciones']), (201, []))
        self.assertFalse(Notificacion.objects.filter(tipo='MENCION').exists())

    def test_el_listado_de_personas_trae_el_usuario_para_sugerir(self):
        gente = self.como(self.ana).get(f'{BASE}/personas/').data
        self.assertTrue(all('usuario' in p for p in gente))
        self.assertIn('luis', {p['usuario'] for p in gente})
