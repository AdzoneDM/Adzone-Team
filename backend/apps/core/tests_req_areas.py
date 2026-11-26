"""Requerimiento: tareas entre áreas con alcance por persona, Call Center oculto, clientes para Marketing, contraseña temporal,
edición de mensajes (5 minutos) y filtro de tareas por departamento. Cada punto de validación tiene su prueba."""
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.chat import servicios as chat
from apps.chat.models import EdicionMensaje, Mensaje
from apps.core.models import AlcanceAreas, Departamento
from apps.desempeno.models import Tarea
from apps.desempeno.permisos import asignables, puede_asignar_a
from apps.organizacion.models import PuestoDeTrabajo
from apps.talento.models import AuditoriaCambio

CLAVE = 'Clave-Segura-2026'


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.d = {n: Departamento.objects.get_or_create(nombre=n)[0] for n in ('Marketing', 'Audiovisual', 'Adzone TV', 'Tecnología', 'Impresión', 'Call Center')}
        gerencia = Departamento.objects.get_or_create(nombre='Gerencia')[0]
        self.p_ceo = PuestoDeTrabajo.objects.create(nombre='CEO', departamento=gerencia)
        self.gente = {n: self._u(n.lower().replace(' ', ''), n) for n in self.d}
        self.oscar = self._u('oscar', 'Adzone TV', grupos=['Coordinación', 'Supervisor', 'Gerente de Departamento'])
        self.dir = User.objects.create_user('dir', password=CLAVE, first_name='Dir')
        self.dir.groups.set([Group.objects.get(name='Administrador')])

    def _u(self, usuario, area, grupos=('Colaborador',)):
        u = User.objects.create_user(usuario, password=CLAVE, first_name=usuario.capitalize())
        u.perfil.puesto_trabajo = PuestoDeTrabajo.objects.create(nombre=f'Puesto {usuario}', departamento=self.d[area], supervisor=self.p_ceo)
        u.perfil.save()
        u.groups.set([Group.objects.get(name=g) for g in grupos])
        return u

    def c(self, u):
        c = APIClient()
        c.force_authenticate(User.objects.get(pk=u.pk))
        return c

    def limitar(self, u, asignar=(), ocultas=()):
        a = AlcanceAreas.objects.create(usuario=u)
        a.asignar_a.set([self.d[n] for n in asignar])
        a.ocultas.set([self.d[n] for n in ocultas])


class AsignarEntreAreasTests(Base):
    AREAS = ('Marketing', 'Audiovisual', 'Adzone TV', 'Tecnología')

    def test_1_2_asigna_a_las_cuatro_areas_y_a_ninguna_otra(self):
        self.limitar(self.oscar, asignar=self.AREAS, ocultas=['Call Center'])
        o = User.objects.get(pk=self.oscar.pk)
        for area in ('Marketing', 'Audiovisual', 'Tecnología'):
            self.assertTrue(puede_asignar_a(o, self.gente[area]), area)
        self.assertFalse(puede_asignar_a(o, self.gente['Impresión']))
        ids = set(asignables(o).values_list('pk', flat=True))
        self.assertTrue({self.gente[a].pk for a in ('Marketing', 'Audiovisual', 'Tecnología')} <= ids)
        self.assertNotIn(self.gente['Impresión'].pk, ids)
        # Por la API: crear la tarea a Marketing sí, a Impresión no; y le da seguimiento en «Las que yo asigné»
        c = self.c(self.oscar)
        hoy = timezone.localdate().isoformat()
        r = c.post('/api/desempeno/tareas/', {'titulo': 'Video del cliente', 'colaborador': self.gente['Marketing'].pk, 'fecha_limite': hoy}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        r = c.post('/api/desempeno/tareas/', {'titulo': 'Lona', 'colaborador': self.gente['Impresión'].pk, 'fecha_limite': hoy}, format='json')
        self.assertEqual(r.status_code, 403)
        seguimiento = c.get('/api/desempeno/tareas/?ambito=equipo&asignadas=1').json()
        self.assertEqual([t['titulo'] for t in seguimiento], ['Video del cliente'])

    def test_3_call_center_oculto_en_listados_y_en_la_api(self):
        self.limitar(self.oscar, asignar=self.AREAS, ocultas=['Call Center'])
        cc = self.gente['Call Center']
        c = self.c(self.oscar)
        self.assertNotIn(cc.pk, [p['id'] for p in c.get('/api/desempeno/equipo/').json()])
        self.assertNotIn(cc.pk, [p['id'] for p in c.get('/api/chat/personas/').json()])
        self.assertNotIn(cc.pk, [p['id'] for p in c.get('/api/operaciones/directorio/').json()])
        self.assertEqual(c.post('/api/chat/conversaciones/', {'persona': cc.pk}, format='json').status_code, 403)
        r = c.post('/api/desempeno/tareas/', {'titulo': 'X', 'colaborador': cc.pk, 'fecha_limite': timezone.localdate().isoformat()}, format='json')
        self.assertEqual(r.status_code, 403)
        # Sin límite, cualquier otra persona sigue viendo a Call Center en el chat
        self.assertIn(cc.pk, [p['id'] for p in self.c(self.gente['Marketing']).get('/api/chat/personas/').json()])

    def test_el_alcance_se_configura_en_accesos_y_queda_en_la_bitacora(self):
        c = self.c(self.dir)
        r = c.post(f'/api/accesos/personas/{self.oscar.pk}/alcance/', {'asignar_a': [self.d['Marketing'].pk], 'ocultas': [self.d['Call Center'].pk]}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['alcance']['ocultas'], [self.d['Call Center'].pk])
        self.assertTrue(AuditoriaCambio.objects.filter(accion='Alcance por áreas').exists())
        self.assertEqual(self.c(self.gente['Marketing']).post(f'/api/accesos/personas/{self.oscar.pk}/alcance/', {}, format='json').status_code, 403)


class ClientesTests(Base):
    def test_4_5_marketing_edita_clientes_y_queda_quien_y_que_cambio(self):
        from apps.operaciones.models import Cliente
        cli = Cliente.objects.create(nombre='Banco X', telefono='809')
        erlyn = self.gente['Marketing']
        self.assertEqual(self.c(erlyn).patch(f'/api/operaciones/clientes/{cli.pk}/', {'telefono': '809-555-0101'}, format='json').status_code, 403)
        erlyn.groups.add(Group.objects.get(name='Gestión de clientes'))
        sesion = APIClient()   # con sesión de verdad (como en la plataforma): así la bitácora sabe quién fue
        sesion.login(username=erlyn.username, password=CLAVE)
        r = sesion.patch(f'/api/operaciones/clientes/{cli.pk}/', {'telefono': '809-555-0101', 'correo': 'cfo@banco.test'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['telefono'], '809-555-0101')   # y ve los datos de contacto que mantiene
        # La pantalla recibe que puede editar (antes el botón solo salía a quien gestiona un área o a Finanzas)
        self.assertTrue(sesion.get('/api/auth/session/').json()['user']['edita_clientes'])
        # Borrar sigue siendo de quien gestiona o de Finanzas
        self.assertEqual(sesion.delete(f'/api/operaciones/clientes/{cli.pk}/').status_code, 403)
        a = AuditoriaCambio.objects.get(accion='Cambió cliente')
        self.assertEqual(a.usuario, erlyn)
        self.assertEqual(a.despues['telefono'], '809-555-0101')


    def test_clientes_completo_borra_clientes_y_crea_proyectos_de_su_area(self):
        """Erlyn, igual que Enmanuel en clientes: editar, eliminar y crear proyectos; sin equipo ni Coordinación."""
        from apps.core.models import ExcepcionPermiso
        from apps.operaciones.models import Cliente, Proyecto
        cli, otro = Cliente.objects.create(nombre='Banco X'), Cliente.objects.create(nombre='Tienda Y')
        erlyn, colega = self.gente['Marketing'], self.gente['Audiovisual']
        erlyn.groups.add(Group.objects.get(name='Gestión de clientes'))
        colega.groups.add(Group.objects.get(name='Gestión de clientes'))
        # Solo con «Gestión de clientes» no borra ni crea proyectos
        self.assertEqual(self.c(erlyn).post('/api/operaciones/proyectos/', {'nombre': 'P', 'cliente': cli.pk}, format='json').status_code, 403)
        ExcepcionPermiso.objects.create(usuario=erlyn, permiso='clientes.completo', motivo='Igual que Enmanuel en clientes')
        sesion = APIClient(); sesion.login(username=erlyn.username, password=CLAVE)
        u = sesion.get('/api/auth/session/').json()['user']
        self.assertTrue(u['edita_clientes']); self.assertTrue(u['clientes_completo']); self.assertFalse(u['gestiona'])
        self.assertEqual(sesion.patch(f'/api/operaciones/clientes/{cli.pk}/', {'telefono': '809'}, format='json').status_code, 200)
        r = sesion.post('/api/operaciones/proyectos/', {'nombre': 'Campaña', 'cliente': cli.pk, 'departamento': self.d['Marketing'].pk}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Proyecto.objects.get(pk=r.json()['id']).responsable, erlyn)
        self.assertEqual(sesion.post('/api/operaciones/proyectos/', {'nombre': 'Varios', 'cliente': cli.pk}, format='json').status_code, 201)
        # No crea proyectos de otro departamento
        self.assertEqual(sesion.post('/api/operaciones/proyectos/', {'nombre': 'Ajeno', 'cliente': cli.pk, 'departamento': self.d['Impresión'].pk}, format='json').status_code, 403)
        self.assertEqual(sesion.delete(f'/api/operaciones/clientes/{otro.pk}/').status_code, 204)
        self.assertFalse(Cliente.objects.filter(pk=otro.pk).exists())
        # Su colega con solo «Gestión de clientes» sigue sin borrar, y Erlyn no gana equipo ni validación
        self.assertEqual(self.c(colega).delete(f'/api/operaciones/clientes/{cli.pk}/').status_code, 403)
        from apps.core.permisos import tiene
        self.assertFalse(tiene(User.objects.get(pk=erlyn.pk), 'tareas.validar'))
        self.assertFalse(tiene(User.objects.get(pk=erlyn.pk), 'operaciones.coordinar'))


class ContrasenaTemporalTests(Base):
    def test_6_7_cuenta_nueva_con_contrasena_temporal_y_sin_privilegios_globales(self):
        mkt = self.gente['Marketing'].perfil.puesto_trabajo
        r = self.c(self.dir).post('/api/organizacion/usuarios/', {
            'username': 'kelvin.hinojosa', 'first_name': 'Kelvin', 'last_name': 'Hinojosa', 'password': 'Temp-Xk29-pq81-Lm',
            'roles_asignados': ['Supervisor'], 'perfil': {'puesto_trabajo_id': mkt.pk}}, format='json')
        self.assertIn(r.status_code, (200, 201), r.content)
        k = User.objects.get(username='kelvin.hinojosa')
        self.assertTrue(k.perfil.debe_cambiar_clave)
        c = APIClient()
        r = c.post('/api/auth/login/', {'username': 'kelvin.hinojosa', 'password': 'Temp-Xk29-pq81-Lm'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['user']['debe_cambiar_clave'])
        self.assertEqual(c.get('/api/desempeno/tareas/').status_code, 403)
        self.assertEqual(c.post('/api/auth/cambiar-clave/', {'actual': 'Temp-Xk29-pq81-Lm', 'nueva': 'Mi-Propia-Clave-77'}, format='json').status_code, 200)
        self.assertEqual(c.get('/api/desempeno/tareas/').status_code, 200)
        from apps.core.permisos import permisos
        self.assertNotIn('direccion', permisos(User.objects.get(pk=k.pk)))


class EditarMensajesTests(Base):
    def setUp(self):
        super().setUp()
        self.a, self.b = self.gente['Marketing'], self.gente['Audiovisual']
        self.conv = chat.privado_con(self.a, self.b)

    def enviar(self):
        return self.c(self.a).post(f'/api/chat/conversaciones/{self.conv.pk}/mensajes/', {'texto': 'Reunion a las 3'}, format='json').json()['id']

    def test_8_10_11_edita_el_suyo_dentro_de_5_minutos_y_queda_marcado(self):
        mid = self.enviar()
        creado = Mensaje.objects.get(pk=mid).creado
        r = self.c(self.a).patch(f'/api/chat/mensajes/{mid}/', {'texto': 'Reunión a las 3:30'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        m = Mensaje.objects.get(pk=mid)
        self.assertEqual((m.texto, m.creado), ('Reunión a las 3:30', creado))   # la hora de envío no cambia
        self.assertIsNotNone(m.editado_en)
        self.assertEqual(EdicionMensaje.objects.get(mensaje=m).texto_anterior, 'Reunion a las 3')
        self.assertEqual(Mensaje.objects.filter(conversacion=self.conv).count(), 1)   # sin duplicados
        # Nadie edita mensajes de otro
        self.assertEqual(self.c(self.b).patch(f'/api/chat/mensajes/{mid}/', {'texto': 'hackeado'}, format='json').status_code, 403)
        # La otra persona recibe la versión editada al consultar lo nuevo
        nuevos = self.c(self.b).get(f'/api/chat/conversaciones/{self.conv.pk}/mensajes/?despues={mid}').json()['mensajes']
        self.assertEqual([(x['id'], x['texto'], bool(x['editado_en'])) for x in nuevos], [(mid, 'Reunión a las 3:30', True)])
        self.assertIsNone(nuevos[0]['editable_hasta'])   # a quien no lo escribió no se le ofrece editar

    def test_9_despues_de_5_minutos_ya_no_se_edita(self):
        mid = self.enviar()
        Mensaje.objects.filter(pk=mid).update(creado=timezone.now() - timedelta(minutes=5, seconds=1))
        r = self.c(self.a).patch(f'/api/chat/mensajes/{mid}/', {'texto': 'tarde'}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Mensaje.objects.get(pk=mid).texto, 'Reunion a las 3')


class FiltroPorDepartamentoTests(Base):
    def test_12_15_tareas_por_departamento_combinado_y_sin_salir_de_lo_permitido(self):
        hoy = timezone.localdate()
        for area in ('Marketing', 'Audiovisual', 'Impresión'):
            Tarea.objects.create(titulo=f'T {area}', colaborador=self.gente[area], fecha_limite=hoy)
        Tarea.objects.create(titulo='T Marketing vencida', colaborador=self.gente['Marketing'], fecha_limite=hoy - timedelta(days=3))
        c = self.c(self.dir)
        r = c.get(f'/api/desempeno/tareas/?ambito=equipo&departamento={self.d["Marketing"].pk}').json()
        self.assertEqual({t['titulo'] for t in r}, {'T Marketing', 'T Marketing vencida'})
        r = c.get(f'/api/desempeno/tareas/?ambito=equipo&departamento={self.d["Marketing"].pk}&vencidas=1').json()
        self.assertEqual([t['titulo'] for t in r], ['T Marketing vencida'])
        # Un colaborador que pide otro departamento por la API no ve nada que no fuera ya suyo
        r = self.c(self.gente['Audiovisual']).get(f'/api/desempeno/tareas/?ambito=equipo&departamento={self.d["Impresión"].pk}').json()
        self.assertEqual(r, [])
