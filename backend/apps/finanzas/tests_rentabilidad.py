"""v10: rentabilidad por OT, cliente y departamento, con materiales, gastos, mano de obra y dólares."""
from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.almacen.models import LineaVale, Material, ValeMaterial
from apps.core.models import Departamento
from apps.operaciones.models import Cliente, OrdenTrabajo
from apps.tiempo.models import RegistroTiempo
from .models import Factura, Gasto, TasaCambio
from .rentabilidad import rentabilidad_ordenes


class RentabilidadTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('dir', password='x', is_staff=True)
        self.admin.groups.add(Group.objects.get_or_create(name='Administrador')[0])
        self.ana = User.objects.create_user('ana', password='x', first_name='Ana')
        self.ana.perfil.costo_hora = Decimal('200')
        self.ana.perfil.save()
        self.dep = Departamento.objects.create(nombre='Impresión')
        self.cli = Cliente.objects.create(nombre='Ferretería')
        self.ot = OrdenTrabajo.objects.create(titulo='Letrero', cliente=self.cli, departamento=self.dep, monto=Decimal('20000'), estado='EN_PRODUCCION')
        self.c = APIClient()
        self.c.force_authenticate(self.admin)

    def _horas(self, minutos):
        ini = timezone.make_aware(datetime(2026, 10, 10, 9))
        RegistroTiempo.objects.create(usuario=self.ana, orden=self.ot, inicio=ini, fin=ini + timezone.timedelta(minutes=minutos), minutos=minutos)

    def test_costo_completo_y_margen_sobre_lo_vendido(self):
        self._horas(300)                                                      # 5 h × 200 = 1,000
        m = Material.objects.create(codigo='LONA', nombre='Lona', costo_unitario=Decimal('500'))
        v = ValeMaterial.objects.create(orden=self.ot, estado='DESPACHADO')
        LineaVale.objects.create(vale=v, material=m, cantidad_solicitada=6, cantidad_despachada=6, costo_unitario=Decimal('500'))  # 3,000
        Gasto.objects.create(concepto='Instalador', categoria='PERSONAL', monto=Decimal('2000'), orden=self.ot, fecha=date(2026, 10, 11))
        d = rentabilidad_ordenes(date(2026, 10, 1), date(2026, 10, 31))
        f = d['ordenes'][0]
        self.assertEqual((f['mano_obra'], f['materiales'], f['externos'], f['costo']), (1000.0, 3000.0, 2000.0, 6000.0))
        self.assertEqual(f['base'], 'VENDIDO')
        self.assertEqual(f['utilidad'], 14000.0)
        self.assertEqual(f['margen'], 70.0)
        self.assertFalse(f['alerta'])
        self.assertEqual(d['clientes'][0]['nombre'], 'Ferretería')
        self.assertEqual(d['departamentos'][0]['nombre'], 'Impresión')

    def test_facturado_en_dolares_con_tasa_y_alerta_de_margen(self):
        self._horas(600)                                                      # 2,000
        Factura.objects.create(cliente=self.cli, orden=self.ot, estado='EMITIDA', moneda='USD', subtotal=Decimal('50'), total=Decimal('59'),
                               fecha=date(2026, 10, 15))
        d = rentabilidad_ordenes(date(2026, 10, 1), date(2026, 10, 31))
        self.assertEqual(d['montos_sin_tasa'], 1)                             # sin tasa no se inventa
        TasaCambio.objects.create(fecha=date(2026, 10, 1), usd_dop=Decimal('60'))
        f = rentabilidad_ordenes(date(2026, 10, 1), date(2026, 10, 31))['ordenes'][0]
        self.assertEqual(f['base'], 'FACTURADO')
        self.assertEqual(f['facturado'], 3000.0)                              # US$ 50 × 60
        self.assertEqual(f['margen'], 33.3)
        self.assertFalse(f['alerta'])
        self._horas(60)
        f = rentabilidad_ordenes(date(2026, 10, 1), date(2026, 10, 31))['ordenes'][0]
        self.assertTrue(f['alerta'])                                          # 2,200 de 3,000 = 26.7 % < 30 %

    def test_api_permisos_detalle_y_excel(self):
        self._horas(120)
        r = self.c.get('/api/finanzas/rentabilidad/ordenes/?desde=2026-10-01&hasta=2026-10-31')
        self.assertEqual(r.status_code, 200)
        det = self.c.get(f'/api/finanzas/rentabilidad/ordenes/{self.ot.pk}/').json()
        self.assertEqual(det['personas'][0], {'nombre': 'Ana', 'horas': 2.0, 'costo': 400.0})
        csv = self.c.get('/api/finanzas/rentabilidad/ordenes/?desde=2026-10-01&hasta=2026-10-31&formato=csv').content.decode('utf-8-sig')
        self.assertIn('Letrero', csv)
        otro = APIClient()
        otro.force_authenticate(self.ana)
        self.assertEqual(otro.get('/api/finanzas/rentabilidad/ordenes/').status_code, 403)
        self.assertEqual(self.c.post('/api/finanzas/tasas/', {'fecha': '2026-11-01', 'usd_dop': '0'}, format='json').status_code, 400)
        self.assertEqual(self.c.post('/api/finanzas/tasas/', {'fecha': '2026-11-01', 'usd_dop': '63.25'}, format='json').status_code, 201)

    def test_rentabilidad_por_proyecto_convierte_dolares(self):
        from .servicios import rentabilidad
        TasaCambio.objects.create(fecha=date(2026, 1, 1), usd_dop=Decimal('60'))
        f = Factura.objects.create(cliente=self.cli, estado='EMITIDA', moneda='USD', subtotal=Decimal('100'), total=Decimal('118'), fecha=date(2026, 10, 1))
        g = Gasto.objects.create(concepto='x', monto=Decimal('10'), moneda='USD', fecha=date(2026, 10, 1))
        r = rentabilidad([f], [g], [])
        self.assertEqual((r['facturado'], r['gastos'], r['margen']), (Decimal('6000.00'), Decimal('600.00'), Decimal('5400.00')))
