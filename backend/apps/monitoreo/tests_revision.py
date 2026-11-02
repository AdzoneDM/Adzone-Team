"""Casos de la revisión independiente de la v8: permisos, medianoche, dos equipos, reglas y entradas inválidas."""
from datetime import datetime, timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.asistencia import servicios as asistencia
from apps.asistencia.models import Marcaje
from apps.core.models import Departamento
from apps.organizacion.models import PuestoDeTrabajo
from . import servicios
from .models import Actividad, Consentimiento, Dispositivo, ReglaProductividad


def local(y, m, d, h, mi=0):
    return timezone.make_aware(datetime(y, m, d, h, mi))


class Base(TestCase):
    def setUp(self):
        self.depto = Departamento.objects.create(nombre='Call Center')
        self.jefe_p = PuestoDeTrabajo.objects.create(nombre='Gerente', departamento=self.depto)
        self.p = PuestoDeTrabajo.objects.create(nombre='Agente', departamento=self.depto, supervisor=self.jefe_p)
        self.jefe = self._u('jefe', self.jefe_p)
        self.ana = self._u('ana', self.p)
        self.otro = self._u('otro', None)

    def _u(self, n, puesto):
        u = User.objects.create_user(n, password='Clave-segura-2026')
        u.perfil.puesto_trabajo = puesto
        u.perfil.save()
        return u

    def como(self, u):
        c = APIClient()
        c.force_authenticate(u)
        return c


class PermisosTests(Base):
    def test_un_marcaje_no_se_pasa_a_otra_persona(self):
        m = Marcaje.objects.create(usuario=self.ana, tipo='ENTRADA', momento=timezone.now() - timedelta(hours=1))
        r = self.como(self.jefe).patch(f'/api/asistencia/marcajes/{m.pk}/', {'usuario': self.jefe.pk}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Marcaje.objects.get(pk=m.pk).usuario, self.ana)

    def test_desvincular_no_borra_el_historial(self):
        d, _ = Dispositivo.crear(self.ana, 'PC')
        Actividad.objects.create(usuario=self.ana, dispositivo=d, minuto=timezone.now().replace(second=0, microsecond=0), activos=60)
        self.assertEqual(self.como(self.ana).delete(f'/api/monitoreo/dispositivos/{d.pk}/').status_code, 204)
        d.refresh_from_db()
        self.assertFalse(d.activo)
        self.assertEqual(Actividad.objects.filter(usuario=self.ana).count(), 1)

    def test_entradas_invalidas_dan_400(self):
        c = self.como(self.ana)
        self.assertEqual(c.get('/api/asistencia/mes/?usuario=abc').status_code, 400)
        self.assertEqual(c.get('/api/monitoreo/dia/?usuario=abc').status_code, 400)
        self.assertEqual(c.get('/api/desempeno/ficha/?usuario=abc').status_code, 400)
        self.assertEqual(c.post('/api/asistencia/marcar/', {'tipo': 'ENTRADA', 'motivo': ['x']}, format='json').status_code, 201)
        d, token = Dispositivo.crear(self.ana, 'PC')
        Consentimiento.objects.create(usuario=self.ana, version='1.0')
        ag = APIClient()
        ag.credentials(HTTP_AUTHORIZATION=f'Dispositivo {token}')
        self.assertEqual(ag.post('/api/monitoreo/agente/actividad/', {'minutos': [1, 'x', None]}, format='json').status_code, 200)
        self.assertEqual(ag.post('/api/monitoreo/agente/marcar/', {'tipo': 'OTRA'}, format='json').status_code, 400)
        admin = User.objects.create_superuser('adm', 'a@x.com', 'Clave-segura-2026')
        a = self.como(admin)
        self.assertEqual(a.post('/api/monitoreo/reclasificar/', {'dias': 'mucho'}, format='json').status_code, 400)
        self.assertEqual(a.patch('/api/monitoreo/configuracion/', {'capturas_cada_min': 0}, format='json').status_code, 400)
        self.assertEqual(a.patch('/api/monitoreo/configuracion/', {'retencion_dias': 0}, format='json').status_code, 400)


class MedianocheTests(Base):
    def test_turno_que_cruza_la_medianoche(self):
        Marcaje.objects.create(usuario=self.ana, tipo='ENTRADA', momento=local(2026, 11, 2, 23, 30))
        ahora = local(2026, 11, 3, 0, 10)
        self.assertEqual(asistencia.estado_actual(self.ana, ahora)[0], 'TRABAJANDO')
        self.assertEqual(asistencia.marcar(self.ana, 'ENTRADA', momento=ahora)[1], 'Ya marcaste entrada.')
        Marcaje.objects.create(usuario=self.ana, tipo='SALIDA', momento=local(2026, 11, 3, 7, 30))
        j = asistencia.jornada(self.ana, local(2026, 11, 2, 12).date(), ahora=local(2026, 11, 3, 9))
        self.assertEqual(j['trabajados'], 8 * 60 - 60)  # 8 h con el almuerzo no marcado descontado
        self.assertFalse(j['sin_salida'])
        tramos = servicios.tramos_en_jornada(self.ana, local(2026, 11, 3, 0, 5), local(2026, 11, 3, 0, 9))
        self.assertTrue(any(a <= local(2026, 11, 3, 0, 6) < b for a, b in tramos))  # el agente sigue midiendo

    def test_quien_nunca_marco_no_sale_tarde_ni_ausente_hoy(self):
        hoy = timezone.localdate()
        j = asistencia.jornada(self.otro, hoy)
        self.assertIn(j['estado'], ('SIN_CONTROL', 'LIBRE'))

    def test_pausa_sin_regreso_en_un_dia_pasado_sale_sin_salida(self):
        Marcaje.objects.create(usuario=self.ana, tipo='ENTRADA', momento=local(2026, 10, 26, 8))
        Marcaje.objects.create(usuario=self.ana, tipo='PAUSA', momento=local(2026, 10, 26, 12))
        j = asistencia.jornada(self.ana, local(2026, 10, 26, 12).date(), ahora=local(2026, 10, 28, 9))
        self.assertTrue(j['sin_salida'])


class DosEquiposYReglasTests(Base):
    def setUp(self):
        super().setUp()
        p = mock.patch('django.utils.timezone.now', return_value=local(2026, 10, 28, 15))
        p.start()
        self.addCleanup(p.stop)

    def test_dos_computadoras_no_duplican_minutos(self):
        Consentimiento.objects.create(usuario=self.ana, version='1.0')
        Marcaje.objects.create(usuario=self.ana, tipo='ENTRADA', momento=timezone.now() - timedelta(hours=1))
        d1, _ = Dispositivo.crear(self.ana, 'PC 1')
        d2, _ = Dispositivo.crear(self.ana, 'Laptop')
        inicio = (timezone.now() - timedelta(minutes=40)).replace(second=0, microsecond=0)
        minutos = [{'minuto': (inicio + timedelta(minutes=i)).isoformat(), 'activos': 60, 'app': 'x'} for i in range(30)]
        servicios.ingestar(d1, minutos)
        servicios.ingestar(d2, minutos)
        self.assertEqual(Actividad.objects.filter(usuario=self.ana).count(), 30)

    def test_sitios_por_dominio_exacto_y_el_patron_mas_largo_gana(self):
        ReglaProductividad.objects.all().delete()
        ReglaProductividad.objects.create(tipo='DOMINIO', patron='x.com', categoria='I')
        ReglaProductividad.objects.create(tipo='TITULO', patron='youtube', categoria='I')
        ReglaProductividad.objects.create(tipo='TITULO', patron='youtube studio', categoria='P')
        c = servicios.Clasificador()
        self.assertEqual(c.categoria(None, dominio='dropbox.com'), 'N')
        self.assertEqual(c.categoria(None, dominio='x.com'), 'I')
        self.assertEqual(c.categoria(None, dominio='m.x.com'), 'I')
        self.assertEqual(c.categoria(None, titulo='Canal - YouTube Studio'), 'P')
        self.assertEqual(c.categoria(None, titulo='Música - YouTube'), 'I')
