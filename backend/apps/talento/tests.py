from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Departamento
from apps.desempeno.models import Notificacion, ResultadoKPI
from apps.kpis.models import KPIAsignado, PlantillaKPI
from apps.organizacion.models import PuestoDeTrabajo
from . import servicios
from .models import COMPETENCIAS, AuditoriaCambio, CambioSalarial, CicloEvaluacion, EventoExpediente, Evaluacion, PlanMejora

TODO5 = {c: 5 for c, _ in COMPETENCIAS}
TODO2 = {c: 2 for c, _ in COMPETENCIAS}


class Base(TestCase):
    def setUp(self):
        self.depto = Departamento.objects.create(nombre='Marketing')
        self.p_jefe = PuestoDeTrabajo.objects.create(nombre='Gerente', departamento=self.depto)
        self.p = PuestoDeTrabajo.objects.create(nombre='Diseñador', departamento=self.depto, supervisor=self.p_jefe)
        self.jefe = self._u('jefe', self.p_jefe)
        self.ana = self._u('ana', self.p)
        self.luis = self._u('luis', self.p)
        self.dir = User.objects.create_user('dir', password='x', is_staff=True)
        self.dir.groups.add(Group.objects.get_or_create(name='Administrador')[0])

    def _u(self, n, puesto):
        u = User.objects.create_user(n, password='x', first_name=n.title())
        u.perfil.puesto_trabajo = puesto
        u.perfil.save()
        return u

    def como(self, u):
        c = APIClient()
        c.force_authenticate(u)
        return c

    def ciclo(self, **extra):
        hoy = date.today()
        return self.como(self.dir).post('/api/talento/ciclos/', {'nombre': 'T4', 'desde': str(hoy - timedelta(days=30)),
                                                              'hasta': str(hoy), 'cierre': str(hoy + timedelta(days=7)), **extra}, format='json')


class EvaluacionTests(Base):
    def test_el_ciclo_genera_auto_supervisor_y_pares(self):
        r = self.ciclo()
        self.assertEqual(r.status_code, 201, r.content)
        c = CicloEvaluacion.objects.get()
        ana = Evaluacion.objects.filter(ciclo=c, evaluado=self.ana)
        self.assertEqual(set(ana.values_list('tipo', flat=True)), {'AUTO', 'SUPERVISOR', 'PAR'})
        self.assertTrue(ana.filter(tipo='SUPERVISOR', evaluador=self.jefe).exists())
        self.assertTrue(Notificacion.objects.filter(destinatario=self.ana, tipo='TALENTO').exists())

    def test_solo_la_direccion_abre_ciclos(self):
        hoy = date.today()
        r = self.como(self.jefe).post('/api/talento/ciclos/', {'nombre': 'x', 'desde': str(hoy), 'hasta': str(hoy), 'cierre': str(hoy)}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_enviar_y_resultados_con_pares_anonimos(self):
        self.ciclo()
        ev = lambda quien, tipo: Evaluacion.objects.get(evaluado=self.ana, evaluador=quien, tipo=tipo)
        self.assertEqual(self.como(self.ana).post(f'/api/talento/evaluaciones/{ev(self.ana, "AUTO").pk}/enviar/', {'puntajes': {'x': 1}}, format='json').status_code, 400)
        self.assertEqual(self.como(self.ana).post(f'/api/talento/evaluaciones/{ev(self.ana, "AUTO").pk}/enviar/', {'puntajes': TODO5}, format='json').status_code, 200)
        # No se puede enviar la de otro.
        self.assertEqual(self.como(self.ana).post(f'/api/talento/evaluaciones/{ev(self.jefe, "SUPERVISOR").pk}/enviar/', {'puntajes': TODO5}, format='json').status_code, 403)
        self.como(self.jefe).post(f'/api/talento/evaluaciones/{ev(self.jefe, "SUPERVISOR").pk}/enviar/', {'puntajes': TODO5, 'fortalezas': 'Creativa'}, format='json')
        self.como(self.luis).post(f'/api/talento/evaluaciones/{ev(self.luis, "PAR").pk}/enviar/', {'puntajes': TODO5, 'comentario': 'Buena'}, format='json')
        r = self.como(self.ana).get('/api/talento/resultados/').json()
        tipos = r['ciclos'][0]['por_tipo']
        self.assertEqual(tipos['SUPERVISOR']['promedio'], 5)
        self.assertIsNone(tipos['PAR']['comentarios'][0]['de'])  # el compañero es anónimo
        self.assertEqual(tipos['SUPERVISOR']['comentarios'][0]['de'], 'Jefe')
        # Luis no ve los resultados de Ana; su jefe sí.
        self.assertEqual(self.como(self.luis).get(f'/api/talento/resultados/?usuario={self.ana.pk}').status_code, 403)
        self.assertEqual(self.como(self.jefe).get(f'/api/talento/resultados/?usuario={self.ana.pk}').status_code, 200)

    def test_una_evaluacion_baja_la_valida_la_direccion(self):
        self.ciclo()
        e = Evaluacion.objects.get(evaluado=self.ana, evaluador=self.jefe, tipo='SUPERVISOR')
        url = f'/api/talento/evaluaciones/{e.pk}/enviar/'
        self.assertEqual(self.como(self.jefe).post(url, {'puntajes': TODO2}, format='json').status_code, 400)  # falta qué mejorar
        self.assertEqual(self.como(self.jefe).post(url, {'puntajes': TODO2, 'a_mejorar': 'Entregas'}, format='json').status_code, 200)
        e.refresh_from_db()
        self.assertEqual(e.estado, 'EN_REVISION')
        self.assertTrue(Notificacion.objects.filter(destinatario=self.dir, tipo='TALENTO').exists())
        self.assertNotIn('SUPERVISOR', self.como(self.ana).get('/api/talento/resultados/').json()['ciclos'][0]['por_tipo'])
        self.assertEqual(self.como(self.jefe).post(f'/api/talento/evaluaciones/{e.pk}/confirmar/', {}, format='json').status_code, 403)
        self.assertEqual(len(self.como(self.dir).get('/api/talento/evaluaciones/por-revisar/').json()), 1)
        self.como(self.dir).post(f'/api/talento/evaluaciones/{e.pk}/confirmar/', {'nota': 'Revisado'}, format='json')
        e.refresh_from_db()
        self.assertEqual(e.estado, 'CERRADA')
        self.assertIn('SUPERVISOR', self.como(self.ana).get('/api/talento/resultados/').json()['ciclos'][0]['por_tipo'])

    def test_devolver_al_evaluador(self):
        self.ciclo()
        e = Evaluacion.objects.get(evaluado=self.ana, evaluador=self.jefe, tipo='SUPERVISOR')
        servicios.enviar(e, TODO2, a_mejorar='x')
        self.como(self.dir).post(f'/api/talento/evaluaciones/{e.pk}/confirmar/', {'devolver': True, 'nota': 'Detalla más'}, format='json')
        e.refresh_from_db()
        self.assertEqual(e.estado, 'PENDIENTE')

    def test_mis_evaluaciones(self):
        self.ciclo()
        d = self.como(self.jefe).get('/api/talento/evaluaciones/').json()
        self.assertGreaterEqual(len(d['evaluaciones']), 3)  # su autoevaluación y las de su equipo
        self.assertEqual(len(d['competencias']), len(COMPETENCIAS))
        self.assertEqual(len(self.como(self.dir).get('/api/talento/avance/').json()['personas']), 3)


class PlanYExpedienteTests(Base):
    def test_plan_de_mejora(self):
        hoy = date.today()
        datos = {'colaborador': self.ana.pk, 'motivo': 'Entregas tarde', 'objetivos': [{'texto': 'Entregar a tiempo', 'meta': '90 %'}],
                 'inicio': str(hoy), 'revision': str(hoy + timedelta(days=30))}
        self.assertEqual(self.como(self.ana).post('/api/talento/planes/', datos, format='json').status_code, 403)
        self.assertEqual(self.como(self.luis).post('/api/talento/planes/', datos, format='json').status_code, 403)
        self.assertEqual(self.como(self.jefe).post('/api/talento/planes/', {**datos, 'objetivos': []}, format='json').status_code, 400)
        r = self.como(self.jefe).post('/api/talento/planes/', datos, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(len(self.como(self.ana).get('/api/talento/planes/').json()), 1)
        self.assertEqual(len(self.como(self.luis).get('/api/talento/planes/').json()), 0)
        self.como(self.jefe).patch(f"/api/talento/planes/{r.json()['id']}/", {'estado': 'CUMPLIDO'}, format='json')
        self.assertEqual(PlanMejora.objects.get().estado, 'CUMPLIDO')

    def test_expediente_visibilidad_y_justificacion(self):
        nota = {'colaborador': self.ana.pk, 'tipo': 'OBSERVACION', 'fecha': str(date.today()), 'titulo': 'x'}
        self.assertEqual(self.como(self.jefe).post('/api/talento/expediente/', nota, format='json').status_code, 403)  # un supervisor no
        self.jefe.groups.add(Group.objects.get(name='Gerente de Departamento'))
        self.jefe = User.objects.get(pk=self.jefe.pk)
        jefe = self.como(self.jefe)
        r = jefe.post('/api/talento/expediente/', {'colaborador': self.ana.pk, 'tipo': 'OBSERVACION', 'fecha': str(date.today()),
                                                   'titulo': 'Llegó tarde a la reunión'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        jefe.post('/api/talento/expediente/', {'colaborador': self.ana.pk, 'tipo': 'INCIDENCIA', 'fecha': str(date.today()),
                                               'titulo': 'Nota interna', 'visible_al_colaborador': False}, format='json')
        self.assertEqual(jefe.post('/api/talento/expediente/', {'colaborador': self.ana.pk, 'tipo': 'BONO', 'fecha': str(date.today()),
                                                                'titulo': 'Bono', 'monto': '5000'}, format='json').status_code, 403)
        ana = self.como(self.ana)
        propios = ana.get('/api/talento/expediente/').json()
        self.assertEqual(len(propios), 1)
        pk = propios[0]['id']
        self.assertEqual(ana.patch(f'/api/talento/expediente/{pk}/', {'titulo': 'otro'}, format='json').status_code, 403)
        self.assertEqual(ana.patch(f'/api/talento/expediente/{pk}/', {'justificacion': 'Había tapón'}, format='json').status_code, 200)
        self.assertEqual(len(jefe.get(f'/api/talento/expediente/?usuario={self.ana.pk}').json()), 2)
        self.assertEqual(self.como(self.luis).get(f'/api/talento/expediente/?usuario={self.ana.pk}').status_code, 403)
        self.assertEqual(jefe.delete(f'/api/talento/expediente/{pk}/').status_code, 403)
        self.assertEqual(self.como(self.dir).delete(f'/api/talento/expediente/{pk}/').status_code, 204)

    def test_el_monto_del_bono_solo_lo_ve_la_administracion(self):
        EventoExpediente.objects.create(colaborador=self.ana, tipo='BONO', fecha=date.today(), titulo='Bono', monto=5000)
        self.assertIsNone(self.como(self.ana).get('/api/talento/expediente/').json()[0]['monto'])
        self.assertIsNone(self.como(self.jefe).get(f'/api/talento/expediente/?usuario={self.ana.pk}').json()[0]['monto'])
        self.assertIsNotNone(self.como(self.dir).get(f'/api/talento/expediente/?usuario={self.ana.pk}').json()[0]['monto'])


class AuditoriaTests(Base):
    def test_cambios_por_la_web_quedan_auditados_y_el_salario_con_historial(self):
        c = APIClient()
        c.force_login(self.dir)
        sesion = c.session
        sesion['dos_pasos_ok'] = True  # como si hubiera entrado con su código de verificación
        sesion.save()
        perfil = self.ana.perfil
        perfil.salario_mensual = 30000
        perfil.save()  # sin sesión: no se audita
        self.assertEqual(AuditoriaCambio.objects.count(), 0)
        from apps.talento.auditoria import _usuario
        token = _usuario.set(self.dir)
        try:
            perfil.salario_mensual = 35000
            perfil.save()
        finally:
            _usuario.reset(token)
        a = AuditoriaCambio.objects.get()
        self.assertEqual(a.antes, {'salario_mensual': 30000.0})
        self.assertEqual(CambioSalarial.objects.get().nuevo, 35000)
        self.assertEqual(c.get('/api/talento/auditoria/').status_code, 200)
        self.assertEqual(len(c.get('/api/talento/salarios/').json()), 1)
        self.assertEqual(self.como(self.jefe).get('/api/talento/auditoria/').status_code, 403)

    def test_cambio_de_ponderacion_por_la_api(self):
        p = PlantillaKPI.objects.create(nombre='Piezas')
        k = KPIAsignado.objects.create(puesto_trabajo=self.p, plantilla_kpi=p, ponderacion=20, objetivo_meta='10')
        c = APIClient()
        c.force_login(self.dir)
        sesion = c.session
        sesion['dos_pasos_ok'] = True  # como si hubiera entrado con su código de verificación
        sesion.save()
        r = c.patch(f'/api/kpis/kpis-asignados/{k.pk}/', {'ponderacion': 30}, format='json')
        self.assertIn(r.status_code, (200, 202), r.content)
        a = AuditoriaCambio.objects.filter(accion__icontains='kpi').first()
        self.assertIsNotNone(a)
        self.assertEqual(a.despues['ponderacion'], 30.0)


class AlertaKpiTests(Base):
    def test_kpi_bajo_umbral_avisa_una_vez(self):
        p = PlantillaKPI.objects.create(nombre='Piezas')
        k = KPIAsignado.objects.create(puesto_trabajo=self.p, plantilla_kpi=p, ponderacion=50, objetivo_meta='10', umbral_alerta=70)
        periodo = date(2026, 9, 1)
        ResultadoKPI.objects.create(kpi_asignado=k, colaborador=self.ana, periodo=periodo, valor_meta=10, valor_real=5)
        ResultadoKPI.objects.create(kpi_asignado=k, colaborador=self.luis, periodo=periodo, valor_meta=10, valor_real=9)
        self.assertEqual(servicios.revisar_kpis(periodo), 1)
        self.assertEqual(servicios.revisar_kpis(periodo), 0)
        self.assertTrue(Notificacion.objects.filter(destinatario=self.jefe, tipo='TALENTO', titulo__contains='Piezas').exists())


class RevisionV9Tests(Base):
    """Casos de la revisión independiente de la v9."""

    def test_el_supervisor_no_sale_como_companero(self):
        for semilla in range(10):
            CicloEvaluacion.objects.all().delete()
            c = CicloEvaluacion.objects.create(nombre=f'C{semilla}', desde=date.today(), hasta=date.today(), cierre=date.today())
            servicios.generar(c, semilla=semilla)
            self.assertFalse(Evaluacion.objects.filter(ciclo=c, tipo='PAR', evaluador=self.jefe, evaluado=self.ana).exists())

    def test_el_supervisor_no_toca_bonos_al_editar(self):
        e = EventoExpediente.objects.create(colaborador=self.ana, tipo='RECONOCIMIENTO', fecha=date.today(), titulo='x')
        r = self.como(self.jefe).patch(f'/api/talento/expediente/{e.pk}/', {'tipo': 'BONO', 'monto': '99999'}, format='json')
        self.assertEqual(r.status_code, 403)
        e.refresh_from_db()
        self.assertEqual(e.tipo, 'RECONOCIMIENTO')

    def test_nadie_valida_su_propia_evaluacion(self):
        otro_dir = User.objects.create_user('dir2', password='x', is_staff=True)
        otro_dir.groups.add(Group.objects.get(name='Administrador'))
        c = CicloEvaluacion.objects.create(nombre='C', desde=date.today(), hasta=date.today(), cierre=date.today())
        e = Evaluacion.objects.create(ciclo=c, evaluado=self.dir, evaluador=otro_dir, tipo='SUPERVISOR')
        servicios.enviar(e, TODO2, a_mejorar='x')
        self.assertFalse(Notificacion.objects.filter(destinatario=self.dir, titulo__contains='por revisar').exists())
        self.assertEqual(self.como(self.dir).get('/api/talento/evaluaciones/por-revisar/').json(), [])
        self.assertEqual(self.como(self.dir).post(f'/api/talento/evaluaciones/{e.pk}/confirmar/', {}, format='json').status_code, 403)

    def test_fecha_invalida_en_auditoria(self):
        self.assertEqual(self.como(self.dir).get('/api/talento/auditoria/?desde=ayer').status_code, 400)
        self.assertEqual(self.como(self.dir).get('/api/talento/auditoria/?desde=2026-01-01').status_code, 200)
