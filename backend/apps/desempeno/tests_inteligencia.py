"""Resumen semanal, sugerencia de asignación y borrador de evaluación (con y sin la API de Claude)."""
import json
from datetime import date, timedelta
from unittest import mock

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import Departamento
from apps.organizacion.models import PuestoDeTrabajo
from .inteligencia import datos_semana, generar_resumen, sugerir_asignacion
from .models import ResumenSemanal, Tarea


class Base(TestCase):
    def setUp(self):
        d = Departamento.objects.create(nombre='Diseño')
        jefe_p = PuestoDeTrabajo.objects.create(nombre='Gerente', departamento=d)
        p = PuestoDeTrabajo.objects.create(nombre='Diseñador', departamento=d, supervisor=jefe_p)
        self.jefe = self._u('jefe', jefe_p)
        self.ana, self.beto = self._u('ana', p), self._u('beto', p)
        self.dir = self._u('dir', None)
        self.dir.groups.set([Group.objects.get(name='Administrador')])
        hoy = timezone.localdate()
        for i in range(4):  # Ana ya hizo brochures, a tiempo y bien
            Tarea.objects.create(titulo=f'Brochure cliente {i}', colaborador=self.ana, estado='COMPLETADA', fecha_limite=hoy - timedelta(days=10 + i),
                                 fecha_completada=hoy - timedelta(days=11 + i), calificacion_calidad=5)
        for i in range(5):  # Beto está cargado y atrasado
            Tarea.objects.create(titulo=f'Post redes {i}', colaborador=self.beto, estado='PENDIENTE', fecha_limite=hoy - timedelta(days=1))

    def _u(self, n, puesto):
        u = User.objects.create_user(n, password='x', first_name=n.title())
        if puesto:
            u.perfil.puesto_trabajo = puesto
            u.perfil.save()
        return User.objects.get(pk=u.pk)


class SugerenciaTests(Base):
    def test_recomienda_a_quien_tiene_menos_carga_y_experiencia(self):
        s = sugerir_asignacion(self.jefe, 'Brochure para Plaza Bonao')
        self.assertEqual([x['nombre'] for x in s], ['Ana', 'Beto'])
        self.assertIn('parecida', s[0]['razon'])
        self.assertEqual(s[1]['vencidas'], 5)
        self.assertEqual(sugerir_asignacion(self.ana, 'x'), [])  # sin equipo, nada
        c = APIClient()
        c.force_authenticate(self.ana)
        self.assertEqual(c.post('/api/desempeno/sugerir-asignacion/', {'titulo': 'x'}, format='json').status_code, 403)


class ResumenTests(Base):
    def test_sin_clave_arma_el_texto_con_los_numeros(self):
        r = generar_resumen()
        self.assertFalse(r.con_ia)
        self.assertIn('Más tareas vencidas: Beto (5)', r.texto)
        self.assertEqual(generar_resumen().pk, r.pk)  # una vez por semana

    @override_settings(ANTHROPIC_API_KEY='sk-prueba')
    def test_con_clave_redacta_la_ia_y_no_le_manda_salarios(self):
        self.ana.perfil.salario_mensual = 55555
        self.ana.perfil.save()
        enviado = {}

        def falso(req, timeout):
            enviado['cuerpo'] = json.loads(req.data)
            enviado['clave'] = req.headers.get('X-api-key')
            m = mock.MagicMock()
            m.__enter__.return_value.read.return_value = json.dumps({'content': [{'type': 'text', 'text': 'Semana tranquila.'}]}).encode()
            return m
        with mock.patch('urllib.request.urlopen', side_effect=falso):
            r = generar_resumen(forzar=True)
        self.assertTrue(r.con_ia)
        self.assertEqual(r.texto, 'Semana tranquila.')
        self.assertEqual(enviado['clave'], 'sk-prueba')
        self.assertNotIn('55555', json.dumps(enviado['cuerpo']))

    @override_settings(ANTHROPIC_API_KEY='sk-prueba')
    def test_si_la_api_falla_usa_el_texto_automatico(self):
        import urllib.error
        with mock.patch('urllib.request.urlopen', side_effect=urllib.error.URLError('caída')):
            r = generar_resumen(forzar=True)
        self.assertFalse(r.con_ia)
        self.assertTrue(r.texto)

    def test_solo_direccion(self):
        c = APIClient()
        c.force_authenticate(self.jefe)
        self.assertEqual(c.get('/api/desempeno/resumen-semanal/').status_code, 403)
        c.force_authenticate(self.dir)
        d = c.get('/api/desempeno/resumen-semanal/').json()
        self.assertIn('texto', d['actual'])
        self.assertFalse(d['ia_configurada'])


class BorradorTests(Base):
    def test_borrador_solo_para_quien_evalua(self):
        from apps.talento.models import CicloEvaluacion, Evaluacion
        ciclo = CicloEvaluacion.objects.create(nombre='2026-S2', desde=date.today().replace(day=1), hasta=date.today(), cierre=date.today() + timedelta(days=14))
        e = Evaluacion.objects.create(ciclo=ciclo, evaluado=self.ana, evaluador=self.jefe, tipo='SUPERVISOR')
        c = APIClient()
        c.force_authenticate(self.beto)
        self.assertEqual(c.post(f'/api/talento/evaluaciones/{e.pk}/borrador/').status_code, 403)
        c.force_authenticate(self.jefe)
        r = c.post(f'/api/talento/evaluaciones/{e.pk}/borrador/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['fortalezas'])
        self.assertFalse(r.json()['con_ia'])
