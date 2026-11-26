"""Mi equipo → Historial: las validadas de un mes se buscan por el día en que se validaron, aunque su fecha límite sea de otro mes."""
from datetime import datetime, timedelta

from django.utils import timezone

from .tests_mejoras import Base


class HistorialEquipoTests(Base):
    def test_validadas_del_mes_por_fecha_de_validacion(self):
        hoy = timezone.localdate()
        mes = hoy.strftime('%Y-%m')
        antes = (hoy.replace(day=1) - timedelta(days=5))
        z = timezone.get_current_timezone()
        vieja = self.tarea(self.erlin, dias=(antes - hoy).days, estado='COMPLETADA', fecha_completada=hoy,
                           fecha_validacion=timezone.make_aware(datetime.combine(hoy, datetime.min.time()).replace(hour=10), z))
        self.tarea(self.erlin, dias=0, estado='COMPLETADA', fecha_completada=antes,
                   fecha_validacion=timezone.make_aware(datetime.combine(antes, datetime.min.time()).replace(hour=10), z))
        self.tarea(self.erlin, dias=1)   # pendiente: no es historial
        self.como(self.vladi)
        r = self.c.get(f'/api/desempeno/tareas/?ambito=equipo&validadas_mes={mes}')
        self.assertEqual(r.status_code, 200)
        self.assertEqual([t['id'] for t in r.json()], [vieja.id])
