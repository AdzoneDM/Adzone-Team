from datetime import date, timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.asistencia.models import Marcaje
from apps.core.models import Departamento
from apps.desempeno.models import Notificacion
from apps.kpis.models import KPIAsignado, PlantillaKPI
from apps.organizacion.models import PuestoDeTrabajo
from . import servicios
from .models import Actividad, ConfiguracionMonitoreo, Consentimiento, Dispositivo


# Reloj fijo (miércoles 28/10/2026, 3:00 p. m.): los casos no dependen de la hora en que corren las pruebas.
AHORA = timezone.make_aware(__import__('datetime').datetime(2026, 10, 28, 15, 0))


def fijar_reloj(caso):
    p = mock.patch('django.utils.timezone.now', return_value=AHORA)
    p.start()
    caso.addCleanup(p.stop)


class Base(TestCase):
    def setUp(self):
        fijar_reloj(self)
        self.mkt, _ = Departamento.objects.get_or_create(nombre='Marketing')
        self.adm, _ = Departamento.objects.get_or_create(nombre='Administración')
        from apps.monitoreo.models import ReglaProductividad
        from apps.monitoreo.reglas_iniciales import sembrar
        sembrar(ReglaProductividad, Departamento)
        self.jefe_p = PuestoDeTrabajo.objects.create(nombre='Gerente', departamento=self.mkt)
        self.cm_p = PuestoDeTrabajo.objects.create(nombre='Community', departamento=self.mkt, supervisor=self.jefe_p)
        self.cont_p = PuestoDeTrabajo.objects.create(nombre='Contador', departamento=self.adm, supervisor=self.jefe_p)
        self.jefe = self._u('jefe', self.jefe_p)
        self.cm = self._u('cm', self.cm_p)
        self.cont = self._u('cont', self.cont_p)
        self.disp, self.token = Dispositivo.crear(self.cm, 'PC 1')
        self.agente = APIClient()
        self.agente.credentials(HTTP_AUTHORIZATION=f'Dispositivo {self.token}')

    def _u(self, nombre, puesto):
        u = User.objects.create_user(nombre, first_name=nombre.title(), password='Clave-segura-2026')
        u.perfil.puesto_trabajo = puesto
        u.perfil.save()
        return u

    def minutos(self, n, inicio=None, **datos):
        inicio = (inicio or timezone.now() - timedelta(minutes=n)).replace(second=0, microsecond=0)
        return [{'minuto': (inicio + timedelta(minutes=i)).isoformat(), 'activos': 50, 'inactivos': 10, 'intensidad': 60,
                 'cambios': 1, 'app': 'chrome', 'titulo': 'Instagram', **datos} for i in range(n)]


class ClasificacionTests(Base):
    def test_el_departamento_gana_y_el_titulo_gana_a_la_app(self):
        c = servicios.Clasificador()
        self.assertEqual(c.categoria(self.mkt.pk, 'chrome.exe', 'Instagram - Google Chrome'), 'P')
        self.assertEqual(c.categoria(self.adm.pk, 'chrome.exe', 'Instagram - Google Chrome'), 'I')
        self.assertEqual(c.categoria(self.adm.pk, 'chrome.exe', 'Nueva pestaña'), 'N')
        self.assertEqual(c.categoria(self.adm.pk, 'EXCEL.EXE', 'Nómina.xlsx'), 'P')
        self.assertEqual(c.categoria(None, 'Photoshop.exe', ''), 'P')


class AgenteTests(Base):
    def test_sin_token_o_con_token_malo_no_entra(self):
        self.assertIn(APIClient().get('/api/monitoreo/agente/estado/').status_code, (401, 403))
        malo = APIClient()
        malo.credentials(HTTP_AUTHORIZATION='Dispositivo adz_falso')
        self.assertEqual(malo.get('/api/monitoreo/agente/estado/').status_code, 401)

    def test_solo_registra_con_consentimiento_y_en_jornada(self):
        estado = self.agente.get('/api/monitoreo/agente/estado/').data
        self.assertFalse(estado['registrar'])
        self.assertIn('política', estado['motivo'])
        Consentimiento.objects.create(usuario=self.cm, version='1.0')
        self.assertIn('entrada', self.agente.get('/api/monitoreo/agente/estado/').data['motivo'])
        # fuera de jornada: se descarta todo
        r = self.agente.post('/api/monitoreo/agente/actividad/', {'minutos': self.minutos(5)}, format='json')
        self.assertEqual(r.data['guardados'], 0)
        # marca entrada desde el agente y ya registra
        self.assertEqual(self.agente.post('/api/monitoreo/agente/marcar/', {'tipo': 'ENTRADA'}, format='json').status_code, 201)
        Marcaje.objects.filter(usuario=self.cm).update(momento=timezone.now() - timedelta(minutes=30))
        self.assertTrue(self.agente.get('/api/monitoreo/agente/estado/').data['registrar'])
        r = self.agente.post('/api/monitoreo/agente/actividad/', {'minutos': self.minutos(10)}, format='json')
        self.assertEqual(r.data['guardados'], 10)
        r = self.agente.post('/api/monitoreo/agente/actividad/', {'minutos': self.minutos(10)}, format='json')
        self.assertEqual(r.data['guardados'], 0)  # duplicados
        self.assertEqual(Actividad.objects.filter(categoria='P').count(), 10)  # Instagram es trabajo en Marketing
        # en pausa ya no registra
        self.agente.post('/api/monitoreo/agente/marcar/', {'tipo': 'PAUSA'}, format='json')
        self.assertFalse(self.agente.get('/api/monitoreo/agente/estado/').data['registrar'])

    def test_capturas_solo_si_estan_activadas(self):
        Consentimiento.objects.create(usuario=self.cm, version='1.0')
        Marcaje.objects.create(usuario=self.cm, tipo='ENTRADA', momento=timezone.now() - timedelta(minutes=5))
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGB', (40, 30), 'white').save(buf, 'PNG')
        buf.seek(0)
        buf.name = 'c.png'
        self.assertEqual(self.agente.post('/api/monitoreo/agente/captura/', {'archivo': buf}, format='multipart').status_code, 409)
        c = ConfiguracionMonitoreo.actual()
        c.capturas = True
        c.save()
        buf.seek(0)
        self.assertEqual(self.agente.post('/api/monitoreo/agente/captura/', {'archivo': buf}, format='multipart').status_code, 201)
        jefe = APIClient()
        jefe.force_authenticate(self.jefe)
        dia = jefe.get(f'/api/monitoreo/dia/?usuario={self.cm.pk}').data
        self.assertEqual(len(dia['capturas']), 1)
        self.assertEqual(jefe.get(f"/api/monitoreo/capturas/{dia['capturas'][0]['id']}/").status_code, 200)
        otro = APIClient()
        otro.force_authenticate(self.cont)
        self.assertEqual(otro.get(f"/api/monitoreo/capturas/{dia['capturas'][0]['id']}/").status_code, 404)


class ConsultasTests(Base):
    def setUp(self):
        super().setUp()
        Consentimiento.objects.create(usuario=self.cm, version='1.0')
        Marcaje.objects.create(usuario=self.cm, tipo='ENTRADA', momento=timezone.now() - timedelta(hours=2))
        servicios.ingestar(self.disp, self.minutos(40, app='photoshop', titulo='Arte.psd')
                           + self.minutos(10, inicio=timezone.now() - timedelta(minutes=70), titulo='Netflix', app='chrome')
                           + self.minutos(5, inicio=timezone.now() - timedelta(minutes=80), activos=0, inactivos=60))

    def test_resumen_del_dia_y_vista_de_equipo(self):
        r = servicios.resumen_dia(self.cm, timezone.localdate())
        self.assertEqual(r['minutos_registrados'], 55)
        self.assertEqual(r['minutos_inactivos'], 5)
        self.assertEqual(r['minutos_productivos'], 40)
        self.assertEqual(r['minutos_improductivos'], 10)
        self.assertEqual(r['minutos_foco'], 40)
        self.assertEqual(r['apps'][0]['nombre'], 'photoshop')
        jefe = APIClient()
        jefe.force_authenticate(self.jefe)
        eq = jefe.get('/api/monitoreo/equipo/').data['personas']
        fila = next(p for p in eq if p['id'] == self.cm.pk)
        self.assertEqual(fila['productividad'], 80.0)
        self.assertTrue(fila['ahora']['en_vivo'])
        yo = APIClient()
        yo.force_authenticate(self.cm)
        self.assertEqual(yo.get('/api/monitoreo/dia/').status_code, 200)  # ve lo suyo
        self.assertEqual(yo.get(f'/api/monitoreo/dia/?usuario={self.cont.pk}').status_code, 403)
        self.assertEqual(yo.get('/api/monitoreo/equipo/').status_code, 403)

    def test_alertas_de_improductivo_y_sin_repetir(self):
        c = ConfiguracionMonitoreo.actual()
        c.alerta_improductivo_pct = 15
        c.save()
        servicios.ingestar(self.disp, self.minutos(15, inicio=timezone.now() - timedelta(minutes=100), titulo='Netflix'))
        servicios.revisar_alertas()
        servicios.revisar_alertas()
        self.assertEqual(Notificacion.objects.filter(tipo='MONITOREO', destinatario=self.jefe).count(), 1)

    def test_kpi_automatico_y_jornada_en_el_puntaje(self):
        from apps.desempeno.puntaje import Mediciones, calcular_ranking
        plantilla = PlantillaKPI.objects.create(nombre='Productividad PC', unidad_medida='%', fuente='PRODUCTIVIDAD_PC')
        KPIAsignado.objects.create(puesto_trabajo=self.cm_p, plantilla_kpi=plantilla, ponderacion=100, objetivo_meta='',
                                   es_entrada_manual=False, meta_numerica=75)
        hoy = timezone.localdate()
        m = Mediciones(self.cm, hoy.replace(day=1), hoy)
        self.assertEqual(m.medir('PRODUCTIVIDAD_PC'), 80.0)
        servicios.ingestar(self.disp, self.minutos(20, inicio=timezone.now() - timedelta(minutes=110), app='photoshop', titulo='x'))
        fila = next(f for f in calcular_ranking(hoy.replace(day=1)) if f['colaborador_id'] == self.cm.pk)
        self.assertEqual(fila['kpis'][0]['cumplimiento'], 100.0)  # 80 % contra meta 75 %
        self.assertIsNotNone(fila['puntaje_jornada'])
        self.assertIn('productividad', fila['jornada_detalle'])
        jefe = APIClient()
        jefe.force_authenticate(self.jefe)
        ficha = jefe.get(f'/api/desempeno/ficha/?usuario={self.cm.pk}').data
        self.assertEqual(ficha['computadora']['productividad'], 85.7)
        self.assertEqual(len(ficha['tendencia']), 6)

    def test_limpieza_por_retencion(self):
        from django.db.models import F
        Actividad.objects.update(minuto=F('minuto') - timedelta(days=200))
        self.assertEqual(servicios.limpiar()[0], 55)


class DispositivosTests(Base):
    def test_vincular_muestra_el_token_una_vez(self):
        c = APIClient()
        c.force_authenticate(self.cm)
        r = c.post('/api/monitoreo/dispositivos/', {'nombre': 'Laptop'}, format='json')
        self.assertTrue(r.data['token'].startswith('adz_'))
        self.assertNotIn('token', c.get('/api/monitoreo/dispositivos/').data[0])
        self.assertEqual(c.post('/api/monitoreo/dispositivos/', {'nombre': 'X', 'usuario': self.cont.pk}, format='json').status_code, 403)
        self.assertEqual(c.get('/api/monitoreo/politica/').data['aceptada'], False)
        c.post('/api/monitoreo/politica/')
        self.assertEqual(c.get('/api/monitoreo/politica/').data['aceptada'], True)
