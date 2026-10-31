from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import Departamento
from apps.desempeno.models import Tarea
from apps.desempeno.puntaje import calcular_ranking, sin_evaluar
from apps.organizacion.models import PuestoDeTrabajo

from .models import Campana


class CallCenterTests(TestCase):
    def setUp(self):
        cc = Departamento.objects.create(nombre="Call Center")
        mkt = Departamento.objects.create(nombre="Marketing")
        self.p_gerente = PuestoDeTrabajo.objects.create(nombre="Gerente de Call Center", departamento=cc)
        self.p_agente = PuestoDeTrabajo.objects.create(nombre="Agente de Call Center Español", departamento=cc, supervisor=self.p_gerente)
        self.p_cm = PuestoDeTrabajo.objects.create(nombre="Community Manager", departamento=mkt)
        self.grupo = Group.objects.get_or_create(name='Agente Call Center')[0]
        self.gerente = self._u("gerente", self.p_gerente)
        self.ana = self._u("ana", self.p_agente, agente=True)
        self.luis = self._u("luis", self.p_agente, agente=True)
        self.cm = self._u("cm", self.p_cm)
        self.admin = self._u("jefa", None)
        self.admin.groups.add(Group.objects.get_or_create(name='Administrador')[0])
        self.c = APIClient()

    def _u(self, username, puesto, agente=False):
        u = User.objects.create_user(username, password="Clave-Segura-2026", first_name=username.title())
        u.perfil.puesto_trabajo = puesto
        u.perfil.save()
        if agente:
            u.groups.add(self.grupo)
        return u

    def campana(self, **kw):
        datos = {'nombre': 'Cobros Banco X', 'tipo': 'COBROS', 'fecha_inicio': timezone.localdate().isoformat(),
                 'meta_contactos_dia': 40, 'meta_conversion': 25, 'canales': ['Llamadas salientes'], 'agentes': [self.ana.id]}
        datos.update(kw)
        return self.c.post('/api/callcenter/campanas/', datos, format='json')

    def test_quien_crea_y_quien_ve_las_campanas(self):
        self.c.force_authenticate(self.ana)
        self.assertEqual(self.campana().status_code, 403)          # el agente no crea campañas
        self.c.force_authenticate(self.cm)
        self.assertEqual(self.campana().status_code, 403)          # otro departamento tampoco
        self.c.force_authenticate(self.gerente)
        r = self.campana()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.campana(nombre='Otra', agentes=[self.luis.id]).status_code, 201)
        # Solo se asignan personas con el acceso de agente
        r = self.campana(nombre='Mal', agentes=[self.cm.id])
        self.assertEqual(r.status_code, 400)
        self.assertIn('Agente Call Center', str(r.data))
        # El agente solo ve las suyas y no las puede cambiar
        self.c.force_authenticate(self.ana)
        vistas = self.c.get('/api/callcenter/campanas/').data
        self.assertEqual([c['nombre'] for c in vistas], ['Cobros Banco X'])
        self.assertEqual(self.c.patch(f"/api/callcenter/campanas/{vistas[0]['id']}/", {'meta_contactos_dia': 1}, format='json').status_code, 403)
        self.assertEqual(Campana.objects.count(), 2)

    def test_la_sesion_dice_si_es_agente(self):
        self.c.force_authenticate(self.ana)
        datos = self.c.get('/api/auth/session/').data['user']
        self.assertTrue(datos['es_agente'])
        self.assertFalse(datos['gestiona_call_center'])
        self.c.force_authenticate(self.gerente)
        datos = self.c.get('/api/auth/session/').data['user']
        self.assertFalse(datos['es_agente'])
        self.assertTrue(datos['gestiona_call_center'])

    def test_los_agentes_se_evaluan_aparte(self):
        periodo = (timezone.localdate().replace(day=1) - timedelta(days=1)).replace(day=1)
        dia = periodo + timedelta(days=5)
        for u in (self.ana, self.cm):
            Tarea.objects.create(titulo="T", colaborador=u, fecha_limite=dia, estado='COMPLETADA', fecha_completada=dia)
        nombres = lambda filas: [f['username'] for f in filas]  # noqa: E731
        self.assertEqual(nombres(calcular_ranking(periodo, grupo='empleados')), ['cm'])
        self.assertEqual(nombres(calcular_ranking(periodo, grupo='agentes')), ['ana'])
        self.assertEqual(sorted(nombres(calcular_ranking(periodo))), ['ana', 'cm'])
        # Luis (agente sin nada evaluado) no aparece entre los «sin evaluar» del equipo, sí entre los del call center
        sin_eq = [f['nombre'] for f in sin_evaluar(periodo, calcular_ranking(periodo, grupo='empleados'), grupo='empleados')]
        sin_cc = [f['nombre'] for f in sin_evaluar(periodo, calcular_ranking(periodo, grupo='agentes'), grupo='agentes')]
        self.assertNotIn('Luis', sin_eq)
        self.assertEqual(sin_cc, ['Luis'])
        self.c.force_authenticate(self.admin)
        mes = periodo.strftime('%Y-%m')
        self.assertEqual([f['nombre'] for f in self.c.get('/api/desempeno/ranking/', {'mes': mes, 'grupo': 'agentes'}).data['ranking']], ['Ana'])
        self.assertEqual([f['nombre'] for f in self.c.get('/api/desempeno/ranking/', {'mes': mes}).data['ranking']], ['Cm'])
        self.assertIn('call-center', self.c.get('/api/desempeno/ranking/exportar/', {'mes': mes, 'grupo': 'agentes'})['Content-Disposition'])

    def test_resumen_del_call_center(self):
        self.c.force_authenticate(self.cm)
        self.assertEqual(self.c.get('/api/callcenter/resumen/').status_code, 403)
        self.c.force_authenticate(self.ana)
        r = self.c.get('/api/callcenter/resumen/').data
        self.assertEqual([a['nombre'] for a in r['agentes']], ['Ana'])  # el agente solo se ve a sí mismo
        self.c.force_authenticate(self.gerente)
        self.assertEqual(len(self.c.get('/api/callcenter/resumen/').data['agentes']), 2)
