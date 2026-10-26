"""Pruebas de la v5: órdenes de trabajo, proyectos, tiempo, finanzas y automatizaciones."""
import json
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
from .models import Cliente, OrdenTrabajo, Proyecto

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
        self.cliente = Cliente.objects.create(nombre='ABAMON')
        self.c = APIClient()

    def _u(self, username, puesto, admin=False):
        u = User.objects.create_user(username, f'{username}@adzone.marketing', 'Clave-Segura-2026',
                                     first_name=username.capitalize())
        u.perfil.puesto_trabajo = puesto
        u.perfil.save()
        if admin:
            u.is_staff = True
            u.save()
            u.groups.add(Group.objects.get_or_create(name='Administrador')[0])
        return u

    def como(self, u):
        self.c.force_authenticate(u)

    def pedir(self, quien=None, **extra):
        self.como(quien or self.erlin)
        datos = {'tipo': 'IMPRESION', 'titulo': 'Lona 3x2 del torneo', 'cliente': self.cliente.id, 'prioridad': 'ALTA',
                 'fecha_requerida': (HOY() + timedelta(days=5)).isoformat(),
                 'detalles': {'trabajo': 'Lona / banner', 'cantidad': 2, 'ancho_cm': 300, 'alto_cm': 200,
                              'arte': 'Lo diseña ADZONE', 'acabados': ['Ojales']}, 'monto': '9500'}
        datos.update(extra)
        return self.c.post('/api/operaciones/ordenes/', datos, format='json')

    def aprobada(self):
        oid = self.pedir().json()['id']
        self.como(self.omar)
        r = self.c.post(f'/api/operaciones/ordenes/{oid}/aprobar/', {
            'responsable': self.daniel.id, 'equipo': [self.keifri.id],
            'fecha_compromiso': (HOY() + timedelta(days=3)).isoformat()}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        return OrdenTrabajo.objects.get(pk=oid)


class OrdenTests(Base):
    def test_pedir_valida_el_formulario_del_area(self):
        r = self.pedir(detalles={'cantidad': 2})
        self.assertEqual(r.status_code, 400)
        self.assertIn('trabajo', r.json()['detalles'])
        r = self.pedir(detalles={'trabajo': 'Algo raro', 'cantidad': 1, 'arte': 'Lo diseña ADZONE'})
        self.assertEqual(r.status_code, 400)
        r = self.pedir()
        self.assertEqual(r.status_code, 201, r.content)
        d = r.json()
        self.assertTrue(d['numero'].startswith(f"OT-{HOY().year}-"))
        self.assertEqual(d['departamento'], self.imp.id)  # el área decide el departamento
        self.assertIsNone(d['monto'])  # un colaborador no fija ni ve precios
        self.assertTrue(Notificacion.objects.filter(destinatario=self.omar, tipo='ORDEN').exists())

    def test_solo_el_gerente_del_area_aprueba_y_se_crea_la_tarea_con_pasos(self):
        oid = self.pedir().json()['id']
        self.como(self.vladi)  # gerente de otro departamento
        r = self.c.post(f'/api/operaciones/ordenes/{oid}/aprobar/', {'responsable': self.daniel.id,
                        'fecha_compromiso': (HOY() + timedelta(days=3)).isoformat()}, format='json')
        self.assertIn(r.status_code, (403, 404))
        orden = self.aprobada()
        self.assertEqual(orden.estado, 'APROBADA')
        tarea = orden.tareas.get()
        self.assertEqual(tarea.colaborador, self.daniel)
        self.assertEqual(list(tarea.companeros.all()), [self.keifri])
        self.assertEqual(tarea.pasos.count(), 6)
        self.assertEqual(tarea.prioridad, 'ALTA')
        self.assertTrue(Notificacion.objects.filter(destinatario=self.erlin, titulo__startswith='Aprobada').exists())

    def test_la_orden_sigue_a_su_tarea_hasta_lista_y_entrega(self):
        orden = self.aprobada()
        tarea = orden.tareas.get()
        self.como(self.daniel)
        self.c.post(f'/api/desempeno/tareas/{tarea.id}/iniciar/')
        orden.refresh_from_db()
        self.assertEqual(orden.estado, 'EN_PRODUCCION')
        self.c.post(f'/api/desempeno/tareas/{tarea.id}/entregar/', {'evidencia_nota': 'Impresas'}, format='multipart')
        orden.refresh_from_db()
        self.assertEqual(orden.estado, 'CONTROL_CALIDAD')
        self.como(self.omar)
        r = self.c.post(f'/api/operaciones/ordenes/{orden.id}/entregar/', {'recibido_por': 'Juan'}, format='json')
        self.assertEqual(r.status_code, 400)  # aún no está lista
        self.c.post(f'/api/desempeno/tareas/{tarea.id}/validar/', {'calificacion_calidad': 5})
        orden.refresh_from_db()
        self.assertEqual(orden.estado, 'LISTA')
        # Regla base: avisar a quien la pidió
        self.assertTrue(Notificacion.objects.filter(destinatario=self.erlin, tipo='AUTOMATIZACION').exists())
        self.como(self.daniel)
        r = self.c.post(f'/api/operaciones/ordenes/{orden.id}/entregar/', {'recibido_por': ''}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.c.post(f'/api/operaciones/ordenes/{orden.id}/entregar/', {'recibido_por': 'Juan Pérez (ABAMON)'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['estado'], 'ENTREGADA')
        self.assertTrue(r.json()['a_tiempo'])
        # Regla base: Finanzas se entera para facturar
        self.assertTrue(Notificacion.objects.filter(destinatario=self.willian, titulo__startswith='Por facturar').exists())

    def test_mover_respeta_el_flujo(self):
        orden = self.aprobada()
        self.como(self.omar)
        r = self.c.post(f'/api/operaciones/ordenes/{orden.id}/mover/', {'estado': 'LISTA'}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.c.post(f'/api/operaciones/ordenes/{orden.id}/mover/', {'estado': 'EN_PAUSA'}, format='json')
        self.assertEqual(r.json()['estado'], 'EN_PAUSA')
        r = self.c.post(f'/api/operaciones/ordenes/{orden.id}/reanudar/')
        self.assertEqual(r.json()['estado'], 'APROBADA')
        self.como(self.erlin)
        r = self.c.post(f'/api/operaciones/ordenes/{orden.id}/mover/', {'estado': 'EN_PAUSA'}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_quien_ve_que(self):
        oid = self.pedir().json()['id']

        def ids(u):
            self.como(u)
            return [o['id'] for o in self.c.get('/api/operaciones/ordenes/').json()]
        self.assertIn(oid, ids(self.erlin))    # la pidió
        self.assertIn(oid, ids(self.keifri))   # es de su departamento
        self.assertIn(oid, ids(self.willian))  # Finanzas ve todo
        self.assertIn(oid, ids(self.omar))     # gestiona Impresión
        self.assertIn(oid, ids(self.vladi))    # la pidió alguien de su equipo
        self.assertNotIn(oid, ids(self.ashley))  # otra persona de Marketing, sin relación

    def test_otro_departamento_no_la_ve(self):
        self.como(self.omar)
        r = self.c.post('/api/operaciones/ordenes/', {'tipo': 'IMPRESION', 'titulo': 'Volantes internos', 'cliente': self.cliente.id,
                                                       'detalles': {'trabajo': 'Volantes', 'cantidad': 100, 'arte': 'Ya está aprobado'}},
                        format='json')
        oid = r.json()['id']
        self.como(self.erlin)
        self.assertEqual(self.c.get(f'/api/operaciones/ordenes/{oid}/').status_code, 404)

    def test_cancelar_pide_motivo_y_cancela_sus_tareas(self):
        orden = self.aprobada()
        self.como(self.omar)
        self.assertEqual(self.c.post(f'/api/operaciones/ordenes/{orden.id}/cancelar/', {}, format='json').status_code, 400)
        r = self.c.post(f'/api/operaciones/ordenes/{orden.id}/cancelar/', {'motivo': 'El cliente desistió'}, format='json')
        self.assertEqual(r.json()['estado'], 'CANCELADA')
        self.assertEqual(orden.tareas.get().estado, 'CANCELADA')

    def test_comentario_con_mencion_avisa(self):
        orden = self.aprobada()
        self.como(self.erlin)
        r = self.c.post(f'/api/operaciones/ordenes/{orden.id}/comentarios/', {'texto': '@willian ¿ya se facturó el anticipo?'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertTrue(Notificacion.objects.filter(destinatario=self.willian, tipo='MENCION').exists())
        self.assertTrue(Notificacion.objects.filter(destinatario=self.daniel, titulo__startswith='Comentario').exists())

    def test_archivos_protegidos_y_tipos_permitidos(self):
        oid = self.pedir().json()['id']
        malo = SimpleUploadedFile('virus.exe', b'MZ', content_type='application/octet-stream')
        self.assertEqual(self.c.post(f'/api/operaciones/ordenes/{oid}/archivos/', {'archivos': [malo]}, format='multipart').status_code, 400)
        arte = SimpleUploadedFile('arte.pdf', b'%PDF-1.4 arte', content_type='application/pdf')
        r = self.c.post(f'/api/operaciones/ordenes/{oid}/archivos/', {'archivos': [arte]}, format='multipart')
        self.assertEqual(r.status_code, 201, r.content)
        url = r.json()[0]['url']
        self.assertEqual(self.c.get(url).status_code, 200)
        self.como(self.ashley)
        self.assertEqual(self.c.get(url).status_code, 404)

    def test_resumen_y_catalogo(self):
        self.aprobada()
        self.como(self.omar)
        cat = self.c.get('/api/operaciones/ordenes/catalogo/').json()
        self.assertEqual({t['tipo'] for t in cat}, {'IMPRESION', 'ADZONE_TV', 'CALL_CENTER', 'MARKETING', 'AUDIOVISUAL',
                                                    'DESARROLLO', 'ADMINISTRATIVA'})
        r = self.c.get('/api/operaciones/ordenes/resumen/').json()
        self.assertEqual(r['abiertas'], 1)


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
        orden = self.aprobada()
        tarea = orden.tareas.get()
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
        orden = self.aprobada()
        self.como(self.erlin)
        r = self.c.post('/api/tiempo/iniciar/', {'tarea': orden.tareas.get().id}, format='json')
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
        r = self.c.post(f"/api/finanzas/cotizaciones/{cot['id']}/aprobar/", {'crear_orden': 'IMPRESION'}, format='json')
        orden = OrdenTrabajo.objects.get(pk=r.json()['orden_creada']['id'])
        self.assertEqual(orden.monto, Decimal('9500'))
        self.assertEqual(orden.departamento, self.imp)
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
        orden = OrdenTrabajo.objects.create(tipo='IMPRESION', titulo='Lonas', cliente=self.cliente, departamento=self.imp,
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
        Regla.objects.create(nombre='Brief', evento='ORDEN_CREADA', condiciones={'tipo': 'IMPRESION'}, accion='CREAR_TAREA',
                             parametros={'titulo': 'Revisar arte de {numero}', 'asignar': 'usuario', 'usuario_id': self.daniel.id, 'dias': 1})
        Regla.objects.create(nombre='Rota', evento='ORDEN_CREADA', accion='CREAR_TAREA', parametros={'titulo': 'x', 'dias': 'muchos'})
        r = self.pedir()
        self.assertEqual(r.status_code, 201)
        self.assertTrue(Tarea.objects.filter(colaborador=self.daniel, titulo__startswith='Revisar arte de OT-').exists())

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
        self.como(self.ashley)
        self.assertNotIn('orden', {x['tipo'] for x in self.c.get('/api/operaciones/buscar/?q=lona').json()})
