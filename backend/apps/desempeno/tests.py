from datetime import date

from django.contrib.auth.models import User, Group
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Departamento
from apps.kpis.models import PlantillaKPI, KPIAsignado
from apps.organizacion.models import PuestoDeTrabajo
from .models import ConfiguracionDesempeno, Tarea, ResultadoKPI, EmpleadoDelMes
from .puntaje import calcular_ranking, nota_tarea

PERIODO = date(2026, 9, 1)
DESPUES_DEL_MES = date(2026, 10, 15)


class BaseDesempeno(TestCase):
    def setUp(self):
        self.depto_mkt = Departamento.objects.create(nombre="Marketing")
        self.depto_tec = Departamento.objects.create(nombre="Tecnología")
        self.puesto_mkt = PuestoDeTrabajo.objects.create(nombre="Diseñador", departamento=self.depto_mkt)
        self.puesto_tec = PuestoDeTrabajo.objects.create(nombre="Desarrollador", departamento=self.depto_tec)

        self.ana = self._usuario("ana", self.puesto_mkt)
        self.luis = self._usuario("luis", self.puesto_tec)
        self.admin = User.objects.create_user("jefe", password="x", is_staff=True)
        self.admin.groups.add(Group.objects.get_or_create(name="Administrador")[0])

    def _usuario(self, username, puesto):
        usuario = User.objects.create_user(username, password="x")
        usuario.perfil.puesto_trabajo = puesto
        usuario.perfil.save()
        return usuario

    def _tarea(self, colaborador, limite, **extra):
        return Tarea.objects.create(titulo="t", colaborador=colaborador, fecha_limite=limite, **extra)


class PuntajeTests(BaseDesempeno):
    def test_nota_de_tarea(self):
        a_tiempo_excelente = Tarea(estado='COMPLETADA', fecha_limite=date(2026, 9, 10),
                                   fecha_completada=date(2026, 9, 9), calificacion_calidad=5)
        tarde_sin_calificar = Tarea(estado='COMPLETADA', fecha_limite=date(2026, 9, 10),
                                    fecha_completada=date(2026, 9, 12))
        no_completada = Tarea(estado='PENDIENTE', fecha_limite=date(2026, 9, 10))
        self.assertEqual(nota_tarea(a_tiempo_excelente), 100)
        self.assertEqual(nota_tarea(tarde_sin_calificar), 50)
        self.assertEqual(nota_tarea(no_completada), 0)

    def test_prioridad_pondera_y_tareas_en_plazo_no_cuentan(self):
        self._tarea(self.ana, date(2026, 9, 10), prioridad='ALTA', estado='COMPLETADA',
                    fecha_completada=date(2026, 9, 10))                      # 100 x3
        self._tarea(self.ana, date(2026, 9, 20), prioridad='BAJA')           # 0 x1 (vencida)
        self._tarea(self.ana, date(2026, 9, 30), prioridad='MEDIA')          # aún en plazo
        self._tarea(self.ana, date(2026, 9, 5), estado='CANCELADA')          # no cuenta
        fila = calcular_ranking(PERIODO, hoy=date(2026, 9, 25))[0]
        self.assertEqual(fila['puntaje_tareas'], 75.0)
        self.assertEqual(fila['tareas']['en_plazo'], 1)
        self.assertEqual(fila['tareas']['vencidas'], 1)

    def test_combina_tareas_60_y_kpis_40(self):
        self._tarea(self.ana, date(2026, 9, 10), estado='COMPLETADA', fecha_completada=date(2026, 9, 10))
        plantilla = PlantillaKPI.objects.create(nombre="Rondas de revisión", menor_es_mejor=True)
        kpi = KPIAsignado.objects.create(puesto_trabajo=self.puesto_mkt, plantilla_kpi=plantilla,
                                         ponderacion=100, objetivo_meta="3")
        ResultadoKPI.objects.create(kpi_asignado=kpi, colaborador=self.ana, periodo=PERIODO,
                                    valor_meta=3, valor_real=6)              # menor es mejor: 50%
        fila = calcular_ranking(PERIODO, hoy=DESPUES_DEL_MES)[0]
        self.assertEqual(fila['puntaje_kpis'], 50.0)
        self.assertEqual(fila['puntaje_total'], 80.0)

    def test_cumplimiento_se_limita_a_100(self):
        plantilla = PlantillaKPI.objects.create(nombre="Ventas")
        kpi = KPIAsignado.objects.create(puesto_trabajo=self.puesto_mkt, plantilla_kpi=plantilla,
                                         ponderacion=50, objetivo_meta="100")
        resultado = ResultadoKPI(kpi_asignado=kpi, colaborador=self.ana, periodo=PERIODO,
                                 valor_meta=100, valor_real=150)
        self.assertEqual(resultado.cumplimiento, 100)


class ApiTests(BaseDesempeno):
    def setUp(self):
        super().setUp()
        self.client = APIClient()

    def test_colaborador_solo_ve_sus_tareas_y_no_puede_crear(self):
        self._tarea(self.ana, PERIODO)
        self._tarea(self.luis, PERIODO)
        self.client.force_authenticate(self.ana)
        respuesta = self.client.get('/api/desempeno/tareas/')
        self.assertEqual(len(respuesta.data), 1)
        crear = self.client.post('/api/desempeno/tareas/', {
            'titulo': 'x', 'colaborador': self.ana.id, 'fecha_limite': '2026-09-10'})
        self.assertEqual(crear.status_code, 403)

    def test_editar_no_salta_la_validacion(self):
        """Antes se podía marcar «Validada» desde el formulario; ahora solo con entregar → validar."""
        tarea = self._tarea(self.ana, date(2099, 1, 1))
        self.client.force_authenticate(self.admin)
        respuesta = self.client.patch(f'/api/desempeno/tareas/{tarea.id}/', {'estado': 'COMPLETADA', 'titulo': 'Nuevo'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['estado'], 'PENDIENTE')
        self.assertEqual(respuesta.data['titulo'], 'Nuevo')
        self.assertIsNone(respuesta.data['fecha_completada'])

    def test_ranking_y_declaracion_empleado_del_mes(self):
        self._tarea(self.ana, date(2026, 9, 10), estado='COMPLETADA',
                    fecha_completada=date(2026, 9, 1), calificacion_calidad=5)
        self._tarea(self.luis, date(2026, 9, 10), estado='COMPLETADA', fecha_completada=date(2026, 9, 15))
        self.client.force_authenticate(self.admin)
        ConfiguracionDesempeno.objects.update(minimo_tareas_empleado_mes=1)

        ranking = self.client.get('/api/desempeno/ranking/?mes=2026-09').data
        self.assertEqual(ranking['candidato_general']['username'], 'ana')
        self.assertEqual(len(ranking['candidatos_departamento']), 2)

        declarar = {'periodo': '2026-09-01', 'colaborador': self.ana.id, 'beneficio': 'Día libre'}
        self.assertEqual(self.client.post('/api/desempeno/empleados-del-mes/', declarar).status_code, 201)
        self.assertEqual(EmpleadoDelMes.objects.get().puntaje, 100)
        # Un solo ganador general por mes
        repetido = self.client.post('/api/desempeno/empleados-del-mes/',
                                    {'periodo': '2026-09-01', 'colaborador': self.luis.id})
        self.assertEqual(repetido.status_code, 400)
        # Por departamento: debe pertenecer a ese departamento
        mal_depto = self.client.post('/api/desempeno/empleados-del-mes/', {
            'periodo': '2026-09-01', 'colaborador': self.luis.id, 'departamento': self.depto_mkt.id})
        self.assertEqual(mal_depto.status_code, 400)

    def test_resultado_kpi_debe_ser_del_puesto_del_colaborador(self):
        plantilla = PlantillaKPI.objects.create(nombre="Ventas")
        kpi = KPIAsignado.objects.create(puesto_trabajo=self.puesto_mkt, plantilla_kpi=plantilla,
                                         ponderacion=50, objetivo_meta="100")
        self.client.force_authenticate(self.admin)
        respuesta = self.client.post('/api/desempeno/resultados-kpi/', {
            'kpi_asignado': kpi.id, 'colaborador': self.luis.id, 'periodo': '2026-09-17',
            'valor_meta': 100, 'valor_real': 80})
        self.assertEqual(respuesta.status_code, 400)
        respuesta = self.client.post('/api/desempeno/resultados-kpi/', {
            'kpi_asignado': kpi.id, 'colaborador': self.ana.id, 'periodo': '2026-09-17',
            'valor_meta': 100, 'valor_real': 80})
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(respuesta.data['periodo'], '2026-09-01')
        self.assertEqual(respuesta.data['cumplimiento'], 80.0)


class FlujoValidacionTests(BaseDesempeno):
    """Colaborador entrega desde el celular → supervisor directo valida → cuenta para puntaje y KPI."""

    def setUp(self):
        super().setUp()
        self.puesto_jefe = PuestoDeTrabajo.objects.create(nombre="Gerente Marketing", departamento=self.depto_mkt)
        self.puesto_mkt.supervisor = self.puesto_jefe
        self.puesto_mkt.save()
        self.jefa = self._usuario("jefa", self.puesto_jefe)
        self.client = APIClient()

    def test_entregar_validar_y_puntaje(self):
        self.client.force_authenticate(self.jefa)
        creada = self.client.post('/api/desempeno/tareas/', {
            'titulo': 'Programar parrilla', 'colaborador': self.ana.id, 'fecha_limite': '2026-09-10'})
        self.assertEqual(creada.status_code, 201)
        tarea_id = creada.data['id']

        # El supervisor no puede entregar por el colaborador, y sin evidencia no se entrega
        self.assertEqual(self.client.post(f'/api/desempeno/tareas/{tarea_id}/entregar/',
                                          {'evidencia_nota': 'x'}).status_code, 403)
        self.client.force_authenticate(self.ana)
        self.assertEqual(self.client.post(f'/api/desempeno/tareas/{tarea_id}/entregar/', {}).status_code, 400)
        entregada = self.client.post(f'/api/desempeno/tareas/{tarea_id}/entregar/',
                                     {'evidencia_enlace': 'https://ejemplo.com/post'})
        self.assertEqual(entregada.data['estado'], 'EN_REVISION')

        # En revisión todavía no suma puntaje
        self.assertEqual(calcular_ranking(PERIODO, hoy=DESPUES_DEL_MES), [])
        # El colaborador no se valida a sí mismo
        self.assertEqual(self.client.post(f'/api/desempeno/tareas/{tarea_id}/validar/',
                                          {'calificacion_calidad': 5}).status_code, 403)

        self.client.force_authenticate(self.jefa)
        validada = self.client.post(f'/api/desempeno/tareas/{tarea_id}/validar/', {'calificacion_calidad': 5})
        self.assertEqual(validada.data['estado'], 'COMPLETADA')
        self.assertEqual(validada.data['validada_por'], self.jefa.id)
        self.assertEqual(len(calcular_ranking(PERIODO, hoy=DESPUES_DEL_MES)), 1)

    def test_rechazo_devuelve_la_tarea_con_comentario(self):
        tarea = self._tarea(self.ana, PERIODO, estado='EN_REVISION', fecha_completada=PERIODO)
        self.client.force_authenticate(self.jefa)
        self.assertEqual(self.client.post(f'/api/desempeno/tareas/{tarea.id}/rechazar/', {}).status_code, 400)
        rechazada = self.client.post(f'/api/desempeno/tareas/{tarea.id}/rechazar/',
                                     {'comentario_revision': 'Falta el logo del cliente'})
        self.assertEqual(rechazada.data['estado'], 'EN_PROGRESO')
        self.assertIsNone(rechazada.data['fecha_completada'])

    def test_supervisor_no_gestiona_otro_equipo(self):
        tarea = self._tarea(self.luis, PERIODO, estado='EN_REVISION', fecha_completada=PERIODO)
        self.client.force_authenticate(self.jefa)
        self.assertEqual(self.client.post(f'/api/desempeno/tareas/{tarea.id}/validar/',
                                          {'calificacion_calidad': 5}).status_code, 404)
        crear = self.client.post('/api/desempeno/tareas/', {
            'titulo': 'x', 'colaborador': self.luis.id, 'fecha_limite': '2026-09-10'})
        self.assertEqual(crear.status_code, 403)
        equipo = self.client.get('/api/desempeno/equipo/').data
        self.assertEqual([m['id'] for m in equipo], [self.ana.id])

    def test_kpi_automatico_se_llena_con_tareas_validadas(self):
        plantilla = PlantillaKPI.objects.create(nombre="Contenidos programados")
        kpi = KPIAsignado.objects.create(puesto_trabajo=self.puesto_mkt, plantilla_kpi=plantilla,
                                         ponderacion=100, objetivo_meta="4 al mes",
                                         es_entrada_manual=False, meta_numerica=4)
        for estado in ('COMPLETADA', 'COMPLETADA', 'COMPLETADA', 'EN_REVISION'):
            self._tarea(self.ana, date(2026, 9, 10), estado=estado, kpi_asignado=kpi,
                        fecha_completada=date(2026, 9, 9))
        fila = calcular_ranking(PERIODO, hoy=DESPUES_DEL_MES)[0]
        self.assertEqual(fila['kpis'][0]['valor'], 3)       # La que está en revisión no cuenta
        self.assertEqual(fila['puntaje_kpis'], 75.0)

        self.client.force_authenticate(self.ana)
        resumen = self.client.get('/api/desempeno/mi-resumen/?mes=2026-09').data
        self.assertEqual(resumen['tareas']['validadas'], 3)
        self.assertEqual(resumen['progreso'], 75)
        self.assertEqual(resumen['posicion'], 1)

    def test_kpi_de_otro_puesto_no_se_puede_vincular(self):
        plantilla = PlantillaKPI.objects.create(nombre="Commits")
        kpi_tec = KPIAsignado.objects.create(puesto_trabajo=self.puesto_tec, plantilla_kpi=plantilla,
                                             ponderacion=100, objetivo_meta="10")
        self.client.force_authenticate(self.admin)
        respuesta = self.client.post('/api/desempeno/tareas/', {
            'titulo': 'x', 'colaborador': self.ana.id, 'fecha_limite': '2026-09-10', 'kpi_asignado': kpi_tec.id})
        self.assertEqual(respuesta.status_code, 400)
