"""Hora de almuerzo fija o solo hoy, «más tarde» y el aviso justo a la hora elegida."""
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.desempeno.models import Notificacion
from .models import AlmuerzoPersonal, AsignacionHorario, Horario, Marcaje
from . import servicios


class AlmuerzoSoloHoyTests(TestCase):
    def setUp(self):
        self.u = User.objects.create_user('ana', password='Clave-Segura-2026')
        self.h = Horario.objects.create(nombre='Oficina', dias={str(d): ['08:00', '17:00'] for d in range(7)}, almuerzo_minutos=60,
                                        almuerzo_inicio='12:00')
        AsignacionHorario.objects.create(usuario=self.u, horario=self.h)
        self.c = APIClient()
        self.c.force_authenticate(self.u)

    def test_fija_y_solo_hoy(self):
        self.assertEqual(servicios.almuerzo_inicio_de(self.u, self.h), '12:00')
        self.assertEqual(self.c.post('/api/asistencia/mi-almuerzo/', {'hora': '13:00'}, format='json').data['almuerzo_inicio'], '13:00')
        r = self.c.post('/api/asistencia/mi-almuerzo/', {'hora': '14:30', 'solo_hoy': True}, format='json')
        self.assertEqual((r.data['almuerzo_inicio'], r.data['almuerzo_hoy'], r.data['almuerzo_propio']), ('14:30', '14:30', '13:00'))
        # Mañana vuelve a valer la fija
        self.assertEqual(servicios.almuerzo_inicio_de(self.u, self.h, timezone.localdate() + timedelta(days=1)), '13:00')
        # Quitar la de hoy
        r = self.c.post('/api/asistencia/mi-almuerzo/', {'hora': '', 'solo_hoy': True}, format='json')
        self.assertEqual((r.data['almuerzo_inicio'], r.data['almuerzo_hoy']), ('13:00', None))
        # Quitar la fija: vale la del horario
        r = self.c.post('/api/asistencia/mi-almuerzo/', {'hora': ''}, format='json')
        self.assertEqual(r.data['almuerzo_inicio'], '12:00')
        self.assertFalse(AlmuerzoPersonal.objects.filter(usuario=self.u).exists())

    def test_posponer_y_aviso_a_la_hora_exacta(self):
        hoy = timezone.localdate()
        doce = timezone.make_aware(timezone.datetime.combine(hoy, timezone.datetime.min.time().replace(hour=12)))
        Marcaje.objects.create(usuario=self.u, tipo=Marcaje.ENTRADA, momento=doce - timedelta(hours=4))
        # 11:59: todavía no; 12:00 en punto: «Es tu hora de comer», una sola vez
        self.assertEqual(servicios.revisar_almuerzos(doce - timedelta(minutes=1)), 0)
        self.assertEqual(servicios.revisar_almuerzos(doce), 1)
        self.assertEqual(servicios.revisar_almuerzos(doce + timedelta(seconds=30)), 0)
        self.assertEqual(Notificacion.objects.filter(destinatario=self.u, tipo='ALMUERZO_HORA').count(), 1)
        # «En 15 min»: vuelve a avisar a las 12:15
        with mock.patch('django.utils.timezone.now', return_value=doce + timedelta(seconds=40)):
            r = self.c.post('/api/asistencia/mi-almuerzo/', {'posponer': 15}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['almuerzo_inicio'], '12:15')
        self.assertEqual(servicios.revisar_almuerzos(doce + timedelta(minutes=14)), 0)
        self.assertEqual(servicios.revisar_almuerzos(doce + timedelta(minutes=15)), 1)
        self.assertEqual(self.c.post('/api/asistencia/mi-almuerzo/', {'posponer': 500}, format='json').status_code, 400)

    def test_visto_en_pantalla_no_se_repite_como_notificacion(self):
        hoy = timezone.localdate()
        doce = timezone.make_aware(timezone.datetime.combine(hoy, timezone.datetime.min.time().replace(hour=12)))
        Marcaje.objects.create(usuario=self.u, tipo=Marcaje.ENTRADA, momento=doce - timedelta(hours=4))
        self.c.post('/api/asistencia/mi-almuerzo/', {'visto': True}, format='json')
        self.assertEqual(servicios.revisar_almuerzos(doce), 0)

    def test_el_estado_trae_la_hora_de_hoy(self):
        self.c.post('/api/asistencia/mi-almuerzo/', {'hora': '15:00', 'solo_hoy': True}, format='json')
        limites = self.c.get('/api/asistencia/estado/').data['limites']
        self.assertEqual((limites['almuerzo_inicio'], limites['almuerzo_hoy']), ('15:00', '15:00'))
