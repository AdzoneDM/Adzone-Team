"""Tablero por departamento: KPIs del mes o trimestre, personal y políticas, con mínimo privilegio."""
from datetime import date

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import Departamento
from apps.kpis.models import KPIAsignado, PlantillaKPI
from apps.organizacion.models import PuestoDeTrabajo
from apps.talento.models import AceptacionPolitica, Politica
from .models import ResultadoKPI


class TableroTests(TestCase):
    def setUp(self):
        self.ti = Departamento.objects.create(nombre='Software & Hardware')
        self.mkt = Departamento.objects.create(nombre='Marketing')
        p_jefe = PuestoDeTrabajo.objects.create(nombre='Gerente TI', departamento=self.ti)
        p_tec = PuestoDeTrabajo.objects.create(nombre='Soporte', departamento=self.ti, supervisor=p_jefe)
        p_cm = PuestoDeTrabajo.objects.create(nombre='Community', departamento=self.mkt)
        self.jefe, self.ana, self.beto = self._u('jefe', p_jefe), self._u('ana', p_tec), self._u('beto', p_tec)
        self.cm = self._u('cm', p_cm)
        self.dir = self._u('dir', None)
        self.dir.groups.set([Group.objects.get(name='Administrador')])
        self.ana.perfil.salario_mensual = 40000
        self.ana.perfil.save()
        inc = PlantillaKPI.objects.create(nombre='Incidentes resueltos', unidad_medida='%')
        cap = PlantillaKPI.objects.create(nombre='Capacitación', unidad_medida='horas')
        pc = PlantillaKPI.objects.create(nombre='Productividad en PC', unidad_medida='%', fuente='PRODUCTIVIDAD_PC')
        self.k1 = KPIAsignado.objects.create(puesto_trabajo=p_tec, plantilla_kpi=inc, ponderacion=50, es_entrada_manual=True)
        KPIAsignado.objects.create(puesto_trabajo=p_tec, plantilla_kpi=cap, ponderacion=50, es_entrada_manual=True)
        KPIAsignado.objects.create(puesto_trabajo=p_tec, plantilla_kpi=pc, ponderacion=0, es_entrada_manual=False, meta_numerica=80)
        self.mes = timezone.localdate().replace(day=1)
        ResultadoKPI.objects.create(kpi_asignado=self.k1, colaborador=self.ana, periodo=self.mes, valor_meta=100, valor_real=100)
        ResultadoKPI.objects.create(kpi_asignado=self.k1, colaborador=self.beto, periodo=self.mes, valor_meta=100, valor_real=50)
        self.pol_ti = Politica.objects.create(clave='uso-equipos', titulo='Uso de equipos', contenido='x', para_todos=False)
        self.pol_ti.departamentos.add(self.ti)
        Politica.objects.create(clave='general', titulo='Código de conducta', contenido='x')
        AceptacionPolitica.objects.create(politica=self.pol_ti, usuario=self.ana, version=1)

    def _u(self, n, puesto):
        u = User.objects.create_user(n, password='x', first_name=n.title())
        if puesto:
            u.perfil.puesto_trabajo = puesto
            u.perfil.save()
        return User.objects.get(pk=u.pk)

    def get(self, u, url):
        c = APIClient()
        c.force_authenticate(u)
        return c.get(url)

    def test_direccion_ve_el_departamento_completo(self):
        r = self.get(self.dir, f'/api/desempeno/departamentos/{self.ti.pk}/?anio={self.mes.year}&mes={self.mes.month}')
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        self.assertEqual([p['nombre'] for p in d['personas']], ['Jefe', 'Ana', 'Beto'])
        inc = next(k for k in d['kpis'] if k['nombre'] == 'Incidentes resueltos')
        self.assertEqual((inc['cumplimiento'], inc['con_dato'], inc['estado']), (75.0, 2, 'BAJO'))
        cap = next(k for k in d['kpis'] if k['nombre'] == 'Capacitación')
        self.assertEqual(cap['estado'], 'SIN_DATO')  # sin dato no es «0 · bajo la meta»
        ana = next(p for p in d['personas'] if p['nombre'] == 'Ana')
        self.assertEqual(ana['salario'], 40000.0)
        self.assertEqual(len(ana['kpis']), 3)
        self.assertIn('rendimiento', d['resumen']['texto'])
        pol = {p['titulo']: p for p in d['politicas']}
        self.assertEqual((pol['Uso de equipos']['aplican'], pol['Uso de equipos']['aceptaron']), (3, 1))
        self.assertIn('Beto', pol['Uso de equipos']['pendientes'])
        self.assertEqual(pol['Código de conducta']['alcance'], 'Toda la empresa')

    def test_supervisor_solo_su_equipo_sin_salario_ni_pc(self):
        lista = self.get(self.jefe, '/api/desempeno/departamentos/').json()
        self.assertEqual([d['nombre'] for d in lista], ['Software & Hardware'])
        self.assertEqual(self.get(self.jefe, f'/api/desempeno/departamentos/{self.mkt.pk}/').status_code, 404)
        d = self.get(self.jefe, f'/api/desempeno/departamentos/{self.ti.pk}/').json()
        self.assertEqual(d['nivel'], 'equipo')
        self.assertEqual(sorted(p['nombre'] for p in d['personas'] if p['detalle']), ['Ana', 'Beto', 'Jefe'])
        self.assertEqual(d['estructura']['encargados'][0]['nombre'], 'Jefe')
        ana = next(p for p in d['personas'] if p['nombre'] == 'Ana')
        self.assertEqual(ana['supervisor'], 'Jefe')
        self.assertIsNone(ana['salario'])
        self.assertEqual(next(k for k in ana['kpis'] if k['nombre'] == 'Productividad en PC')['estado'], 'RESERVADO')
        self.assertFalse(d['puede']['ingresar'])

    def test_colaborador_ve_su_departamento_y_solo_lo_suyo(self):
        self.assertEqual([d['nombre'] for d in self.get(self.cm, '/api/desempeno/departamentos/').json()], ['Marketing'])
        self.assertEqual(self.get(self.cm, f'/api/desempeno/departamentos/{self.ti.pk}/').status_code, 404)
        d = self.get(self.ana, f'/api/desempeno/departamentos/{self.ti.pk}/').json()
        self.assertEqual(d['nivel'], 'miembro')
        beto = next(p for p in d['personas'] if p['nombre'] == 'Beto')
        self.assertFalse(beto['detalle'])
        self.assertNotIn('kpis', beto)
        self.assertNotIn('salario', beto)
        yo = next(p for p in d['personas'] if p['soy_yo'])
        self.assertEqual(len(yo['kpis']), 3)
        self.assertIsNone(yo['salario'])
        pol = next(p for p in d['politicas'] if p['titulo'] == 'Uso de equipos')
        self.assertTrue(pol['la_acepte'])
        self.assertNotIn('pendientes', pol)  # no ve quién falta

    def test_procedimientos_y_documentos(self):
        from apps.core.models import DocumentoArea
        c = APIClient()
        c.force_authenticate(self.ana)
        datos = {'tipo': 'PROCEDIMIENTO', 'titulo': 'Alta de un equipo nuevo', 'contenido': '1. Registrar\n2. Etiquetar'}
        self.assertEqual(c.post(f'/api/desempeno/departamentos/{self.ti.pk}/documentos/', datos, format='json').status_code, 403)
        c.force_authenticate(self.jefe)  # encargado del área
        r = c.post(f'/api/desempeno/departamentos/{self.ti.pk}/documentos/', datos, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        c.post(f'/api/desempeno/departamentos/{self.ti.pk}/documentos/', {**datos, 'titulo': 'Claves de servidores', 'solo_encargados': True}, format='json')
        self.assertEqual(DocumentoArea.objects.count(), 2)
        d = self.get(self.ana, f'/api/desempeno/departamentos/{self.ti.pk}/').json()
        self.assertEqual([x['titulo'] for x in d['documentos']], ['Alta de un equipo nuevo'])
        privado = DocumentoArea.objects.get(titulo='Claves de servidores')
        self.assertEqual(self.get(self.ana, f'/api/desempeno/documentos-area/{privado.pk}/').status_code, 404)
        self.assertEqual(self.get(self.cm, f'/api/desempeno/documentos-area/{r.json()["id"]}/').status_code, 404)
        c.force_authenticate(self.jefe)
        self.assertEqual(c.patch(f'/api/desempeno/departamentos/{self.ti.pk}/', {'objetivos': 'Cero caídas\nSoporte en 2 h'}, format='json').status_code, 200)
        self.assertEqual(self.get(self.ana, f'/api/desempeno/departamentos/{self.ti.pk}/').json()['departamento']['objetivos'], ['Cero caídas', 'Soporte en 2 h'])

    def test_trimestral(self):
        d = self.get(self.dir, f'/api/desempeno/departamentos/{self.ti.pk}/?vista=trimestral&anio={self.mes.year}&mes={self.mes.month}').json()
        self.assertEqual(d['vista'], 'trimestral')
        self.assertTrue(1 <= len(d['meses']) <= 3)
        self.assertIn('trimestre', d['resumen']['texto'])
