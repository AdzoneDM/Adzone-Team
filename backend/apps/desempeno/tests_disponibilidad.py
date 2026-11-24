"""Quién está libre (público para todos) e historial de tareas (quién la hizo, la asignó y la validó)."""
from datetime import timedelta

from django.contrib.auth.models import Group
from django.utils import timezone

from apps.asistencia.models import Ausencia
from apps.core.models import Departamento
from apps.organizacion.models import PuestoDeTrabajo
from .models import Tarea
from .tests_mejoras import Base

DISP = '/api/desempeno/disponibilidad/'
HIST = '/api/desempeno/historial-tareas/'


def lista(r):
    j = r.json()
    return j['results'] if isinstance(j, dict) and 'results' in j else j


class DisponibilidadTests(Base):
    def setUp(self):
        super().setUp()
        self.vladi.groups.add(Group.objects.get(name='Gerente de Departamento'))

    def estados(self, quien):
        self.como(quien)
        r = self.c.get(DISP)
        self.assertEqual(r.status_code, 200, r.content)
        return {p['usuario']: p for p in r.json()['personas']}, r.json()

    def test_libre_poca_carga_y_ocupado(self):
        self.tarea(self.erlin)
        for _ in range(3):
            self.tarea(self.ashley)                                                # 3 abiertas = ocupada
        for _ in range(2):
            self.tarea(self.dev)                                                   # 2 abiertas = poca carga
        p, j = self.estados(self.vladi)
        self.assertEqual((p['erlin']['estado'], p['erlin']['tareas_abiertas']), ('POCA', 1))
        self.assertEqual((p['ashley']['estado'], p['ashley']['tareas_abiertas']), ('OCUPADO', 3))
        self.assertEqual((p['dev']['estado'], p['dev']['tareas_abiertas']), ('POCA', 2))
        self.assertEqual(p['vladi']['estado'], 'LIBRE')                            # sin tareas = libre
        self.assertEqual(j['resumen'], {'libres': 1, 'poca_carga': 2, 'ocupados': 1, 'no_disponibles': 0})

    def test_lo_entregado_o_terminado_no_cuenta_como_carga(self):
        self.tarea(self.erlin, estado='EN_REVISION')
        self.tarea(self.erlin, estado='COMPLETADA')
        self.tarea(self.erlin, estado='CANCELADA')
        p, _ = self.estados(self.vladi)
        self.assertEqual((p['erlin']['estado'], p['erlin']['en_revision']), ('LIBRE', 1))

    def test_colaborar_en_una_tarea_cuenta_y_se_ve_la_proxima_entrega_y_las_horas(self):
        t = self.tarea(self.erlin, dias=5, horas_estimadas=3)
        t.companeros.add(self.ashley)
        p, _ = self.estados(self.vladi)
        self.assertEqual(p['ashley']['tareas_abiertas'], 1)
        self.assertEqual(p['erlin']['horas_pendientes'], 3.0)
        self.assertEqual(p['erlin']['proxima_entrega'], str(timezone.localdate() + timedelta(days=5)))

    def test_quien_esta_de_permiso_hoy_no_aparece_como_libre(self):
        hoy = timezone.localdate()
        Ausencia.objects.create(usuario=self.erlin, tipo='VACACIONES', desde=hoy - timedelta(days=1), hasta=hoy + timedelta(days=2), estado='APROBADA')
        Ausencia.objects.create(usuario=self.ashley, tipo='PERMISO', desde=hoy, hasta=hoy, estado='PENDIENTE')     # sin aprobar: no cuenta
        p, j = self.estados(self.vladi)
        self.assertEqual((p['erlin']['estado'], p['ashley']['estado']), ('AUSENTE', 'LIBRE'))
        self.assertEqual(j['resumen']['no_disponibles'], 1)

    def test_es_publico_para_todos_los_departamentos_y_no_revela_de_que_son_las_tareas(self):
        Tarea.objects.create(titulo='Plan secreto del cliente X', colaborador=self.dev, fecha_limite=timezone.localdate() + timedelta(days=2))
        for quien in (self.erlin, self.dev, self.vladi):                          # una colaboradora raso, alguien de otra área y una gerente
            p, _ = self.estados(quien)
            self.assertTrue({'vladi', 'erlin', 'ashley', 'dev'} <= set(p), quien.username)         # todos los departamentos
        self.como(self.erlin)
        self.assertNotIn('Plan secreto', self.c.get(DISP).content.decode())

    def test_no_aparecen_inactivos_agentes_ni_gente_sin_puesto(self):
        cc = Departamento.objects.create(nombre='Call Center')
        agente = self._u('agente', PuestoDeTrabajo.objects.create(nombre='Agente', departamento=cc), 'Ana', 'Agente')
        agente.groups.add(Group.objects.get_or_create(name='Agente Call Center')[0])
        self.ashley.is_active = False
        self.ashley.save()
        p, _ = self.estados(self.vladi)
        self.assertNotIn('agente', p)
        self.assertNotIn('ashley', p)
        self.assertNotIn('osiris', p)                                              # sin puesto

    def test_marca_a_quien_puedo_asignar_y_a_quien_puedo_pedir_apoyo(self):
        p, _ = self.estados(self.vladi)                                             # gerente: asigna a su equipo y pide apoyo entre áreas
        self.assertTrue(p['erlin']['puedo_asignar'] and p['erlin']['puedo_pedir_apoyo'])
        self.assertFalse(p['vladi']['puedo_asignar'] or p['vladi']['puedo_pedir_apoyo'])           # a sí mismo no
        p, _ = self.estados(self.erlin)                                             # colaboradora: apoyo solo dentro de su departamento
        self.assertTrue(p['ashley']['puedo_pedir_apoyo'])
        self.assertFalse(p['dev']['puedo_pedir_apoyo'])
        self.assertFalse(any(x['puedo_asignar'] for x in p.values()))

    def test_exige_sesion(self):
        self.c.force_authenticate(None)
        self.assertIn(self.c.get(DISP).status_code, (401, 403))


class HistorialTareasTests(Base):
    def setUp(self):
        super().setUp()
        self.vladi.groups.add(Group.objects.get(name='Gerente de Departamento'))
        hoy = timezone.now()
        self.t1 = Tarea.objects.create(titulo='Post de lanzamiento', cliente='Solymar', colaborador=self.erlin, asignada_por=self.vladi, validada_por=self.vladi,
                                       estado='COMPLETADA', fecha_limite=timezone.localdate(), fecha_validacion=hoy, calificacion_calidad=5)
        self.t2 = Tarea.objects.create(titulo='Informe de redes', colaborador=self.ashley, asignada_por=self.vladi, validada_por=self.vladi,
                                       estado='COMPLETADA', fecha_limite=timezone.localdate(), fecha_validacion=hoy - timedelta(days=3), calificacion_calidad=3)
        self.t3 = Tarea.objects.create(titulo='Servidor nuevo', colaborador=self.dev, asignada_por=self.dev, validada_por=self.dev,
                                       estado='COMPLETADA', fecha_limite=timezone.localdate(), fecha_validacion=hoy - timedelta(days=1))
        self.abierta = self.tarea(self.erlin)                                       # abierta: no es historial

    def ver(self, quien, **params):
        self.como(quien)
        r = self.c.get(HIST, params)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def test_muestra_quien_la_hizo_quien_la_asigno_y_quien_la_valido(self):
        j = self.ver(self.osiris)
        fila = next(f for f in j['resultados'] if f['id'] == self.t1.id)
        self.assertEqual((fila['hizo']['nombre'], fila['asigno'], fila['valido'], fila['calidad'], fila['cliente']), ('Erlin Pérez', 'Vladimir Gómez', 'Vladimir Gómez', 5, 'Solymar'))
        self.assertEqual((fila['hizo']['puesto'], fila['hizo']['departamento']), ('Community Manager', 'Marketing'))
        self.assertNotIn(self.abierta.id, [f['id'] for f in j['resultados']])
        self.assertEqual([f['id'] for f in j['resultados']][:3], [self.t1.id, self.t3.id, self.t2.id])   # lo más reciente primero

    def test_marca_la_autovalidacion(self):
        j = self.ver(self.osiris)
        self.assertTrue(next(f for f in j['resultados'] if f['id'] == self.t3.id)['autovalidada'])
        self.assertFalse(next(f for f in j['resultados'] if f['id'] == self.t1.id)['autovalidada'])

    def test_cada_quien_ve_lo_que_ya_veia_su_equipo_y_lo_suyo(self):
        self.assertEqual({f['id'] for f in self.ver(self.erlin)['resultados']}, {self.t1.id})                       # solo la suya
        self.assertEqual({f['id'] for f in self.ver(self.vladi)['resultados']}, {self.t1.id, self.t2.id})           # su equipo (no la de Tecnología)
        self.assertEqual({f['id'] for f in self.ver(self.dev)['resultados']}, {self.t3.id})
        self.assertEqual(len(self.ver(self.osiris)['resultados']), 3)                                              # Dirección: todo

    def test_filtros(self):
        ids = lambda **p: {f['id'] for f in self.ver(self.osiris, **p)['resultados']}   # noqa: E731
        self.assertEqual(ids(persona=self.ashley.id), {self.t2.id})
        self.assertEqual(ids(validador=self.dev.id), {self.t3.id})
        self.assertEqual(ids(asignador=self.vladi.id), {self.t1.id, self.t2.id})
        self.assertEqual(ids(departamento=self.tec.id), {self.t3.id})
        self.assertEqual(ids(q='lanzamiento'), {self.t1.id})
        self.assertEqual(ids(cliente='solym'), {self.t1.id})
        self.assertEqual(ids(desde=str(timezone.localdate() - timedelta(days=1))), {self.t1.id, self.t3.id})
        self.assertEqual(ids(hasta=str(timezone.localdate() - timedelta(days=2))), {self.t2.id})

    def test_las_canceladas_solo_si_se_piden(self):
        c = Tarea.objects.create(titulo='Cancelada', colaborador=self.erlin, estado='CANCELADA', fecha_limite=timezone.localdate())
        self.assertNotIn(c.id, {f['id'] for f in self.ver(self.osiris)['resultados']})
        self.assertIn(c.id, {f['id'] for f in self.ver(self.osiris, estado='todas')['resultados']})
        self.assertEqual({f['id'] for f in self.ver(self.osiris, estado='CANCELADA')['resultados']}, {c.id})

    def test_paginacion(self):
        for i in range(45):
            Tarea.objects.create(titulo=f'Extra {i}', colaborador=self.erlin, estado='COMPLETADA', fecha_limite=timezone.localdate(), fecha_validacion=timezone.now() - timedelta(days=10))
        j = self.ver(self.osiris)
        self.assertEqual((j['count'], j['paginas'], len(j['resultados'])), (48, 2, 40))
        self.assertEqual(len(self.ver(self.osiris, pagina=2)['resultados']), 8)
        self.assertEqual(self.ver(self.osiris, pagina=99)['pagina'], 2)             # una página fuera de rango no rompe

    def test_descarga_csv_respeta_filtros_y_neutraliza_formulas(self):
        Tarea.objects.create(titulo='=HYPERLINK("http://x")', colaborador=self.erlin, estado='COMPLETADA', fecha_limite=timezone.localdate(), fecha_validacion=timezone.now())
        self.como(self.erlin)
        r = self.c.get(HIST, {'formato': 'csv'})
        self.assertEqual(r.status_code, 200)
        self.assertIn('text/csv', r['Content-Type'])
        texto = r.content.decode('utf-8-sig')
        self.assertIn('Quién la hizo', texto.splitlines()[0])
        self.assertIn('Post de lanzamiento', texto)
        self.assertNotIn('Informe de redes', texto)                                # no es de su alcance
        self.assertIn("'=HYPERLINK", texto)                                         # la fórmula queda como texto

    def test_exige_sesion(self):
        self.c.force_authenticate(None)
        self.assertIn(self.c.get(HIST).status_code, (401, 403))
