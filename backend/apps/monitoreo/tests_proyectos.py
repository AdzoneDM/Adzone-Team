"""v9 · Fase 2: actividad por OT y proyecto, justificaciones, desconexiones y aviso a Tecnología."""
from datetime import datetime, timedelta
from unittest import mock

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.asistencia.models import Marcaje
from apps.core.models import Departamento
from apps.desempeno.models import Notificacion, Tarea
from apps.operaciones.models import Cliente, OrdenTrabajo, Proyecto
from apps.organizacion.models import PuestoDeTrabajo
from apps.tiempo.models import RegistroTiempo
from . import servicios
from .models import Actividad, Consentimiento, Dispositivo, ReglaProductividad


def local(y, m, d, h, mi=0):
    return timezone.make_aware(datetime(y, m, d, h, mi))


AHORA = local(2026, 10, 28, 15)


class Base(TestCase):
    def setUp(self):
        p = mock.patch('django.utils.timezone.now', return_value=AHORA)
        p.start()
        self.addCleanup(p.stop)
        self.mkt = Departamento.objects.create(nombre='Marketing')
        self.tec = Departamento.objects.create(nombre='Tecnología')
        self.p_jefe = PuestoDeTrabajo.objects.create(nombre='Gerente', departamento=self.mkt)
        self.p = PuestoDeTrabajo.objects.create(nombre='Diseñador', departamento=self.mkt, supervisor=self.p_jefe)
        self.p_ti = PuestoDeTrabajo.objects.create(nombre='Encargado TI', departamento=self.tec)
        self.jefe, self.ana, self.ti = self._u('jefe', self.p_jefe), self._u('ana', self.p), self._u('ti', self.p_ti)
        self.ana.perfil.costo_hora = 200
        self.ana.perfil.save()
        self.dir = User.objects.create_user('dir', password='x', is_staff=True)
        self.dir.groups.add(Group.objects.get_or_create(name='Administrador')[0])
        Consentimiento.objects.create(usuario=self.ana, version='1.0')
        self.disp, _ = Dispositivo.crear(self.ana, 'PC')
        cli = Cliente.objects.create(nombre='Cliente X')
        self.proy = Proyecto.objects.create(nombre='Campaña', cliente=cli)
        self.ot = OrdenTrabajo.objects.create(titulo='Brochure', cliente=cli, proyecto=self.proy, estado='EN_PRODUCCION')

    def _u(self, n, puesto):
        u = User.objects.create_user(n, password='x', first_name=n.title())
        u.perfil.puesto_trabajo = puesto
        u.perfil.save()
        return u

    def como(self, u):
        c = APIClient()
        c.force_authenticate(u)
        return c

    def minutos(self, desde, n, **extra):
        return [{'minuto': (desde + timedelta(minutes=i)).isoformat(), 'activos': 60, 'app': 'Photoshop', **extra} for i in range(n)]


class AtribucionTests(Base):
    def test_minutos_con_cronometro_corriendo_van_a_la_ot(self):
        Marcaje.objects.create(usuario=self.ana, tipo='ENTRADA', momento=local(2026, 10, 28, 8))
        r = RegistroTiempo.objects.create(usuario=self.ana, orden=self.ot, proyecto=self.proy, inicio=local(2026, 10, 28, 13))
        servicios.ingestar(self.disp, self.minutos(local(2026, 10, 28, 12, 50), 30))
        self.assertEqual(Actividad.objects.filter(registro=r).count(), 20)
        self.assertEqual(Actividad.objects.filter(registro__isnull=True).count(), 10)

    def test_al_anotar_horas_despues_se_unen_los_minutos(self):
        Marcaje.objects.create(usuario=self.ana, tipo='ENTRADA', momento=local(2026, 10, 28, 8))
        servicios.ingestar(self.disp, self.minutos(local(2026, 10, 28, 10), 60))
        r = RegistroTiempo.objects.create(usuario=self.ana, orden=self.ot, proyecto=self.proy, inicio=local(2026, 10, 28, 10),
                                          fin=local(2026, 10, 28, 10, 30), minutos=30)
        self.assertEqual(Actividad.objects.filter(registro=r).count(), 30)

    def test_reporte_por_ot_con_costo_solo_para_finanzas(self):
        Marcaje.objects.create(usuario=self.ana, tipo='ENTRADA', momento=local(2026, 10, 28, 8))
        servicios.ingestar(self.disp, self.minutos(local(2026, 10, 28, 9), 60))
        RegistroTiempo.objects.create(usuario=self.ana, orden=self.ot, proyecto=self.proy, inicio=local(2026, 10, 28, 9),
                                      fin=local(2026, 10, 28, 11), minutos=120)
        Tarea.objects.create(titulo='Diseño', colaborador=self.ana, orden=self.ot, proyecto=self.proy, fecha_limite=AHORA.date(),
                             estado='COMPLETADA', fecha_completada=AHORA.date(), rondas_revision=2, horas_estimadas=1)
        d = self.como(self.dir).get('/api/monitoreo/proyectos/?mes=2026-10').json()
        ot = d['ordenes'][0]
        self.assertEqual(ot['horas'], 2.0)
        self.assertEqual(ot['minutos_pc'], 60)
        self.assertEqual(ot['cobertura_pc'], 50.0)
        self.assertEqual(ot['correcciones'], 2)
        self.assertEqual(ot['horas_estimadas'], 1.0)
        self.assertTrue(ot['sobre_estimado'])
        self.assertEqual(ot['costo'], 400.0)
        self.assertEqual(d['totales']['costo'], 400.0)  # la OT y su proyecto no suman dos veces
        j = self.como(self.jefe).get('/api/monitoreo/proyectos/?mes=2026-10').json()
        self.assertNotIn('costo', j['ordenes'][0])
        self.assertEqual(self.como(self.ana).get('/api/monitoreo/proyectos/').status_code, 403)


class JustificacionTests(Base):
    def test_aprobar_pasa_los_minutos_a_productivos_y_no_se_reclasifican(self):
        ReglaProductividad.objects.create(tipo='DOMINIO', patron='youtube.com', categoria='I')
        Marcaje.objects.create(usuario=self.ana, tipo='ENTRADA', momento=local(2026, 10, 28, 8))
        servicios.ingestar(self.disp, self.minutos(local(2026, 10, 28, 10), 20, app='Chrome', dominio='youtube.com'))
        self.assertEqual(Actividad.objects.filter(categoria='I').count(), 20)
        r = self.como(self.ana).post('/api/monitoreo/justificaciones/', {'desde': local(2026, 10, 28, 10).isoformat(),
                                     'hasta': local(2026, 10, 28, 10, 15).isoformat(), 'motivo': 'Referencias de video para el cliente'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(Notificacion.objects.filter(destinatario=self.jefe, tipo='MONITOREO').exists())
        pk = r.json()['id']
        self.assertEqual(self.como(self.ana).post(f'/api/monitoreo/justificaciones/{pk}/revisar/', {'aprobar': True}, format='json').status_code, 403)
        pend = self.como(self.jefe).get('/api/monitoreo/justificaciones/?ver=equipo&estado=PENDIENTE').json()
        self.assertEqual(pend[0]['resumen']['improductivos'], 15)
        r = self.como(self.jefe).post(f'/api/monitoreo/justificaciones/{pk}/revisar/', {'aprobar': True}, format='json')
        self.assertEqual(r.json()['minutos'], 15)
        servicios.reclasificar()
        self.assertEqual(Actividad.objects.filter(categoria='P').count(), 15)
        self.assertEqual(self.como(self.jefe).post(f'/api/monitoreo/justificaciones/{pk}/revisar/', {'aprobar': True}, format='json').status_code, 400)

    def test_tramos_invalidos(self):
        c = self.como(self.ana)
        self.assertEqual(c.post('/api/monitoreo/justificaciones/', {'desde': AHORA.isoformat(), 'hasta': (AHORA - timedelta(hours=1)).isoformat(),
                                                                     'motivo': 'x'}, format='json').status_code, 400)
        self.assertEqual(c.post('/api/monitoreo/justificaciones/', {'desde': (AHORA - timedelta(days=30)).isoformat(),
                                                                     'hasta': (AHORA - timedelta(days=30, hours=-1)).isoformat(), 'motivo': 'x'}, format='json').status_code, 400)


class DesconexionYTecnologiaTests(Base):
    def test_huecos_en_jornada(self):
        Marcaje.objects.create(usuario=self.ana, tipo='ENTRADA', momento=local(2026, 10, 28, 9))
        servicios.ingestar(self.disp, self.minutos(local(2026, 10, 28, 9), 30) + self.minutos(local(2026, 10, 28, 10), 30))
        huecos = servicios.desconexiones(self.ana, AHORA.date())
        self.assertEqual(huecos[0]['minutos'], 30)  # 9:30 a 10:00
        self.assertEqual(huecos[1]['minutos'], 270)  # 10:30 hasta ahora (15:00)

    def test_computadora_sin_reportar_avisa_tambien_a_tecnologia(self):
        Marcaje.objects.create(usuario=self.ana, tipo='ENTRADA', momento=AHORA - timedelta(minutes=40))
        servicios.revisar_alertas()
        self.assertTrue(Notificacion.objects.filter(destinatario=self.ti, titulo__contains='no reporta').exists())
        self.assertTrue(Notificacion.objects.filter(destinatario=self.jefe, titulo__contains='no reporta').exists())
