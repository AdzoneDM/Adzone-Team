"""Jornada: empieza sola al abrir la plataforma; el cierre es manual (apagar o cerrar la plataforma no la cierra)."""
from datetime import timedelta
from unittest import mock

from django.utils import timezone
from rest_framework.test import APIClient

from apps.tiempo.models import RegistroTiempo
from . import servicios
from .models import Marcaje
from .tests import LUNES, Base, momento


class JornadaAutomaticaTests(Base):
    def setUp(self):
        super().setUp()
        self.c = APIClient()
        self.c.force_authenticate(self.ana)

    def en(self, hhmm, dia=LUNES):
        return mock.patch('django.utils.timezone.now', return_value=momento(dia, hhmm))

    def test_al_abrir_la_plataforma_se_ofrece_la_entrada_automatica(self):
        with self.en('07:50'):
            self.assertTrue(self.c.get('/api/asistencia/estado/').data['entrada_automatica'])
            r = self.c.post('/api/asistencia/marcar/', {'tipo': 'ENTRADA', 'automatica': True}, format='json')
            self.assertEqual(r.status_code, 201)
            self.assertEqual(Marcaje.objects.get(usuario=self.ana).origen, 'AUTO')
            self.assertFalse(self.c.get('/api/asistencia/estado/').data['entrada_automatica'])   # ya está trabajando

    def test_fuera_de_horario_o_dia_libre_no_empieza_sola(self):
        with self.en('03:00'):
            self.assertFalse(servicios.entrada_automatica(self.ana))
        with self.en('10:00', LUNES + timedelta(days=6)):   # domingo
            self.assertFalse(servicios.entrada_automatica(self.ana))

    def test_cerrar_la_plataforma_o_apagar_no_cierra_la_jornada(self):
        self.marcas(LUNES, ('ENTRADA', '08:00'))
        RegistroTiempo.objects.create(usuario=self.ana, descripcion='Diseño', inicio=momento(LUNES, '09:00'))
        with self.en('12:00'):
            self.assertEqual(self.c.post('/api/asistencia/presencia/').status_code, 200)
        # horas sin señal (apagó el equipo, se fue la luz, cerró el navegador): sigue abierta y el cronómetro sigue
        self.assertEqual(servicios.estado_actual(self.ana, momento(LUNES, '16:00'))[0], 'TRABAJANDO')
        self.assertFalse(Marcaje.objects.filter(usuario=self.ana, tipo='SALIDA').exists())
        self.assertIsNone(RegistroTiempo.objects.get(usuario=self.ana).fin)
        self.assertFalse(hasattr(servicios, 'cerrar_jornadas_sin_senal'))

    def test_la_cierra_cada_quien_a_mano(self):
        with self.en('08:00'):
            self.c.post('/api/asistencia/marcar/', {'tipo': 'ENTRADA', 'automatica': True}, format='json')
        with self.en('17:02'):
            r = self.c.post('/api/asistencia/marcar/', {'tipo': 'SALIDA'}, format='json')
            self.assertEqual(r.status_code, 201)
        salida = Marcaje.objects.get(usuario=self.ana, tipo='SALIDA')
        self.assertNotEqual(salida.origen, 'AUTO')
        self.assertEqual(servicios.estado_actual(self.ana, momento(LUNES, '17:30'))[0], 'FUERA')

    def test_recordatorio_si_la_olvida_abierta_una_hora_despues_del_turno(self):
        from apps.desempeno.models import Notificacion
        self.marcas(LUNES, ('ENTRADA', '08:00'))
        self.assertEqual(servicios.recordar_jornadas_abiertas(momento(LUNES, '17:30')), 0)   # turno hasta las 17:00: aún no
        self.assertEqual(servicios.recordar_jornadas_abiertas(momento(LUNES, '18:05')), 1)
        self.assertEqual(servicios.recordar_jornadas_abiertas(momento(LUNES, '18:30')), 0)   # una sola vez al día
        self.assertTrue(Notificacion.objects.filter(destinatario=self.ana, titulo='Tu jornada sigue abierta').exists())
        self.assertEqual(servicios.estado_actual(self.ana, momento(LUNES, '18:30'))[0], 'TRABAJANDO')   # recordar no la cierra

    def test_olvidada_al_dia_siguiente_vuelve_a_abrirse_sola(self):
        self.marcas(LUNES, ('ENTRADA', '08:00'))
        martes = LUNES + timedelta(days=1)
        with self.en('07:55', martes):
            self.assertTrue(servicios.entrada_automatica(self.ana))
        j = servicios.jornada(self.ana, LUNES, ahora=momento(martes, '08:00'))
        self.assertTrue(j['sin_salida'])

    def test_salida_a_mano_no_reabre_sola(self):
        self.marcas(LUNES, ('ENTRADA', '08:00'), ('SALIDA', '12:00'))
        with self.en('13:00'):
            self.assertFalse(servicios.entrada_automatica(self.ana))

    def test_quien_no_marca_obligatoriamente_no_empieza_sola(self):
        from .models import AsignacionHorario
        AsignacionHorario.objects.create(usuario=self.ana, horario=self.horario, marca_obligatoria=False)
        with self.en('08:00'):
            self.assertFalse(servicios.entrada_automatica(self.ana))
