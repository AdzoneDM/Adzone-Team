from django.contrib.auth.models import Group, User
from django.test import TestCase
from rest_framework.test import APIClient

from . import servicios
from .models import Mensaje


class ChatTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', password='x', first_name='Ana', last_name='Pérez')
        self.luis = User.objects.create_user('luis', password='x')
        self.dir = User.objects.create_user('dir', password='x')
        self.dir.groups.add(Group.objects.get_or_create(name='Administrador')[0])

    def como(self, u):
        c = APIClient()
        c.force_authenticate(u)
        return c

    def test_exige_sesion(self):
        self.assertIn(APIClient().get('/api/chat/mensajes/').status_code, (401, 403))

    def test_enviar_y_leer(self):
        r = self.como(self.ana).post('/api/chat/mensajes/', {'texto': '  Hola equipo  '}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['texto'], 'Hola equipo')
        self.assertEqual(r.data['autor_nombre'], 'Ana Pérez')
        lista = self.como(self.luis).get('/api/chat/mensajes/').data
        self.assertEqual([m['texto'] for m in lista['mensajes']], ['Hola equipo'])

    def test_validaciones(self):
        c = self.como(self.ana)
        self.assertEqual(c.post('/api/chat/mensajes/', {'texto': '   '}, format='json').status_code, 400)
        self.assertEqual(c.post('/api/chat/mensajes/', {'texto': 'x' * 2001}, format='json').status_code, 400)
        self.assertEqual(Mensaje.objects.count(), 0)

    def test_limite_de_ritmo(self):
        c = self.como(self.ana)
        for i in range(servicios.MAX_POR_MINUTO):
            self.assertEqual(c.post('/api/chat/mensajes/', {'texto': f'm{i}'}, format='json').status_code, 201)
        self.assertEqual(c.post('/api/chat/mensajes/', {'texto': 'otro'}, format='json').status_code, 429)
        # el límite es por persona
        self.assertEqual(self.como(self.luis).post('/api/chat/mensajes/', {'texto': 'hola'}, format='json').status_code, 201)

    def test_paginacion_y_nuevos(self):
        for i in range(1, 8):
            Mensaje.objects.create(autor=self.ana, texto=f'm{i}')
        c = self.como(self.luis)
        p1 = c.get('/api/chat/mensajes/?limite=3').data
        self.assertEqual([m['texto'] for m in p1['mensajes']], ['m5', 'm6', 'm7'])
        self.assertTrue(p1['hay_mas'])
        p2 = c.get(f"/api/chat/mensajes/?limite=3&antes={p1['mensajes'][0]['id']}").data
        self.assertEqual([m['texto'] for m in p2['mensajes']], ['m2', 'm3', 'm4'])
        p3 = c.get(f"/api/chat/mensajes/?limite=3&antes={p2['mensajes'][0]['id']}").data
        self.assertEqual([m['texto'] for m in p3['mensajes']], ['m1'])
        self.assertFalse(p3['hay_mas'])
        nuevos = c.get(f"/api/chat/mensajes/?despues={p1['mensajes'][1]['id']}").data
        self.assertEqual([m['texto'] for m in nuevos['mensajes']], ['m7'])
        self.assertEqual(c.get('/api/chat/mensajes/?despues=abc&limite=zz').status_code, 200)

    def test_borrar(self):
        m = Mensaje.objects.create(autor=self.ana, texto='secreto')
        self.assertEqual(self.como(self.luis).delete(f'/api/chat/mensajes/{m.id}/').status_code, 403)
        self.assertEqual(self.como(self.ana).delete(f'/api/chat/mensajes/{m.id}/').status_code, 200)
        m.refresh_from_db()
        self.assertTrue(m.eliminado)
        visto = self.como(self.luis).get('/api/chat/mensajes/').data['mensajes'][0]
        self.assertEqual((visto['eliminado'], visto['texto']), (True, ''))
        # Dirección modera cualquier mensaje
        m2 = Mensaje.objects.create(autor=self.ana, texto='inapropiado')
        self.assertTrue(self.como(self.dir).get('/api/chat/mensajes/').data['mensajes'][-1]['puede_borrar'])
        self.assertEqual(self.como(self.dir).delete(f'/api/chat/mensajes/{m2.id}/').status_code, 200)
        self.assertEqual(self.como(self.dir).delete('/api/chat/mensajes/99999/').status_code, 404)

    def test_no_leidos(self):
        c = self.como(self.luis)
        a = Mensaje.objects.create(autor=self.ana, texto='uno')
        b = Mensaje.objects.create(autor=self.ana, texto='dos')
        self.assertEqual(c.get('/api/chat/resumen/').data['no_leidos'], 2)
        self.assertEqual(c.post('/api/chat/leido/', {'hasta': a.id}, format='json').data['no_leidos'], 1)
        self.assertEqual(c.post('/api/chat/leido/', {'hasta': 0}, format='json').data['no_leidos'], 1)  # nunca retrocede
        self.assertEqual(c.post('/api/chat/leido/', {'hasta': 10**9}, format='json').data['no_leidos'], 0)
        # los míos no cuentan, y enviar marca todo como leído
        self.assertEqual(self.como(self.ana).get('/api/chat/resumen/').data['no_leidos'], 0)
        c.post('/api/chat/mensajes/', {'texto': 'hola'}, format='json')
        self.assertEqual(c.get('/api/chat/resumen/').data['no_leidos'], 0)
        self.assertEqual(self.como(self.ana).get('/api/chat/resumen/').data['no_leidos'], 1)
