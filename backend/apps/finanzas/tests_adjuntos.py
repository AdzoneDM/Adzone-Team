"""Facturas: imágenes y documentos, comprobante de cada pago y reporte descargable."""
import io
import shutil
import tempfile
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.operaciones.models import Cliente
from .models import AdjuntoFactura, Factura, LineaFactura, Pago

MEDIA = tempfile.mkdtemp()


def imagen(nombre='foto.png'):
    b = io.BytesIO()
    Image.new('RGB', (20, 20), 'red').save(b, 'PNG')
    return SimpleUploadedFile(nombre, b.getvalue(), content_type='image/png')


def pdf(nombre='doc.pdf'):
    return SimpleUploadedFile(nombre, b'%PDF-1.4 prueba', content_type='application/pdf')


@override_settings(MEDIA_ROOT=MEDIA)
class AdjuntosTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.admin = User.objects.create_user('dir', password='x', is_staff=True)
        self.admin.groups.add(Group.objects.get_or_create(name='Administrador')[0])
        self.otro = User.objects.create_user('otro', password='x')
        self.cli = Cliente.objects.create(nombre='Ferretería Sol', rnc='101010101')
        self.f = Factura.objects.create(cliente=self.cli, estado='EMITIDA', vencimiento=timezone.localdate() - timedelta(days=10), titulo='Letrero')
        LineaFactura.objects.create(documento=self.f, descripcion='Letrero', cantidad=1, precio=Decimal('1000'), aplica_itbis=False)
        self.f.recalcular()
        self.c = APIClient()
        self.c.force_authenticate(self.admin)

    def url(self, extra=''):
        return f'/api/finanzas/facturas/{self.f.pk}/{extra}'

    # ---- imágenes y documentos de la factura
    def test_agrega_imagenes_y_pdf_a_la_factura(self):
        r = self.c.post(self.url('adjuntos/'), {'archivos': [imagen(), pdf()], 'nota': 'Entrega'}, format='multipart')
        self.assertEqual(r.status_code, 201, r.content)
        adj = r.json()['adjuntos']
        self.assertEqual([(a['nombre'], a['es_imagen']) for a in adj], [('foto.png', True), ('doc.pdf', False)])
        self.assertEqual(self.f.adjuntos.count(), 2)

    def test_ve_y_descarga_un_adjunto(self):
        self.c.post(self.url('adjuntos/'), {'archivos': [imagen()]}, format='multipart')
        a = self.f.adjuntos.get()
        r = self.c.get(self.url(f'adjuntos/{a.pk}/'))
        self.assertEqual((r.status_code, r['Content-Type']), (200, 'image/png'))
        self.assertIn('attachment', self.c.get(self.url(f'adjuntos/{a.pk}/?descargar=1'))['Content-Disposition'])

    def test_borra_un_adjunto(self):
        self.c.post(self.url('adjuntos/'), {'archivos': [imagen()]}, format='multipart')
        a = self.f.adjuntos.get()
        self.assertEqual(self.c.delete(self.url(f'adjuntos/{a.pk}/')).status_code, 200)
        self.assertFalse(AdjuntoFactura.objects.exists())

    def test_rechaza_lo_que_no_es_imagen_ni_pdf_ni_pesa_demasiado(self):
        malo = SimpleUploadedFile('virus.exe', b'MZ', content_type='application/octet-stream')
        self.assertEqual(self.c.post(self.url('adjuntos/'), {'archivos': [malo]}, format='multipart').status_code, 400)
        falsa = SimpleUploadedFile('rota.png', b'no soy una imagen', content_type='image/png')
        self.assertEqual(self.c.post(self.url('adjuntos/'), {'archivos': [falsa]}, format='multipart').status_code, 400)
        grande = SimpleUploadedFile('grande.pdf', b'0' * (10 * 1024 * 1024 + 1), content_type='application/pdf')
        self.assertEqual(self.c.post(self.url('adjuntos/'), {'archivos': [grande]}, format='multipart').status_code, 400)
        self.assertEqual(self.c.post(self.url('adjuntos/'), {}, format='multipart').status_code, 400)
        self.assertFalse(AdjuntoFactura.objects.exists())

    def test_solo_finanzas_ve_los_adjuntos(self):
        self.c.post(self.url('adjuntos/'), {'archivos': [imagen()]}, format='multipart')
        a = self.f.adjuntos.get()
        otro = APIClient()
        otro.force_authenticate(self.otro)
        self.assertEqual(otro.get(self.url(f'adjuntos/{a.pk}/')).status_code, 403)
        self.assertEqual(otro.post(self.url('adjuntos/'), {'archivos': [imagen()]}, format='multipart').status_code, 403)

    # ---- comprobante de pago
    def test_registra_un_pago_con_su_comprobante(self):
        r = self.c.post(self.url('pagos/'), {'monto': '400', 'metodo': 'TRANSFERENCIA', 'referencia': 'TR-1', 'comprobante': imagen('transf.png')}, format='multipart')
        self.assertEqual(r.status_code, 201, r.content)
        p = r.json()['pagos'][0]
        self.assertTrue(p['tiene_comprobante'])
        self.assertTrue(p['comprobante_es_imagen'])
        self.assertEqual(self.c.get(f"/api/finanzas/pagos/{p['id']}/comprobante/")['Content-Type'], 'image/png')

    def test_un_comprobante_malo_no_registra_el_pago(self):
        falsa = SimpleUploadedFile('rota.png', b'nada', content_type='image/png')
        r = self.c.post(self.url('pagos/'), {'monto': '400', 'metodo': 'TRANSFERENCIA', 'comprobante': falsa}, format='multipart')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Pago.objects.exists())

    def test_agrega_cambia_y_quita_el_comprobante_despues(self):
        r = self.c.post(self.url('pagos/'), {'monto': '400', 'metodo': 'EFECTIVO'}, format='multipart')
        pid = r.json()['pagos'][0]['id']
        self.assertFalse(r.json()['pagos'][0]['tiene_comprobante'])
        self.assertEqual(self.c.get(f'/api/finanzas/pagos/{pid}/comprobante/').status_code, 404)
        r = self.c.post(f'/api/finanzas/pagos/{pid}/comprobante/', {'comprobante': pdf('recibo.pdf')}, format='multipart')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()['pagos'][0]['tiene_comprobante'], r.json()['pagos'][0]['comprobante_es_imagen']), (True, False))
        r = self.c.delete(f'/api/finanzas/pagos/{pid}/comprobante/')
        self.assertFalse(r.json()['pagos'][0]['tiene_comprobante'])

    # ---- reporte descargable
    def test_reporte_de_facturas_en_excel(self):
        self.c.post(self.url('pagos/'), {'monto': '400', 'metodo': 'TRANSFERENCIA', 'comprobante': imagen()}, format='multipart')
        self.c.post(self.url('adjuntos/'), {'archivos': [imagen(), pdf()]}, format='multipart')
        r = self.c.get('/api/finanzas/facturas/reporte/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('attachment', r['Content-Disposition'])
        texto = r.content.decode('utf-8-sig')
        lineas = [l for l in texto.splitlines() if l]
        self.assertTrue(lineas[0].startswith('Número,Fecha,Cliente'))
        fila = lineas[1].split(',')
        self.assertIn(self.f.numero, fila[0])
        self.assertIn('Ferretería Sol', lineas[1])
        self.assertIn('1000.00,400.00,600.00', lineas[1])        # total, pagado, saldo
        self.assertIn(',10,1,', lineas[1])                        # 10 días de atraso · 1 pago
        self.assertTrue(lineas[1].endswith(',1,2,,'))             # 1 comprobante · 2 imágenes o documentos
        self.assertIn('TOTAL', texto)

    def test_el_reporte_respeta_los_filtros(self):
        Factura.objects.create(cliente=self.cli, estado='BORRADOR')
        self.assertEqual(len([l for l in self.c.get('/api/finanzas/facturas/reporte/?estado=BORRADOR').content.decode('utf-8-sig').splitlines() if l.startswith('FAC')]), 1)
        self.assertEqual(len([l for l in self.c.get('/api/finanzas/facturas/reporte/?vencidas=1').content.decode('utf-8-sig').splitlines() if l.startswith('FAC')]), 1)

    def test_reporte_de_pagos_con_comprobante(self):
        self.c.post(self.url('pagos/'), {'monto': '400', 'metodo': 'TRANSFERENCIA', 'referencia': 'TR-9', 'comprobante': imagen()}, format='multipart')
        self.c.post(self.url('pagos/'), {'monto': '100', 'metodo': 'EFECTIVO'}, format='multipart')
        texto = self.c.get('/api/finanzas/facturas/reporte/?tipo=pagos').content.decode('utf-8-sig')
        self.assertIn('Fecha del pago,Factura,Cliente,Monto', texto)
        self.assertIn('TR-9,Sí', texto)
        self.assertIn(',No,', texto)

    def test_solo_finanzas_descarga_el_reporte(self):
        otro = APIClient()
        otro.force_authenticate(self.otro)
        self.assertEqual(otro.get('/api/finanzas/facturas/reporte/').status_code, 403)
