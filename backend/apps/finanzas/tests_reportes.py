"""Requerimiento #10, etapa 4: reportes de facturas en Excel y PDF, con totales solo de lo filtrado."""
import io
import re
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.utils import timezone
from openpyxl import load_workbook
from rest_framework.test import APIClient

from apps.operaciones.models import Cliente
from . import reportes
from .models import Factura, LineaFactura, Pago

R = '/api/finanzas/facturas/reporte/'
XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


class ReportesDeFacturasTests(TestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        self.admin = User.objects.create_user('dir', password='x', is_staff=True, first_name='Dir', last_name='Ección')
        self.admin.groups.add(Group.objects.get_or_create(name='Administrador')[0])
        self.otro = User.objects.create_user('otro', password='x')
        self.sol = Cliente.objects.create(nombre='Ferretería Sol', rnc='101010101')
        self.luz = Cliente.objects.create(nombre='Colmado Luz', rnc='202020202')
        self.c = APIClient()
        self.c.force_authenticate(self.admin)
        # Un caso de cada situación, en dos clientes y dos monedas
        self.vencida = self.factura(self.sol, 'EMITIDA', 1000, dias=-10, titulo='Letrero luminoso', fecha=self.hoy - timedelta(days=40))
        self.pronto = self.factura(self.sol, 'EMITIDA', 500, dias=3, pagado=200, titulo='Pendón', fecha=self.hoy - timedelta(days=5))
        self.pagada = self.factura(self.luz, 'EMITIDA', 800, dias=-30, pagado=800, titulo='Rótulo', fecha=self.hoy - timedelta(days=60))
        self.lejos = self.factura(self.luz, 'EMITIDA', 300, dias=45, titulo='Volantes', fecha=self.hoy - timedelta(days=2))
        self.dolares = self.factura(self.luz, 'EMITIDA', 100, dias=20, moneda='USD', titulo='Dominio', fecha=self.hoy - timedelta(days=3))
        self.borrador = self.factura(self.sol, 'BORRADOR', 9999, titulo='Sin emitir', fecha=self.hoy)
        self.anulada = self.factura(self.luz, 'ANULADA', 7777, titulo='Error', fecha=self.hoy)

    def factura(self, cliente, estado, monto, dias=None, pagado=0, moneda='DOP', titulo='', fecha=None):
        f = Factura.objects.create(cliente=cliente, estado=estado, moneda=moneda, titulo=titulo, fecha=fecha or self.hoy,
                                   vencimiento=self.hoy + timedelta(days=dias) if dias is not None else None)
        LineaFactura.objects.create(documento=f, descripcion=titulo or 'Servicio', cantidad=1, precio=Decimal(monto), aplica_itbis=False)
        f.recalcular()
        if pagado:
            Pago.objects.create(factura=f, monto=Decimal(pagado), registrado_por=self.admin)
            f.actualizar_pagos()
        return f

    # ---------------------------------------------------------------- ayudas
    def libro(self, **params):
        r = self.c.get(R, {'formato': 'xlsx', **params})
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(r['Content-Type'], XLSX)
        self.assertIn('.xlsx', r['Content-Disposition'])
        return load_workbook(io.BytesIO(r.content))

    def numeros(self, **params):
        ws = self.libro(**params)['Facturas']
        return [row[0].value for row in ws.iter_rows(min_row=2) if row[0].value and str(row[0].value).startswith('FAC')]

    def resumen(self, **params):
        r = self.c.get(R, {'formato': 'resumen', **params})
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def moneda(self, resumen, codigo):
        return next(m for m in resumen['monedas'] if m['moneda'] == codigo)

    # ---------------------------------------------------------------- Excel
    def test_el_excel_trae_las_columnas_y_los_datos_reales(self):
        wb = self.libro()
        self.assertEqual(wb.sheetnames, ['Resumen', 'Facturas'])
        ws = wb['Facturas']
        self.assertEqual([c.value for c in ws[1]], reportes.ENCABEZADOS)
        fila = next(r for r in ws.iter_rows(min_row=2) if r[0].value == self.pronto.numero)
        v = {h: c.value for h, c in zip(reportes.ENCABEZADOS, fila)}
        self.assertEqual((v['Cliente'], v['RNC'], v['Concepto'], v['Moneda']), ('Ferretería Sol', '101010101', 'Pendón', 'DOP'))
        self.assertEqual((float(v['Subtotal']), float(v['Impuestos (ITBIS)']), float(v['Total facturado']), float(v['Monto pagado']), float(v['Balance pendiente'])),
                         (500.0, 0.0, 500.0, 200.0, 300.0))
        self.assertEqual(v['Estado de pago'], 'Por vencer')
        self.assertEqual(v['Días'], 'faltan 3')
        self.assertEqual(v['Fecha de emisión'].date(), self.pronto.fecha)
        self.assertEqual(v['Vencimiento'].date(), self.pronto.vencimiento)
        self.assertEqual(v['Fecha de registro'].date(), timezone.localtime(self.pronto.fecha_creacion).date())

    def test_el_excel_incluye_todas_las_facturas_sin_filtros(self):
        self.assertEqual(set(self.numeros()), {f.numero for f in Factura.objects.all()})

    def test_la_hoja_resumen_lleva_filtros_conteos_y_montos(self):
        ws = self.libro(situacion='vencida', cliente=self.sol.pk)['Resumen']
        texto = '\n'.join(str(c.value) for fila in ws.iter_rows() for c in fila if c.value is not None)
        self.assertIn('Situación', texto)
        self.assertIn('Vencidas', texto)
        self.assertIn('Ferretería Sol', texto)
        self.assertIn('Facturas consultadas', texto)
        self.assertIn('Generado el', texto)
        self.assertIn('Dir Ección', texto)

    def test_el_excel_trae_los_totales_al_final(self):
        ws = self.libro()['Facturas']
        totales = {r[0].value: [c.value for c in r[9:14]] for r in ws.iter_rows(min_row=2) if r[0].value and str(r[0].value).startswith('TOTAL')}
        dop = next(v for k, v in totales.items() if 'DOP' in k)
        self.assertEqual([float(x) for x in dop], [2600.0, 0.0, 2600.0, 1000.0, 1600.0])         # 1000 + 500 + 800 + 300 (sin borrador ni anulada)
        usd = next(v for k, v in totales.items() if 'USD' in k)
        self.assertEqual([float(x) for x in usd], [100.0, 0.0, 100.0, 0.0, 100.0])

    def test_un_nombre_que_parece_formula_se_guarda_como_texto(self):
        malo = Cliente.objects.create(nombre='=HYPERLINK("http://malo.example","clic")', rnc='1')
        self.factura(malo, 'EMITIDA', 10, dias=5, titulo='+SUM(1+1)')
        ws = self.libro(numero='FAC')['Facturas']
        celdas = [c for fila in ws.iter_rows(min_row=2) for c in fila if isinstance(c.value, str) and c.value.startswith(('=', '+'))]
        self.assertEqual({c.value for c in celdas}, {'=HYPERLINK("http://malo.example","clic")', '+SUM(1+1)'})
        self.assertTrue(all(c.data_type == 's' for c in celdas))

    # ---------------------------------------------------------------- totales y conteos
    def test_los_totales_son_solo_de_lo_filtrado(self):
        todo = self.resumen()
        sol = self.resumen(cliente=self.sol.pk)
        self.assertEqual(self.moneda(todo, 'DOP')['facturado'], '2600.00')
        self.assertEqual(self.moneda(sol, 'DOP')['facturado'], '1500.00')                          # Sol: 1000 + 500 (el borrador no cuenta)
        self.assertEqual(self.moneda(sol, 'DOP')['pagado'], '200.00')
        self.assertEqual(self.moneda(sol, 'DOP')['pendiente'], '1300.00')
        self.assertEqual([m['moneda'] for m in sol['monedas']], ['DOP'])                           # Sol no tiene facturas en dólares

    def test_los_conteos(self):
        d = self.resumen()
        self.assertEqual((d['cantidad'], d['pendientes'], d['por_vencer'], d['vencidas'], d['pagadas'], d['borradores'], d['anuladas']),
                         (7, 4, 1, 1, 1, 1, 1))     # pendientes: vencida + pronto + lejos + dólares; por vencer: solo «pronto» (vence en 3 días)

    def test_los_borradores_y_las_anuladas_no_suman_montos(self):
        d = self.resumen()
        self.assertEqual(self.moneda(d, 'DOP')['cantidad'], 4)
        solo_borrador = self.resumen(estado='BORRADOR,ANULADA')
        self.assertEqual(solo_borrador['monedas'], [])
        self.assertEqual(solo_borrador['cantidad'], 2)

    def test_cada_moneda_se_suma_por_separado(self):
        d = self.resumen()
        self.assertEqual({m['moneda'] for m in d['monedas']}, {'DOP', 'USD'})
        self.assertEqual(self.moneda(d, 'USD')['facturado'], '100.00')

    def test_el_resumen_json_coincide_con_el_excel(self):
        ws = self.libro(situacion='pendiente')['Facturas']
        n_excel = len([r for r in ws.iter_rows(min_row=2) if r[0].value and str(r[0].value).startswith('FAC')])
        self.assertEqual(self.resumen(situacion='pendiente')['cantidad'], n_excel)

    # ---------------------------------------------------------------- filtros
    def test_cada_filtro(self):
        d = lambda n: str(self.hoy + timedelta(days=n))   # noqa: E731
        self.assertEqual(set(self.numeros(situacion='vencida')), {self.vencida.numero})
        self.assertEqual(set(self.numeros(estado_pago='pagada')), {self.pagada.numero})
        self.assertEqual(set(self.numeros(estado_pago='parcial')), {self.pronto.numero})
        self.assertEqual(set(self.numeros(estado_pago='pendiente')), {self.vencida.numero, self.pronto.numero, self.lejos.numero, self.dolares.numero})
        self.assertEqual(set(self.numeros(estado='BORRADOR')), {self.borrador.numero})
        self.assertEqual(set(self.numeros(vence_desde=d(0), vence_hasta=d(10))), {self.pronto.numero})
        self.assertEqual(set(self.numeros(desde=str(self.hoy - timedelta(days=45)), hasta=str(self.hoy - timedelta(days=4)))), {self.vencida.numero, self.pronto.numero})
        self.assertEqual(set(self.numeros(numero=self.lejos.numero)), {self.lejos.numero})
        self.assertEqual(set(self.numeros(cliente_nombre='colmado')), {self.pagada.numero, self.lejos.numero, self.dolares.numero, self.anulada.numero})

    def test_el_numero_tambien_busca_por_ncf(self):
        Factura.objects.filter(pk=self.lejos.pk).update(ncf='B0100000077')
        self.assertEqual(set(self.numeros(numero='0000077')), {self.lejos.numero})

    def test_los_filtros_se_combinan(self):
        self.assertEqual(set(self.numeros(cliente=self.luz.pk, estado_pago='pendiente')), {self.lejos.numero, self.dolares.numero})
        self.assertEqual(set(self.numeros(cliente=self.luz.pk, estado_pago='pendiente', situacion='por_vencer')), set())               # los de Luz vencen en 20 y 45 días
        self.assertEqual(set(self.numeros(cliente=self.sol.pk, estado_pago='parcial', situacion='por_vencer')), {self.pronto.numero})
        self.assertEqual(self.numeros(cliente=self.sol.pk, situacion='vencida', cliente_nombre='Colmado'), [])

    def test_sin_resultados_el_reporte_se_genera_igual(self):
        wb = self.libro(numero='NO-EXISTE')
        self.assertEqual(self.numeros(numero='NO-EXISTE'), [])
        d = self.resumen(numero='NO-EXISTE')
        self.assertEqual((d['cantidad'], d['monedas']), (0, []))
        self.assertIn('Resumen', wb.sheetnames)
        r = self.c.get(R, {'formato': 'pdf', 'numero': 'NO-EXISTE'})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))

    def test_la_fecha_mal_escrita_no_rompe_el_reporte(self):
        self.assertEqual(self.c.get(R, {'formato': 'xlsx', 'vence_desde': 'mañana', 'situacion': 'inventada'}).status_code, 200)

    # ---------------------------------------------------------------- PDF
    def test_el_pdf_se_genera_con_acentos_y_los_totales(self):
        r = self.c.get(R, {'formato': 'pdf'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertIn('.pdf', r['Content-Disposition'])
        self.assertTrue(r.content.startswith(b'%PDF'))
        self.assertGreater(len(r.content), 2000)

    def test_el_pdf_con_muchas_facturas_ocupa_varias_paginas(self):
        for i in range(70):
            self.factura(self.sol, 'EMITIDA', 10 + i, dias=i, titulo=f'Servicio número {i} con un texto largo para que ocupe espacio en la fila')
        r = self.c.get(R, {'formato': 'pdf'})
        paginas = len(re.findall(rb'/Type\s*/Page(?![s\w])', r.content))
        self.assertGreater(paginas, 1)

    def test_un_pdf_demasiado_largo_se_rechaza_con_un_mensaje_claro(self):
        with mock.patch.object(reportes, 'MAX_FILAS_PDF', 3):
            r = self.c.get(R, {'formato': 'pdf'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('Excel', str(r.json()))
        with mock.patch.object(reportes, 'MAX_FILAS_PDF', 3):
            self.assertEqual(self.c.get(R, {'formato': 'xlsx'}).status_code, 200)                    # el Excel no tiene ese tope

    def test_caracteres_fuera_de_latin1_no_rompen_el_pdf(self):
        raro = Cliente.objects.create(nombre='Café ☕ 北京 <b>&</b>', rnc='1')
        self.factura(raro, 'EMITIDA', 10, dias=5, titulo='Promoción 🎉')
        self.assertEqual(self.c.get(R, {'formato': 'pdf', 'numero': 'FAC'}).status_code, 200)

    # ---------------------------------------------------------------- permisos y formatos
    def test_solo_finanzas_descarga_los_reportes(self):
        self.c.force_authenticate(self.otro)
        for formato in ('xlsx', 'pdf', 'resumen', 'csv'):
            self.assertEqual(self.c.get(R, {'formato': formato}).status_code, 403, formato)
        self.c.force_authenticate(None)
        self.assertIn(self.c.get(R, {'formato': 'xlsx'}).status_code, (401, 403))

    def test_un_formato_inventado_se_rechaza(self):
        self.assertEqual(self.c.get(R, {'formato': 'exe'}).status_code, 400)

    def test_el_csv_de_siempre_sigue_funcionando(self):
        r = self.c.get(R)
        self.assertEqual(r.status_code, 200)
        self.assertIn('text/csv', r['Content-Type'])
        self.assertIn('Número', r.content.decode('utf-8-sig').splitlines()[0])
