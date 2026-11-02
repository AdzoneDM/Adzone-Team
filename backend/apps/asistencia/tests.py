from datetime import date, datetime, timedelta
from unittest import mock

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import Departamento
from apps.organizacion.models import PuestoDeTrabajo
from . import servicios
from .models import AsignacionHorario, Ausencia, Feriado, Horario, Marcaje

LUNES = date(2026, 10, 26)  # lunes


def momento(dia, hhmm):
    h, m = map(int, hhmm.split(':'))
    return timezone.make_aware(datetime(dia.year, dia.month, dia.day, h, m))


class Base(TestCase):
    def setUp(self):
        self.depto = Departamento.objects.create(nombre='Marketing')
        self.jefe_p = PuestoDeTrabajo.objects.create(nombre='Gerente', departamento=self.depto)
        self.p = PuestoDeTrabajo.objects.create(nombre='Diseñador', departamento=self.depto, supervisor=self.jefe_p)
        self.jefe = User.objects.create_user('jefe', password='Clave-segura-2026')
        self.jefe.perfil.puesto_trabajo = self.jefe_p
        self.jefe.perfil.save()
        self.ana = User.objects.create_user('ana', first_name='Ana', password='Clave-segura-2026')
        self.ana.perfil.puesto_trabajo = self.p
        self.ana.perfil.save()
        self.horario = Horario.objects.get(por_defecto=True)  # oficina, creado por la migración

    def marcas(self, dia, *pares, usuario=None):
        for tipo, hora in pares:
            Marcaje.objects.create(usuario=usuario or self.ana, tipo=tipo, momento=momento(dia, hora))


class JornadaTests(Base):
    def test_a_tiempo_con_almuerzo_marcado(self):
        self.marcas(LUNES, ('ENTRADA', '07:58'), ('PAUSA', '12:00'), ('REGRESO', '13:00'), ('SALIDA', '17:05'))
        j = servicios.jornada(self.ana, LUNES, ahora=momento(LUNES + timedelta(days=1), '09:00'))
        self.assertEqual(j['llegada'], 'A_TIEMPO')
        self.assertEqual(j['trabajados'], 8 * 60 + 7)
        self.assertEqual(j['pausa'], 60)
        self.assertEqual(j['programados'], 8 * 60)
        self.assertEqual(j['extra'], 0)  # 7 minutos no llegan a extra

    def test_tarde_sin_almuerzo_marcado_y_salida_temprana(self):
        self.marcas(LUNES, ('ENTRADA', '08:25'), ('SALIDA', '16:30'))
        j = servicios.jornada(self.ana, LUNES, ahora=momento(LUNES + timedelta(days=1), '09:00'))
        self.assertEqual(j['llegada'], 'TARDE')
        self.assertEqual(j['tardanza'], 25)
        self.assertEqual(j['trabajados'], 8 * 60 + 5 - 60)  # se descuenta el almuerzo no marcado
        self.assertEqual(j['salida_temprana'], 30)

    def test_dia_sin_salida_se_cierra_al_fin_del_turno(self):
        self.marcas(LUNES, ('ENTRADA', '08:00'))
        j = servicios.jornada(self.ana, LUNES, ahora=momento(LUNES + timedelta(days=1), '09:00'))
        self.assertTrue(j['sin_salida'])
        self.assertEqual(j['trabajados'], 8 * 60)

    def test_ausente_permiso_feriado_y_antes_de_usar_el_control(self):
        martes, miercoles, jueves = LUNES + timedelta(days=1), LUNES + timedelta(days=2), LUNES + timedelta(days=3)
        self.marcas(LUNES, ('ENTRADA', '08:00'), ('SALIDA', '17:00'))
        Ausencia.objects.create(usuario=self.ana, tipo='VACACIONES', desde=miercoles, hasta=miercoles, estado='APROBADA')
        Feriado.objects.create(fecha=jueves, nombre='Feriado')
        ahora = momento(LUNES + timedelta(days=5), '09:00')
        self.assertEqual(servicios.jornada(self.ana, martes, ahora)['estado'], 'AUSENTE')
        self.assertEqual(servicios.jornada(self.ana, miercoles, ahora)['estado'], 'PERMISO')
        self.assertFalse(servicios.jornada(self.ana, jueves, ahora)['laborable'])
        self.assertEqual(servicios.jornada(self.ana, LUNES - timedelta(days=7), ahora)['estado'], 'SIN_CONTROL')

    def test_resumen_del_periodo(self):
        martes = LUNES + timedelta(days=1)
        self.marcas(LUNES, ('ENTRADA', '08:00'), ('PAUSA', '12:00'), ('REGRESO', '13:00'), ('SALIDA', '17:00'))
        self.marcas(martes, ('ENTRADA', '08:30'), ('PAUSA', '12:00'), ('REGRESO', '13:00'), ('SALIDA', '19:00'))
        with mock.patch('django.utils.timezone.localdate', return_value=LUNES + timedelta(days=2)):
            r = servicios.resumen(self.ana, LUNES, martes, ahora=momento(LUNES + timedelta(days=2), '07:00'))
        self.assertEqual(r['dias_laborables'], 2)
        self.assertEqual(r['tardanzas'], 1)
        self.assertEqual(r['puntualidad'], 50.0)
        self.assertEqual(r['asistencia'], 100.0)
        self.assertEqual(r['minutos_extra'], 90)
        self.assertIsNotNone(servicios.adherencia(r))

    def test_horario_propio(self):
        call = Horario.objects.create(nombre='Call Center', dias={'0': ['09:00', '18:00']}, almuerzo_minutos=60)
        AsignacionHorario.objects.create(usuario=self.ana, horario=call)
        self.marcas(LUNES, ('ENTRADA', '08:55'))
        self.assertEqual(servicios.jornada(self.ana, LUNES, momento(LUNES, '10:00'))['llegada'], 'A_TIEMPO')


class ApiTests(Base):
    def setUp(self):
        super().setUp()
        self.c = APIClient()
        self.c.force_authenticate(self.ana)

    def test_flujo_de_marcaje(self):
        self.assertEqual(self.c.get('/api/asistencia/estado/').data['estado'], 'FUERA')
        self.assertEqual(self.c.post('/api/asistencia/marcar/', {'tipo': 'SALIDA'}).status_code, 400)
        self.assertEqual(self.c.post('/api/asistencia/marcar/', {'tipo': 'ENTRADA'}).status_code, 201)
        self.assertEqual(self.c.post('/api/asistencia/marcar/', {'tipo': 'ENTRADA'}).status_code, 400)
        self.assertEqual(self.c.post('/api/asistencia/marcar/', {'tipo': 'PAUSA', 'motivo': 'Almuerzo'}).status_code, 201)
        self.assertEqual(self.c.get('/api/asistencia/estado/').data['estado'], 'EN_PAUSA')
        self.assertEqual(self.c.post('/api/asistencia/marcar/', {'tipo': 'REGRESO'}).status_code, 201)
        self.assertEqual(self.c.post('/api/asistencia/marcar/', {'tipo': 'SALIDA'}).status_code, 201)
        self.assertEqual(len(self.c.get('/api/asistencia/mes/').data['dias'][-1]['marcajes']), 4)

    def test_solo_el_supervisor_corrige_y_ve_al_equipo(self):
        r = self.c.post('/api/asistencia/marcajes/', {'usuario': self.ana.pk, 'tipo': 'ENTRADA', 'momento': momento(LUNES, '08:00'), 'nota': 'x'})
        self.assertEqual(r.status_code, 403)  # nadie se corrige a sí mismo
        self.assertEqual(self.c.get('/api/asistencia/hoy/').status_code, 403)
        jefe = APIClient()
        jefe.force_authenticate(self.jefe)
        r = jefe.post('/api/asistencia/marcajes/', {'usuario': self.ana.pk, 'tipo': 'ENTRADA', 'momento': momento(LUNES, '08:00')})
        self.assertEqual(r.status_code, 400)  # falta la nota
        r = jefe.post('/api/asistencia/marcajes/', {'usuario': self.ana.pk, 'tipo': 'ENTRADA', 'momento': momento(LUNES, '08:00'), 'nota': 'Olvidó marcar'})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Marcaje.objects.get().origen, 'MANUAL')
        hoy = jefe.get('/api/asistencia/hoy/')
        self.assertEqual(hoy.status_code, 200)
        self.assertEqual([p['nombre'] for p in hoy.data['personas']], ['Ana'])
        self.assertEqual(jefe.get(f'/api/asistencia/mes/?usuario={self.ana.pk}').status_code, 200)
        self.assertEqual(self.c.get(f'/api/asistencia/mes/?usuario={self.jefe.pk}').status_code, 403)

    def test_permisos_se_piden_y_los_aprueba_el_supervisor(self):
        r = self.c.post('/api/asistencia/ausencias/', {'tipo': 'PERMISO', 'desde': LUNES, 'hasta': LUNES, 'motivo': 'Cita'})
        self.assertEqual(r.status_code, 201)
        pk = r.data['id']
        self.assertEqual(self.c.post(f'/api/asistencia/ausencias/{pk}/revisar/', {'aprobar': True}).status_code, 403)
        jefe = APIClient()
        jefe.force_authenticate(self.jefe)
        self.assertEqual(len(jefe.get('/api/asistencia/ausencias/?ver=equipo').data), 1)
        r = jefe.post(f'/api/asistencia/ausencias/{pk}/revisar/', {'aprobar': True}, format='json')
        self.assertEqual(r.data['estado'], 'APROBADA')

    def test_reporte_csv_y_horarios(self):
        admin = User.objects.create_superuser('admin', 'a@x.com', 'Clave-segura-2026')
        c = APIClient()
        c.force_authenticate(admin)
        r = c.get('/api/asistencia/reporte/?formato=csv')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Puntualidad %', r.content.decode())
        r = c.post('/api/asistencia/horarios/', {'nombre': 'Malo', 'dias': {'0': ['18:00', '08:00']}}, format='json')
        self.assertEqual(r.status_code, 400)
        r = c.post('/api/asistencia/horarios/', {'nombre': 'Call', 'dias': {'0': ['9:00', '18:00']}}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        r = c.post('/api/asistencia/asignaciones/', {'usuarios': [self.ana.pk], 'horario': r.data['id']}, format='json')
        self.assertEqual(AsignacionHorario.objects.get(usuario=self.ana).horario.nombre, 'Call')
        self.assertEqual(self.c.post('/api/asistencia/horarios/', {'nombre': 'X', 'dias': {'0': ['08:00', '09:00']}}, format='json').status_code, 403)
