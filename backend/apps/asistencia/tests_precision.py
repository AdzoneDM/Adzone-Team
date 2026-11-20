"""El tiempo marcado se cuenta al segundo: de ahí sale el pago, así que no se pierden segundos tramo por tramo."""
from datetime import datetime, timedelta

from django.utils import timezone

from . import servicios
from .models import AsignacionHorario, Marcaje
from .tests import LUNES, Base


def t(hhmmss, dia=LUNES, micro=0):
    h, m, s = map(int, hhmmss.split(':'))
    return timezone.make_aware(datetime(dia.year, dia.month, dia.day, h, m, s, micro))


class PrecisionTests(Base):
    def marcar(self, *pares):
        for tipo, hora in pares:
            Marcaje.objects.create(usuario=self.ana, tipo=tipo, momento=t(hora))

    def dia(self):
        return servicios.jornada(self.ana, LUNES, ahora=t('23:00:00', LUNES + timedelta(days=1)))

    def test_los_segundos_no_se_pierden_en_cada_tramo(self):
        # Tramo 1: 2:00:59 · tramo 2: 1:30:59 → 3:31:58. Redondeando cada tramo a minutos serían 3:30 (se perdían 58 s).
        self.marcar(('ENTRADA', '08:00:00'), ('PAUSA', '10:00:59'), ('REGRESO', '10:30:00'), ('SALIDA', '12:00:59'))
        j = self.dia()
        self.assertEqual(j['trabajados_seg'], 2 * 3600 + 59 + 1 * 3600 + 30 * 60 + 59)
        self.assertEqual(j['trabajados'], 211)           # minutos = piso del total en segundos
        self.assertEqual(j['pausa_seg'], 29 * 60 + 1)

    def test_tardanza_y_salida_temprana_al_segundo(self):
        # Turno 8:00 a 17:00, tolerancia 10 min. Entra 8:10:30 → ya pasó la tolerancia: cuenta 10:30 completos.
        self.marcar(('ENTRADA', '08:10:30'), ('SALIDA', '16:59:00'))
        j = self.dia()
        self.assertEqual((j['llegada'], j['tardanza_seg'], j['tardanza']), ('TARDE', 10 * 60 + 30, 10))
        self.assertEqual(j['salida_temprana_seg'], 0)    # 1 min antes: dentro de la tolerancia

    def test_dentro_de_la_tolerancia_no_cuenta(self):
        self.marcar(('ENTRADA', '08:10:00'), ('SALIDA', '17:00:00'))
        j = self.dia()
        self.assertEqual((j['llegada'], j['tardanza_seg']), ('A_TIEMPO', 0))

    def test_extra_exacta_desde_15_minutos(self):
        self.marcar(('ENTRADA', '08:00:00'), ('SALIDA', '17:14:59'))  # 9:14:59 trabajado, 8:00 programadas, sin almuerzo marcado
        j = self.dia()
        self.assertEqual(j['extra_seg'], 0)              # el almuerzo no marcado se descuenta y no llega a 15 min extra
        Marcaje.objects.filter(usuario=self.ana).delete()
        self.marcar(('ENTRADA', '08:00:00'), ('PAUSA', '12:00:00'), ('REGRESO', '13:00:00'), ('SALIDA', '17:15:01'))
        j = self.dia()
        self.assertEqual(j['trabajados_seg'], 4 * 3600 + 4 * 3600 + 15 * 60 + 1)
        self.assertEqual(j['extra_seg'], 15 * 60 + 1)

    def test_en_curso_cuenta_hasta_este_segundo(self):
        self.marcar(('ENTRADA', '08:00:00'))
        j = servicios.jornada(self.ana, LUNES, ahora=t('09:15:42'))
        self.assertEqual(j['trabajados_seg'], 3600 + 15 * 60 + 42)
        self.assertEqual(j['trabajados'], 75)

    def test_resumen_suma_en_segundos(self):
        self.marcar(('ENTRADA', '08:00:00'), ('PAUSA', '10:00:59'), ('REGRESO', '10:30:00'), ('SALIDA', '12:00:59'))
        r = servicios.resumen(self.ana, LUNES, LUNES, ahora=t('23:00:00', LUNES + timedelta(days=1)))
        self.assertEqual(r['segundos_trabajados'], 12718)
        self.assertEqual(r['minutos_trabajados'], 211)


class EstadoParaPantallaDeEntradaTests(Base):
    """La pantalla «Marcar entrada» al iniciar sesión necesita saber si hoy toca marcar y si es obligatorio."""

    def estado(self):
        from rest_framework.test import APIClient
        c = APIClient()
        c.force_authenticate(self.ana)
        return c.get('/api/asistencia/estado/').json()

    def test_expone_ahora_y_si_la_marca_es_obligatoria(self):
        d = self.estado()
        self.assertTrue(d['marca_obligatoria'])
        self.assertIn('T', d['ahora'])
        AsignacionHorario.objects.create(usuario=self.ana, horario=self.horario, marca_obligatoria=False)
        self.assertFalse(self.estado()['marca_obligatoria'])
