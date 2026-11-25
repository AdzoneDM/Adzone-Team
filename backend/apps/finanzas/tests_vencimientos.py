"""Requerimiento #10, etapa 3: control y seguimiento de vencimientos."""
import csv
import io
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.desempeno.models import Notificacion
from apps.operaciones.models import Cliente
from . import servicios
from .models import DIAS_VENCE_PRONTO, Factura, LineaFactura, Pago

F = '/api/finanzas/facturas/'


class VencimientosTests(TestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        self.admin = User.objects.create_user('dir', password='x', is_staff=True)
        self.admin.groups.add(Group.objects.get_or_create(name='Administrador')[0])
        self.finanzas = User.objects.create_user('fin', password='x', first_name='Fina')
        self.finanzas.groups.add(Group.objects.get_or_create(name='Finanzas')[0])
        self.otro = User.objects.create_user('otro', password='x')
        self.cli = Cliente.objects.create(nombre='Ferretería Sol', rnc='101010101')
        self.cli2 = Cliente.objects.create(nombre='Colmado Luz', rnc='202020202')
        self.c = APIClient()
        self.c.force_authenticate(self.admin)

    def factura(self, dias=None, estado='EMITIDA', total='1000', pagado='0', cliente=None, titulo=''):
        f = Factura.objects.create(cliente=cliente or self.cli, estado=estado, titulo=titulo,
                                   vencimiento=self.hoy + timedelta(days=dias) if dias is not None else None)
        LineaFactura.objects.create(documento=f, descripcion='Servicio', cantidad=1, precio=Decimal(total), aplica_itbis=False)
        f.recalcular()
        if Decimal(pagado):
            f.pagado = Decimal(pagado)
            f.save(update_fields=['pagado'])
        return f

    # ---------------------------------------------------------------- situación y días
    def test_situacion_segun_los_dias_que_faltan(self):
        casos = [(-30, 'VENCIDA'), (-1, 'VENCIDA'), (0, 'POR_VENCER'), (3, 'POR_VENCER'), (DIAS_VENCE_PRONTO, 'POR_VENCER'),
                 (DIAS_VENCE_PRONTO + 1, 'PENDIENTE'), (45, 'PENDIENTE')]
        for dias, esperado in casos:
            f = self.factura(dias)
            self.assertEqual((f.situacion, f.dias_para_vencer), (esperado, dias), dias)

    def test_las_pagadas_borradores_y_anuladas_no_cuentan_dias(self):
        for estado, esperado in (('PAGADA', 'PAGADA'), ('BORRADOR', 'BORRADOR'), ('ANULADA', 'ANULADA')):
            f = self.factura(-10, estado=estado)
            self.assertEqual((f.situacion, f.dias_para_vencer, f.vencida), (esperado, None, False), estado)

    def test_una_factura_sin_fecha_de_vencimiento_queda_pendiente(self):
        f = self.factura(None)
        self.assertEqual((f.situacion, f.dias_para_vencer), ('PENDIENTE', None))

    def test_un_pago_parcial_no_la_saca_de_vencida(self):
        f = self.factura(-5, pagado='400')
        self.assertEqual((f.situacion, f.saldo), ('VENCIDA', Decimal('600.00')))

    def test_el_estado_pagada_gana_aunque_el_vencimiento_ya_pasara(self):
        f = self.factura(-20)
        Pago.objects.create(factura=f, monto=f.total, registrado_por=self.admin)
        f.actualizar_pagos()
        self.assertEqual(f.situacion, 'PAGADA')

    def test_la_api_entrega_la_situacion_y_los_dias(self):
        f = self.factura(3)
        d = self.c.get(f'{F}{f.pk}/').json()
        self.assertEqual((d['situacion'], d['situacion_nombre'], d['dias_para_vencer']), ('POR_VENCER', 'Por vencer', 3))
        v = self.c.get(f'{F}{self.factura(-12).pk}/').json()
        self.assertEqual((v['situacion_nombre'], v['dias_para_vencer'], v['vencida']), ('Vencida', -12, True))

    # ---------------------------------------------------------------- filtros
    def numeros(self, **params):
        r = self.c.get(F, params)
        self.assertEqual(r.status_code, 200, r.content)
        return [x['numero'] for x in r.json()]

    def test_filtrar_por_situacion(self):
        vencida, pronto, lejos = self.factura(-3), self.factura(2), self.factura(40)
        sin_fecha, pagada = self.factura(None), self.factura(-1, estado='PAGADA')
        self.assertEqual(self.numeros(situacion='vencida'), [vencida.numero])
        self.assertEqual(self.numeros(situacion='por_vencer'), [pronto.numero])
        self.assertEqual(set(self.numeros(situacion='pendiente')), {lejos.numero, sin_fecha.numero})
        self.assertNotIn(pagada.numero, self.numeros(situacion='vencida'))

    def test_filtrar_por_rango_de_vencimiento(self):
        a, b, c = self.factura(-10), self.factura(5), self.factura(30)
        d = lambda n: str(self.hoy + timedelta(days=n))   # noqa: E731
        self.assertEqual(set(self.numeros(vence_desde=d(0), vence_hasta=d(10))), {b.numero})
        self.assertEqual(set(self.numeros(vence_desde=d(0))), {b.numero, c.numero})
        self.assertEqual(set(self.numeros(vence_hasta=d(0))), {a.numero})
        self.assertEqual(set(self.numeros(vence_desde=d(5), vence_hasta=d(5))), {b.numero})                # los extremos cuentan

    def test_los_filtros_se_combinan_con_los_demas(self):
        a = self.factura(-3, cliente=self.cli)
        self.factura(-3, cliente=self.cli2)
        self.factura(-3, cliente=self.cli, titulo='Otra', estado='PAGADA')
        self.assertEqual(self.numeros(situacion='vencida', cliente=self.cli.pk), [a.numero])
        self.assertEqual(self.numeros(situacion='vencida', cliente=self.cli.pk, q='Servicio'), [])
        self.assertEqual(self.numeros(situacion='vencida', cliente=self.cli.pk, vence_hasta=str(self.hoy - timedelta(days=10))), [])

    def test_una_fecha_mal_escrita_se_ignora_sin_romper(self):
        f = self.factura(1)
        self.assertEqual(self.numeros(vence_desde='mañana', vence_hasta='31-02-2026', situacion='cualquiera'), [f.numero])

    def test_ordenar_por_vencimiento(self):
        lejos, cerca, sin_fecha, vencida = self.factura(30), self.factura(2), self.factura(None), self.factura(-9)
        self.assertEqual(self.numeros(ordenar='vencimiento'), [vencida.numero, cerca.numero, lejos.numero, sin_fecha.numero])

    def test_el_filtro_de_cotizaciones_no_se_ve_afectado(self):
        r = self.c.get('/api/finanzas/cotizaciones/', {'situacion': 'vencida', 'vence_desde': '2026-01-01'})
        self.assertEqual(r.status_code, 200)

    # ---------------------------------------------------------------- resumen
    def test_el_resumen_cuenta_las_por_vencer_y_las_vencidas(self):
        self.factura(-4, total='500'), self.factura(-1, total='300')
        self.factura(2, total='200'), self.factura(6, total='100', pagado='40'), self.factura(30, total='900')
        d = self.c.get('/api/finanzas/resumen/').json()
        self.assertEqual((d['vencidas_n'], Decimal(d['vencido'])), (2, Decimal('800.00')))
        self.assertEqual((d['por_vencer_n'], Decimal(d['por_vencer'])), (2, Decimal('260.00')))             # el saldo, no el total
        self.assertEqual(d['dias_vence_pronto'], DIAS_VENCE_PRONTO)
        self.assertEqual(Decimal(d['por_cobrar']), Decimal('800') + Decimal('260') + Decimal('900'))

    # ---------------------------------------------------------------- reporte
    def filas(self, **params):
        r = self.c.get(F + 'reporte/', params)
        self.assertEqual(r.status_code, 200)
        filas = list(csv.reader(io.StringIO(r.content.decode('utf-8-sig'))))
        return [x[0] for x in filas[1:] if x and x[0].startswith('FAC')]

    def test_el_reporte_respeta_los_filtros_de_vencimiento(self):
        vencida, pronto, lejos = self.factura(-5), self.factura(3), self.factura(50)
        self.assertEqual(self.filas(situacion='vencida'), [vencida.numero])
        self.assertEqual(self.filas(situacion='por_vencer'), [pronto.numero])
        self.assertEqual(self.filas(vence_desde=str(self.hoy + timedelta(days=20))), [lejos.numero])

    # ---------------------------------------------------------------- recordatorios
    def avisos(self, quien=None):
        return Notificacion.objects.filter(tipo='FINANZAS', **({'destinatario': quien} if quien else {}))

    def test_avisa_en_los_hitos_y_solo_a_finanzas(self):
        for dias in (3, 0, -1, -7, -15, -30):
            self.factura(dias)
        servicios.avisar_vencimientos(self.hoy)
        self.assertEqual({n.titulo.split(': ')[1] for n in self.avisos(self.finanzas)},
                         {'vence en 3 días', 'vence hoy', 'venció ayer', 'lleva 7 días vencida', 'lleva 15 días vencida', 'lleva 30 días vencida'})
        self.assertEqual(self.avisos(self.admin).count(), 6)                                              # Dirección también
        self.assertEqual(self.avisos(self.otro).count(), 0)

    def test_no_avisa_fuera_de_los_hitos_ni_de_lo_que_no_se_cobra(self):
        for dias in (5, 2, -2, -10, 60):
            self.factura(dias)
        self.factura(0, estado='PAGADA'), self.factura(0, estado='ANULADA'), self.factura(0, estado='BORRADOR'), self.factura(None)
        self.assertEqual(servicios.avisar_vencimientos(self.hoy), 0)
        self.assertFalse(self.avisos().exists())

    def test_no_repite_el_aviso_si_el_cron_corre_dos_veces(self):
        self.factura(0)
        primero = servicios.avisar_vencimientos(self.hoy)
        self.assertGreater(primero, 0)
        self.assertEqual(servicios.avisar_vencimientos(self.hoy), 0)
        self.assertEqual(self.avisos(self.finanzas).count(), 1)

    def test_el_aviso_dice_cliente_saldo_y_lleva_a_la_factura(self):
        f = self.factura(3, total='1500', pagado='500')
        servicios.avisar_vencimientos(self.hoy)
        n = self.avisos(self.finanzas).get()
        self.assertEqual(n.titulo, f"{f.numero}: vence en 3 días")
        self.assertIn('Ferretería Sol', n.mensaje)
        self.assertIn('1,000.00', n.mensaje)
        self.assertEqual(n.enlace, f'/finanzas?ver=facturas&id={f.pk}')

    def test_una_factura_pagada_antes_del_hito_ya_no_avisa(self):
        f = self.factura(3)
        Pago.objects.create(factura=f, monto=f.total, registrado_por=self.admin)
        f.actualizar_pagos()
        self.assertEqual(servicios.avisar_vencimientos(self.hoy), 0)

    def test_el_dia_siguiente_avisa_el_hito_siguiente(self):
        self.factura(1)
        self.assertEqual(servicios.avisar_vencimientos(self.hoy), 0)                                      # hoy faltan 1 día: sin hito
        self.assertGreater(servicios.avisar_vencimientos(self.hoy + timedelta(days=1)), 0)               # mañana vence hoy
