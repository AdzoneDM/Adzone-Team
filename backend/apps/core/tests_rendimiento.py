"""Las pantallas grandes no deben hacer una consulta por persona: con más gente tardan más, pero no en proporción."""
from django.contrib.auth.models import Group, User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.asistencia.models import AsignacionHorario, Horario
from apps.core.models import Departamento
from apps.kpis.models import KPIAsignado, PlantillaKPI
from apps.organizacion.models import PuestoDeTrabajo

ENDPOINTS = ['/api/organizacion/usuarios/', '/api/organizacion/puestos-trabajo/', '/api/kpis/kpis-asignados/', '/api/accesos/personas/', '/api/asistencia/hoy/']
TOLERANCIA = 4  # consultas de más al triplicar la gente (por ejemplo, otra página de resultados)


class RendimientoTests(TestCase):
    def setUp(self):
        self.depto = Departamento.objects.create(nombre='Marketing')
        self.jefe_p = PuestoDeTrabajo.objects.create(nombre='Gerente', departamento=self.depto)
        self.puestos = [PuestoDeTrabajo.objects.create(nombre=f'Puesto {i}', departamento=self.depto, supervisor=self.jefe_p) for i in range(4)]
        for p in self.puestos:
            for k in range(3):
                KPIAsignado.objects.create(puesto_trabajo=p, plantilla_kpi=PlantillaKPI.objects.create(nombre=f'KPI {p.nombre} {k}'), ponderacion=30, es_entrada_manual=True)
        self.admin = User.objects.create_user('dir', password='x', first_name='Dirección')
        self.admin.groups.add(Group.objects.get_or_create(name='Administrador')[0])
        self.horario = Horario.objects.get(por_defecto=True)
        self.n = 0

    def agregar_personas(self, cuantas):
        for _ in range(cuantas):
            self.n += 1
            u = User.objects.create_user(f'p{self.n}', password='x', first_name=f'Persona {self.n}', last_name='Prueba')
            u.perfil.puesto_trabajo = self.puestos[self.n % 4]
            u.perfil.save()
            u.perfil.puestos_adicionales.add(self.puestos[(self.n + 1) % 4])
            if self.n % 2:
                AsignacionHorario.objects.create(usuario=u, horario=self.horario)

    def consultas(self, ruta):
        c = APIClient()
        c.force_authenticate(User.objects.get(pk=self.admin.pk))
        c.get(ruta)  # calienta cachés (tipos de contenido, etc.)
        with CaptureQueriesContext(connection) as q:
            r = c.get(ruta)
        self.assertEqual(r.status_code, 200, ruta)
        return len(q)

    def test_las_consultas_no_crecen_con_la_cantidad_de_personas(self):
        self.agregar_personas(4)
        pocas = {r: self.consultas(r) for r in ENDPOINTS}
        self.agregar_personas(8)
        muchas = {r: self.consultas(r) for r in ENDPOINTS}
        for ruta in ENDPOINTS:
            self.assertLessEqual(muchas[ruta] - pocas[ruta], TOLERANCIA, f'{ruta}: {pocas[ruta]} consultas con 4 personas y {muchas[ruta]} con 12')
