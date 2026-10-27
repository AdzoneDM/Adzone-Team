"""Pruebas: OT Maestra y Órdenes de Área (formatos ADZONE), almacén, Cashflow, proyectos, tiempo, finanzas y automatizaciones."""
import json
import os
import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.automatizaciones.models import Regla
from apps.core.models import Departamento
from apps.desempeno.models import Notificacion, Tarea
from apps.finanzas.models import Factura, Gasto
from apps.organizacion.models import PuestoDeTrabajo
from apps.tiempo.models import RegistroTiempo
from .formatos import AREAS, G0, G5_ACTA, VALIDACION_FINAL, VERIFICACION_TRASPASO
from .models import Cliente, OrdenArea, OrdenTrabajo, Proyecto

MEDIA = tempfile.mkdtemp()
HOY = timezone.localdate


@override_settings(MEDIA_ROOT=MEDIA, AUTOMATIZACIONES_SINCRONO=True)
class Base(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        d = lambda n: Departamento.objects.create(nombre=n)  # noqa: E731
        self.imp, self.mkt, self.adm = d('Impresión'), d('Marketing'), d('Administración')
        p_dir = PuestoDeTrabajo.objects.create(nombre='Director', departamento=d('Gerencia'))
        p_omar = PuestoDeTrabajo.objects.create(nombre='Gerente de Impresión', departamento=self.imp, supervisor=p_dir)
        p_daniel = PuestoDeTrabajo.objects.create(nombre='Operador', departamento=self.imp, supervisor=p_omar)
        p_vladi = PuestoDeTrabajo.objects.create(nombre='Gerente de Marketing', departamento=self.mkt, supervisor=p_dir)
        p_erlin = PuestoDeTrabajo.objects.create(nombre='Community Manager', departamento=self.mkt, supervisor=p_vladi)
        p_cont = PuestoDeTrabajo.objects.create(nombre='Contabilidad', departamento=self.adm, supervisor=p_dir)
        self.osiris = self._u('osiris', p_dir, admin=True)
        self.omar = self._u('omar', p_omar)
        self.daniel = self._u('daniel', p_daniel)
        self.keifri = self._u('keifri', p_daniel)
        self.vladi = self._u('vladi', p_vladi)
        self.erlin = self._u('erlin', p_erlin)
        self.ashley = self._u('ashley', p_erlin)  # compañera de Erlin, sin relación con la orden
        self.willian = self._u('willian', p_cont)
        p_coord = PuestoDeTrabajo.objects.create(nombre='Coordinadora de Producción', departamento=d('Producción'), supervisor=p_dir)
        self.yokasta = self._u('yokasta', p_coord, grupo='Coordinación')
        self.pedro = self._u('pedro', p_coord, grupo='Almacén')
        p_aud = PuestoDeTrabajo.objects.create(nombre='Editor', departamento=d('Audiovisual'), supervisor=p_dir)
        self.luis = self._u('luis', p_aud)
        self.cliente = Cliente.objects.create(nombre='ABAMON')
        self.c = APIClient()

    def _u(self, username, puesto, admin=False, grupo=None):
        u = User.objects.create_user(username, f'{username}@adzone.marketing', 'Clave-Segura-2026',
                                     first_name=username.capitalize())
        u.perfil.puesto_trabajo = puesto
        u.perfil.save()
        if grupo:
            u.groups.add(Group.objects.get_or_create(name=grupo)[0])
        if admin:
            u.is_staff = True
            u.save()
            u.groups.add(Group.objects.get_or_create(name='Administrador')[0])
        return u

    def como(self, u):
        self.c.force_authenticate(u)

    def pedir(self, quien=None, **extra):
        """Comercial (Erlin) pide una OT con diseño y luego impresión, G0 completo menos el anticipo."""
        self.como(quien or self.erlin)
        g0 = {t: True for _, t in G0}
        datos = {'titulo': 'Lona 3x2 del torneo', 'cliente': self.cliente.id, 'prioridad': 'U', 'contacto': 'Ana',
                 'fecha_requerida': (HOY() + timedelta(days=10)).isoformat(), 'monto': '9500', 'anticipo_requerido': '4750',
                 'descripcion': '2 lonas 3x2 con ojales', 'g0': g0,
                 'plan_areas': [{'area': 'DIS', 'secuencia': 1, 'que_produce': 'Arte de la lona', 'tiempo_estandar_dias': 1},
                                {'area': 'IMP', 'secuencia': 2, 'que_produce': 'Impresión de 2 lonas', 'tiempo_estandar_dias': 1}]}
        datos.update(extra)
        return self.c.post('/api/operaciones/ordenes/', datos, format='json')

    def liberada(self):
        oid = self.pedir().json()['id']
        self.como(self.willian)
        self.assertEqual(self.c.post(f'/api/operaciones/ordenes/{oid}/confirmar_anticipo/').status_code, 200)
        self.como(self.yokasta)
        r = self.c.post(f'/api/operaciones/ordenes/{oid}/liberar/')
        self.assertEqual(r.status_code, 200, r.content)
        return OrdenTrabajo.objects.get(pk=oid)

    def oa(self, orden, area):
        return orden.areas.get(area=area)

    def recibir(self, oa, quien, responsable):
        self.como(quien)
        g1 = {t: True for t in AREAS[oa.area]['g1']}
        r = self.c.post(f'/api/operaciones/areas/{oa.id}/recibir/', {'g1': g1, 'responsable': responsable.id}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        return oa.tareas.get()

    def visto_bueno(self, oa, supervisor):
        """Revisión interna del Gerente de Marketing (checklist de validación final)."""
        self.como(supervisor)
        r = self.c.post(f'/api/operaciones/areas/{oa.id}/revision_interna/', {
            'aprobar': True, 'checklist': {t: True for t in VALIDACION_FINAL}}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

    def terminar_tarea(self, tarea, ejecutor, supervisor):
        self.como(ejecutor)
        self.c.post(f'/api/desempeno/tareas/{tarea.id}/iniciar/')
        oa = tarea.oa
        if oa.requiere_g4:
            if AREAS[oa.area].get('revision_interna'):
                self.visto_bueno(oa, supervisor)
                self.como(ejecutor)
            self.assertEqual(self.c.post(f'/api/operaciones/areas/{oa.id}/enviar_aprobacion/').status_code, 200)
            r = self.c.post(f'/api/operaciones/areas/{oa.id}/registrar_g4/', {'aprobado': True, 'canales': ['WhatsApp archivado'],
                                                                              'aprobado_por': 'Ana', 'version': 'v2'}, format='json')
            self.assertEqual(r.status_code, 200, r.content)
        r = self.c.post(f'/api/desempeno/tareas/{tarea.id}/entregar/', {'evidencia_nota': 'Listo'}, format='multipart')
        self.assertEqual(r.status_code, 200, r.content)
        self.como(supervisor)
        g3 = {t: True for t in AREAS[oa.area]['g3']}
        r = self.c.post(f'/api/desempeno/tareas/{tarea.id}/validar/', {'calificacion_calidad': 5, 'g3': g3}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

    def traspasar(self, oa, quien, destino=None):
        self.como(quien)
        g2 = {t: True for t in AREAS[oa.area]['g2']}
        r = self.c.post(f'/api/operaciones/areas/{oa.id}/traspasar/', {'g2': g2, 'destino_oa': destino.id if destino else None},
                        format='json')
        self.assertEqual(r.status_code, 200, r.content)
        return oa.traspasos.get(resultado='PENDIENTE')

    def aceptar(self, traspaso, quien):
        self.como(quien)
        r = self.c.post(f'/api/operaciones/traspasos/{traspaso.id}/recibir/', {
            'aceptar': True, 'verificacion': {t: True for t in VERIFICACION_TRASPASO}}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

    def lista(self):
        """OT con diseño e impresión terminados y traspasados: lista para entregar."""
        orden = self.liberada()
        dis, imp = self.oa(orden, 'DIS'), self.oa(orden, 'IMP')
        self.terminar_tarea(self.recibir(dis, self.vladi, self.erlin), self.erlin, self.vladi)
        self.aceptar(self.traspasar(dis, self.erlin, imp), self.omar)
        self.terminar_tarea(self.recibir(imp, self.omar, self.daniel), self.daniel, self.omar)
        self.aceptar(self.traspasar(imp, self.daniel), self.yokasta)
        orden.refresh_from_db()
        return orden


class OrdenTests(Base):
    def test_solicitud_g0_y_numeracion_por_coordinacion(self):
        r = self.pedir(plan_areas=[{'area': 'XXX'}])
        self.assertEqual(r.status_code, 400)
        r = self.pedir()
        self.assertEqual(r.status_code, 201, r.content)
        d = r.json()
        self.assertIsNone(d['numero'])  # Comercial no numera
        self.assertTrue(d['solicitud'].startswith(f"S-{HOY():%y}-"))
        self.assertEqual(d['monto'], '9500.00')  # quien vendió ve el monto
        self.assertIn('Anticipo confirmado por Administración', d['g0_faltan'])  # Comercial no marca el anticipo
        self.assertTrue(Notificacion.objects.filter(destinatario=self.yokasta, tipo='ORDEN').exists())
        oid = d['id']
        self.como(self.vladi)  # un gerente de área no libera
        self.assertEqual(self.c.post(f'/api/operaciones/ordenes/{oid}/liberar/').status_code, 400)
        self.como(self.yokasta)
        r = self.c.post(f'/api/operaciones/ordenes/{oid}/liberar/')
        self.assertEqual(r.status_code, 400)
        self.assertIn('Anticipo', r.json()['detail'])
        r = self.c.post(f'/api/operaciones/ordenes/{oid}/excepcion/', {'motivo': 'Cliente de iguala'}, format='json')
        self.assertEqual(r.status_code, 400)  # solo Gerencia General
        self.como(self.osiris)
        self.assertEqual(self.c.post(f'/api/operaciones/ordenes/{oid}/excepcion/', {'motivo': 'Cliente de iguala'},
                                     format='json').status_code, 200)
        self.como(self.yokasta)
        r = self.c.post(f'/api/operaciones/ordenes/{oid}/liberar/')
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        self.assertEqual(d['numero'], f"OT-{HOY():%y}-0001")
        self.assertEqual(d['estado'], 'LIBERADA')
        self.assertEqual([a['numero'] for a in d['areas_resumen']], [f"OT-{HOY():%y}-0001-DIS", f"OT-{HOY():%y}-0001-IMP"])
        self.assertIsNotNone(d['fecha_compromiso'])
        self.assertEqual(d['colchon_pct'], 20)
        self.assertTrue(Notificacion.objects.filter(destinatario=self.vladi, titulo__contains='-DIS').exists())

    def test_rechazo_g0_vuelve_a_comercial(self):
        oid = self.pedir().json()['id']
        self.como(self.yokasta)
        self.assertEqual(self.c.post(f'/api/operaciones/ordenes/{oid}/rechazar_g0/', {}, format='json').status_code, 400)
        r = self.c.post(f'/api/operaciones/ordenes/{oid}/rechazar_g0/', {'causa': 'Faltan medidas'}, format='json')
        self.assertEqual(r.json()['estado'], 'DEVUELTA')
        self.assertTrue(Notificacion.objects.filter(destinatario=self.erlin, titulo__startswith='Devuelta en G0').exists())
        self.como(self.erlin)
        self.assertEqual(self.c.patch(f'/api/operaciones/ordenes/{oid}/', {'exclusiones': 'No incluye instalación'},
                                      format='json').status_code, 200)
        self.assertEqual(self.c.post(f'/api/operaciones/ordenes/{oid}/reenviar/').json()['estado'], 'SOLICITADA')

    def test_calcular_fecha_comprometida(self):
        self.como(self.erlin)
        r = self.c.post('/api/operaciones/ordenes/calcular/', {'prioridad': 'E', 'plan_areas': [
            {'area': 'DIS', 'secuencia': 1, 'que_produce': 'Arte', 'tiempo_estandar_dias': 2},
            {'area': 'IMP', 'secuencia': 2, 'que_produce': 'Lona', 'tiempo_estandar_dias': 1},
            {'area': 'LET', 'secuencia': 2, 'que_produce': 'Letras', 'tiempo_estandar_dias': 3}]}, format='json').json()
        self.assertEqual(Decimal(str(r['tiempo_estandar_dias'])), Decimal('5'))  # 2 + max(1, 3): en paralelo cuenta la más larga
        self.assertEqual(Decimal(str(r['aprobacion_dias'])), Decimal('2'))  # diseño requiere G4: 24 h × 2 rondas
        self.assertEqual(r['colchon_pct'], 30)  # emergencia
        self.assertEqual(Decimal(str(r['dias_habiles'])), Decimal('9.1'))

    def test_flujo_completo_g1_g4_g3_traspaso_acta_factura_cierre(self):
        orden = self.liberada()
        dis, imp = self.oa(orden, 'DIS'), self.oa(orden, 'IMP')
        # G1: solo el supervisor del área y con la lista completa
        self.como(self.omar)
        self.assertEqual(self.c.post(f'/api/operaciones/areas/{dis.id}/recibir/', {'g1': {}, 'responsable': self.erlin.id},
                                     format='json').status_code, 400)
        self.como(self.vladi)
        r = self.c.post(f'/api/operaciones/areas/{dis.id}/recibir/', {'g1': {}, 'responsable': self.erlin.id}, format='json')
        self.assertIn('Falta', r.json()['detail'])
        tarea = self.recibir(dis, self.vladi, self.erlin)
        self.assertEqual(list(tarea.pasos.values_list('texto', flat=True)), AREAS['DIS']['etapas'])
        # la siguiente área espera su turno
        self.como(self.omar)
        r = self.c.post(f'/api/operaciones/areas/{imp.id}/recibir/', {'g1': {t: True for t in AREAS['IMP']['g1']},
                                                                     'responsable': self.daniel.id}, format='json')
        self.assertIn('Primero tiene que terminar', r.json()['detail'])
        # E3/E4: aprobación del cliente por escrito
        self.como(self.erlin)
        self.c.post(f'/api/desempeno/tareas/{tarea.id}/iniciar/')
        dis.refresh_from_db()
        self.assertEqual(dis.estado, 'EN_EJECUCION')
        self.assertEqual(OrdenTrabajo.objects.get(pk=orden.pk).estado, 'EN_PRODUCCION')
        # Revisión interna antes del cliente: «si no hay revisión humana, no hay publicación»
        r = self.c.post(f'/api/operaciones/areas/{dis.id}/enviar_aprobacion/')
        self.assertIn('revisión interna', r.json()['detail'])
        self.assertEqual(self.c.post(f'/api/operaciones/areas/{dis.id}/pedir_revision/').status_code, 200)
        self.assertTrue(Notificacion.objects.filter(destinatario=self.vladi, titulo__startswith='Revisión interna').exists())
        self.assertEqual(self.c.post(f'/api/operaciones/areas/{dis.id}/revision_interna/', {'aprobar': True}, format='json').status_code, 400)
        self.como(self.vladi)
        r = self.c.post(f'/api/operaciones/areas/{dis.id}/revision_interna/', {'aprobar': True, 'checklist': {VALIDACION_FINAL[0]: True}},
                        format='json')
        self.assertIn('Falta', r.json()['detail'])
        self.c.post(f'/api/operaciones/areas/{dis.id}/revision_interna/', {'aprobar': False, 'comentario': 'El CTA no se lee'}, format='json')
        self.assertEqual(OrdenArea.objects.get(pk=dis.pk).revisiones_internas_devueltas, 1)
        self.visto_bueno(dis, self.vladi)
        self.como(self.erlin)
        self.c.post(f'/api/operaciones/areas/{dis.id}/enviar_aprobacion/')
        r = self.c.post(f'/api/operaciones/areas/{dis.id}/registrar_g4/', {'aprobado': True, 'aprobado_por': 'Ana'}, format='json')
        self.assertEqual(r.status_code, 400)  # sin canal escrito no hay aprobación
        self.c.post(f'/api/operaciones/areas/{dis.id}/registrar_g4/', {'aprobado': False, 'comentario': 'Más grande el logo'}, format='json')
        self.assertIsNone(OrdenArea.objects.get(pk=dis.pk).revision_interna_por)  # la nueva versión se revisa otra vez
        self.visto_bueno(dis, self.vladi)
        self.como(self.erlin)
        self.c.post(f'/api/operaciones/areas/{dis.id}/enviar_aprobacion/')
        r = self.c.post(f'/api/operaciones/areas/{dis.id}/registrar_g4/', {'aprobado': False, 'comentario': 'Otro color'}, format='json')
        self.assertIn('F-14', r.json()['aviso'])  # rondas agotadas
        self.visto_bueno(dis, self.vladi)
        self.como(self.erlin)
        self.c.post(f'/api/operaciones/areas/{dis.id}/enviar_aprobacion/')
        self.c.post(f'/api/operaciones/areas/{dis.id}/registrar_g4/', {'aprobado': True, 'canales': ['Correo'], 'aprobado_por': 'Ana'},
                    format='json')
        self.c.post(f'/api/desempeno/tareas/{tarea.id}/entregar/', {'evidencia_nota': 'Arte final'}, format='multipart')
        # G3 al validar
        self.como(self.vladi)
        r = self.c.post(f'/api/desempeno/tareas/{tarea.id}/validar/', {'calificacion_calidad': 5}, format='json')
        self.assertIn('G3', r.json()['detail'])
        self.c.post(f'/api/desempeno/tareas/{tarea.id}/validar/', {'calificacion_calidad': 5,
                                                                   'g3': {t: True for t in AREAS['DIS']['g3']}}, format='json')
        # G2 con doble firma
        self.como(self.erlin)
        r = self.c.post(f'/api/operaciones/areas/{dis.id}/traspasar/', {'g2': {}, 'destino_oa': imp.id}, format='json')
        self.assertEqual(r.status_code, 400)
        t = self.traspasar(dis, self.erlin, imp)
        self.assertEqual(self.c.post(f'/api/operaciones/traspasos/{t.id}/recibir/', {'aceptar': True}, format='json').status_code, 400)
        self.como(self.omar)
        r = self.c.post(f'/api/operaciones/traspasos/{t.id}/recibir/', {'aceptar': False, 'causa': 'Arte en baja resolución'},
                        format='json')
        self.assertEqual(r.json()['resultado'], 'RECHAZADO')
        dis.refresh_from_db()
        self.assertEqual((dis.estado, dis.pase_retrabajo), ('EN_EJECUCION', 1))
        self.assertEqual(Tarea.objects.get(pk=tarea.pk).estado, 'EN_PROGRESO')
        self.como(self.erlin)
        self.c.post(f'/api/desempeno/tareas/{tarea.id}/entregar/', {'evidencia_nota': 'Arte en alta'}, format='multipart')
        self.como(self.vladi)
        self.c.post(f'/api/desempeno/tareas/{tarea.id}/validar/', {'calificacion_calidad': 4,
                                                                   'g3': {t: True for t in AREAS['DIS']['g3']}}, format='json')
        self.aceptar(self.traspasar(dis, self.erlin, imp), self.omar)
        self.assertEqual(OrdenArea.objects.get(pk=dis.pk).estado, 'TERMINADA')
        # Impresión y salida a Coordinación (G5)
        self.terminar_tarea(self.recibir(imp, self.omar, self.daniel), self.daniel, self.omar)
        self.aceptar(self.traspasar(imp, self.daniel), self.yokasta)
        orden.refresh_from_db()
        self.assertEqual(orden.estado, 'LISTA')
        # Sin acta no se factura
        self.como(self.willian)
        r = self.c.post('/api/finanzas/facturas/desde_orden/', {'orden': orden.id}, format='json')
        self.assertIn('acta', r.json()['detail'])
        # Acta F-12: G5 con saldo y firma del cliente
        self.como(self.yokasta)
        acta = self.c.post(f'/api/operaciones/ordenes/{orden.id}/actas/', {'modalidad': 'INSTALACION'}, format='json').json()
        self.assertEqual(len(acta['items']), 2)
        g5 = {t: True for _, t in G5_ACTA}
        self.como(self.willian)
        r = self.c.post(f"/api/operaciones/actas/{acta['id']}/liberar/", {'g5': g5}, format='json')
        self.assertIn('debe', r.json()['detail'])  # el anticipo no cubre el saldo
        self.como(self.osiris)
        g5[dict(G5_ACTA)['saldo']] = False
        self.assertEqual(self.c.post(f"/api/operaciones/actas/{acta['id']}/liberar/", {'g5': g5}, format='json').status_code, 200)
        self.como(self.omar)  # supervisa Instalación
        r = self.c.post(f"/api/operaciones/actas/{acta['id']}/firmar/", {'cliente_nombre': 'Ana Pérez', 'conformidad': 'CONFORME'},
                        format='json')
        self.assertIn('fotográfica', r.json()['detail'])
        r = self.c.post(f"/api/operaciones/actas/{acta['id']}/firmar/", {
            'cliente_nombre': 'Ana Pérez', 'cliente_cedula': '001-0000000-1', 'conformidad': 'CONFORME',
            'firma': 'data:image/png;base64,iVBORw0KGgo=', 'verificacion': {'Medidas verificadas': True}}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        orden.refresh_from_db()
        self.assertEqual((orden.estado, orden.recibido_por), ('ENTREGADA', 'Ana Pérez'))
        # Factura y cierre G6
        self.como(self.willian)
        self.assertEqual(self.c.post(f'/api/operaciones/ordenes/{orden.id}/cerrar/').status_code, 400)  # falta factura
        fac = self.c.post('/api/finanzas/facturas/desde_orden/', {'orden': orden.id}, format='json').json()
        self.assertEqual(Decimal(fac['subtotal']), Decimal('9500'))
        self.c.post(f"/api/finanzas/facturas/{fac['id']}/emitir/", {}, format='json')
        r = self.c.post(f'/api/operaciones/ordenes/{orden.id}/cerrar/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['estado'], 'CERRADA')
        costos = self.c.get(f'/api/operaciones/ordenes/{orden.id}/costos/').json()
        self.assertEqual(Decimal(str(costos['cotizado'])), Decimal('9500'))
        ind = self.c.get('/api/operaciones/ordenes/indicadores/').json()
        dis_fila = next(f for f in ind['areas'] if f['area'] == 'DIS')
        self.assertEqual((dis_fila['terminadas'], dis_fila['traspasos_rechazados']), (1, 1))
        self.assertEqual(dis_fila['devoluciones_internas'], 1)
        self.assertEqual(dis_fila['primera_aprobacion_pct'], 0)  # se aprobó en la tercera ronda
        self.assertIsNotNone(dis_fila['brief_a_propuesta_h'])
        self.assertEqual(ind['ot']['entregadas'], 1)
        bitacora = self.c.get('/api/operaciones/ordenes/bitacora/')
        self.assertIn(orden.numero, bitacora.content.decode('utf-8'))

    def test_ventanas_de_anticipacion_del_contenido(self):
        self.como(self.erlin)
        base = {'plan_areas': [{'area': 'MKT', 'secuencia': 1, 'que_produce': 'Calendario', 'tiempo_estandar_dias': 3}]}
        for dias, nivel in ((20, 'ideal'), (11, 'seguro'), (4, 'insuficiente')):
            r = self.c.post('/api/operaciones/ordenes/calcular/', {**base, 'fecha_requerida': (HOY() + timedelta(days=dias)).isoformat()},
                            format='json').json()
            self.assertEqual(r['anticipacion']['nivel'], nivel)
        r = self.c.post('/api/operaciones/ordenes/calcular/', {'plan_areas': [{'area': 'IMP', 'secuencia': 1, 'que_produce': 'Lona'}],
                                                               'fecha_requerida': HOY().isoformat()}, format='json').json()
        self.assertIsNone(r['anticipacion'])  # la regla es del contenido (Marketing, Diseño, Audiovisuales)

    def test_cronograma_de_produccion_cargado_y_horas_a_la_tarea(self):
        from .models import TiempoEstandar
        logo = TiempoEstandar.objects.get(area='DIS', trabajo='Logotipo corporativo')
        self.assertEqual((logo.horas, logo.dias), (Decimal('8.00'), Decimal('1.00')))
        self.assertEqual(TiempoEstandar.objects.get(area='AUD', trabajo__startswith='Plano').dias, Decimal('10.00'))
        self.assertGreaterEqual(TiempoEstandar.objects.filter(area__in=['DIS', 'AUD']).count(), 26)
        plan = [{'area': 'DIS', 'secuencia': 1, 'que_produce': '3 flyers', 'trabajo': 'Flyer o volante publicitario', 'cantidad': 3,
                 'tiempo_estandar_dias': 0.38, 'horas_estimadas': 3}]
        oid = self.pedir(plan_areas=plan).json()['id']
        self.como(self.willian)
        self.c.post(f'/api/operaciones/ordenes/{oid}/confirmar_anticipo/')
        self.como(self.yokasta)
        self.c.post(f'/api/operaciones/ordenes/{oid}/liberar/')
        oa = OrdenTrabajo.objects.get(pk=oid).areas.get()
        self.assertEqual(oa.horas_estimadas, Decimal('3.00'))
        self.assertEqual(self.recibir(oa, self.vladi, self.erlin).horas_estimadas, Decimal('3.00'))

    def test_automatizacion_de_handoff_entre_areas(self):
        Regla.objects.create(nombre='Handoff', evento='TRASPASO', condiciones={'area': 'IMP'}, accion='AVISAR',
                             parametros={'a': ['jefes'], 'titulo': 'Llega {titulo}', 'mensaje': '{entrega} → {recibe}'})
        orden = self.liberada()
        dis, imp = self.oa(orden, 'DIS'), self.oa(orden, 'IMP')
        self.terminar_tarea(self.recibir(dis, self.vladi, self.erlin), self.erlin, self.vladi)
        self.traspasar(dis, self.erlin, imp)
        self.assertTrue(Notificacion.objects.filter(destinatario=self.omar, titulo__startswith='Llega').exists())

    def test_anticipo_por_factura_y_pago_marca_g0(self):
        oid = self.pedir().json()['id']
        self.como(self.willian)
        fac = self.c.post('/api/finanzas/facturas/desde_orden/', {'orden': oid, 'anticipo': True}, format='json').json()
        self.assertTrue(fac['es_anticipo'])
        self.assertEqual(Decimal(fac['subtotal']), Decimal('4750'))
        self.c.post(f"/api/finanzas/facturas/{fac['id']}/emitir/", {}, format='json')
        self.c.post(f"/api/finanzas/facturas/{fac['id']}/pagos/", {'monto': fac['total']}, format='json')
        orden = OrdenTrabajo.objects.get(pk=oid)
        self.assertTrue(orden.anticipo_confirmado)
        self.assertEqual(orden.g0['Anticipo confirmado por Administración'], True)

    def test_quien_ve_que(self):
        oid = self.liberada().id

        def ids(u):
            self.como(u)
            return [o['id'] for o in self.c.get('/api/operaciones/ordenes/').json()]
        self.assertIn(oid, ids(self.erlin))    # la vendió
        self.assertIn(oid, ids(self.keifri))   # tiene un área de su departamento (IMP)
        self.assertIn(oid, ids(self.willian))  # Administración ve todo
        self.assertIn(oid, ids(self.yokasta))  # Coordinación ve todo
        self.assertIn(oid, ids(self.omar))     # supervisa Impresión
        self.assertNotIn(oid, ids(self.luis))  # Audiovisual, sin relación
        self.como(self.keifri)
        self.assertIsNone(self.c.get(f'/api/operaciones/ordenes/{oid}/').json()['monto'])  # el operador no ve precios

    def test_cancelar_pide_motivo_y_cancela_areas(self):
        orden = self.liberada()
        self.recibir(self.oa(orden, 'DIS'), self.vladi, self.erlin)
        self.como(self.erlin)
        self.assertEqual(self.c.post(f'/api/operaciones/ordenes/{orden.id}/cancelar/', {'motivo': 'x'}, format='json').status_code, 403)
        self.como(self.yokasta)
        self.assertEqual(self.c.post(f'/api/operaciones/ordenes/{orden.id}/cancelar/', {}, format='json').status_code, 400)
        r = self.c.post(f'/api/operaciones/ordenes/{orden.id}/cancelar/', {'motivo': 'El cliente desistió'}, format='json')
        self.assertEqual(r.json()['estado'], 'CANCELADA')
        self.assertEqual(set(orden.areas.values_list('estado', flat=True)), {'CANCELADA'})
        self.assertEqual(orden.tareas.get().estado, 'CANCELADA')

    def test_solicitud_de_cambio_cobrable(self):
        orden = self.liberada()
        self.como(self.erlin)
        r = self.c.post(f'/api/operaciones/ordenes/{orden.id}/cambios/', {
            'tipo': 'CAMBIO', 'clasificacion': ['Cambio de medidas'], 'descripcion': 'Ahora la lona es 4x2', 'monto_cliente': '2000',
            'impacto': {'fecha': {'antes': str(orden.fecha_compromiso), 'despues': str(orden.fecha_compromiso + timedelta(days=2))}}},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        cid = r.json()['id']
        self.como(self.yokasta)
        self.assertEqual(self.c.post(f'/api/operaciones/cambios/{cid}/autorizar/', {}, format='json').status_code, 400)
        r = self.c.post(f'/api/operaciones/cambios/{cid}/autorizar/', {'autorizaciones': {
            'Aprobación del cliente por escrito adjunta': True}}, format='json')
        self.assertEqual(r.json()['estado'], 'AUTORIZADA')
        orden.refresh_from_db()
        self.assertEqual(orden.monto, Decimal('11500'))

    def test_comentario_con_mencion_avisa(self):
        orden = self.liberada()
        self.recibir(self.oa(orden, 'DIS'), self.vladi, self.erlin)
        self.como(self.keifri)
        r = self.c.post(f'/api/operaciones/ordenes/{orden.id}/comentarios/', {'texto': '@willian ¿ya se facturó el anticipo?'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertTrue(Notificacion.objects.filter(destinatario=self.willian, tipo='MENCION').exists())
        self.assertTrue(Notificacion.objects.filter(destinatario=self.erlin, titulo__startswith='Comentario').exists())

    def test_archivos_protegidos_y_tipos_permitidos(self):
        orden = self.liberada()
        self.como(self.erlin)
        oid = orden.id
        malo = SimpleUploadedFile('virus.exe', b'MZ', content_type='application/octet-stream')
        self.assertEqual(self.c.post(f'/api/operaciones/ordenes/{oid}/archivos/', {'archivos': [malo]}, format='multipart').status_code, 400)
        arte = SimpleUploadedFile('arte.pdf', b'%PDF-1.4 arte', content_type='application/pdf')
        r = self.c.post(f'/api/operaciones/ordenes/{oid}/archivos/', {'archivos': [arte], 'oa': self.oa(orden, 'DIS').id,
                                                                      'categoria': 'APROBACION'}, format='multipart')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()[0]['categoria'], 'APROBACION')
        url = r.json()[0]['url']
        self.assertEqual(self.c.get(url).status_code, 200)
        self.como(self.luis)
        self.assertEqual(self.c.get(url).status_code, 404)

    def test_resumen_y_catalogo(self):
        self.liberada()
        self.como(self.omar)
        cat = self.c.get('/api/operaciones/ordenes/catalogo/').json()
        self.assertEqual({a['codigo'] for a in cat['areas']} >= {'DIS', 'MKT', 'AUD', 'POD', 'IMP', 'LET', 'FAB', 'EVT', 'SOF', 'CCT'}, True)
        self.assertIn('IMP', cat['mis_areas'])
        self.assertEqual(len(cat['g0']), 11)
        r = self.c.get('/api/operaciones/ordenes/resumen/').json()
        self.assertEqual(r['abiertas'], 1)
        self.assertEqual(r['por_area'], {'DIS': 1, 'IMP': 1})


class AlmacenTests(Base):
    def test_vale_autoriza_despacha_descuenta_y_devuelve(self):
        from apps.almacen.models import Material
        lona = Material.objects.create(codigo='LON-13', nombre='Lona 13 oz', unidad='pie²', existencia=Decimal('100'),
                                       punto_reposicion=Decimal('40'), costo_unitario=Decimal('12'))
        orden = self.liberada()
        imp = self.oa(orden, 'IMP')
        self.como(self.daniel)
        self.assertEqual(self.c.post('/api/almacen/vales/', {'oa': imp.id, 'lineas': [{'material': lona.id, 'cantidad': 70}]},
                                     format='json').status_code, 400)  # el área todavía no recibió
        self.recibir(self.oa(orden, 'DIS'), self.vladi, self.erlin)
        OrdenArea.objects.filter(pk=imp.pk).update(estado='RECIBIDA', responsable=self.daniel)
        self.como(self.daniel)
        r = self.c.post('/api/almacen/vales/', {'oa': imp.id, 'lineas': [{'material': lona.id, 'cantidad': 70}]}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        vale = r.json()
        self.assertIsNone(vale['costo_total'])  # el operador no ve costos
        self.como(self.pedro)
        self.assertEqual(self.c.post(f"/api/almacen/vales/{vale['id']}/despachar/", {}, format='json').status_code, 400)  # sin autorizar
        self.como(self.yokasta)
        self.c.post(f"/api/almacen/vales/{vale['id']}/autorizar/")
        self.como(self.pedro)
        linea = vale['lineas'][0]['id']
        r = self.c.post(f"/api/almacen/vales/{vale['id']}/despachar/", {'lineas': [{'id': linea, 'cantidad_despachada': 70, 'lote': 'L-9'}]},
                        format='json')
        self.assertEqual(r.json()['estado'], 'DESPACHADO')
        lona.refresh_from_db()
        self.assertEqual(lona.existencia, Decimal('30'))
        self.assertTrue(Notificacion.objects.filter(titulo='Material bajo el punto de reposición').exists())
        self.assertEqual(self.c.post(f"/api/almacen/vales/{vale['id']}/recibir/").status_code, 400)  # no firma quien despachó
        self.como(self.daniel)
        self.assertEqual(self.c.post(f"/api/almacen/vales/{vale['id']}/recibir/").status_code, 200)
        self.como(self.pedro)
        r = self.c.post(f"/api/almacen/vales/{vale['id']}/cerrar/", {'lineas': [
            {'id': linea, 'cantidad_devuelta': 10, 'desperdicio': 5}]}, format='json')
        self.assertIn('causa', r.json()['detail'])
        r = self.c.post(f"/api/almacen/vales/{vale['id']}/cerrar/", {'lineas': [
            {'id': linea, 'cantidad_devuelta': 10, 'desperdicio': 5, 'causa_desperdicio': 'Corte mal medido'}]}, format='json')
        self.assertEqual(Decimal(str(r.json()['costo_total'])), Decimal('720'))  # (70 - 10) × 12
        lona.refresh_from_db()
        self.assertEqual(lona.existencia, Decimal('40'))
        from .servicios_ot import costos_oa
        self.assertEqual(costos_oa(imp)['materiales'], Decimal('720.00'))

    def test_entrada_promedia_costo(self):
        from apps.almacen.models import Material
        m = Material.objects.create(codigo='VIN', nombre='Vinil', existencia=Decimal('10'), costo_unitario=Decimal('10'))
        self.como(self.daniel)
        self.assertEqual(self.c.post(f'/api/almacen/materiales/{m.id}/entrada/', {'cantidad': 10}, format='json').status_code, 400)
        self.como(self.pedro)
        r = self.c.post(f'/api/almacen/materiales/{m.id}/entrada/', {'cantidad': 10, 'costo_unitario': 20}, format='json').json()
        self.assertEqual((Decimal(r['existencia']), Decimal(r['costo_unitario'])), (Decimal('20'), Decimal('15')))


class CashflowTests(Base):
    """El conector en modo prueba (simulador): mismas reglas, sin tocar Cashflow."""
    def test_factura_fiscal_y_pagos_desde_cashflow(self):
        from apps.integraciones.cashflow import servicios as cf
        from apps.integraciones.models import SincronizacionCashflow
        self.cliente.rnc = '101-00000-1'
        self.cliente.save()
        orden = self.lista()
        orden.estado = 'ENTREGADA'
        orden.save()
        self.como(self.willian)
        fac = self.c.post('/api/finanzas/facturas/desde_orden/', {'orden': orden.id}, format='json').json()
        r = self.c.post(f"/api/finanzas/facturas/{fac['id']}/cashflow/")
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        self.assertEqual(d['estado'], 'EMITIDA')
        self.assertTrue(d['ncf'].startswith('E31'))  # crédito fiscal (empresa con RNC)
        self.assertTrue(d['cashflow_id'])
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.cashflow_id)
        self.assertEqual(self.c.post(f"/api/finanzas/facturas/{fac['id']}/cashflow/").status_code, 400)  # no se duplica
        f = Factura.objects.get(pk=fac['id'])
        cf.conexion().pagar(f.cashflow_id, f.total, 'TRANSFERENCIA')
        r = self.c.post(f"/api/finanzas/facturas/{fac['id']}/cashflow_actualizar/").json()
        self.assertEqual((r['pagos_nuevos'], r['estado']), (1, 'PAGADA'))
        self.assertEqual(self.c.post(f"/api/finanzas/facturas/{fac['id']}/cashflow_actualizar/").json()['pagos_nuevos'], 0)
        estado = self.c.get('/api/integraciones/cashflow/').json()
        self.assertEqual(estado['modo'], 'prueba')
        self.assertFalse(estado['clave_configurada'])
        self.assertGreater(len(estado['bitacora']), 3)
        self.assertFalse(any('KEY' in s.detalle.upper() for s in SincronizacionCashflow.objects.all()))
        self.como(self.erlin)
        self.assertEqual(self.c.get('/api/integraciones/cashflow/').status_code, 403)

    def test_cliente_real_sin_clave_no_llama(self):
        from apps.integraciones.cashflow.cliente import CashflowAPI, CashflowError
        with override_settings(CASHFLOW_API_KEY=''):
            with self.assertRaises(CashflowError):
                CashflowAPI().llamar('probar')


class ProyectoTests(Base):
    def test_gerente_crea_proyecto_y_colaborador_no(self):
        datos = {'nombre': 'Torneo 2027', 'cliente': self.cliente.id, 'departamento': self.mkt.id, 'miembros': [self.erlin.id],
                 'fecha_inicio': HOY().isoformat(), 'fecha_fin': (HOY() + timedelta(days=60)).isoformat(), 'presupuesto': '150000'}
        self.como(self.erlin)
        self.assertEqual(self.c.post('/api/operaciones/proyectos/', datos, format='json').status_code, 403)
        self.como(self.omar)  # otro departamento
        self.assertEqual(self.c.post('/api/operaciones/proyectos/', datos, format='json').status_code, 403)
        self.como(self.vladi)
        r = self.c.post('/api/operaciones/proyectos/', datos, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        pid = r.json()['id']
        self.assertTrue(r.json()['codigo'].startswith('PRY-'))
        self.como(self.erlin)
        r = self.c.get(f'/api/operaciones/proyectos/{pid}/')
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()['presupuesto'])  # el miembro no ve el dinero
        self.assertTrue(Notificacion.objects.filter(destinatario=self.erlin, tipo='PROYECTO').exists())

    def test_tareas_del_proyecto_y_fechas(self):
        p = Proyecto.objects.create(nombre='Web', cliente=self.cliente, departamento=self.mkt, responsable=self.vladi)
        self.como(self.vladi)
        r = self.c.post('/api/desempeno/tareas/', {'titulo': 'Maqueta', 'colaborador': self.erlin.id, 'proyecto': p.id,
                                                    'fecha_inicio': (HOY() + timedelta(days=5)).isoformat(),
                                                    'fecha_limite': (HOY() + timedelta(days=2)).isoformat()}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.c.post('/api/desempeno/tareas/', {'titulo': 'Maqueta', 'colaborador': self.erlin.id, 'proyecto': p.id,
                                                    'horas_estimadas': '6', 'fecha_inicio': HOY().isoformat(),
                                                    'fecha_limite': (HOY() + timedelta(days=2)).isoformat()}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        d = self.c.get(f'/api/operaciones/proyectos/{p.id}/detalle/').json()
        self.assertEqual(len(d['tareas']), 1)
        self.assertIn('finanzas', d)  # el responsable ve la rentabilidad


class TiempoTests(Base):
    def test_cronometro_uno_a_la_vez_y_empieza_la_tarea(self):
        orden = self.liberada()
        tarea = self.recibir(self.oa(orden, 'DIS'), self.vladi, self.daniel)
        self.como(self.daniel)
        r = self.c.post('/api/tiempo/iniciar/', {'tarea': tarea.id}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        tarea.refresh_from_db()
        self.assertEqual(tarea.estado, 'EN_PROGRESO')
        primero = RegistroTiempo.objects.get()
        self.assertEqual(primero.orden, orden)  # hereda la orden de la tarea
        RegistroTiempo.objects.filter(pk=primero.pk).update(inicio=timezone.now() - timedelta(minutes=50))
        r = self.c.post('/api/tiempo/iniciar/', {'descripcion': 'Reunión de producción'}, format='json')
        self.assertEqual(r.json()['detenido']['minutos'], 50)
        self.assertEqual(RegistroTiempo.objects.filter(fin__isnull=True).count(), 1)
        self.c.post('/api/tiempo/detener/')
        self.assertIsNone(self.c.get('/api/tiempo/activo/').json()['activo'])

    def test_no_se_anota_tiempo_en_tareas_ajenas_ni_en_el_futuro(self):
        orden = self.liberada()
        tarea = self.recibir(self.oa(orden, 'DIS'), self.vladi, self.daniel)
        self.como(self.erlin)
        r = self.c.post('/api/tiempo/iniciar/', {'tarea': tarea.id}, format='json')
        self.assertEqual(r.status_code, 403)
        r = self.c.post('/api/tiempo/registros/', {'minutos': 90, 'fecha': (HOY() + timedelta(days=1)).isoformat(),
                                                   'descripcion': 'x'}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.c.post('/api/tiempo/registros/', {'minutos': 90, 'descripcion': 'Diseño de artes'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        semana = self.c.get('/api/tiempo/semana/').json()
        self.assertEqual(semana['total'], 90)
        self.assertEqual(semana['capacidad'], 44 * 60)

    def test_carga_del_equipo(self):
        Tarea.objects.create(titulo='Grande', colaborador=self.daniel, fecha_limite=HOY(), horas_estimadas=Decimal('50'))
        self.como(self.omar)
        filas = {f['id']: f for f in self.c.get('/api/tiempo/equipo/').json()['personas']}
        self.assertGreater(filas[self.daniel.id]['carga_pct'], 100)  # sobrecargado
        self.como(self.daniel)
        self.assertEqual(self.c.get('/api/tiempo/equipo/').status_code, 403)


class FinanzasTests(Base):
    def test_solo_finanzas_entra(self):
        self.como(self.vladi)
        self.assertEqual(self.c.get('/api/finanzas/facturas/').status_code, 403)
        self.como(self.willian)  # Administración
        self.assertEqual(self.c.get('/api/finanzas/facturas/').status_code, 200)

    def test_ciclo_cotizacion_orden_factura_cobro(self):
        self.como(self.willian)
        r = self.c.post('/api/finanzas/cotizaciones/', {'cliente': self.cliente.id, 'titulo': 'Lonas del torneo', 'lineas': [
            {'descripcion': 'Lona 3x2', 'cantidad': 2, 'precio': '4000'},
            {'descripcion': 'Instalación', 'cantidad': 1, 'precio': '1500', 'aplica_itbis': False}]}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        cot = r.json()
        self.assertEqual(Decimal(cot['subtotal']), Decimal('9500'))
        self.assertEqual(Decimal(cot['itbis']), Decimal('1440'))  # 18% de 8,000
        self.assertEqual(Decimal(cot['total']), Decimal('10940'))
        r = self.c.post(f"/api/finanzas/cotizaciones/{cot['id']}/aprobar/", {'crear_orden': True}, format='json')
        orden = OrdenTrabajo.objects.get(pk=r.json()['orden_creada']['id'])
        self.assertEqual((orden.monto, orden.estado, orden.cotizacion_id), (Decimal('9500'), 'SOLICITADA', cot['id']))
        self.assertTrue(orden.g0['Cotización aprobada por escrito (adjunta)'])
        r = self.c.post(f"/api/finanzas/cotizaciones/{cot['id']}/facturar/")
        fac = r.json()
        self.assertEqual(Decimal(fac['total']), Decimal('10940'))
        self.assertEqual(self.c.post(f"/api/finanzas/facturas/{fac['id']}/pagos/", {'monto': '100'}, format='json').status_code, 400)
        self.c.post(f"/api/finanzas/facturas/{fac['id']}/emitir/", {'dias_credito': 15}, format='json')
        r = self.c.post(f"/api/finanzas/facturas/{fac['id']}/pagos/", {'monto': '5470'}, format='json')
        self.assertEqual(r.json()['estado'], 'EMITIDA')
        self.assertEqual(Decimal(r.json()['saldo']), Decimal('5470'))
        r = self.c.post(f"/api/finanzas/facturas/{fac['id']}/pagos/", {'monto': '9999'}, format='json')
        self.assertEqual(r.status_code, 400)  # no se cobra de más
        r = self.c.post(f"/api/finanzas/facturas/{fac['id']}/pagos/", {'monto': '5470'}, format='json')
        self.assertEqual(r.json()['estado'], 'PAGADA')

    def test_por_facturar_y_rentabilidad(self):
        p = Proyecto.objects.create(nombre='Torneo', cliente=self.cliente, departamento=self.imp)
        orden = OrdenTrabajo.objects.create(titulo='Lonas', cliente=self.cliente, departamento=self.imp, numero='OT-26-0099',
                                            proyecto=p, estado='ENTREGADA', monto=Decimal('10000'), solicitada_por=self.erlin)
        self.daniel.perfil.costo_hora = Decimal('200')
        self.daniel.perfil.save()
        RegistroTiempo.objects.create(usuario=self.daniel, proyecto=p, inicio=timezone.now() - timedelta(hours=5),
                                      fin=timezone.now(), minutos=300)
        Gasto.objects.create(concepto='Lona', monto=Decimal('2500'), proyecto=p)
        self.como(self.willian)
        resumen = self.c.get('/api/finanzas/resumen/').json()
        self.assertIn(orden.numero, [x['numero'] for x in resumen['por_facturar']])
        fac = self.c.post('/api/finanzas/facturas/desde_orden/', {'orden': orden.id}, format='json').json()
        self.assertEqual(self.c.post('/api/finanzas/facturas/desde_orden/', {'orden': orden.id}, format='json').status_code, 400)
        self.c.post(f"/api/finanzas/facturas/{fac['id']}/emitir/", {}, format='json')
        fila = self.c.get('/api/finanzas/rentabilidad/').json()['filas'][0]
        self.assertEqual(Decimal(str(fila['facturado'])), Decimal('10000'))
        self.assertEqual(Decimal(str(fila['costo_horas'])), Decimal('1000'))
        self.assertEqual(Decimal(str(fila['margen'])), Decimal('6500'))
        self.assertNotIn(orden.numero, [x['numero'] for x in self.c.get('/api/finanzas/resumen/').json()['por_facturar']])

    def test_factura_vencida_avisa_una_sola_vez(self):
        from apps.automatizaciones.motor import revisar_vencimientos
        f = Factura.objects.create(cliente=self.cliente, estado='EMITIDA', total=Decimal('1000'),
                                   vencimiento=HOY() - timedelta(days=3))
        revisar_vencimientos()
        revisar_vencimientos()
        self.assertEqual(Notificacion.objects.filter(destinatario=self.willian, titulo=f"Factura vencida: {f.numero}").count(), 1)


class AutomatizacionTests(Base):
    def test_webhook_a_n8n_firmado(self):
        Regla.objects.create(nombre='A n8n', evento='ORDEN_CREADA', accion='WEBHOOK',
                             parametros={'url': 'https://n8n.adzone.marketing/webhook/ordenes'})
        enviados = []

        class Resp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def falso(pedido, timeout):
            enviados.append(pedido)
            return Resp()
        with override_settings(AUTOMATIZACIONES_SECRETO='clave'), mock.patch('urllib.request.urlopen', falso):
            self.pedir()
        self.assertEqual(len(enviados), 1)
        cuerpo = json.loads(enviados[0].data)
        self.assertEqual(cuerpo['evento'], 'ORDEN_CREADA')
        self.assertEqual(cuerpo['datos']['cliente'], 'ABAMON')
        self.assertIn('X-adzone-firma', enviados[0].headers)

    def test_crear_tarea_por_regla_y_regla_rota_no_frena(self):
        Regla.objects.create(nombre='Brief', evento='ORDEN_CREADA', condiciones={'area': 'IMP'}, accion='CREAR_TAREA',
                             parametros={'titulo': 'Revisar arte de {numero}', 'asignar': 'usuario', 'usuario_id': self.daniel.id, 'dias': 1})
        Regla.objects.create(nombre='Rota', evento='ORDEN_CREADA', accion='CREAR_TAREA', parametros={'titulo': 'x', 'dias': 'muchos'})
        r = self.pedir()
        self.assertEqual(r.status_code, 201)
        self.assertTrue(Tarea.objects.filter(colaborador=self.daniel, titulo__startswith='Revisar arte de S-').exists())

    def test_solo_la_direccion_configura(self):
        self.como(self.omar)
        self.assertEqual(self.c.get('/api/automatizaciones/reglas/').status_code, 403)
        self.como(self.osiris)
        r = self.c.post('/api/automatizaciones/reglas/', {'nombre': 'x', 'evento': 'ORDEN_CREADA', 'accion': 'WEBHOOK',
                                                          'parametros': {'url': 'ftp://algo'}}, format='json')
        self.assertEqual(r.status_code, 400)


class BuscarTests(Base):
    def test_busca_solo_lo_que_puede_ver(self):
        self.pedir()
        self.como(self.erlin)
        tipos = {x['tipo'] for x in self.c.get('/api/operaciones/buscar/?q=lona').json()}
        self.assertIn('orden', tipos)
        self.como(self.luis)
        self.assertNotIn('orden', {x['tipo'] for x in self.c.get('/api/operaciones/buscar/?q=lona').json()})


class OrganigramaTests(TestCase):
    def test_organigrama_2026_renombra_crea_y_encadena(self):
        from django.core.management import call_command
        call_command('departamentos_oficiales', '--aplicar', stdout=open(os.devnull, 'w'))
        ceo = PuestoDeTrabajo.objects.create(nombre='CEO / Director General', departamento=Departamento.objects.get(nombre='Gerencia'))
        viejo = PuestoDeTrabajo.objects.create(nombre='Supervisor de Call Center', departamento=Departamento.objects.get(nombre='Call Center'),
                                               supervisor=ceo)
        call_command('organigrama_2026', stdout=open(os.devnull, 'w'))  # sin --aplicar no cambia nada
        self.assertFalse(PuestoDeTrabajo.objects.filter(nombre='Director Comercial').exists())
        call_command('organigrama_2026', '--aplicar', stdout=open(os.devnull, 'w'))
        viejo.refresh_from_db()
        self.assertEqual(viejo.nombre, 'Gerente de Call Center')  # la persona se queda en su puesto renombrado
        self.assertEqual(PuestoDeTrabajo.objects.get(nombre='Encargado de Ventas y Cuentas').supervisor.nombre, 'Director Comercial')
        self.assertEqual(PuestoDeTrabajo.objects.get(nombre='Community Manager').supervisor.nombre, 'Encargado de Medios Digitales')
        self.assertEqual(PuestoDeTrabajo.objects.get(nombre='Director Comercial').departamento.nombre, 'Comercial')
        soporte = PuestoDeTrabajo.objects.get(nombre='Soporte Técnico (TI)')
        self.assertIn('Atender las solicitudes de soporte', soporte.funciones_principales)  # descripción cargada
        from apps.kpis.models import KPIAsignado
        kpis = KPIAsignado.objects.filter(puesto_trabajo=soporte)
        self.assertEqual(kpis.count(), 4)
        self.assertEqual(sum(k.ponderacion for k in kpis), 100)
        herrero = KPIAsignado.objects.filter(puesto_trabajo__nombre='Herrero', es_entrada_manual=False)
        self.assertEqual(herrero.count(), 2)  # automáticos: tareas validadas y rondas
        PuestoDeTrabajo.objects.filter(pk=soporte.pk).update(funciones_principales='Escrita a mano')
        call_command('organigrama_2026', '--aplicar', stdout=open(os.devnull, 'w'))  # se puede repetir
        self.assertEqual(PuestoDeTrabajo.objects.get(pk=soporte.pk).funciones_principales, 'Escrita a mano')  # no la pisa
        self.assertEqual(KPIAsignado.objects.filter(puesto_trabajo=soporte).count(), 4)  # no duplica KPIs
        self.assertEqual(PuestoDeTrabajo.objects.filter(nombre='Gerente de Call Center').count(), 1)
