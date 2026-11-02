"""Puntaje de cuatro partes de la v9: 40 tareas, 35 KPIs, 15 calidad y satisfacción, 10 asistencia."""
from datetime import date, datetime

from django.utils import timezone

from apps.asistencia.models import Marcaje
from apps.kpis.models import KPIAsignado, PlantillaKPI
from apps.talento.models import CicloEvaluacion, Evaluacion
from .models import ConfiguracionDesempeno, ResultadoKPI
from .puntaje import calcular_ranking
from .tests import DESPUES_DEL_MES, PERIODO, BaseDesempeno


class CuatroPartesTests(BaseDesempeno):
    def setUp(self):
        super().setUp()
        ConfiguracionDesempeno.objects.all().delete()
        self.config = ConfiguracionDesempeno.objects.create(tramos_bono=ConfiguracionDesempeno.TRAMOS_POR_DEFECTO)

    def test_pesos_por_defecto(self):
        c = self.config
        self.assertEqual((c.peso_tareas, c.peso_kpis, c.peso_calidad, c.peso_jornada), (40, 35, 15, 10))

    def test_calidad_sale_de_estrellas_primera_y_supervisor(self):
        # Tarea a tiempo, 3 estrellas (50) y con una ronda de corrección (a la primera 0 %).
        self._tarea(self.ana, date(2026, 9, 10), estado='COMPLETADA', fecha_completada=date(2026, 9, 10),
                    calificacion_calidad=3, rondas_revision=1)
        fila = calcular_ranking(PERIODO, hoy=DESPUES_DEL_MES)[0]
        self.assertEqual(fila['puntaje_tareas'], 100.0)  # con calidad aparte, la nota de la tarea es el cumplimiento
        self.assertEqual(fila['puntaje_calidad'], 25.0)  # (50 + 0) / 2
        self.assertIsNone(fila['puntaje_kpis'])
        self.assertIsNone(fila['puntaje_asistencia'])   # nunca marcó: no se le cuenta
        self.assertAlmostEqual(fila['puntaje_total'], (100 * 40 + 25 * 15) / 55, places=1)

        ciclo = CicloEvaluacion.objects.create(nombre='T3', desde=date(2026, 7, 1), hasta=date(2026, 9, 30), cierre=date(2026, 10, 10))
        Evaluacion.objects.create(ciclo=ciclo, evaluado=self.ana, evaluador=self.admin, tipo='SUPERVISOR', estado='CERRADA',
                                  puntajes={'a': 5, 'b': 5})  # 100 %
        fila = calcular_ranking(PERIODO, hoy=DESPUES_DEL_MES)[0]
        self.assertEqual(fila['puntaje_calidad'], round((50 + 0 + 100) / 3, 2))

    def test_una_evaluacion_en_revision_no_cuenta(self):
        self._tarea(self.ana, date(2026, 9, 10), estado='COMPLETADA', fecha_completada=date(2026, 9, 10), calificacion_calidad=5)
        ciclo = CicloEvaluacion.objects.create(nombre='T3', desde=date(2026, 7, 1), hasta=date(2026, 9, 30), cierre=date(2026, 10, 10))
        Evaluacion.objects.create(ciclo=ciclo, evaluado=self.ana, evaluador=self.admin, tipo='SUPERVISOR', estado='EN_REVISION',
                                  puntajes={'a': 1})
        self.assertEqual(calcular_ranking(PERIODO, hoy=DESPUES_DEL_MES)[0]['puntaje_calidad'], 100.0)

    def test_kpi_de_seguimiento_no_pesa(self):
        self._tarea(self.ana, date(2026, 9, 10), estado='COMPLETADA', fecha_completada=date(2026, 9, 10), calificacion_calidad=5)
        p = PlantillaKPI.objects.create(nombre='Leads')
        seg = KPIAsignado.objects.create(puesto_trabajo=self.puesto_mkt, plantilla_kpi=p, ponderacion=0, objetivo_meta='10')
        ResultadoKPI.objects.create(kpi_asignado=seg, colaborador=self.ana, periodo=PERIODO, valor_meta=10, valor_real=1)
        fila = calcular_ranking(PERIODO, hoy=DESPUES_DEL_MES)[0]
        self.assertIsNone(fila['puntaje_kpis'])
        self.assertEqual(fila['kpis_registrados'], 0)

    def test_la_computadora_no_da_puntos(self):
        self._tarea(self.ana, date(2026, 9, 10), estado='COMPLETADA', fecha_completada=date(2026, 9, 10), calificacion_calidad=5)
        sin = calcular_ranking(PERIODO, hoy=DESPUES_DEL_MES)[0]['puntaje_total']
        from apps.monitoreo.models import Actividad
        Actividad.objects.create(usuario=self.ana, minuto=timezone.make_aware(datetime(2026, 9, 10, 10)), activos=0, categoria='I')
        self.assertEqual(calcular_ranking(PERIODO, hoy=DESPUES_DEL_MES)[0]['puntaje_total'], sin)

    def test_asistencia_cuenta_si_usa_el_control(self):
        self._tarea(self.ana, date(2026, 9, 10), estado='COMPLETADA', fecha_completada=date(2026, 9, 10), calificacion_calidad=5)
        Marcaje.objects.create(usuario=self.ana, tipo='ENTRADA', momento=timezone.make_aware(datetime(2026, 9, 10, 8)))
        Marcaje.objects.create(usuario=self.ana, tipo='SALIDA', momento=timezone.make_aware(datetime(2026, 9, 10, 17)))
        fila = calcular_ranking(PERIODO, hoy=DESPUES_DEL_MES)[0]
        self.assertIsNotNone(fila['puntaje_asistencia'])
        self.assertLess(fila['puntaje_asistencia'], 100)  # faltó los demás días laborables
