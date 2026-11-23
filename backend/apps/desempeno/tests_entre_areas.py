"""Asignar entre áreas, autovalidación y el caso de Enmanuel (todas las áreas menos Call Center)."""
from datetime import timedelta

from django.contrib.auth.models import Group
from django.utils import timezone

from apps.core.models import Departamento
from apps.organizacion.models import PuestoDeTrabajo
from .models import HistorialTarea, Tarea
from .tests_mejoras import Base

T = '/api/desempeno/tareas/'


class EntreAreasTests(Base):
    def setUp(self):
        super().setUp()
        self.cc = Departamento.objects.create(nombre='Call Center')
        self.p_agente = PuestoDeTrabajo.objects.create(nombre='Agente', departamento=self.cc)
        self.agente = self._u('agente', self.p_agente, 'Ana', 'Agente')
        self.enmanuel = self._u('enmanuel', self.p_gerente, 'Enmanuel', 'Beltre')                       # gerente de Marketing
        self.enmanuel.groups.add(Group.objects.get(name='Gerente de Departamento'))
        self.sup_ti = self._u('sup_ti', self.p_dev, 'Sup', 'TI')
        self.sup_ti.groups.add(Group.objects.get(name='Supervisor'))                                      # supervisor: sin permiso entre áreas

    def crear(self, quien, para, **extra):
        self.como(quien)
        return self.c.post(T, {'titulo': 'Aporte', 'colaborador': para.id, 'fecha_limite': str(timezone.localdate() + timedelta(days=3)),
                               'prioridad': 'MEDIA', **extra}, format='json')

    def test_un_gerente_asigna_a_otra_area_y_la_tarea_conserva_su_origen(self):
        r = self.crear(self.enmanuel, self.dev)
        self.assertEqual(r.status_code, 201, r.content)
        j = r.json()
        self.assertEqual((j['departamento_origen_nombre'], j['colaborador_departamento'], j['entre_areas']), ('Marketing', 'Tecnología', True))
        self.assertEqual(j['asignada_por'], self.enmanuel.id)
        self.assertTrue(HistorialTarea.objects.filter(tarea_id=j['id']).exists())                         # queda el historial

    def test_a_su_propio_equipo_no_es_entre_areas(self):
        j = self.crear(self.enmanuel, self.erlin).json()
        self.assertEqual((j['departamento_origen_nombre'], j['entre_areas']), ('Marketing', False))

    def test_call_center_y_direccion_no_reciben_tareas_de_otras_areas(self):
        r = self.crear(self.enmanuel, self.agente)
        self.assertEqual(r.status_code, 403, r.content)
        self.assertFalse(Tarea.objects.filter(colaborador=self.agente).exists())
        self.assertEqual(self.crear(self.enmanuel, self.osiris).status_code, 403)

    def test_sin_el_permiso_no_se_asigna_a_otras_areas(self):
        self.assertEqual(self.crear(self.sup_ti, self.erlin).status_code, 403)
        self.assertEqual(self.crear(self.erlin, self.dev).status_code, 403)                               # colaborador raso

    def test_la_lista_de_a_quien_asignar_incluye_otras_areas_sin_call_center(self):
        self.como(self.enmanuel)
        ids = {p['id'] for p in self.c.get('/api/desempeno/equipo/').json()}
        self.assertTrue({self.erlin.id, self.dev.id, self.sup_ti.id} <= ids)
        self.assertNotIn(self.agente.id, ids)
        self.assertNotIn(self.osiris.id, ids)
        self.assertNotIn(self.enmanuel.id, ids - {self.enmanuel.id})
        self.como(self.sup_ti)
        self.assertNotIn(self.erlin.id, {p['id'] for p in self.c.get('/api/desempeno/equipo/').json()})

    def test_quien_asigno_la_ve_y_la_gestiona_pero_otro_gerente_no_la_toca(self):
        t = self.crear(self.enmanuel, self.dev).json()
        self.como(self.enmanuel)
        ids = {x['id'] for x in (lambda r: r['results'] if isinstance(r, dict) else r)(self.c.get(T + '?ambito=equipo').json())}
        self.assertIn(t['id'], ids)
        self.assertTrue(self.c.get(f"{T}{t['id']}/").json()['puedo_gestionar'])
        self.assertEqual(self.c.patch(f"{T}{t['id']}/", {'titulo': 'Cambiado'}, format='json').status_code, 200)
        otro = self._u('otro', self.p_gerente, 'Otro', 'Gerente')
        otro.groups.add(Group.objects.get(name='Gerente de Departamento'))
        self.como(otro)
        self.assertEqual(self.c.patch(f"{T}{t['id']}/", {'titulo': 'Robada'}, format='json').status_code, 404)  # ni siquiera la ve

    def test_el_destinatario_la_trabaja_y_quien_la_pidio_la_valida(self):
        t = self.crear(self.enmanuel, self.dev).json()
        Tarea.objects.filter(pk=t['id']).update(estado='EN_REVISION', evidencia_nota='listo', fecha_completada=timezone.localdate())
        self.como(self.enmanuel)
        pend = (lambda r: r['results'] if isinstance(r, dict) else r)(self.c.get(T + '?ambito=por_validar').json())
        self.assertIn(t['id'], {x['id'] for x in pend})
        r = self.c.post(f"{T}{t['id']}/validar/", {'calificacion_calidad': 5, 'comentario_evaluacion': 'bien'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(Tarea.objects.get(pk=t['id']).validada_por, self.enmanuel)


class AutovalidacionTests(Base):
    def setUp(self):
        super().setUp()
        self.vladi.groups.add(Group.objects.get(name='Supervisor'))                                       # tiene «Asignarse tareas a sí mismo»

    def propia(self, quien):
        self.como(quien)
        r = self.c.post(T, {'titulo': 'Mi tarea', 'colaborador': quien.id, 'fecha_limite': str(timezone.localdate() + timedelta(days=2)),
                            'prioridad': 'MEDIA'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return Tarea.objects.get(pk=r.json()['id'])

    def entregar_y(self, t):
        Tarea.objects.filter(pk=t.pk).update(estado='EN_REVISION', evidencia_nota='hecho', fecha_completada=timezone.localdate())

    def test_quien_se_asigna_tareas_las_valida_y_queda_registrado(self):
        t = self.propia(self.vladi)
        self.assertIsNone(t.revisor)                                                                      # el revisor ya no es obligatorio
        self.entregar_y(t)
        r = self.c.post(f'{T}{t.id}/validar/', {'calificacion_calidad': 4, 'comentario_evaluacion': 'ok'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        t.refresh_from_db()
        self.assertEqual((t.estado, t.validada_por, t.asignada_por, t.colaborador), ('COMPLETADA', self.vladi, self.vladi, self.vladi))
        self.assertTrue(r.json()['autovalidada'])
        h = HistorialTarea.objects.filter(tarea=t, accion='VALIDADA').get()
        self.assertEqual(h.usuario, self.vladi)
        self.assertIn('Autovalidada', h.comentario)

    def test_aparece_en_por_validar_y_en_el_conteo(self):
        t = self.propia(self.vladi)
        self.entregar_y(t)
        pend = (lambda r: r['results'] if isinstance(r, dict) else r)(self.c.get(T + '?ambito=por_validar').json())
        self.assertIn(t.id, {x['id'] for x in pend})
        self.assertGreaterEqual(self.c.get('/api/desempeno/notificaciones/').json()['por_validar'], 1)

    def test_devolver_o_reabrir_lo_propio_sigue_prohibido(self):
        t = self.propia(self.vladi)
        self.entregar_y(t)
        r = self.c.post(f'{T}{t.id}/rechazar/', {'comentario_revision': 'rehacer esto por favor'}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_no_se_valida_lo_que_otra_persona_te_asigno_ni_sin_el_permiso(self):
        ajena = self.tarea(self.vladi, estado='EN_REVISION', asignada_por=self.osiris, fecha_completada=timezone.localdate())
        self.como(self.vladi)
        self.assertEqual(self.c.post(f'{T}{ajena.id}/validar/', {'calificacion_calidad': 5}, format='json').status_code, 403)
        # un colaborador sin «Asignarse tareas» no puede ni crearse una tarea ni validarla
        self.como(self.erlin)
        propia_erlin = self.tarea(self.erlin, estado='EN_REVISION', asignada_por=self.erlin, fecha_completada=timezone.localdate())
        self.assertEqual(self.c.post(f'{T}{propia_erlin.id}/validar/', {'calificacion_calidad': 5}, format='json').status_code, 403)

    def test_si_eligio_revisor_este_tambien_puede_validar(self):
        from .models import ConfiguracionDesempeno
        helen = self._u('helen', None, 'Helen', 'Castillo')
        helen.groups.add(Group.objects.get_or_create(name='Administrador')[0])
        ConfiguracionDesempeno.actual().revisores_propias.set([helen])
        self.como(self.vladi)
        r = self.c.post(T, {'titulo': 'Con revisor', 'colaborador': self.vladi.id, 'revisor': helen.id,
                            'fecha_limite': str(timezone.localdate() + timedelta(days=2)), 'prioridad': 'MEDIA'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        t = Tarea.objects.get(pk=r.json()['id'])
        self.entregar_y(t)
        self.como(helen)
        self.assertEqual(self.c.post(f'{T}{t.id}/validar/', {'calificacion_calidad': 5}, format='json').status_code, 200)
