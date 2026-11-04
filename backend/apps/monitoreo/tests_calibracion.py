"""Calibración del piloto: lo que ninguna regla clasifica y clasificarlo de un toque."""
from apps.monitoreo.models import Actividad, ReglaProductividad
from . import servicios
from .tests_proyectos import Base, local


class CalibracionTests(Base):
    def test_lista_lo_sin_regla_y_crea_la_regla(self):
        from apps.asistencia.models import Marcaje
        Marcaje.objects.create(usuario=self.ana, tipo='ENTRADA', momento=local(2026, 10, 28, 8))
        ReglaProductividad.objects.create(tipo='APP', patron='photoshop', categoria='P')
        servicios.ingestar(self.disp, self.minutos(local(2026, 10, 28, 9), 20, app='Photoshop.exe')
                           + self.minutos(local(2026, 10, 28, 10), 15, app='chrome.exe', dominio='www.sitio-nuevo.do', titulo='Inicio')
                           + self.minutos(local(2026, 10, 28, 11), 5, app='RarApp.exe', titulo='Inicio'))
        self.assertEqual(self.como(self.jefe).get('/api/monitoreo/calibracion/').status_code, 403)
        c = self.como(self.ti)
        d = c.get('/api/monitoreo/calibracion/?dias=7').json()
        self.assertEqual(d['minutos_con_regla'], 20)
        self.assertEqual([(x['tipo'], x['patron'], x['minutos']) for x in d['sin_clasificar']],
                         [('DOMINIO', 'sitio-nuevo.do', 15), ('APP', 'rarapp.exe', 5)])
        self.assertEqual(d['sin_clasificar'][0]['departamentos'][0]['nombre'], 'Marketing')
        r = c.post('/api/monitoreo/calibracion/', {'tipo': 'DOMINIO', 'patron': 'sitio-nuevo.do', 'categoria': 'P', 'departamento': self.mkt.pk}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['reclasificados'], 15)
        self.assertEqual(Actividad.objects.filter(dominio='www.sitio-nuevo.do', categoria='P').count(), 15)
        d = c.get('/api/monitoreo/calibracion/').json()
        self.assertEqual([x['patron'] for x in d['sin_clasificar']], ['rarapp.exe'])
        self.assertEqual(c.post('/api/monitoreo/calibracion/', {'tipo': 'APP', 'patron': 'x', 'categoria': 'Z'}, format='json').status_code, 400)
