"""Requerimiento #10, etapa 2: historial y trazabilidad de las facturas."""
from datetime import timedelta
from decimal import Decimal

from django.test import override_settings
from django.utils import timezone

from . import servicios
from .models import Cotizacion, Factura, HistorialFactura, LineaCotizacion
from .tests_adjuntos import MEDIA, imagen, pdf
from .tests_adjuntos import AdjuntosTests as Base

F = '/api/finanzas/facturas/'


@override_settings(MEDIA_ROOT=MEDIA)
class HistorialDeFacturaTests(Base):
    def acciones(self, f=None):
        return list((f or self.f).historial.order_by('id').values_list('accion', flat=True))

    def ultimo(self, accion, f=None):
        return (f or self.f).historial.filter(accion=accion).order_by('-id').first()

    def borrador(self, **extra):
        r = self.c.post(F, {'cliente': self.cli.pk, 'titulo': 'Rótulo', 'fecha': str(timezone.localdate()), 'moneda': 'DOP',
                            'lineas': [{'descripcion': 'Rótulo', 'cantidad': '1', 'precio': '1000', 'aplica_itbis': False}], **extra}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return Factura.objects.get(pk=r.json()['id'])

    # ---------------------------------------------------------------- creación y cambios
    def test_registra_quien_creo_la_factura(self):
        f = self.borrador()
        h = self.ultimo('CREADA', f)
        self.assertEqual(h.usuario, self.admin)
        self.assertIn(f.numero, h.detalle)
        self.assertIn('Ferretería Sol', h.detalle)

    def test_registra_los_cambios_con_antes_y_despues(self):
        f = self.borrador()
        nuevo_venc = timezone.localdate() + timedelta(days=20)
        r = self.c.patch(f'{F}{f.pk}/', {'titulo': 'Rótulo grande', 'vencimiento': str(nuevo_venc)}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        h = self.ultimo('EDITADA', f)
        self.assertEqual(h.usuario, self.admin)
        self.assertIn('Título: Rótulo → Rótulo grande', h.detalle)
        self.assertIn(f"Vencimiento: sin definir → {nuevo_venc:%d/%m/%Y}", h.detalle)

    def test_cambiar_las_lineas_dice_el_total_anterior_y_el_nuevo(self):
        f = self.borrador()
        self.c.patch(f'{F}{f.pk}/', {'lineas': [{'descripcion': 'Rótulo', 'cantidad': '2', 'precio': '1000', 'aplica_itbis': False}]}, format='json')
        self.assertIn('Líneas: actualizadas (total 1,000.00 → 2,000.00)', self.ultimo('EDITADA', f).detalle)

    def test_guardar_sin_cambios_no_llena_el_historial(self):
        f = self.borrador()
        self.c.patch(f'{F}{f.pk}/', {'titulo': 'Rótulo'}, format='json')
        self.assertEqual(self.acciones(f), ['CREADA'])

    def test_registra_el_cambio_de_ncf_en_una_factura_emitida(self):
        self.c.patch(f'{F}{self.f.pk}/', {'ncf': 'B0100000001'}, format='json')
        self.assertIn('NCF: sin NCF → B0100000001', self.ultimo('EDITADA').detalle)

    # ---------------------------------------------------------------- emisión, pagos y estado
    def test_emitir_pagar_y_borrar_pagos_dejan_rastro(self):
        f = self.borrador()
        self.assertEqual(self.c.post(f'{F}{f.pk}/emitir/', {'dias_credito': 15}, format='json').status_code, 200)
        self.assertIn('Vence:', self.ultimo('EMITIDA', f).detalle)
        r = self.c.post(f'{F}{f.pk}/pagos/', {'monto': '400', 'metodo': 'TRANSFERENCIA', 'referencia': 'TR-889'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        h = self.ultimo('PAGO', f)
        self.assertIn('400.00 DOP', h.detalle)
        self.assertIn('ref. TR-889', h.detalle)
        self.assertIn('saldo 600.00', h.detalle)
        self.assertIsNone(self.ultimo('ESTADO', f))                                                   # sigue emitida: el estado no cambió
        self.c.post(f'{F}{f.pk}/pagos/', {'monto': '600', 'metodo': 'EFECTIVO'}, format='json')
        self.assertEqual(self.ultimo('ESTADO', f).detalle, 'Estado: Emitida → Pagada')
        pago = f.pagos.order_by('-id').first()
        self.assertEqual(self.c.delete(f'/api/finanzas/pagos/{pago.pk}/').status_code, 200)
        self.assertEqual(self.ultimo('PAGO_BORRADO', f).usuario, self.admin)
        self.assertEqual(self.ultimo('ESTADO', f).detalle, 'Estado: Pagada → Emitida')

    def test_anular_guarda_el_motivo(self):
        self.c.post(f'{F}{self.f.pk}/anular/', {'motivo': 'Cliente canceló'}, format='json')
        self.assertEqual(self.ultimo('ANULADA').detalle, 'Cliente canceló')

    def test_comprobante_de_pago_agregado_y_quitado(self):
        f = self.borrador()
        self.c.post(f'{F}{f.pk}/emitir/', {}, format='json')
        self.c.post(f'{F}{f.pk}/pagos/', {'monto': '100', 'metodo': 'TRANSFERENCIA', 'comprobante': imagen()}, format='multipart')
        self.assertIn('Adjuntó el comprobante', self.ultimo('COMPROBANTE', f).detalle)
        pago = f.pagos.get()
        self.c.delete(f'/api/finanzas/pagos/{pago.pk}/comprobante/')
        self.assertIn('Quitó el comprobante', self.ultimo('COMPROBANTE', f).detalle)

    # ---------------------------------------------------------------- documentos
    def test_documentos_agregados_modificados_reemplazados_y_quitados(self):
        self.c.post(self.url('adjuntos/'), {'archivos': [pdf('a.pdf')], 'tipo': 'COMPROBANTE'}, format='multipart')
        self.assertEqual(self.ultimo('ADJUNTO').detalle, 'a.pdf · Comprobante de pago')
        a = self.f.adjuntos.get()
        self.c.patch(self.url(f'adjuntos/{a.pk}/'), {'tipo': 'COTIZACION'}, format='json')
        self.assertIn('tipo: Comprobante de pago → Cotización', self.ultimo('ADJUNTO_EDITADO').detalle)
        self.c.post(self.url(f'adjuntos/{a.pk}/reemplazar/'), {'archivo': pdf('b.pdf')}, format='multipart')
        self.assertEqual(self.ultimo('ADJUNTO_REEMPLAZADO').detalle, 'a.pdf → b.pdf')
        self.c.delete(self.url(f'adjuntos/{a.pk}/'))
        self.assertEqual(self.ultimo('ADJUNTO_QUITADO').detalle, 'b.pdf')
        self.assertEqual(self.acciones(), ['ADJUNTO', 'ADJUNTO_EDITADO', 'ADJUNTO_REEMPLAZADO', 'ADJUNTO_QUITADO'])

    def test_un_documento_rechazado_no_deja_rastro(self):
        self.c.post(self.url('adjuntos/'), {'archivos': [pdf('falso.exe')]}, format='multipart')
        self.assertEqual(self.acciones(), [])

    def test_cambiar_el_tipo_al_mismo_valor_no_registra_nada(self):
        self.c.post(self.url('adjuntos/'), {'archivos': [pdf()]}, format='multipart')
        a = self.f.adjuntos.get()
        self.c.patch(self.url(f'adjuntos/{a.pk}/'), {'tipo': a.tipo}, format='json')
        self.assertEqual(self.acciones(), ['ADJUNTO'])

    # ---------------------------------------------------------------- origen
    def test_una_factura_que_viene_de_una_cotizacion_lo_dice(self):
        cot = Cotizacion.objects.create(cliente=self.cli, estado='APROBADA', titulo='Campaña')
        LineaCotizacion.objects.create(documento=cot, descripcion='Campaña', cantidad=1, precio=Decimal('500'))
        f = servicios.factura_desde(cot, self.admin)
        self.assertIn(f'desde la cotización {cot.numero}', self.ultimo('CREADA', f).detalle)

    # ---------------------------------------------------------------- consulta y permisos
    def test_la_consulta_muestra_lo_mas_reciente_primero_con_quien_lo_hizo(self):
        self.c.post(self.url('adjuntos/'), {'archivos': [pdf('a.pdf')]}, format='multipart')
        self.c.post(f'{F}{self.f.pk}/anular/', {'motivo': 'Error'}, format='json')
        r = self.c.get(self.url('historial/'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual([x['accion'] for x in r.json()], ['ANULADA', 'ADJUNTO'])
        self.assertEqual(r.json()[0]['usuario_nombre'], 'dir')
        self.assertEqual(r.json()[0]['accion_texto'], 'Anuló la factura')

    def test_un_movimiento_de_un_usuario_borrado_se_conserva(self):
        self.c.post(f'{F}{self.f.pk}/anular/', {'motivo': 'x'}, format='json')
        HistorialFactura.objects.filter(factura=self.f).update(usuario=None)
        self.assertEqual(self.c.get(self.url('historial/')).json()[0]['usuario_nombre'], 'Sistema')

    def test_solo_finanzas_consulta_el_historial(self):
        self.c.post(f'{F}{self.f.pk}/anular/', {'motivo': 'x'}, format='json')
        self.c.force_authenticate(self.otro)
        self.assertEqual(self.c.get(self.url('historial/')).status_code, 403)
        self.c.force_authenticate(None)
        self.assertIn(self.c.get(self.url('historial/')).status_code, (401, 403))

    def test_el_historial_no_se_puede_modificar_por_la_api(self):
        self.c.post(f'{F}{self.f.pk}/anular/', {'motivo': 'x'}, format='json')
        for metodo in ('post', 'put', 'patch', 'delete'):
            self.assertIn(getattr(self.c, metodo)(self.url('historial/'), {}, format='json').status_code, (404, 405), metodo)
        self.assertEqual(self.f.historial.count(), 1)

    def test_el_historial_se_va_con_la_factura_borrador_pero_no_con_las_ediciones(self):
        f = self.borrador()
        self.c.patch(f'{F}{f.pk}/', {'titulo': 'Otro'}, format='json')
        self.assertEqual(self.acciones(f), ['CREADA', 'EDITADA'])
