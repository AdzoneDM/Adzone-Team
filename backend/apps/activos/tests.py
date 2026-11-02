from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Departamento
from apps.desempeno.models import Notificacion
from apps.organizacion.models import PuestoDeTrabajo
from . import servicios
from .models import Activo


class ActivosTests(TestCase):
    def setUp(self):
        tec = Departamento.objects.create(nombre='Tecnología')
        self.ti = User.objects.create_user('ti', password='x', first_name='Julián')
        self.ti.perfil.puesto_trabajo = PuestoDeTrabajo.objects.create(nombre='Encargado TI', departamento=tec)
        self.ti.perfil.save()
        self.ana = User.objects.create_user('ana', password='x', first_name='Ana')
        self.luis = User.objects.create_user('luis', password='x')
        self.dir = User.objects.create_user('dir', password='x', is_staff=True)
        self.dir.groups.add(Group.objects.get_or_create(name='Administrador')[0])

    def como(self, u):
        c = APIClient()
        c.force_authenticate(u)
        return c

    def test_alta_asignacion_reporte_y_devolucion(self):
        ti = self.como(self.ti)
        r = ti.post('/api/activos/', {'nombre': 'Laptop Dell', 'categoria': 'LAPTOP', 'serie': 'X1', 'costo': '60000',
                                      'fecha_compra': str(date.today() - timedelta(days=365)), 'vida_util_meses': 36}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        a = r.json()
        self.assertEqual(a['codigo'], 'ACT-0001')
        self.assertLess(a['valor_actual'], 60000)
        self.assertEqual(self.como(self.ana).post('/api/activos/', {'nombre': 'x'}, format='json').status_code, 403)
        self.assertEqual(ti.post(f"/api/activos/{a['id']}/mover/", {'tipo': 'ASIGNACION'}, format='json').status_code, 400)
        r = ti.post(f"/api/activos/{a['id']}/mover/", {'tipo': 'ASIGNACION', 'persona': self.ana.pk}, format='json')
        self.assertEqual(r.json()['estado'], 'ASIGNADO')
        self.assertTrue(Notificacion.objects.filter(destinatario=self.ana, titulo__contains='ACT-0001').exists())
        mios = self.como(self.ana).get('/api/activos/').json()
        self.assertEqual(len(mios), 1)
        self.assertIsNone(mios[0]['costo'])  # el costo no lo ve quien lo usa
        self.assertEqual(self.como(self.luis).post(f"/api/activos/{a['id']}/reportar/", {'nota': 'x'}, format='json').status_code, 403)
        r = self.como(self.ana).post(f"/api/activos/{a['id']}/reportar/", {'nota': 'Se cayó y no enciende'}, format='json')
        self.assertEqual(r.json()['estado'], 'DANADO')
        self.assertTrue(Notificacion.objects.filter(destinatario=self.ti, titulo__contains='daño').exists())
        ti.post(f"/api/activos/{a['id']}/mover/", {'tipo': 'REPARACION', 'costo': '3500', 'nota': 'Cambio de pantalla'}, format='json')
        r = ti.post(f"/api/activos/{a['id']}/mover/", {'tipo': 'DEVOLUCION'}, format='json')
        self.assertEqual(r.json()['estado'], 'DISPONIBLE')
        hist = ti.get(f"/api/activos/{a['id']}/historial/").json()
        self.assertEqual([h['tipo'] for h in hist][::-1], ['ALTA', 'ASIGNACION', 'DANO', 'REPARACION', 'DEVOLUCION'])
        self.assertEqual(ti.delete(f"/api/activos/{a['id']}/").status_code, 400)  # con historial: baja, no borrar
        ti.post(f"/api/activos/{a['id']}/mover/", {'tipo': 'BAJA'}, format='json')
        self.assertEqual(ti.get('/api/activos/').json(), [])
        self.assertEqual(len(ti.get('/api/activos/?bajas=1').json()), 1)

    def test_depreciacion_mantenimiento_y_resumen(self):
        a = Activo.objects.create(nombre='Cámara', costo=Decimal('36000'), fecha_compra=date(2025, 11, 1), vida_util_meses=36,
                                  mantenimiento_cada_meses=6, proximo_mantenimiento=date.today() - timedelta(days=1))
        self.assertEqual(a.valor_actual(date(2026, 11, 1)), Decimal('24000.00'))
        self.assertEqual(a.valor_actual(date(2030, 1, 1)), Decimal('0.00'))
        self.assertEqual(servicios.revisar(), 1)
        self.assertEqual(servicios.revisar(), 0)
        servicios.mover(a, 'MANTENIMIENTO', self.ti, costo=500)
        a.refresh_from_db()
        self.assertGreater(a.proximo_mantenimiento, date.today())
        r = self.como(self.dir).get('/api/activos/resumen/').json()
        self.assertEqual(r['total'], 1)
        self.assertEqual(self.como(self.ana).get('/api/activos/resumen/').status_code, 403)
