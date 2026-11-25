"""Jornada automática: empieza sola al abrir la plataforma y termina sola al cerrarla (5 min sin señal)."""
from datetime import timedelta
from unittest import mock

from django.utils import timezone
from rest_framework.test import APIClient

from apps.tiempo.models import RegistroTiempo
from . import servicios
from .models import Marcaje, PresenciaPlataforma
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

    def test_sin_senal_5_minutos_se_cierra_a_la_hora_de_la_ultima_senal_y_para_el_cronometro(self):
        self.marcas(LUNES, ('ENTRADA', '08:00'))
        RegistroTiempo.objects.create(usuario=self.ana, descripcion='Diseño', inicio=momento(LUNES, '09:00'))
        with self.en('16:30'):
            self.assertEqual(self.c.post('/api/asistencia/presencia/').status_code, 200)
        with self.en('16:34'):   # 4 min: todavía no
            self.assertEqual(servicios.cerrar_jornadas_sin_senal(), 0)
        with self.en('16:36'):
            self.assertEqual(servicios.cerrar_jornadas_sin_senal(), 1)
        salida = Marcaje.objects.filter(usuario=self.ana, tipo='SALIDA').get()
        self.assertEqual((salida.origen, salida.momento), ('AUTO', momento(LUNES, '16:30')))
        reg = RegistroTiempo.objects.get(usuario=self.ana)
        self.assertEqual((reg.fin, reg.minutos), (momento(LUNES, '16:30'), 7 * 60 + 30))
        with self.en('16:40'):
            self.assertEqual(servicios.cerrar_jornadas_sin_senal(), 0)   # no se cierra dos veces

    def test_al_volver_a_abrir_empieza_otro_tramo_y_se_suman(self):
        self.marcas(LUNES, ('ENTRADA', '08:00'))
        PresenciaPlataforma.objects.create(usuario=self.ana, ultima_senal=momento(LUNES, '12:00'))
        with self.en('12:10'):
            servicios.cerrar_jornadas_sin_senal()
        with self.en('13:00'):
            self.assertTrue(self.c.post('/api/asistencia/presencia/').data['entrada_automatica'])
            self.assertEqual(self.c.post('/api/asistencia/marcar/', {'tipo': 'ENTRADA', 'automatica': True}, format='json').status_code, 201)
        self.marcas(LUNES, ('SALIDA', '17:00'))
        j = servicios.jornada(self.ana, LUNES, ahora=momento(LUNES, '18:00'))
        self.assertEqual(j['trabajados'], 8 * 60)

    def test_salida_a_mano_no_reabre_sola(self):
        self.marcas(LUNES, ('ENTRADA', '08:00'), ('SALIDA', '12:00'))
        with self.en('13:00'):
            self.assertFalse(servicios.entrada_automatica(self.ana))

    def test_quien_marco_por_qr_y_no_abrio_la_plataforma_no_se_cierra(self):
        self.marcas(LUNES, ('ENTRADA', '08:00'))
        PresenciaPlataforma.objects.create(usuario=self.ana, ultima_senal=momento(LUNES, '07:00'))   # señal de antes de entrar
        with self.en('12:00'):
            self.assertEqual(servicios.cerrar_jornadas_sin_senal(), 0)

    def test_en_pausa_tambien_se_cierra(self):
        self.marcas(LUNES, ('ENTRADA', '08:00'), ('PAUSA', '12:00'))
        PresenciaPlataforma.objects.create(usuario=self.ana, ultima_senal=momento(LUNES, '12:01'))
        with self.en('12:10'):
            self.assertEqual(servicios.cerrar_jornadas_sin_senal(), 1)
        self.assertEqual(servicios.estado_actual(self.ana, momento(LUNES, '12:10'))[0], 'FUERA')

    def test_quien_no_marca_obligatoriamente_no_empieza_sola(self):
        from .models import AsignacionHorario
        AsignacionHorario.objects.create(usuario=self.ana, horario=self.horario, marca_obligatoria=False)
        with self.en('08:00'):
            self.assertFalse(servicios.entrada_automatica(self.ana))
