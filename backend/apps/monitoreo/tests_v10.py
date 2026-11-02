"""v10: reglas de comportamiento e incidencias, uso de IA, resumen, riesgo, perfiles, pantallas y computadoras."""
from datetime import timedelta

from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.asistencia.models import Marcaje
from apps.core.models import Departamento
from apps.desempeno.models import Notificacion
from apps.organizacion.models import PuestoDeTrabajo
from . import servicios
from .comportamiento import herramienta_ia, nivel_riesgo, parametros, sembrar_reglas
from .models import Actividad, Incidencia, PerfilMonitoreo, ReglaComportamiento
from .tests_proyectos import AHORA, Base, local


class ReglasTests(Base):
    def setUp(self):
        super().setUp()
        Marcaje.objects.create(usuario=self.ana, tipo='ENTRADA', momento=local(2026, 10, 28, 8))

    def test_reglas_iniciales_sembradas_y_tecnologia_excluida_del_acceso_remoto(self):
        self.assertGreaterEqual(ReglaComportamiento.objects.count(), 10)
        sembrar_reglas()  # no duplica
        self.assertEqual(ReglaComportamiento.objects.filter(nombre='Acceso remoto').count(), 1)

    def test_incidencia_acumula_y_avisa_al_cruzar_el_minimo(self):
        r = ReglaComportamiento.objects.create(nombre='Juegos test', campo='APP', patrones='steam', minutos_minimos=10,
                                               riesgo='ALTO', accion='ALERTAR', categoria='PRODUCTIVIDAD')
        servicios.ingestar(self.disp, self.minutos(local(2026, 10, 28, 10), 6, app='steam.exe'))
        inc = Incidencia.objects.get(regla=r)
        self.assertEqual(inc.minutos, 6)
        self.assertFalse(inc.avisada)
        servicios.ingestar(self.disp, self.minutos(local(2026, 10, 28, 11), 6, app='Steam.exe'))
        inc.refresh_from_db()
        self.assertEqual(inc.minutos, 12)
        self.assertTrue(inc.avisada)
        self.assertTrue(Notificacion.objects.filter(destinatario=self.jefe, titulo__contains='Juegos test').exists())
        self.assertTrue(Notificacion.objects.filter(destinatario=self.ti, titulo__contains='Juegos test').exists())  # riesgo alto: Tecnología
        servicios.ingestar(self.disp, self.minutos(local(2026, 10, 28, 12), 6, app='steam.exe'))
        self.assertEqual(Notificacion.objects.filter(destinatario=self.jefe, titulo__contains='Juegos test').count(), 1)  # una vez por día

    def test_dominio_y_departamento_excluido(self):
        r = ReglaComportamiento.objects.create(nombre='Remoto test', campo='DOMINIO', patrones='anydesk.com', minutos_minimos=1, accion='REGISTRAR')
        r.excluir_departamentos.add(self.mkt)
        servicios.ingestar(self.disp, self.minutos(local(2026, 10, 28, 10), 3, app='chrome', dominio='my.anydesk.com'))
        self.assertFalse(Incidencia.objects.filter(regla=r).exists())

    def test_herramientas_de_ia_y_nivel_de_riesgo(self):
        self.assertEqual(herramienta_ia('chrome.exe', 'chatgpt.com'), 'ChatGPT')
        self.assertEqual(herramienta_ia('chrome.exe', 'gemini.google.com'), 'Gemini')
        self.assertEqual(herramienta_ia('Claude.exe', ''), 'Claude')
        self.assertIsNone(herramienta_ia('chrome.exe', 'google.com'))
        self.assertEqual(nivel_riesgo(0), 'SIN_RIESGO')
        self.assertEqual(nivel_riesgo(6), 'MEDIO')
        self.assertEqual(nivel_riesgo(40), 'CRITICO')


class ResumenTests(Base):
    def test_resumen_con_ia_incidencias_riesgo_e_insights(self):
        Marcaje.objects.create(usuario=self.ana, tipo='ENTRADA', momento=local(2026, 10, 28, 8))
        servicios.ingestar(self.disp, self.minutos(local(2026, 10, 28, 9), 40, app='chrome', dominio='chatgpt.com')
                           + self.minutos(local(2026, 10, 28, 10), 20, app='chrome', dominio='bet365.com'))
        c = self.como(self.jefe)
        d = c.get('/api/monitoreo/resumen/?desde=2026-10-22&hasta=2026-10-28').json()
        self.assertEqual(d['ia']['herramientas'][0], {'nombre': 'ChatGPT', 'minutos': 40, 'personas': 1})
        self.assertEqual(d['incidencias'][0]['nombre'], 'Apuestas y casinos en línea')
        self.assertEqual(d['riesgo'][0]['nivel'], 'MEDIO')  # una incidencia de riesgo alto = 6 puntos
        self.assertEqual(d['sitios'][0]['nombre'], 'chatgpt.com')
        self.assertTrue(d['insights'])
        self.assertEqual(self.como(self.ana).get('/api/monitoreo/resumen/').status_code, 403)
        self.assertEqual(c.get('/api/monitoreo/resumen/?desde=2026-01-01&hasta=2026-10-28').status_code, 400)
        self.assertEqual(c.get('/api/monitoreo/resumen/?desde=ayer').status_code, 400)

    def test_incidencias_se_revisan_por_el_supervisor_y_la_persona_ve_las_suyas(self):
        Marcaje.objects.create(usuario=self.ana, tipo='ENTRADA', momento=local(2026, 10, 28, 8))
        servicios.ingestar(self.disp, self.minutos(local(2026, 10, 28, 9), 5, app='chrome', dominio='bet365.com'))
        mias = self.como(self.ana).get('/api/monitoreo/incidencias/?desde=2026-10-01&hasta=2026-10-31').json()
        self.assertEqual(len(mias), 1)
        pk = mias[0]['id']
        self.assertEqual(self.como(self.ana).patch(f'/api/monitoreo/incidencias/{pk}/', {'estado': 'DESCARTADA'}, format='json').status_code, 403)
        r = self.como(self.jefe).patch(f'/api/monitoreo/incidencias/{pk}/', {'estado': 'DESCARTADA', 'nota': 'Era una investigación'}, format='json')
        self.assertEqual(r.json()['estado'], 'DESCARTADA')
        d = self.como(self.jefe).get('/api/monitoreo/resumen/?desde=2026-10-22&hasta=2026-10-28').json()
        self.assertEqual(d['riesgo'], [])  # las descartadas no suman riesgo
        otro = self._u('otro', self.p_ti)
        self.assertEqual(self.como(otro).get('/api/monitoreo/incidencias/?desde=2026-10-01&hasta=2026-10-31').json(), [])


class PerfilesTests(Base):
    def test_perfil_por_departamento_y_por_persona(self):
        self.assertIsNone(parametros(self.ana)['perfil'])
        dep = PerfilMonitoreo.objects.create(nombre='Marketing', capturas=True, capturas_cada_min=5)
        dep.departamentos.add(self.mkt)
        self.assertEqual(parametros(self.ana)['capturas_cada_min'], 5)
        direc = PerfilMonitoreo.objects.create(nombre='Dirección', monitorear=False)
        direc.personas.add(self.ana)
        p = parametros(self.ana)
        self.assertFalse(p['monitorear'])
        estado = servicios.estado_agente(self.disp)
        self.assertFalse(estado['registrar'])
        Marcaje.objects.create(usuario=self.ana, tipo='ENTRADA', momento=local(2026, 10, 28, 8))
        self.assertEqual(servicios.ingestar(self.disp, self.minutos(local(2026, 10, 28, 9), 5))[0], 0)

    def test_api_de_perfiles_no_repite_departamento(self):
        a = self.como(self.dir)
        self.assertEqual(a.post('/api/monitoreo/perfiles/', {'nombre': 'A', 'departamentos': [self.mkt.pk]}, format='json').status_code, 201)
        r = a.post('/api/monitoreo/perfiles/', {'nombre': 'B', 'departamentos': [self.mkt.pk]}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.como(self.jefe).post('/api/monitoreo/perfiles/', {'nombre': 'C'}, format='json').status_code, 403)

    def test_reglas_api_valida_patrones(self):
        a = self.como(self.dir)
        self.assertEqual(a.post('/api/monitoreo/reglas-comportamiento/', {'nombre': 'x', 'campo': 'APP', 'patrones': 'a'}, format='json').status_code, 400)
        r = a.post('/api/monitoreo/reglas-comportamiento/', {'nombre': 'x', 'campo': 'APP', 'patrones': ' Steam \n\n Roblox '}, format='json')
        self.assertEqual(r.json()['patrones'], 'steam\nroblox')


class PantallasYComputadorasTests(Base):
    def test_computadoras_solo_tecnologia_y_admin(self):
        self.assertEqual(self.como(self.jefe).get('/api/monitoreo/computadoras/').status_code, 403)
        d = self.como(self.ti).get('/api/monitoreo/computadoras/').json()
        ana = next(p for p in d['personas'] if p['id'] == self.ana.pk)
        self.assertEqual(ana['estado'], 'DESCONECTADO')
        self.assertEqual(len(d['computadoras']), 1)
        self.assertEqual(self.como(self.dir).get('/api/monitoreo/computadoras/').status_code, 200)

    def test_pantallas_y_actividad_reciente(self):
        self.assertEqual(self.como(self.jefe).get('/api/monitoreo/pantallas/').status_code, 200)
        self.assertEqual(self.como(self.ana).get('/api/monitoreo/pantallas/').status_code, 403)
        Marcaje.objects.create(usuario=self.ana, tipo='ENTRADA', momento=AHORA - timedelta(hours=2))
        servicios.ingestar(self.disp, self.minutos(AHORA - timedelta(minutes=20), 15))
        fila = next(p for p in self.como(self.jefe).get('/api/monitoreo/equipo/').json()['personas'] if p['id'] == self.ana.pk)
        self.assertEqual(sum(fila['reciente']), 15)


class ReaplicarTests(Base):
    def test_regla_nueva_se_aplica_a_lo_pasado_sin_avisar(self):
        Marcaje.objects.create(usuario=self.ana, tipo='ENTRADA', momento=local(2026, 10, 27, 8))
        servicios.ingestar(self.disp, self.minutos(local(2026, 10, 27, 9), 8, app='chrome', dominio='pinterest.com'))
        r = ReglaComportamiento.objects.create(nombre='Pinterest', campo='DOMINIO', patrones='pinterest.com', minutos_minimos=5, accion='ALERTAR')
        d = self.como(self.dir).post('/api/monitoreo/reglas-comportamiento/reaplicar/').json()
        self.assertGreaterEqual(d['incidencias'], 1)
        inc = Incidencia.objects.get(regla=r)
        self.assertEqual(inc.minutos, 8)
        self.assertTrue(inc.avisada)
        self.assertFalse(Notificacion.objects.filter(titulo__contains='Pinterest').exists())
        from .comportamiento import reaplicar
        reaplicar(30)  # repetir no duplica minutos
        inc.refresh_from_db()
        self.assertEqual(inc.minutos, 8)


class RiesgoCriticoTests(Base):
    def test_una_incidencia_critica_es_riesgo_alto(self):
        from .comportamiento import riesgo
        Marcaje.objects.create(usuario=self.ana, tipo='ENTRADA', momento=local(2026, 10, 28, 8))
        servicios.ingestar(self.disp, self.minutos(local(2026, 10, 28, 9), 1, app='chrome', dominio='xvideos.com'))
        r = riesgo([self.ana.pk], local(2026, 10, 28, 0).date(), local(2026, 10, 28, 0).date())
        self.assertEqual(r[self.ana.pk]['nivel'], 'ALTO')
