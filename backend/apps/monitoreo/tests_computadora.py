"""Ficha de una computadora: actividad por día, mapa por hora, tareas, registro por sesiones, IP y monitoreo encendido/apagado."""
from rest_framework.test import APIClient

from apps.asistencia.models import Marcaje
from apps.tiempo.models import RegistroTiempo
from apps.desempeno.models import Tarea
from . import servicios
from .models import Actividad, IPDispositivo
from .tests_proyectos import AHORA, Base, local


class FichaComputadoraTests(Base):
    def setUp(self):
        super().setUp()
        Marcaje.objects.create(usuario=self.ana, tipo='ENTRADA', momento=local(2026, 10, 28, 8))
        t = Tarea.objects.create(titulo='Diseño de brochure', colaborador=self.ana, fecha_limite=AHORA.date())
        RegistroTiempo.objects.create(usuario=self.ana, tarea=t, inicio=local(2026, 10, 28, 9), fin=local(2026, 10, 28, 9, 30), minutos=30)
        servicios.ingestar(self.disp, self.minutos(local(2026, 10, 28, 9), 30, app='Photoshop.exe', titulo='Brochure.psd', intensidad=80)
                           + self.minutos(local(2026, 10, 28, 9, 30), 10, app='chrome.exe', dominio='youtube.com', titulo='Música'))

    def test_ficha_con_sesiones_mapa_y_tareas(self):
        d = self.como(self.jefe).get(f'/api/monitoreo/computadoras/{self.disp.pk}/?desde=2026-10-22&hasta=2026-10-28').json()
        self.assertEqual(len(d['por_dia']), 7)
        dia = d['por_dia'][-1]
        self.assertEqual((dia['registrados'], dia['activos']), (40, 40))
        self.assertEqual(d['mapa_horas'][2][9], {'minutos': 40, 'intensidad': 60})  # miércoles 9 a. m.: (30×80 + 10×0) ÷ 40
        self.assertEqual(d['tareas'][0], {'nombre': 'Diseño de brochure', 'minutos': 30})
        self.assertEqual(len(d['registro']), 2)                                         # dos sesiones, la más reciente primero
        self.assertEqual((d['registro'][0]['dominio'], d['registro'][0]['minutos']), ('youtube.com', 10))
        self.assertEqual(d['registro'][1]['tarea'], 'Diseño de brochure')
        self.assertFalse(d['puede_cambiar'])
        q = self.como(self.jefe).get(f'/api/monitoreo/computadoras/{self.disp.pk}/?desde=2026-10-22&hasta=2026-10-28&q=youtube').json()
        self.assertEqual(len(q['registro']), 1)

    def test_permisos_y_rango(self):
        self.assertEqual(self.como(self.ana).get(f'/api/monitoreo/computadoras/{self.disp.pk}/').status_code, 200)  # su propia computadora
        otro = self._u('otro', self.p)
        self.assertEqual(self.como(otro).get(f'/api/monitoreo/computadoras/{self.disp.pk}/').status_code, 404)
        self.assertEqual(self.como(self.ti).get(f'/api/monitoreo/computadoras/{self.disp.pk}/').status_code, 200)
        self.assertEqual(self.como(self.ti).get(f'/api/monitoreo/computadoras/{self.disp.pk}/?desde=2026-08-01&hasta=2026-10-28').status_code, 400)

    def test_apagar_el_monitoreo_del_equipo(self):
        self.assertEqual(self.como(self.jefe).post(f'/api/monitoreo/computadoras/{self.disp.pk}/monitorear/', {'monitorear': False}, format='json').status_code, 403)
        self.assertEqual(self.como(self.ti).post(f'/api/monitoreo/computadoras/{self.disp.pk}/monitorear/', {'monitorear': False}, format='json').status_code, 200)
        self.disp.refresh_from_db()
        self.assertFalse(servicios.estado_agente(self.disp)['registrar'])
        antes = Actividad.objects.count()
        servicios.ingestar(self.disp, self.minutos(local(2026, 10, 28, 11), 5))
        self.assertEqual(Actividad.objects.count(), antes)

    def test_el_agente_reporta_nombre_e_ip(self):
        from .models import Dispositivo
        d, token = Dispositivo.crear(self.ana, 'Laptop')
        ag = APIClient()
        ag.credentials(HTTP_AUTHORIZATION=f'Dispositivo {token}')
        ag.get('/api/monitoreo/agente/estado/?version=1.2&sistema=Windows+11&equipo=PC-DISENO-02', REMOTE_ADDR='192.168.1.40')
        ag.get('/api/monitoreo/agente/estado/', REMOTE_ADDR='192.168.1.40')
        d.refresh_from_db()
        self.assertEqual((d.nombre_equipo, d.ip), ('PC-DISENO-02', '192.168.1.40'))
        self.assertEqual(IPDispositivo.objects.get(dispositivo=d).veces, 2)
