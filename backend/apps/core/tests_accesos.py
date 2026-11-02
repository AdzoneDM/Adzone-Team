"""Mínimo privilegio: perfiles + organigrama, excepciones, equipo adicional y anti-escalada."""
from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient
from django.test import TestCase

from apps.core.models import Departamento, EquipoExtra, ExcepcionPermiso, PermisosDePerfil
from apps.core.permisos import permisos, tiene
from apps.desempeno.models import Tarea
from apps.organizacion.models import PuestoDeTrabajo

LIMITE = str(date.today() + timedelta(days=5))


class Base(TestCase):
    def setUp(self):
        mkt = Departamento.objects.create(nombre='Marketing')
        ven = Departamento.objects.create(nombre='Ventas')
        self.p_jefe = PuestoDeTrabajo.objects.create(nombre='Gerente MKT', departamento=mkt)
        self.p_cm = PuestoDeTrabajo.objects.create(nombre='Community', departamento=mkt, supervisor=self.p_jefe)
        self.p_ven = PuestoDeTrabajo.objects.create(nombre='Vendedor', departamento=ven)
        self.jefe = self._u('jefe', self.p_jefe)
        self.ana = self._u('ana', self.p_cm)
        self.beto = self._u('beto', self.p_ven)
        self.dir = self._u('dir', None, 'Administrador')
        self.sis = self._u('sis', None, 'Administrador del sistema')

    def _u(self, n, puesto, perfil=None):
        u = User.objects.create_user(n, password='x', first_name=n.title())
        if puesto:
            u.perfil.puesto_trabajo = puesto
            u.perfil.salario_mensual = 50000
            u.perfil.save()
        if perfil:
            u.groups.set([Group.objects.get(name=perfil)])
        return User.objects.get(pk=u.pk)

    def como(self, u):
        c = APIClient()
        c.force_authenticate(User.objects.get(pk=u.pk))  # sin la caché de permisos de una petición anterior
        return c

    def tarea(self, quien, para):
        return self.como(quien).post('/api/desempeno/tareas/', {'titulo': 'x', 'colaborador': para.pk, 'fecha_limite': LIMITE})


class PerfilesYOrganigramaTests(Base):
    def test_el_organigrama_da_el_perfil_de_supervisor(self):
        self.assertIn('Supervisor', self.jefe.groups.values_list('name', flat=True))
        self.assertTrue(tiene(self.jefe, 'tareas.asignar'))
        self.assertEqual(permisos(self.ana), set())  # colaborador: solo lo suyo
        self.assertTrue(tiene(self.dir, 'tareas.validar'))  # Dirección: todo el equipo, toda la empresa

    def test_colaborador_solo_cumple_sus_tareas(self):
        self.assertEqual(self.tarea(self.ana, self.beto).status_code, 403)
        self.assertEqual(self.como(self.ana).get('/api/monitoreo/equipo/').status_code, 403)
        self.assertEqual(self.como(self.ana).get('/api/asistencia/hoy/').status_code, 403)
        self.assertEqual(self.como(self.ana).get('/api/accesos/').status_code, 403)
        s = self.como(self.ana).get('/api/auth/session/').json()['user']
        self.assertEqual(s['permisos'], [])
        self.assertFalse(s['puede_asignar'])

    def test_supervisor_asigna_y_valida_solo_a_su_equipo_y_no_ve_monitoreo(self):
        self.assertEqual(self.tarea(self.jefe, self.ana).status_code, 201)
        self.assertEqual(self.tarea(self.jefe, self.beto).status_code, 403)  # no depende de él
        self.assertEqual(self.como(self.jefe).get('/api/monitoreo/equipo/').status_code, 403)
        self.assertEqual(self.como(self.jefe).get('/api/monitoreo/pantallas/').status_code, 403)
        self.assertEqual(self.como(self.jefe).get('/api/asistencia/hoy/').status_code, 200)
        self.assertEqual(self.como(self.jefe).get('/api/talento/salarios/').status_code, 403)
        s = self.como(self.jefe).get('/api/auth/session/').json()['user']
        self.assertTrue(s['puede_asignar'])
        self.assertFalse(s['ve_monitoreo'])
        self.assertFalse(s['es_administrador'])

    def test_equipo_adicional_y_vencido(self):
        EquipoExtra.objects.create(jefe=self.jefe, colaborador=self.beto, motivo='Proyecto Q4')
        self.assertEqual(self.tarea(self.jefe, self.beto).status_code, 201)
        EquipoExtra.objects.filter(jefe=self.jefe).update(hasta=date.today() - timedelta(days=1))
        self.assertEqual(self.tarea(self.jefe, self.beto).status_code, 403)

    def test_excepcion_quita_un_permiso_del_perfil(self):
        ExcepcionPermiso.objects.create(usuario=self.jefe, permiso='tareas.asignar', conceder=False, motivo='Solo valida')
        self.assertEqual(self.tarea(self.jefe, self.ana).status_code, 403)
        self.assertTrue(tiene(User.objects.get(pk=self.jefe.pk), 'tareas.validar'))

    def test_gerente_de_departamento_maneja_el_expediente(self):
        nota = {'colaborador': self.ana.pk, 'tipo': 'OBSERVACION', 'fecha': str(date.today()), 'titulo': 'x'}
        self.assertEqual(self.como(self.jefe).post('/api/talento/expediente/', nota, format='json').status_code, 403)
        self.jefe.groups.set([Group.objects.get(name='Gerente de Departamento')])
        self.assertEqual(self.como(self.jefe).post('/api/talento/expediente/', nota, format='json').status_code, 201)


class AdministradorDelSistemaTests(Base):
    def test_configura_pero_no_ve_salarios_ni_expedientes(self):
        c = self.como(self.sis)
        self.assertEqual(c.get('/api/accesos/').status_code, 200)
        usuarios = c.get('/api/organizacion/usuarios/').json()
        fila = next(u for u in (usuarios['results'] if isinstance(usuarios, dict) else usuarios) if u['id'] == self.ana.pk)
        self.assertIsNone(fila['salario_mensual'])
        self.assertEqual(c.get('/api/talento/salarios/').status_code, 403)
        self.assertEqual(c.get(f'/api/talento/documentos/?usuario={self.ana.pk}').json(), [])
        self.assertEqual(c.get('/api/monitoreo/equipo/').status_code, 200)
        self.assertEqual(c.get('/api/talento/auditoria/').status_code, 200)
        self.assertFalse(c.get('/api/auth/session/').json()['user']['es_administrador'])

    def test_anti_escalada(self):
        c = self.como(self.sis)
        r = c.post(f'/api/accesos/personas/{self.ana.pk}/perfiles/', {'perfiles': ['Gestión del Talento']}, format='json')
        self.assertEqual(r.status_code, 403)  # daría salarios y RRHH, que él no tiene
        r = c.post(f'/api/accesos/personas/{self.ana.pk}/perfiles/', {'perfiles': ['Tecnología']}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['perfiles'], ['Tecnología'])
        self.assertEqual(c.post(f'/api/accesos/personas/{self.sis.pk}/perfiles/', {'perfiles': ['Administrador']}, format='json').status_code, 403)
        self.assertEqual(c.post(f'/api/accesos/personas/{self.dir.pk}/perfiles/', {'perfiles': ['Colaborador']}, format='json').status_code, 403)
        r = c.post('/api/accesos/excepciones/', {'usuario': self.ana.pk, 'permiso': 'personal.salarios', 'motivo': 'x'}, format='json')
        self.assertEqual(r.status_code, 403)
        r = c.post('/api/accesos/excepciones/', {'usuario': self.ana.pk, 'permiso': 'auditoria.ver'}, format='json')
        self.assertEqual(r.status_code, 400)  # sin motivo
        self.assertEqual(c.patch(f"/api/accesos/perfiles/{Group.objects.get(name='Supervisor').pk}/", {'permisos': []}, format='json').status_code, 403)
        # tampoco puede cambiarle la contraseña a Dirección para entrar como ella
        self.assertEqual(c.patch(f'/api/organizacion/usuarios/{self.dir.pk}/', {'password': 'Otra-clave-2026!'}, format='json').status_code, 400)
        # por la API de personas tampoco
        r = c.patch(f'/api/organizacion/usuarios/{self.ana.pk}/', {'roles_asignados': ['Finanzas']}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_excepciones_y_equipo_adicional_por_la_api(self):
        c = self.como(self.sis)
        r = c.post('/api/accesos/excepciones/', {'usuario': self.ana.pk, 'permiso': 'monitoreo.ver', 'motivo': 'Apoyo a TI'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(tiene(User.objects.get(pk=self.ana.pk), 'monitoreo.ver'))
        self.assertEqual(c.delete(f"/api/accesos/excepciones/{r.json()['id']}/").status_code, 204)
        datos = {'jefe': self.jefe.pk, 'colaborador': self.beto.pk, 'motivo': 'Proyecto'}
        self.assertEqual(c.post('/api/accesos/equipo-extra/', datos, format='json').status_code, 403)  # delegaría permisos de equipo que no tiene
        d = self.como(self.dir)
        self.assertEqual(d.post('/api/accesos/equipo-extra/', {**datos, 'hasta': '2020-01-01'}, format='json').status_code, 400)
        r = d.post('/api/accesos/equipo-extra/', datos, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(d.post('/api/accesos/equipo-extra/', {'jefe': self.jefe.pk, 'colaborador': self.sis.pk}, format='json').status_code, 403)
        personas = {p['id']: p for p in c.get('/api/accesos/personas/').json()}
        self.assertEqual(personas[self.jefe.pk]['equipo_extra'][0]['colaborador'], self.beto.pk)
        self.assertEqual(c.post('/api/accesos/equipo-extra/', {'jefe': self.sis.pk, 'colaborador': self.ana.pk}, format='json').status_code, 403)
        from apps.talento.models import AuditoriaCambio
        self.assertTrue(AuditoriaCambio.objects.filter(accion='Equipo adicional').exists())


class DireccionTests(Base):
    def test_direccion_ajusta_perfiles(self):
        c = self.como(self.dir)
        cat = c.get('/api/accesos/').json()
        self.assertTrue(cat['edita_perfiles'])
        sup = Group.objects.get(name='Supervisor')
        r = c.patch(f'/api/accesos/perfiles/{sup.pk}/', {'permisos': ['tareas.asignar', 'tareas.validar', 'equipo.ver', 'equipo.evaluar',
                                                                        'asistencia.ver', 'equipo.expediente']}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(tiene(User.objects.get(pk=self.jefe.pk), 'equipo.expediente'))
        self.assertEqual(c.patch(f'/api/accesos/perfiles/{sup.pk}/', {'permisos': ['no.existe']}, format='json').status_code, 400)
        adm = Group.objects.get(name='Administrador')
        self.assertEqual(c.patch(f'/api/accesos/perfiles/{adm.pk}/', {'permisos': []}, format='json').status_code, 400)
        r = c.post('/api/accesos/perfiles/', {'nombre': 'Coordinador de proyecto', 'permisos': ['tareas.asignar']}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(c.delete(f"/api/accesos/perfiles/{r.json()['id']}/").status_code, 204)
        self.assertEqual(c.delete(f'/api/accesos/perfiles/{sup.pk}/').status_code, 400)  # de la plataforma

    def test_perfiles_iniciales(self):
        nombres = set(PermisosDePerfil.objects.values_list('grupo__name', flat=True))
        self.assertTrue({'Colaborador', 'Supervisor', 'Gerente de Departamento', 'Administrador', 'Administrador del sistema',
                         'Tecnología', 'Gestión del Talento'} <= nombres)
        self.assertNotIn('personal.salarios', PermisosDePerfil.objects.get(grupo__name='Administrador del sistema').permisos)
        self.assertNotIn('talento.rrhh', PermisosDePerfil.objects.get(grupo__name='Administrador del sistema').permisos)


class SeguridadTests(Base):
    """Casos de la revisión de seguridad de v11."""

    def test_no_se_cambia_su_propio_puesto_para_ganar_equipo(self):
        c = self.como(self.sis)
        r = c.patch(f'/api/organizacion/usuarios/{self.sis.pk}/', {'puesto_trabajo_id': self.p_jefe.pk}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertNotIn('Supervisor', User.objects.get(pk=self.sis.pk).groups.values_list('name', flat=True))

    def test_el_organigrama_no_reparte_supervisor_sin_permiso_de_quien_cambia(self):
        self.jefe.groups.set([Group.objects.get(name='Colaborador')])  # la Dirección lo dejó como colaborador
        c = self.como(self.sis)
        self.assertEqual(c.patch(f'/api/organizacion/usuarios/{self.jefe.pk}/', {'horas_semana': 40}, format='json').status_code, 200)
        self.assertEqual(list(User.objects.get(pk=self.jefe.pk).groups.values_list('name', flat=True)), ['Colaborador'])
        # crear a alguien en un puesto con gente a cargo tampoco le da Supervisor si quien lo crea no puede darlo
        p2 = PuestoDeTrabajo.objects.create(nombre='Jefe 2', departamento=self.p_jefe.departamento)
        self.p_cm.supervisor = p2
        self.p_cm.save()
        r = c.post('/api/organizacion/usuarios/', {'first_name': 'Nuevo', 'username': 'nuevo', 'password': 'Clave-muy-segura-2026',
                                                   'puesto_trabajo_id': p2.pk}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(list(User.objects.get(username='nuevo').groups.values_list('name', flat=True)), ['Colaborador'])
        # la Dirección sí
        r = self.como(self.dir).post('/api/organizacion/usuarios/', {'first_name': 'Otro', 'username': 'otro', 'password': 'Clave-muy-segura-2026',
                                                                     'puesto_trabajo_id': p2.pk}, format='json')
        self.assertIn('Supervisor', User.objects.get(username='otro').groups.values_list('name', flat=True))

    def test_auditoria_sin_salarios_ni_expedientes_para_el_admin_del_sistema(self):
        from apps.talento.auditoria import auditar
        auditar('Cambió perfil de persona', 'Ana', {'salario_mensual': 40000, 'horas_semana': 44}, {'salario_mensual': 55000, 'horas_semana': 40})
        auditar('Creó documento del expediente', 'Amonestación de Ana', None, {'titulo': 'Amonestación'})
        filas = self.como(self.sis).get('/api/talento/auditoria/').json()
        sal = next(f for f in filas if f['accion'] == 'Cambió perfil de persona')
        self.assertEqual(sal['despues'], {'salario_mensual': 'reservado', 'horas_semana': 40})
        doc = next(f for f in filas if 'expediente' in f['accion'])
        self.assertEqual((doc['objeto'], doc['despues']), ('reservado', None))
        filas = self.como(self.dir).get('/api/talento/auditoria/').json()
        self.assertEqual(next(f for f in filas if f['accion'] == 'Cambió perfil de persona')['despues']['salario_mensual'], 55000)

    def test_quitar_a_la_ultima_persona_de_direccion(self):
        self.dir2 = self._u('dir2', None, 'Administrador')
        r = self.como(self.dir2).post(f'/api/accesos/personas/{self.dir.pk}/perfiles/', {'perfiles': ['Colaborador']}, format='json')
        self.assertEqual(r.status_code, 200)
        r = self.como(self.dir).post(f'/api/accesos/personas/{self.dir2.pk}/perfiles/', {'perfiles': ['Colaborador']}, format='json')
        self.assertEqual(r.status_code, 403)  # ya no es Dirección
