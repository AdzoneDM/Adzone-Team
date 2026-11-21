"""Ponches de almuerzo y pausas, alerta al pasar el límite y horarios por departamento."""
from datetime import timedelta

from rest_framework.test import APIClient

from apps.desempeno.models import Notificacion
from . import servicios
from .models import AsignacionHorario, Horario, Marcaje
from .tests import LUNES, Base, momento


def en(hhmm, dia=LUNES):
    return momento(dia, hhmm)


class PausasTests(Base):
    def marcar(self, *pares, almuerzo_en=()):
        for tipo, hora in pares:
            Marcaje.objects.create(usuario=self.ana, tipo=tipo, momento=en(hora), es_almuerzo=(tipo == 'PAUSA' and hora in almuerzo_en),
                                   alerta_enviada=False)

    def test_almuerzo_y_pausas_se_cuentan_por_separado(self):
        self.marcar(('ENTRADA', '08:00'), ('PAUSA', '10:00'), ('REGRESO', '10:15'), ('PAUSA', '12:00'), ('REGRESO', '13:00'), ('SALIDA', '17:00'),
                    almuerzo_en=('12:00',))
        j = servicios.jornada(self.ana, LUNES, ahora=en('23:00', LUNES + timedelta(days=1)))
        self.assertEqual(j['almuerzo_seg'], 3600)
        self.assertEqual(j['pausas_seg'], 15 * 60)
        self.assertEqual(j['pausa_seg'], 75 * 60)              # el total sigue igual
        self.assertEqual(j['excesos'], 0)
        self.assertEqual([p['almuerzo'] for p in j['pausas']], [False, True])
        self.assertEqual(j['almuerzo_inicio'], '12:00')

    def test_pausa_que_pasa_del_limite_cuenta_como_exceso(self):
        self.marcar(('ENTRADA', '08:00'), ('PAUSA', '10:00'), ('REGRESO', '11:20'), ('SALIDA', '17:00'))
        j = servicios.jornada(self.ana, LUNES, ahora=en('23:00', LUNES + timedelta(days=1)))
        self.assertEqual(j['excesos'], 1)
        self.assertEqual(j['exceso_seg'], 20 * 60)
        self.assertTrue(j['pausas'][0]['excedida'])

    def test_el_limite_de_pausa_es_configurable_y_distinto_al_almuerzo(self):
        self.horario.pausa_max_minutos = 10
        self.horario.save()
        # 30 min de pausa: pasa el límite de 10; 50 min de almuerzo: no pasa el de 60 (el almuerzo no usa el límite de pausas)
        self.marcar(('ENTRADA', '08:00'), ('PAUSA', '10:00'), ('REGRESO', '10:30'), ('PAUSA', '12:00'), ('REGRESO', '12:50'), ('SALIDA', '17:00'),
                    almuerzo_en=('12:00',))
        j = servicios.jornada(self.ana, LUNES, ahora=en('23:00', LUNES + timedelta(days=1)))
        self.assertEqual([p['excedida'] for p in j['pausas']], [True, False])

    def test_alerta_a_los_60_minutos_a_la_persona_y_a_su_supervisor(self):
        self.marcar(('ENTRADA', '08:00'), ('PAUSA', '10:00'))
        self.assertEqual(servicios.revisar_pausas(ahora=en('10:59')), 0)           # todavía no
        self.assertFalse(Notificacion.objects.filter(tipo='ASISTENCIA').exists())
        self.assertEqual(servicios.revisar_pausas(ahora=en('11:02')), 1)
        avisos = Notificacion.objects.filter(tipo='ASISTENCIA')
        self.assertTrue(avisos.filter(destinatario=self.ana).exists())
        para_jefe = avisos.get(destinatario=self.jefe)
        self.assertIn('Ana', para_jefe.titulo)
        self.assertIn('1:02:00', para_jefe.titulo)                                  # tiempo transcurrido
        self.assertEqual(servicios.revisar_pausas(ahora=en('11:30')), 0)            # una sola vez

    def test_al_regresar_el_contador_se_detiene_y_no_hay_alerta(self):
        self.marcar(('ENTRADA', '08:00'), ('PAUSA', '10:00'), ('REGRESO', '10:40'))
        self.assertEqual(servicios.revisar_pausas(ahora=en('12:00')), 0)

    def test_el_almuerzo_alerta_con_su_propio_limite(self):
        self.horario.almuerzo_minutos = 45
        self.horario.save()
        self.marcar(('ENTRADA', '08:00'), ('PAUSA', '12:00'), almuerzo_en=('12:00',))
        self.assertEqual(servicios.revisar_pausas(ahora=en('12:44')), 0)
        self.assertEqual(servicios.revisar_pausas(ahora=en('12:46')), 1)
        self.assertIn('almuerzo', Notificacion.objects.filter(destinatario=self.jefe, tipo='ASISTENCIA').first().titulo)

    def test_las_pausas_viejas_no_generan_alertas(self):
        self.marcar(('ENTRADA', '08:00'), ('PAUSA', '10:00'))
        self.assertEqual(servicios.revisar_pausas(ahora=en('10:00', LUNES + timedelta(days=3))), 0)

    def test_ponches_de_almuerzo_por_la_api(self):
        c = APIClient()
        c.force_authenticate(self.ana)
        self.assertEqual(c.post('/api/asistencia/marcar/', {'tipo': 'ENTRADA'}).status_code, 201)
        self.assertEqual(c.post('/api/asistencia/marcar/', {'tipo': 'ALMUERZO'}).status_code, 201)
        e = c.get('/api/asistencia/estado/').json()
        self.assertEqual(e['estado'], 'EN_PAUSA')
        self.assertTrue(e['en_almuerzo'])
        self.assertEqual(e['limites']['pausa_min'], 60)
        self.assertEqual(c.post('/api/asistencia/marcar/', {'tipo': 'FIN_ALMUERZO'}).status_code, 201)
        self.assertEqual(c.post('/api/asistencia/marcar/', {'tipo': 'PAUSA'}).status_code, 201)
        self.assertFalse(c.get('/api/asistencia/estado/').json()['en_almuerzo'])
        tipos = list(Marcaje.objects.filter(usuario=self.ana).values_list('tipo', 'es_almuerzo'))
        self.assertEqual(tipos, [('ENTRADA', False), ('PAUSA', True), ('REGRESO', False), ('PAUSA', False)])

    def test_la_campanita_revisa_las_pausas(self):
        from django.core.cache import cache
        cache.clear()
        self.marcar(('ENTRADA', '08:00'), ('PAUSA', '10:00'))
        c = APIClient()
        c.force_authenticate(self.jefe)
        from unittest import mock
        from django.utils import timezone
        with mock.patch.object(timezone, 'now', return_value=en('11:30')):
            r = c.get('/api/desempeno/notificaciones/').json()
        self.assertTrue(any('en pausa' in a['titulo'] for a in r['avisos']))


class HorarioPorDepartamentoTests(Base):
    def setUp(self):
        super().setUp()
        self.admin = Horario.objects.create(nombre='Call Center mañana', dias={'0': ['09:00', '17:00']}, almuerzo_minutos=60)
        self.admin.departamentos.add(self.depto)

    def test_el_departamento_manda_sobre_el_general(self):
        self.assertEqual(servicios.horario_de(self.ana)[0], self.admin)
        j = servicios.jornadas_del_dia([self.ana], LUNES, ahora=en('09:30'))[self.ana.pk]
        self.assertEqual(j['turno'], ['09:00', '17:00'])

    def test_el_horario_propio_manda_sobre_el_del_departamento(self):
        turno = Horario.objects.create(nombre='Turno especial', dias={'0': ['13:00', '21:00']}, especial=True)
        AsignacionHorario.objects.create(usuario=self.ana, horario=turno)
        self.assertEqual(servicios.horario_de(self.ana)[0], turno)
        self.assertEqual(servicios.jornadas_del_dia([self.ana], LUNES, ahora=en('13:30'))[self.ana.pk]['turno'], ['13:00', '21:00'])

    def test_sin_departamento_con_horario_se_usa_el_general(self):
        self.admin.departamentos.clear()
        self.assertEqual(servicios.horario_de(self.ana)[0], self.horario)

    def test_se_guarda_por_la_api_con_almuerzo_y_pausa(self):
        from django.contrib.auth.models import Group, User
        adm = User.objects.create_superuser('root', password='Clave-segura-2026')
        c = APIClient()
        c.force_authenticate(adm)
        r = c.post('/api/asistencia/horarios/', {'nombre': 'Soporte', 'dias': {'0': ['10:00', '18:00']}, 'almuerzo_minutos': 60, 'almuerzo_inicio': '13:00',
                                                  'pausa_max_minutos': 45, 'departamentos': [self.depto.pk], 'especial': True}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.json()['almuerzo_inicio'], r.json()['pausa_max_minutos'], r.json()['especial']), ('13:00', 45, True))
        self.assertEqual(c.post('/api/asistencia/horarios/', {'nombre': 'Malo', 'dias': {'0': ['10:00', '18:00']}, 'almuerzo_inicio': '25:99'},
                                format='json').status_code, 400)
