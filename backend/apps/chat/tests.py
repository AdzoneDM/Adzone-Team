from django.contrib.auth.models import Group, User
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Departamento
from apps.organizacion.models import PuestoDeTrabajo

from . import servicios
from .models import Conversacion, Mensaje

BASE = '/api/chat'


class Base(TestCase):
    def setUp(self):
        depto = Departamento.objects.create(nombre='Diseño')
        self.ana = User.objects.create_user('ana', password='x', first_name='Ana', last_name='Pérez')
        self.ana.perfil.puesto_trabajo = PuestoDeTrabajo.objects.create(nombre='Diseñadora', departamento=depto)
        self.ana.perfil.save()
        self.luis = User.objects.create_user('luis', password='x', first_name='Luis')
        self.eva = User.objects.create_user('eva', password='x', first_name='Eva')
        self.dir = User.objects.create_user('dir', password='x', first_name='Dirección')
        self.dir.groups.add(Group.objects.get_or_create(name='Administrador')[0])
        self.sala = servicios.sala_global()

    def como(self, u):
        c = APIClient()
        c.force_authenticate(u)
        return c

    def enviar(self, u, conv, texto):
        return self.como(u).post(f'{BASE}/conversaciones/{conv}/mensajes/', {'texto': texto}, format='json')

    def privado(self, u, otro):
        return self.como(u).post(f'{BASE}/conversaciones/', {'persona': otro.id}, format='json').data['id']


class SalaGlobalTests(Base):
    def test_exige_sesion(self):
        self.assertIn(APIClient().get(f'{BASE}/conversaciones/').status_code, (401, 403))

    def test_enviar_y_leer(self):
        r = self.enviar(self.ana, self.sala.id, '  Hola equipo  ')
        self.assertEqual(r.status_code, 201)
        self.assertEqual((r.data['texto'], r.data['autor_nombre']), ('Hola equipo', 'Ana Pérez'))
        lista = self.como(self.luis).get(f'{BASE}/conversaciones/{self.sala.id}/mensajes/').data
        self.assertEqual([m['texto'] for m in lista['mensajes']], ['Hola equipo'])

    def test_validaciones(self):
        self.assertEqual(self.enviar(self.ana, self.sala.id, '   ').status_code, 400)
        self.assertEqual(self.enviar(self.ana, self.sala.id, 'x' * 2001).status_code, 400)
        self.assertEqual(Mensaje.objects.count(), 0)

    def test_limite_de_ritmo_por_persona_y_en_total(self):
        priv = self.privado(self.ana, self.luis)
        for i in range(servicios.MAX_POR_MINUTO // 2):
            self.assertEqual(self.enviar(self.ana, self.sala.id, f'g{i}').status_code, 201)
            self.assertEqual(self.enviar(self.ana, priv, f'p{i}').status_code, 201)
        self.assertEqual(self.enviar(self.ana, priv, 'otro').status_code, 429)
        self.assertEqual(self.enviar(self.luis, self.sala.id, 'hola').status_code, 201)

    def test_paginacion_y_nuevos(self):
        for i in range(1, 8):
            Mensaje.objects.create(conversacion=self.sala, autor=self.ana, texto=f'm{i}')
        c, url = self.como(self.luis), f'{BASE}/conversaciones/{self.sala.id}/mensajes/'
        p1 = c.get(url + '?limite=3').data
        self.assertEqual([m['texto'] for m in p1['mensajes']], ['m5', 'm6', 'm7'])
        self.assertTrue(p1['hay_mas'])
        p2 = c.get(url + f"?limite=3&antes={p1['mensajes'][0]['id']}").data
        self.assertEqual([m['texto'] for m in p2['mensajes']], ['m2', 'm3', 'm4'])
        p3 = c.get(url + f"?limite=3&antes={p2['mensajes'][0]['id']}").data
        self.assertEqual(([m['texto'] for m in p3['mensajes']], p3['hay_mas']), (['m1'], False))
        nuevos = c.get(url + f"?despues={p1['mensajes'][1]['id']}").data
        self.assertEqual([m['texto'] for m in nuevos['mensajes']], ['m7'])
        self.assertEqual(c.get(url + '?despues=abc&limite=zz').status_code, 200)

    def test_borrar_y_moderacion(self):
        m = Mensaje.objects.create(conversacion=self.sala, autor=self.ana, texto='secreto')
        self.assertEqual(self.como(self.luis).delete(f'{BASE}/mensajes/{m.id}/').status_code, 403)
        self.assertEqual(self.como(self.ana).delete(f'{BASE}/mensajes/{m.id}/').status_code, 200)
        visto = self.como(self.luis).get(f'{BASE}/conversaciones/{self.sala.id}/mensajes/').data['mensajes'][0]
        self.assertEqual((visto['eliminado'], visto['texto']), (True, ''))
        m2 = Mensaje.objects.create(conversacion=self.sala, autor=self.ana, texto='inapropiado')
        self.assertEqual(self.como(self.dir).delete(f'{BASE}/mensajes/{m2.id}/').status_code, 200)
        self.assertEqual(self.como(self.dir).delete(f'{BASE}/mensajes/99999/').status_code, 404)


class PrivadosTests(Base):
    def test_abrir_es_idempotente_y_simetrico(self):
        a = self.privado(self.ana, self.luis)
        self.assertEqual(self.privado(self.ana, self.luis), a)
        self.assertEqual(self.privado(self.luis, self.ana), a)
        self.assertEqual(Conversacion.objects.filter(tipo='DIRECTA').count(), 1)

    def test_no_se_puede_chatear_con_uno_mismo_ni_con_inactivos(self):
        c = self.como(self.ana)
        self.assertEqual(c.post(f'{BASE}/conversaciones/', {'persona': self.ana.id}, format='json').status_code, 400)
        self.eva.is_active = False
        self.eva.save()
        self.assertEqual(c.post(f'{BASE}/conversaciones/', {'persona': self.eva.id}, format='json').status_code, 404)
        self.assertEqual(c.post(f'{BASE}/conversaciones/', {'persona': 'x'}, format='json').status_code, 404)

    def test_solo_los_dos_participantes_lo_ven_ni_direccion(self):
        conv = self.privado(self.ana, self.luis)
        self.enviar(self.ana, conv, 'esto es privado')
        for intruso in (self.eva, self.dir):
            c = self.como(intruso)
            self.assertEqual(c.get(f'{BASE}/conversaciones/{conv}/mensajes/').status_code, 404)
            self.assertEqual(self.enviar(intruso, conv, 'me cuelo').status_code, 404)
            self.assertEqual(c.post(f'{BASE}/conversaciones/{conv}/leido/', {'hasta': 5}, format='json').status_code, 404)
            self.assertNotIn(conv, [x['id'] for x in c.get(f'{BASE}/conversaciones/').data['conversaciones']])
        m = Mensaje.objects.get(conversacion=conv)
        self.assertEqual(self.como(self.dir).delete(f'{BASE}/mensajes/{m.id}/').status_code, 404)
        self.assertEqual(self.como(self.luis).delete(f'{BASE}/mensajes/{m.id}/').status_code, 403)  # el otro participante tampoco
        self.assertEqual(self.como(self.ana).delete(f'{BASE}/mensajes/{m.id}/').status_code, 200)

    def test_lista_con_resumen_orden_y_no_leidos(self):
        c_luis = self.privado(self.ana, self.luis)
        c_eva = self.privado(self.ana, self.eva)
        vacio = self.privado(self.ana, self.dir)  # abierto pero sin mensajes: no aparece
        self.enviar(self.luis, c_luis, 'hola Ana')
        self.enviar(self.eva, c_eva, 'ya tengo el brief')
        self.enviar(self.eva, c_eva, 'te lo paso')
        lista = self.como(self.ana).get(f'{BASE}/conversaciones/').data
        ids = [x['id'] for x in lista['conversaciones']]
        self.assertEqual(ids, [self.sala.id, c_eva, c_luis])
        self.assertNotIn(vacio, ids)
        por = {x['id']: x for x in lista['conversaciones']}
        self.assertEqual((por[c_eva]['no_leidos'], por[c_eva]['titulo'], por[c_eva]['ultimo_texto']), (2, 'Eva', 'te lo paso'))
        self.assertEqual(por[c_luis]['persona']['id'], self.luis.id)
        self.assertEqual(lista['no_leidos'], 3)
        self.assertEqual(self.como(self.ana).get(f'{BASE}/resumen/').data['no_leidos'], 3)
        # Leer una baja solo esa; nunca retrocede; el tope es el último mensaje
        c = self.como(self.ana)
        self.assertEqual(c.post(f'{BASE}/conversaciones/{c_eva}/leido/', {'hasta': 10**9}, format='json').data['no_leidos'], 0)
        self.assertEqual(c.post(f'{BASE}/conversaciones/{c_eva}/leido/', {'hasta': 0}, format='json').data['no_leidos'], 0)
        self.assertEqual(c.get(f'{BASE}/resumen/').data['no_leidos'], 1)
        # Mis propios mensajes no cuentan, y enviar marca la conversación como leída
        self.enviar(self.ana, c_luis, 'hola Luis')
        self.assertEqual(c.get(f'{BASE}/resumen/').data['no_leidos'], 0)
        self.assertEqual(self.como(self.luis).get(f'{BASE}/resumen/').data['no_leidos'], 1)

    def test_directorio(self):
        r = self.como(self.luis).get(f'{BASE}/personas/').data
        self.assertNotIn(self.luis.id, [p['id'] for p in r])
        ana = next(p for p in self.como(self.luis).get(f'{BASE}/personas/?q=diseñ').data)
        self.assertEqual((ana['nombre'], ana['puesto'], ana['departamento']), ('Ana Pérez', 'Diseñadora', 'Diseño'))
        self.assertEqual(self.como(self.luis).get(f'{BASE}/personas/?q=zzzz').data, [])

    def test_borrar_el_ultimo_limpia_la_vista_previa(self):
        conv = self.privado(self.ana, self.luis)
        mid = self.enviar(self.ana, conv, 'me arrepiento').data['id']
        self.como(self.ana).delete(f'{BASE}/mensajes/{mid}/')
        fila = next(x for x in self.como(self.luis).get(f'{BASE}/conversaciones/').data['conversaciones'] if x['id'] == conv)
        self.assertEqual(fila['ultimo_texto'], '')
