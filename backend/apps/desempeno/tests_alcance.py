"""Alcance configurable desde «Accesos y permisos»: supervisar a toda la empresa y asignarse tareas a sí mismo."""
from datetime import timedelta

from django.contrib.auth.models import Group
from django.utils import timezone

from apps.core.models import ExcepcionPermiso
from apps.core.permisos import PERMISOS
from apps.organizacion.models import PuestoDeTrabajo
from .models import Notificacion, Tarea
from .permisos import equipo_gestionable, puede_gestionar, revisores_de
from .tests_mejoras import Base

T = '/api/desempeno/tareas/'


class AlcanceTests(Base):
    def setUp(self):
        super().setUp()
        self.p_ops = PuestoDeTrabajo.objects.create(nombre='Gerente de Operaciones', departamento=self.tec)
        self.rebeca = self._u('rebeca', self.p_ops, 'Rebeca', 'Acosta')
        self.rebeca.groups.add(Group.objects.get(name='Gerente de Departamento'))
        self.ana = self._u('ana', None, 'Ana', 'Sola')  # sin puesto en el organigrama

    def dar(self, usuario, codigo, conceder=True):
        ExcepcionPermiso.objects.create(usuario=usuario, permiso=codigo, conceder=conceder)
        usuario.__dict__.pop('_permisos_acceso', None)  # los permisos se calculan una vez por petición; aquí se recalculan

    def nueva(self, quien, para):
        self.como(quien)
        datos = {'titulo': 'Reporte', 'colaborador': para.id, 'fecha_limite': str(timezone.localdate() + timedelta(days=2)), 'prioridad': 'MEDIA'}
        if para.pk == quien.pk:
            datos['revisor'] = self.osiris.id  # una tarea propia la valida un revisor (Dirección)
        return self.c.post(T, datos, format='json')

    def test_catalogo_incluye_los_permisos_nuevos(self):
        codigos = {p[0] for p in PERMISOS}
        self.assertLessEqual({'tareas.propias', 'equipo.todos'}, codigos)

    def test_sin_el_permiso_un_gerente_sin_equipo_no_ve_a_nadie(self):
        self.assertEqual(list(equipo_gestionable(self.rebeca)), [])
        # Sin «Asignar tareas a otras áreas» no puede asignarle a nadie fuera de su equipo (que está vacío)...
        self.dar(self.rebeca, 'tareas.otras_areas', conceder=False)
        self.assertEqual(self.nueva(self.rebeca, self.erlin).status_code, 403)
        # ...y con ese permiso (lo trae el perfil de gerente) sí puede pedirle un aporte a otra área
        ExcepcionPermiso.objects.filter(usuario=self.rebeca, permiso='tareas.otras_areas').delete()
        self.rebeca.__dict__.pop('_permisos_acceso', None)
        self.assertEqual(self.nueva(self.rebeca, self.erlin).status_code, 201)

    def test_supervisar_a_toda_la_empresa(self):
        self.dar(self.rebeca, 'equipo.todos')
        visibles = set(equipo_gestionable(self.rebeca).values_list('username', flat=True))
        self.assertEqual(visibles, {'vladi', 'erlin', 'ashley', 'dev', 'ana'})  # todos menos ella y Dirección (osiris)
        self.assertEqual(self.nueva(self.rebeca, self.dev).status_code, 201)        # otro departamento
        self.assertEqual(self.nueva(self.rebeca, self.osiris).status_code, 403)     # Dirección queda fuera
        self.assertTrue(puede_gestionar(self.rebeca, self.rebeca, 'tareas.asignar'))   # su perfil de gerente incluye asignarse tareas
        self.assertFalse(puede_gestionar(self.rebeca, self.rebeca, 'tareas.validar'))  # pero nunca valida lo suyo
        # ve y valida el trabajo de cualquiera, nunca el propio
        t = self.tarea(self.erlin, estado='EN_REVISION', evidencia_nota='listo')
        self.como(self.rebeca)
        self.assertEqual(self.c.get(f'{T}{t.id}/').status_code, 200)
        lista = self.c.get(T, {'ambito': 'por_validar'}).json()
        lista = lista['results'] if isinstance(lista, dict) else lista
        self.assertIn(t.id, [x['id'] for x in lista])
        self.assertEqual(self.c.post(f'{T}{t.id}/validar/', {'calificacion_calidad': 5, 'comentario_evaluacion': 'Bien'}, format='json').status_code, 200)

    def test_recibe_los_avisos_de_entrega_de_todos(self):
        self.dar(self.rebeca, 'equipo.todos')
        self.assertIn(self.rebeca, revisores_de(self.dev))
        self.assertIn(self.rebeca, revisores_de(self.erlin))
        self.assertNotIn(self.rebeca, revisores_de(self.osiris))
        self.assertNotIn(self.rebeca, revisores_de(self.rebeca))

    def test_asignarse_tareas_a_si_mismo(self):
        self.assertEqual(self.nueva(self.ana, self.ana).status_code, 403)          # sin el permiso
        self.dar(self.ana, 'tareas.propias')
        r = self.nueva(self.ana, self.ana)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.nueva(self.ana, self.erlin).status_code, 403)        # solo a sí misma
        # aparece entre las personas a quienes puede asignar
        self.assertEqual(list(equipo_gestionable(self.ana, 'tareas.asignar')), [self.ana])
        self.como(self.ana)
        self.assertEqual([p['id'] for p in self.c.get('/api/desempeno/equipo/').json()], [self.ana.id])
        # quien se asigna tareas también las valida (autovalidación), pero no devuelve ni reabre lo propio
        tid = r.json()['id']
        Tarea.objects.filter(pk=tid).update(estado='EN_REVISION', evidencia_nota='hecho')
        self.como(self.ana)
        self.assertEqual(self.c.post(f'{T}{tid}/rechazar/', {'comentario_revision': 'rehacer todo'}, format='json').status_code, 403)
        self.assertEqual(self.c.post(f'{T}{tid}/validar/', {'calificacion_calidad': 5, 'comentario_evaluacion': 'Yo'}, format='json').status_code, 200)

    def test_gerente_puede_asignarse_a_si_mismo_y_se_le_puede_quitar(self):
        self.assertEqual(self.nueva(self.vladi, self.vladi).status_code, 201)          # por defecto, por ser quien supervisa
        self.dar(self.vladi, 'tareas.propias', conceder=False)                          # se quita desde Accesos y permisos
        self.assertEqual(self.nueva(self.vladi, self.vladi).status_code, 403)
        ExcepcionPermiso.objects.filter(usuario=self.vladi, permiso='tareas.propias').delete()
        self.vladi.__dict__.pop('_permisos_acceso', None)
        self.assertEqual(self.nueva(self.vladi, self.vladi).status_code, 201)
        self.assertEqual(self.nueva(self.vladi, self.erlin).status_code, 201)      # y a su equipo, como siempre
        # no se le avisa a sí mismo de su propia tarea
        self.assertFalse(Notificacion.objects.filter(destinatario=self.vladi, tipo='ASIGNADA', remitente=self.vladi).exists())


class SupervisoresSeAsignanTests(Base):
    def test_supervisores_y_gerentes_se_asignan_tareas_por_su_perfil(self):
        from django.core.management import call_command
        from apps.core.permisos import sembrar_perfiles
        sembrar_perfiles()
        for perfil, quien in (('Supervisor', self.vladi), ('Gerente de Departamento', self.erlin)):
            quien.groups.add(Group.objects.get(name=perfil))
            quien.__dict__.pop('_permisos_acceso', None)
            self.como(quien)
            r = self.c.post(T, {'titulo': 'Mi tarea', 'colaborador': quien.id, 'revisor': self.osiris.id,
                                'fecha_limite': str(timezone.localdate() + timedelta(days=2)), 'prioridad': 'MEDIA'}, format='json')
            self.assertEqual(r.status_code, 201, (perfil, r.content))
        # Dirección también (lo trae por ser Dirección, sin configurar nada)
        otra_direccion = self._u('helen', None, 'Helen', 'Castillo')
        otra_direccion.groups.add(Group.objects.get_or_create(name='Administrador')[0])
        self.como(self.osiris)
        r = self.c.post(T, {'titulo': 'Mi tarea', 'colaborador': self.osiris.id, 'revisor': otra_direccion.id,
                            'fecha_limite': str(timezone.localdate() + timedelta(days=2)), 'prioridad': 'MEDIA'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
