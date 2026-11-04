"""Portal del cliente: enlace seguro, ver sus OT, aprobar artes (G4) y firmar el acta."""
from datetime import timedelta

from django.core.files.base import ContentFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.desempeno.models import Notificacion
from .models import Acta, ArchivoOrden, EnlaceCliente, EventoOrden, OrdenArea, OrdenTrabajo
from .tests import MEDIA, Base

FIRMA = 'data:image/png;base64,iVBORw0KGgo='


@override_settings(MEDIA_ROOT=MEDIA)
class PortalTests(Base):
    def setUp(self):
        super().setUp()
        self.ot = OrdenTrabajo.objects.create(titulo='Brochure', cliente=self.cliente, numero='OT-26-0500', estado='EN_PRODUCCION',
                                              asesor_comercial=self.erlin, monto=10000)
        self.oa = OrdenArea.objects.create(orden=self.ot, area='DIS', que_produce='Brochure tríptico', estado='EN_APROBACION',
                                           responsable=self.daniel, g4_ronda=1)
        self.arte = ArchivoOrden.objects.create(orden=self.ot, oa=self.oa, categoria='ARTE', nombre_original='brochure-v1.pdf',
                                                tipo='application/pdf', archivo=ContentFile(b'%PDF-1.4', name='b.pdf'))
        self.interno = ArchivoOrden.objects.create(orden=self.ot, categoria='COMPROBANTE', nombre_original='pago.pdf', tipo='application/pdf',
                                                   archivo=ContentFile(b'%PDF', name='p.pdf'))
        otro = OrdenTrabajo.objects.create(titulo='De otro cliente', cliente=self.cliente.__class__.objects.create(nombre='Otro'), numero='OT-26-0501')
        self.ajeno = ArchivoOrden.objects.create(orden=otro, categoria='ARTE', nombre_original='x.pdf', archivo=ContentFile(b'x', name='x.pdf'))

    def enlace(self, quien=None, **datos):
        self.como(quien or self.erlin)
        r = self.c.post(f'/api/operaciones/ordenes/{self.ot.pk}/enlaces-cliente/', datos, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()['url'].rsplit('/portal/', 1)[1]

    def test_solo_quien_lleva_la_ot_crea_enlaces_y_se_guarda_la_huella(self):
        self.como(self.ashley)
        self.assertEqual(self.c.post(f'/api/operaciones/ordenes/{self.ot.pk}/enlaces-cliente/', {}, format='json').status_code, 403)
        token = self.enlace()
        self.assertFalse(EnlaceCliente.objects.filter(huella=token).exists())  # nunca el enlace en claro
        self.assertEqual(len(self.c.get(f'/api/operaciones/ordenes/{self.ot.pk}/enlaces-cliente/').json()), 1)

    def test_el_cliente_ve_su_ot_y_solo_los_artes(self):
        token = self.enlace()
        p = APIClient()
        d = p.get(f'/api/portal/{token}/').json()
        self.assertEqual(d['cliente'], 'ABAMON')
        ot = d['ordenes'][0]
        self.assertEqual(ot['estado'], 'En producción')
        self.assertNotIn('monto', ot)
        self.assertEqual(ot['por_aprobar'][0]['archivos'][0]['nombre'], 'brochure-v1.pdf')
        self.assertEqual(p.get(f'/api/portal/{token}/archivos/{self.arte.pk}/').status_code, 200)
        self.assertEqual(p.get(f'/api/portal/{token}/archivos/{self.interno.pk}/').status_code, 404)  # comprobante interno
        self.assertEqual(p.get(f'/api/portal/{token}/archivos/{self.ajeno.pk}/').status_code, 404)    # de otro cliente
        self.assertEqual(p.get('/api/portal/inventado/').status_code, 404)
        self.assertEqual(EnlaceCliente.objects.get().usos, 1)

    def test_aprobar_y_pedir_cambios(self):
        token = self.enlace()
        p = APIClient()
        self.assertEqual(p.post(f'/api/portal/{token}/aprobar/{self.oa.pk}/', {'aprobado': False, 'nombre': 'Ana Cliente'}, format='json').status_code, 400)
        r = p.post(f'/api/portal/{token}/aprobar/{self.oa.pk}/', {'aprobado': False, 'nombre': 'Ana Cliente', 'comentario': 'Cambiar el logo'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.oa.refresh_from_db()
        self.assertEqual((self.oa.estado, self.oa.g4_aprobado), ('EN_EJECUCION', False))
        self.assertTrue(Notificacion.objects.filter(destinatario=self.daniel, titulo__contains='Cambios pedidos').exists())
        self.assertEqual(p.post(f'/api/portal/{token}/aprobar/{self.oa.pk}/', {'aprobado': True, 'nombre': 'Ana Cliente'}, format='json').status_code, 400)
        OrdenArea.objects.filter(pk=self.oa.pk).update(estado='EN_APROBACION', g4_ronda=2)
        r = p.post(f'/api/portal/{token}/aprobar/{self.oa.pk}/', {'aprobado': True, 'nombre': 'Ana Cliente'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.oa.refresh_from_db()
        self.assertTrue(self.oa.g4_aprobado)
        self.assertEqual(self.oa.g4_canales, ['Portal del cliente'])
        self.assertTrue(EventoOrden.objects.filter(orden=self.ot, texto__contains='aprobó en el portal').exists())

    def test_firmar_el_acta(self):
        acta = Acta.objects.create(orden=self.ot, items=[{'descripcion': '500 brochures', 'cantidad': 500}])
        token = self.enlace()
        p = APIClient()
        datos = {'nombre': 'Ana Cliente', 'conformidad': 'CONFORME', 'firma': FIRMA}
        self.assertEqual(p.post(f'/api/portal/{token}/actas/{acta.pk}/firmar/', datos, format='json').status_code, 400)  # sin G5
        Acta.objects.filter(pk=acta.pk).update(liberada_por=self.willian, liberada_fecha=timezone.now())
        self.assertEqual(p.post(f'/api/portal/{token}/actas/{acta.pk}/firmar/', {**datos, 'firma': 'x'}, format='json').status_code, 400)
        r = p.post(f'/api/portal/{token}/actas/{acta.pk}/firmar/', datos, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.ot.refresh_from_db()
        self.assertEqual((self.ot.estado, self.ot.recibido_por), ('ENTREGADA', 'Ana Cliente'))
        self.assertEqual(p.post(f'/api/portal/{token}/actas/{acta.pk}/firmar/', datos, format='json').status_code, 400)

    def test_vencido_revocado_y_solo_una_ot(self):
        token = self.enlace()
        e = EnlaceCliente.objects.get()
        self.como(self.erlin)
        self.assertEqual(self.c.post(f'/api/operaciones/enlaces-cliente/{e.pk}/revocar/').status_code, 200)
        self.assertEqual(APIClient().get(f'/api/portal/{token}/').status_code, 404)
        token = self.enlace()
        EnlaceCliente.objects.filter(revocado=False).update(vence=timezone.now() - timedelta(minutes=1))
        self.assertEqual(APIClient().get(f'/api/portal/{token}/').status_code, 404)
        OrdenTrabajo.objects.create(titulo='Otra del mismo cliente', cliente=self.cliente, numero='OT-26-0502')
        token = self.enlace()
        self.assertEqual(len(APIClient().get(f'/api/portal/{token}/').json()['ordenes']), 1)  # solo esta OT
        token = self.enlace(todas=True)
        self.assertEqual(len(APIClient().get(f'/api/portal/{token}/').json()['ordenes']), 2)
