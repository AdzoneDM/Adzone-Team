"""v9 · Fase 4: panel gerencial."""
from datetime import date, datetime

from django.utils import timezone
from rest_framework.test import APIClient

from apps.operaciones.models import Cliente, OrdenArea, OrdenTrabajo
from apps.tiempo.models import RegistroTiempo
from .models import ConfiguracionDesempeno
from .panel import panel
from .tests import BaseDesempeno


class PanelTests(BaseDesempeno):
    def setUp(self):
        super().setUp()
        ConfiguracionDesempeno.objects.all().delete()
        ConfiguracionDesempeno.objects.create(tramos_bono=ConfiguracionDesempeno.TRAMOS_POR_DEFECTO)
        self.cli = Cliente.objects.create(nombre='Cliente')

    def test_indicadores_y_alertas(self):
        hoy = date(2026, 10, 20)
        self._tarea(self.ana, date(2026, 10, 5), estado='COMPLETADA', fecha_completada=date(2026, 10, 4), calificacion_calidad=5)
        for i in range(3):
            self._tarea(self.luis, date(2026, 10, 1 + i))  # vencidas sin entregar
        OrdenTrabajo.objects.create(titulo='Entregada', cliente=self.cli, estado='ENTREGADA', fecha_entrega=date(2026, 10, 10),
                                    fecha_compromiso=date(2026, 10, 12))
        OrdenTrabajo.objects.create(titulo='Tarde', cliente=self.cli, estado='CERRADA', fecha_entrega=date(2026, 10, 15),
                                    fecha_compromiso=date(2026, 10, 12))
        ot = OrdenTrabajo.objects.create(titulo='Abierta', cliente=self.cli, estado='EN_PRODUCCION', monto=1000)
        OrdenArea.objects.create(orden=ot, area='DIS', que_produce='Arte', horas_estimadas=2)
        self.ana.perfil.costo_hora = 300
        self.ana.perfil.save()
        RegistroTiempo.objects.create(usuario=self.ana, orden=ot, inicio=timezone.make_aware(datetime(2026, 10, 6, 9)),
                                      fin=timezone.make_aware(datetime(2026, 10, 6, 12)), minutos=180)
        d = panel(date(2026, 10, 1), hoy=hoy)
        self.assertEqual(d['personal_activo'], 2)
        self.assertEqual(d['ot_completadas'], 2)
        self.assertEqual(d['ot_a_tiempo'], 50.0)
        self.assertEqual(d['tareas_a_tiempo'], 100.0)
        tipos = {a['tipo'] for a in d['alertas']}
        self.assertIn('HORAS', tipos)          # 3 h de 2 estimadas
        self.assertIn('COSTO', tipos)          # RD$ 900 en horas de una OT de RD$ 1,000
        self.assertIn('ACUMULACION', tipos)    # Tecnología: 3 vencidas con 1 persona
        self.assertEqual(len(d['tendencia']), 6)
        tec = next(x for x in d['departamentos'] if x['nombre'] == 'Tecnología')
        self.assertEqual(tec['tareas_vencidas'], 3)

    def test_solo_la_direccion(self):
        c = APIClient()
        c.force_authenticate(self.ana)
        self.assertEqual(c.get('/api/desempeno/panel/').status_code, 403)
        c.force_authenticate(self.admin)
        self.assertEqual(c.get('/api/desempeno/panel/?mes=2026-10').status_code, 200)
        r = c.get('/api/desempeno/panel/exportar/?mes=2026-10')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Panel gerencial 2026-10', r.content.decode('utf-8-sig'))
