"""Requerimiento «Módulo de Clientes y gestión comercial de Marketing»: una prueba por cada escenario de aceptación (6.1 a 6.10),
más la separación de departamentos y el aviso de seguimiento."""
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import Departamento, ExcepcionPermiso
from apps.desempeno.models import Notificacion
from apps.operaciones.models import Cliente, Proyecto
from apps.organizacion.models import PuestoDeTrabajo

from .models import InteraccionComercial, MovimientoComercial, Oportunidad, SolicitudServicio
from .servicios import avisar_seguimientos

CLAVE = 'Clave-Segura-2026'
API = '/api/comercial'


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.d = {n: Departamento.objects.get_or_create(nombre=n)[0] for n in ('Marketing', 'Audiovisual', 'Tecnología', 'Administración')}
        gerencia = Departamento.objects.get_or_create(nombre='Gerencia')[0]
        ceo = PuestoDeTrabajo.objects.create(nombre='CEO', departamento=gerencia)
        self.jefe_av_puesto = PuestoDeTrabajo.objects.create(nombre='Jefe AV', departamento=self.d['Audiovisual'], supervisor=ceo)
        self.jefe_tec_puesto = PuestoDeTrabajo.objects.create(nombre='Jefe TEC', departamento=self.d['Tecnología'], supervisor=ceo)
        self.erlyn = self._u('erlyn', PuestoDeTrabajo.objects.create(nombre='CM', departamento=self.d['Marketing'], supervisor=ceo),
                             ['Colaborador', 'Gestión de clientes'])
        ExcepcionPermiso.objects.create(usuario=self.erlyn, permiso='clientes.completo')
        self.jefe_av = self._u('jefeav', self.jefe_av_puesto, ['Supervisor'])
        self.camarografo = self._u('camara', PuestoDeTrabajo.objects.create(nombre='Cámara', departamento=self.d['Audiovisual'],
                                                                            supervisor=self.jefe_av_puesto))
        self.jefe_tec = self._u('jefetec', self.jefe_tec_puesto, ['Supervisor'])
        self.dev = self._u('dev', PuestoDeTrabajo.objects.create(nombre='Dev', departamento=self.d['Tecnología'], supervisor=self.jefe_tec_puesto))
        self.enmanuel = self._u('enmanuel', PuestoDeTrabajo.objects.create(nombre='Coord', departamento=self.d['Administración'], supervisor=ceo),
                                ['Coordinación', 'Supervisor', 'Gerente de Departamento', 'Gestión de clientes'])
        self.finanzas = self._u('fin', PuestoDeTrabajo.objects.create(nombre='Contable', departamento=self.d['Administración'], supervisor=ceo),
                                ['Finanzas'])
        self.cliente = Cliente.objects.create(nombre='Banco X', telefono='809')

    def _u(self, usuario, puesto, grupos=('Colaborador',)):
        u = User.objects.create_user(usuario, password=CLAVE, first_name=usuario.capitalize())
        u.perfil.puesto_trabajo = puesto
        u.perfil.save()
        u.groups.set([Group.objects.get(name=g) for g in grupos])
        return u

    def sesion(self, u):
        c = APIClient()
        c.login(username=u.username, password=CLAVE)
        return c

    def oportunidad(self, c=None, **extra):
        c = c or self.sesion(self.erlyn)
        r = c.post(f'{API}/oportunidades/', {'cliente': self.cliente.pk, 'titulo': 'Campaña 2027', 'necesidades': 'Redes, video y web',
                                              **extra}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def solicitud(self, op, servicio, c=None, **extra):
        c = c or self.sesion(self.erlyn)
        r = c.post(f'{API}/solicitudes/', {'oportunidad': op['id'], 'servicio': servicio, 'descripcion': f'Necesita {servicio}', **extra},
                   format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()


class AceptacionTests(Base):
    def test_1_erlyn_edita_la_informacion_general_del_cliente(self):
        c = self.sesion(self.erlyn)
        r = c.patch(f'/api/operaciones/clientes/{self.cliente.pk}/', {'telefono': '809-555-0101', 'notas': 'Prefiere WhatsApp'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.notas, 'Prefiere WhatsApp')
        self.assertTrue(c.get('/api/auth/session/').json()['user']['edita_clientes'])

    def test_2_erlyn_no_toca_facturas_pagos_ni_movimientos(self):
        c = self.sesion(self.erlyn)
        for url in ['/api/finanzas/facturas/', '/api/finanzas/cotizaciones/', '/api/finanzas/gastos/', '/api/finanzas/resumen/',
                    '/api/finanzas/rentabilidad/', '/api/finanzas/tasas/']:
            self.assertEqual(c.get(url).status_code, 403, url)
        self.assertEqual(c.post('/api/finanzas/facturas/', {'cliente': self.cliente.pk}, format='json').status_code, 403)
        self.assertEqual(c.delete('/api/finanzas/pagos/1/').status_code, 403)
        # La ficha del cliente no le trae saldos ni facturas, y el cashflow_id no se puede cambiar
        self.assertNotIn('finanzas', c.get(f'/api/operaciones/clientes/{self.cliente.pk}/resumen/').json())
        c.patch(f'/api/operaciones/clientes/{self.cliente.pk}/', {'cashflow_id': 'CF-1'}, format='json')
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.cashflow_id, '')
        # Aunque sea responsable de un proyecto, no ve su rentabilidad
        p = Proyecto.objects.create(nombre='P', cliente=self.cliente, responsable=self.erlyn, departamento=self.d['Marketing'])
        self.assertNotIn('finanzas', c.get(f'/api/operaciones/proyectos/{p.pk}/detalle/').json())
        u = c.get('/api/auth/session/').json()['user']
        self.assertFalse(u['es_finanzas'])
        self.assertNotIn('finanzas.gestionar', u['permisos'])

    def test_3_enmanuel_conserva_sus_permisos(self):
        from apps.core.permisos import permisos
        antes = permisos(self.enmanuel)
        self.assertIn('operaciones.coordinar', antes)
        self.assertIn('clientes.gestionar', antes)
        # El módulo comercial le suma las oportunidades (por «Gestión de clientes») y no le quita nada
        self.assertIn('comercial.oportunidades', antes)
        # y quien tiene Finanzas sigue entrando a facturas
        self.assertEqual(self.sesion(self.finanzas).get('/api/finanzas/facturas/').status_code, 200)

    def test_4_tablero_independiente_solo_para_marketing(self):
        self.assertEqual(self.sesion(self.erlyn).get(f'{API}/oportunidades/').status_code, 200)
        self.assertTrue(self.sesion(self.erlyn).get('/api/auth/session/').json()['user']['es_comercial'])
        for u in (self.camarografo, self.dev, self.finanzas):
            self.assertEqual(self.sesion(u).get(f'{API}/oportunidades/').status_code, 403, u.username)
        r = self.sesion(self.erlyn).get(f'{API}/oportunidades/resumen/').json()
        self.assertEqual([e['codigo'] for e in r['estados']],
                         ['NUEVO', 'CONTACTADO', 'NEGOCIACION', 'COTIZADA', 'APROBADA', 'NO_CONCRETADA'])

    def test_5_marketing_registra_cliente_nuevo_y_oportunidad(self):
        c = self.sesion(self.erlyn)
        cli = c.post('/api/operaciones/clientes/', {'nombre': 'Tienda Nueva'}, format='json').json()
        r = c.post(f'{API}/oportunidades/', {'cliente': cli['id'], 'titulo': 'Primer contacto'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        o = Oportunidad.objects.get(pk=r.json()['id'])
        self.assertEqual((o.creado_por, o.responsable, o.estado, o.departamento), (self.erlyn, self.erlyn, 'NUEVO', self.d['Marketing']))
        self.assertEqual(o.fecha_contacto, timezone.localdate())
        self.assertTrue(o.codigo.startswith('OPC-'))

    def test_6_7_varias_oportunidades_y_servicios_de_varios_departamentos(self):
        op1, op2 = self.oportunidad(), self.oportunidad(titulo='Otra')
        s1, s2, s3 = self.solicitud(op1, 'REDES'), self.solicitud(op1, 'VIDEO'), self.solicitud(op1, 'WEB')
        self.solicitud(op2, 'FOTOGRAFIA')
        self.assertEqual([s1['departamento_nombre'], s2['departamento_nombre'], s3['departamento_nombre']], ['Marketing', 'Audiovisual', 'Tecnología'])
        self.assertEqual(self.cliente.oportunidades.count(), 2)
        self.assertEqual(self.cliente.solicitudes_servicio.count(), 4)
        r = self.sesion(self.erlyn).get(f'/api/operaciones/clientes/{self.cliente.pk}/resumen/').json()
        self.assertEqual(len(r['oportunidades']), 2)
        self.assertEqual(len(r['solicitudes']), 4)
        # Avisos: al jefe de Audiovisual y al de Tecnología (no tienen responsable todavía)
        self.assertTrue(Notificacion.objects.filter(destinatario=self.jefe_av, tipo='COMERCIAL').exists())
        self.assertTrue(Notificacion.objects.filter(destinatario=self.jefe_tec, tipo='COMERCIAL').exists())

    def test_8_cada_solicitud_con_su_estado_y_responsable(self):
        op = self.oportunidad()
        video, web = self.solicitud(op, 'VIDEO'), self.solicitud(op, 'WEB')
        jefe = self.sesion(self.jefe_av)
        self.assertEqual(jefe.patch(f'{API}/solicitudes/{video["id"]}/', {'estado': 'APROBADA', 'responsable': self.camarografo.pk},
                                    format='json').status_code, 200)
        self.assertEqual(SolicitudServicio.objects.get(pk=video['id']).estado, 'APROBADA')
        self.assertEqual(SolicitudServicio.objects.get(pk=web['id']).estado, 'RECIBIDA')
        self.assertEqual(SolicitudServicio.objects.get(pk=video['id']).responsable, self.camarografo)
        # Audiovisual no cambia la solicitud de Tecnología, y ni siquiera la ve
        self.assertEqual(jefe.patch(f'{API}/solicitudes/{web["id"]}/', {'estado': 'NO_CONCRETADA'}, format='json').status_code, 404)
        self.assertEqual([s['id'] for s in jefe.get(f'{API}/solicitudes/').json()], [video['id']])
        # Marketing ve todo pero no cambia el estado de la solicitud de otro departamento
        self.assertEqual(self.sesion(self.erlyn).patch(f'{API}/solicitudes/{web["id"]}/', {'estado': 'APROBADA'}, format='json').status_code, 403)
        # Un miembro de Tecnología sin ser responsable ni jefe la ve y comenta, pero no la cambia
        dev = self.sesion(self.dev)
        self.assertEqual(dev.post(f'{API}/solicitudes/{web["id"]}/comentar/', {'texto': 'Revisando'}, format='json').status_code, 201)
        self.assertEqual(dev.patch(f'{API}/solicitudes/{web["id"]}/', {'estado': 'EVALUACION'}, format='json').status_code, 403)

    def test_9_aprobada_se_convierte_en_proyecto_sin_duplicar(self):
        op = self.oportunidad()
        video = self.solicitud(op, 'VIDEO')
        jefe = self.sesion(self.jefe_av)
        self.assertEqual(jefe.post(f'{API}/solicitudes/{video["id"]}/convertir/', {}, format='json').status_code, 400)  # aún no aprobada
        jefe.patch(f'{API}/solicitudes/{video["id"]}/', {'estado': 'APROBADA'}, format='json')
        r = jefe.post(f'{API}/solicitudes/{video["id"]}/convertir/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        s = SolicitudServicio.objects.get(pk=video['id'])
        self.assertEqual(s.estado, 'EN_EJECUCION')
        self.assertEqual((s.proyecto.cliente, s.proyecto.departamento), (self.cliente, self.d['Audiovisual']))
        self.assertEqual(Proyecto.objects.filter(cliente=self.cliente).count(), 1)
        self.assertEqual(Cliente.objects.filter(nombre='Banco X').count(), 1)
        # Enlazar una orden de otro cliente no se permite
        from apps.operaciones.models import OrdenTrabajo
        otro = Cliente.objects.create(nombre='Otro')
        web = self.solicitud(op, 'WEB')
        self.sesion(self.jefe_tec).patch(f'{API}/solicitudes/{web["id"]}/', {'estado': 'APROBADA'}, format='json')
        orden = OrdenTrabajo.objects.create(titulo='OT', cliente=otro, solicitada_por=self.jefe_tec)
        self.assertEqual(self.sesion(self.jefe_tec).post(f'{API}/solicitudes/{web["id"]}/convertir/', {'orden': orden.pk}, format='json').status_code, 400)

    def test_10_historial_de_todo(self):
        c = self.sesion(self.erlyn)
        op = self.oportunidad(c)
        c.patch(f'{API}/oportunidades/{op["id"]}/', {'estado': 'CONTACTADO'}, format='json')
        c.patch(f'{API}/oportunidades/{op["id"]}/', {'titulo': 'Campaña grande'}, format='json')
        c.post(f'{API}/oportunidades/{op["id"]}/comentar/', {'texto': 'Llamó el gerente'}, format='json')
        self.assertEqual(c.patch(f'{API}/oportunidades/{op["id"]}/', {'estado': 'NO_CONCRETADA'}, format='json').status_code, 400)  # sin motivo
        c.patch(f'{API}/oportunidades/{op["id"]}/', {'estado': 'NO_CONCRETADA', 'motivo_no_concretado': 'Sin presupuesto'}, format='json')
        tipos = list(MovimientoComercial.objects.filter(oportunidad_id=op['id']).order_by('id').values_list('tipo', 'estado_antes', 'estado_despues'))
        self.assertEqual([t[0] for t in tipos], ['CREADA', 'ESTADO', 'CAMBIO', 'COMENTARIO', 'ESTADO', 'CAMBIO'])
        self.assertEqual(tipos[1][1:], ('NUEVO', 'CONTACTADO'))
        self.assertTrue(all(m.usuario == self.erlyn for m in MovimientoComercial.objects.filter(oportunidad_id=op['id'])))
        cambio = MovimientoComercial.objects.filter(oportunidad_id=op['id'], tipo='CAMBIO').order_by('id').first()
        self.assertEqual(cambio.cambios['titulo'], {'antes': 'Campaña 2027', 'despues': 'Campaña grande'})
        historial = c.get(f'{API}/oportunidades/{op["id"]}/').json()['historial']
        self.assertEqual(len(historial), 6)
        self.assertIsNotNone(Oportunidad.objects.get(pk=op['id']).fecha_cierre)


class SeguimientoTests(Base):
    def test_filtros_y_aviso_de_seguimiento_atrasado(self):
        c = self.sesion(self.erlyn)
        ayer = (timezone.localdate() - timedelta(days=1)).isoformat()
        atrasada = self.oportunidad(c, proximo_seguimiento=ayer)
        self.oportunidad(c, proximo_seguimiento=(timezone.localdate() + timedelta(days=5)).isoformat())
        self.assertEqual([o['id'] for o in c.get(f'{API}/oportunidades/?vista=seguimiento').json()], [atrasada['id']])
        self.assertTrue(c.get(f'{API}/oportunidades/{atrasada["id"]}/').json()['seguimiento_vencido'])
        self.assertEqual(len(c.get(f'{API}/oportunidades/?responsable={self.erlyn.pk}&departamento={self.d["Marketing"].pk}').json()), 2)
        self.assertEqual(len(c.get(f'{API}/oportunidades/?estado=APROBADA').json()), 0)
        self.assertEqual(avisar_seguimientos(), 1)
        self.assertTrue(Notificacion.objects.filter(destinatario=self.erlyn, titulo__startswith='Seguimiento pendiente').exists())

    def test_solo_marketing_crea_solicitudes_y_solo_direccion_borra_oportunidades(self):
        op = self.oportunidad()
        r = self.sesion(self.jefe_av).post(f'{API}/solicitudes/', {'oportunidad': op['id'], 'servicio': 'VIDEO'}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.sesion(self.erlyn).delete(f'{API}/oportunidades/{op["id"]}/').status_code, 403)
        self.assertTrue(self.sesion(self.jefe_av).get('/api/auth/session/').json()['user']['ve_solicitudes'] is False)
        self.solicitud(op, 'VIDEO')
        self.assertTrue(self.sesion(self.jefe_av).get('/api/auth/session/').json()['user']['ve_solicitudes'])


class FlujoComercialTests(Base):
    """Punto 9 del requerimiento: estados del flujo, posibles clientes, seguimiento y conversión en cliente sin duplicar."""

    def prospecto(self, c=None, **extra):
        c = c or self.sesion(self.erlyn)
        datos = {'prospecto_nombre': 'Café Ñandú', 'prospecto_contacto': 'Ana Pérez', 'prospecto_telefono': '809-555-0000',
                 'prospecto_correo': 'ana@nandu.do', 'titulo': 'Redes y fotos', 'servicios_interes': ['REDES', 'FOTOGRAFIA'],
                 'valor_estimado': '45000.00', **extra}
        r = c.post(f'{API}/oportunidades/', datos, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def test_estados_del_flujo_con_sus_nombres(self):
        self.assertEqual([n for c, n in Oportunidad.ESTADOS if c in Oportunidad.ESTADOS_VIGENTES],
                         ['Nueva oportunidad', 'Contactado', 'En negociación', 'Propuesta enviada', 'Ganada', 'Perdida'])
        c = self.sesion(self.erlyn)
        op = self.oportunidad(c)
        for estado in ('CONTACTADO', 'NEGOCIACION', 'COTIZADA', 'APROBADA'):
            self.assertEqual(c.patch(f'{API}/oportunidades/{op["id"]}/', {'estado': estado}, format='json').status_code, 200, estado)
        self.assertEqual(c.get(f'{API}/oportunidades/{op["id"]}/').json()['estado_nombre'], 'Ganada')
        # El estado anterior «Evaluación» ya no se ofrece, pero lo que lo tenía se sigue viendo y puede avanzar
        self.assertEqual(c.patch(f'{API}/oportunidades/{op["id"]}/', {'estado': 'EVALUACION'}, format='json').status_code, 400)
        vieja = Oportunidad.objects.create(cliente=self.cliente, titulo='De antes', estado='EVALUACION')
        r = c.get(f'{API}/oportunidades/resumen/').json()
        self.assertIn('EVALUACION', [e['codigo'] for e in r['estados']])
        self.assertEqual(c.patch(f'{API}/oportunidades/{vieja.pk}/', {'titulo': 'De antes (editada)'}, format='json').status_code, 200)
        self.assertEqual(c.patch(f'{API}/oportunidades/{vieja.pk}/', {'estado': 'NEGOCIACION'}, format='json').status_code, 200)
        # «Perdida» pide el motivo
        self.assertEqual(c.patch(f'{API}/oportunidades/{vieja.pk}/', {'estado': 'NO_CONCRETADA'}, format='json').status_code, 400)

    def test_posible_cliente_sin_registrarlo(self):
        c = self.sesion(self.erlyn)
        clientes_antes = Cliente.objects.count()
        op = self.prospecto(c)
        self.assertTrue(op['es_prospecto'])
        self.assertIsNone(op['cliente'])
        self.assertEqual(op['cliente_nombre'], 'Café Ñandú')
        self.assertEqual(op['servicios_interes'], ['REDES', 'FOTOGRAFIA'])
        self.assertEqual(Cliente.objects.count(), clientes_antes)  # no se registró ningún cliente
        # Sin cliente ni nombre del prospecto no se guarda; los servicios deben ser de la lista
        self.assertEqual(c.post(f'{API}/oportunidades/', {'titulo': 'Sin nadie'}, format='json').status_code, 400)
        self.assertEqual(c.post(f'{API}/oportunidades/', {'prospecto_nombre': 'X', 'titulo': 'Y', 'servicios_interes': ['NADA']},
                                format='json').status_code, 400)
        # Se encuentra buscando por el nombre del prospecto y con el filtro de prospectos
        self.assertEqual([o['id'] for o in c.get(f'{API}/oportunidades/?q=Ñandú').json()], [op['id']])
        self.oportunidad(c)
        self.assertEqual([o['id'] for o in c.get(f'{API}/oportunidades/?tipo=prospecto').json()], [op['id']])
        # Todavía no se le crean solicitudes a los departamentos
        r = c.post(f'{API}/solicitudes/', {'oportunidad': op['id'], 'servicio': 'VIDEO'}, format='json')
        self.assertEqual(r.status_code, 400)
        # Resumen: pendientes, ganadas, perdidas y valor potencial de las abiertas
        self.oportunidad(c, valor_estimado='5000')
        perdida = self.oportunidad(c, valor_estimado='99999')
        c.patch(f'{API}/oportunidades/{perdida["id"]}/', {'estado': 'NO_CONCRETADA', 'motivo_no_concretado': 'Precio'}, format='json')
        r = c.get(f'{API}/oportunidades/resumen/').json()
        self.assertEqual((r['pendientes'], r['ganadas'], r['perdidas'], r['prospectos']), (3, 0, 1, 1))
        self.assertEqual(float(r['valor_abierto']), 50000.0)

    def test_convertir_enlaza_al_cliente_existente_sin_duplicar(self):
        c = self.sesion(self.erlyn)
        existente = Cliente.objects.create(nombre='CAFE NANDU', rnc='1-01-12345-6')
        op = self.prospecto(c)
        r = c.get(f'{API}/oportunidades/{op["id"]}/coincidencias/').json()
        self.assertEqual([x['id'] for x in r['iguales']], [existente.pk])
        # Pedir crear uno nuevo no duplica: avisa que ya existe
        r = c.post(f'{API}/oportunidades/{op["id"]}/convertir_cliente/', {}, format='json')
        self.assertEqual(r.status_code, 409, r.content)
        self.assertEqual(Cliente.objects.count(), 2)
        # Mismo RNC con otro nombre también se detecta
        op2 = self.prospecto(c, prospecto_nombre='Distribuidora del Este', prospecto_rnc='101123456')
        self.assertEqual([x['id'] for x in c.get(f'{API}/oportunidades/{op2["id"]}/coincidencias/').json()['iguales']], [existente.pk])
        # Se enlaza al que ya existe
        c.patch(f'{API}/oportunidades/{op["id"]}/', {'estado': 'APROBADA'}, format='json')
        r = c.post(f'{API}/oportunidades/{op["id"]}/convertir_cliente/', {'cliente': existente.pk}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(r.json()['cliente_nuevo'])
        o = Oportunidad.objects.get(pk=op['id'])
        self.assertEqual(o.cliente, existente)
        self.assertEqual(Cliente.objects.count(), 2)  # Banco X y el existente: ninguno nuevo
        self.assertTrue(MovimientoComercial.objects.filter(oportunidad=o, tipo='CLIENTE').exists())
        # Los servicios de interés pasan a ser solicitudes para su departamento, listas para proyecto u orden
        sols = list(SolicitudServicio.objects.filter(oportunidad=o).order_by('id'))
        self.assertEqual([(s.servicio, s.departamento.nombre, s.cliente_id) for s in sols],
                         [('REDES', 'Marketing', existente.pk), ('FOTOGRAFIA', 'Audiovisual', existente.pk)])
        jefe = self.sesion(self.jefe_av)
        foto = sols[1]
        jefe.patch(f'{API}/solicitudes/{foto.pk}/', {'estado': 'APROBADA'}, format='json')
        self.assertEqual(jefe.post(f'{API}/solicitudes/{foto.pk}/convertir/', {}, format='json').status_code, 200)
        self.assertEqual(Proyecto.objects.get(solicitudes_servicio=foto).cliente, existente)
        # Ya convertida, no se vuelve a convertir
        self.assertEqual(c.post(f'{API}/oportunidades/{op["id"]}/convertir_cliente/', {}, format='json').status_code, 400)

    def test_convertir_crea_el_cliente_con_los_datos_del_prospecto(self):
        c = self.sesion(self.erlyn)
        op = self.prospecto(c, prospecto_nombre='Ferretería La Unión', prospecto_rnc='131-00000-1')
        self.assertEqual(c.get(f'{API}/oportunidades/{op["id"]}/coincidencias/').json()['iguales'], [])
        c.patch(f'{API}/oportunidades/{op["id"]}/', {'estado': 'APROBADA'}, format='json')
        r = c.post(f'{API}/oportunidades/{op["id"]}/convertir_cliente/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['cliente_nuevo'])
        self.assertFalse(r.json()['es_prospecto'])
        nuevo = Cliente.objects.get(nombre='Ferretería La Unión')
        self.assertEqual((nuevo.contacto, nuevo.telefono, nuevo.correo, nuevo.rnc, nuevo.creado_por),
                         ('Ana Pérez', '809-555-0000', 'ana@nandu.do', '131-00000-1', self.erlyn))
        self.assertEqual(Oportunidad.objects.get(pk=op['id']).cliente, nuevo)
        self.assertEqual(nuevo.solicitudes_servicio.count(), 2)
        # Una perdida no se convierte
        perdida = self.prospecto(c, prospecto_nombre='Otro prospecto')
        c.patch(f'{API}/oportunidades/{perdida["id"]}/', {'estado': 'NO_CONCRETADA', 'motivo_no_concretado': 'No respondió'}, format='json')
        self.assertEqual(c.post(f'{API}/oportunidades/{perdida["id"]}/convertir_cliente/', {}, format='json').status_code, 400)
        # Quien no es comercial no convierte (ni entra)
        self.assertEqual(self.sesion(self.dev).post(f'{API}/oportunidades/{perdida["id"]}/convertir_cliente/', {},
                                                    format='json').status_code, 403)

    def test_interacciones_de_seguimiento(self):
        c = self.sesion(self.erlyn)
        op = self.prospecto(c)
        manana = (timezone.localdate() + timedelta(days=1)).isoformat()
        r = c.post(f'{API}/oportunidades/{op["id"]}/interacciones/', {'tipo': 'LLAMADA', 'nota': 'Le interesa empezar en enero',
                                                                       'proximo_seguimiento': manana}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['usuario_nombre'], 'Erlyn')
        r = c.post(f'{API}/oportunidades/{op["id"]}/interacciones/', {'tipo': 'PROPUESTA', 'nota': 'Plan trimestral',
                                                                       'monto_propuesta': '42000', 'usuario': self.enmanuel.pk}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(c.post(f'{API}/oportunidades/{op["id"]}/interacciones/', {'tipo': 'REUNION', 'nota': '  '},
                                format='json').status_code, 400)
        self.assertEqual(c.post(f'{API}/oportunidades/{op["id"]}/interacciones/', {'tipo': 'FAX', 'nota': 'x'},
                                format='json').status_code, 400)
        detalle = c.get(f'{API}/oportunidades/{op["id"]}/').json()
        self.assertEqual([i['tipo'] for i in detalle['interacciones']], ['PROPUESTA', 'LLAMADA'])
        self.assertEqual(detalle['interacciones'][0]['usuario_nombre'], 'Enmanuel')
        self.assertEqual(detalle['proximo_seguimiento'], manana)
        self.assertEqual(InteraccionComercial.objects.filter(oportunidad_id=op['id'], registrado_por=self.erlyn).count(), 2)
        self.assertEqual(MovimientoComercial.objects.filter(oportunidad_id=op['id'], tipo='INTERACCION').count(), 2)
        self.assertEqual(len(c.get(f'{API}/oportunidades/{op["id"]}/interacciones/').json()), 2)
        # Fuera de Marketing/Dirección no se ve ni se registra
        self.assertEqual(self.sesion(self.camarografo).post(f'{API}/oportunidades/{op["id"]}/interacciones/',
                                                            {'tipo': 'LLAMADA', 'nota': 'x'}, format='json').status_code, 403)
        # El aviso diario de seguimiento usa el nombre del prospecto
        Oportunidad.objects.filter(pk=op['id']).update(proximo_seguimiento=timezone.localdate())
        avisar_seguimientos()
        self.assertTrue(Notificacion.objects.filter(destinatario=self.erlyn, titulo='Seguimiento pendiente: Café Ñandú').exists())
