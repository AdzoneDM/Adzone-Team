"""Asistente con IA: la IA solo ve datos por las herramientas, y estas respetan los permisos de quien pregunta."""
import json
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import Departamento
from apps.desempeno.models import Notificacion, Tarea
from apps.organizacion.models import PuestoDeTrabajo

from . import alertas, herramientas
from .models import ConversacionIA, InformeIA, MensajeIA
from .servicio import para_reenviar

CLAVE = 'Clave-Segura-2026'


def bloque(tipo, **kw):
    b = mock.MagicMock(type=tipo, **kw)
    b.to_dict.return_value = {'type': tipo, **kw}
    return b


def respuesta(stop, *bloques):
    return mock.MagicMock(stop_reason=stop, content=list(bloques),
                          usage=mock.MagicMock(input_tokens=100, output_tokens=20, cache_read_input_tokens=50))


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.mkt = Departamento.objects.create(nombre='Marketing')
        self.tec = Departamento.objects.create(nombre='Tecnología')
        p_jefe = PuestoDeTrabajo.objects.create(nombre='Gerente Mkt', departamento=self.mkt)
        p_cm = PuestoDeTrabajo.objects.create(nombre='CM', departamento=self.mkt, supervisor=p_jefe)
        p_dev = PuestoDeTrabajo.objects.create(nombre='Dev', departamento=self.tec)
        self.jefe = self._u('jefe', p_jefe, ['Supervisor'])
        self.ana = self._u('ana', p_cm)
        self.luis = self._u('luis', p_cm)
        self.dev = self._u('dev', p_dev)
        self.dir = self._u('dir', None, ['Administrador'])
        ayer = timezone.localdate() - timedelta(days=1)
        for u, t in ((self.ana, 'Post banco'), (self.luis, 'Video cliente'), (self.dev, 'Servidor secreto')):
            Tarea.objects.create(titulo=t, colaborador=u, fecha_limite=ayer, estado='PENDIENTE')

    def _u(self, nombre, puesto, grupos=('Colaborador',)):
        u = User.objects.create_user(nombre, password=CLAVE, first_name=nombre.capitalize())
        if puesto:
            u.perfil.puesto_trabajo = puesto
            u.perfil.save()
        u.groups.set([Group.objects.get(name=g) for g in grupos])
        return u

    def como(self, u):
        c = APIClient()
        c.force_authenticate(User.objects.get(pk=u.pk))
        return c


class AlcanceTests(Base):
    def test_cada_quien_ve_solo_lo_suyo_su_equipo_o_todo(self):
        titulos = lambda u: {t['titulo'] for t in herramientas.tareas_lista(herramientas.Alcance(u), 'vencidas')['tareas']}  # noqa: E731
        self.assertEqual(titulos(self.ana), {'Post banco'})
        self.assertEqual(titulos(self.jefe), {'Post banco', 'Video cliente'})
        self.assertEqual(titulos(self.dir), {'Post banco', 'Video cliente', 'Servidor secreto'})

    def test_finanzas_solo_con_permiso(self):
        a = herramientas.Alcance(self.jefe)
        self.assertNotIn('finanzas', [t['name'] for t in herramientas.disponibles(a)])
        with self.assertRaises(PermissionError):
            herramientas.ejecutar(a, 'finanzas', {})
        self.assertIn('finanzas', [t['name'] for t in herramientas.disponibles(herramientas.Alcance(self.dir))])


class PreguntarTests(Base):
    def test_sin_clave_avisa_que_no_esta_configurado(self):
        r = self.como(self.ana).post('/api/asistente/preguntar/', {'texto': '¿Cómo voy?'}, format='json')
        self.assertEqual(r.status_code, 503)

    @override_settings(ANTHROPIC_API_KEY='sk-prueba')
    def test_consulta_con_herramientas_y_responde_sin_ver_lo_ajeno(self):
        llamadas = []

        def falso(**kw):
            llamadas.append(json.loads(json.dumps(kw, default=str)))
            if len(llamadas) == 1:
                return respuesta('tool_use', bloque('tool_use', id='t1', name='tareas_lista', input={'filtro': 'vencidas'}))
            return respuesta('end_turn', bloque('text', text='Tienes 1 tarea vencida: Post banco.'))
        with mock.patch('apps.core.ia.cliente') as cli:
            cli.return_value.beta.messages.create.side_effect = falso
            r = self.como(self.ana).post('/api/asistente/preguntar/', {'texto': '¿Qué tengo vencido?'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['respuesta']['texto'], 'Tienes 1 tarea vencida: Post banco.')
        self.assertEqual(r.json()['respuesta']['herramientas'], ['tareas_lista'])
        # Lo que se mandó a la IA: el resultado de la herramienta tiene su tarea y NO las de otros
        resultado = llamadas[1]['messages'][-1]['content'][0]
        self.assertEqual(resultado['type'], 'tool_result')
        self.assertIn('Post banco', resultado['content'])
        self.assertNotIn('Video cliente', resultado['content'])
        self.assertNotIn('Servidor secreto', json.dumps(llamadas))
        # Parámetros de la API: modelo configurado, esfuerzo, caché y respaldo ante rechazos
        self.assertEqual(llamadas[0]['output_config'], {'effort': 'medium'})
        self.assertEqual(llamadas[0]['cache_control'], {'type': 'ephemeral'})
        self.assertEqual(llamadas[0]['fallbacks'], 'default')
        self.assertNotIn('finanzas', [t['name'] for t in llamadas[0]['tools']])
        # Historial: la pregunta y la respuesta visibles; las vueltas internas, ocultas
        conv = ConversacionIA.objects.get()
        self.assertEqual([m.rol for m in conv.mensajes.filter(visible=True)], ['user', 'assistant'])
        self.assertEqual(conv.mensajes.count(), 4)

    @override_settings(ANTHROPIC_API_KEY='sk-prueba')
    def test_herramienta_sin_permiso_devuelve_error_a_la_ia(self):
        llamadas = []

        def falso(**kw):
            llamadas.append(kw)
            if len(llamadas) == 1:
                return respuesta('tool_use', bloque('tool_use', id='t1', name='finanzas', input={}))
            return respuesta('end_turn', bloque('text', text='No tienes acceso a finanzas.'))
        with mock.patch('apps.core.ia.cliente') as cli:
            cli.return_value.beta.messages.create.side_effect = falso
            self.como(self.ana).post('/api/asistente/preguntar/', {'texto': '¿Cuánto facturamos?'}, format='json')
        resultado = llamadas[1]['messages'][-1]['content'][0]
        self.assertTrue(resultado['is_error'])

    @override_settings(ANTHROPIC_API_KEY='sk-prueba')
    def test_rechazo_y_conversaciones_privadas(self):
        with mock.patch('apps.core.ia.cliente') as cli:
            cli.return_value.beta.messages.create.return_value = respuesta('refusal', bloque('text', text=''))
            r = self.como(self.ana).post('/api/asistente/preguntar/', {'texto': 'algo raro'}, format='json')
        self.assertIn('No puedo ayudar', r.json()['respuesta']['texto'])
        cid = r.json()['conversacion']
        self.assertEqual(self.como(self.luis).get(f'/api/asistente/conversaciones/{cid}/').status_code, 404)
        self.assertEqual(self.como(self.ana).get(f'/api/asistente/conversaciones/{cid}/').status_code, 200)

    @override_settings(ANTHROPIC_API_KEY='sk-prueba', IA_LIMITE_DIARIO=1)
    def test_limite_diario(self):
        with mock.patch('apps.core.ia.cliente') as cli:
            cli.return_value.beta.messages.create.return_value = respuesta('end_turn', bloque('text', text='Hola'))
            self.assertEqual(self.como(self.ana).post('/api/asistente/preguntar/', {'texto': 'a'}, format='json').status_code, 200)
            r = self.como(self.ana).post('/api/asistente/preguntar/', {'texto': 'b'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('límite', r.json()['detail'])

    def test_reenvio_tras_cambio_de_modelo(self):
        contenido = [{'type': 'thinking', 'thinking': ''}, {'type': 'tool_use', 'id': 'x'}, {'type': 'fallback'},
                     {'type': 'thinking', 'thinking': ''}, {'type': 'text', 'text': 'ok'}]
        self.assertEqual([b['type'] for b in para_reenviar(contenido)], ['fallback', 'thinking', 'text'])
        self.assertEqual(para_reenviar([{'type': 'text'}]), [{'type': 'text'}])


class AnalisisDiarioTests(Base):
    def test_alertas_con_numeros_sin_ia_y_aviso(self):
        self.assertIn(self.jefe, alertas.destinatarios())
        self.assertNotIn(self.ana, alertas.destinatarios())
        informe = alertas.generar_informe(self.jefe)
        self.assertFalse(informe.con_ia)
        tareas = next(a for a in informe.alertas if a['tema'] == 'Tareas')
        self.assertIn('2 tarea(s) vencida(s)', tareas['titulo'])
        self.assertNotIn('Servidor secreto', json.dumps(informe.alertas))   # otra área: no
        self.assertTrue(Notificacion.objects.filter(destinatario=self.jefe, tipo='ANALISIS').exists())
        d = self.como(self.jefe).get('/api/asistente/informe/').json()['informe']
        self.assertEqual(len(d['alertas']), len(informe.alertas))
        self.assertEqual(self.como(self.ana).post('/api/asistente/informe/').status_code, 403)

    @override_settings(ANTHROPIC_API_KEY='sk-prueba')
    def test_lectura_con_ia(self):
        with mock.patch('apps.core.ia.cliente') as cli:
            cli.return_value.beta.messages.create.return_value = respuesta('end_turn', bloque('text', text='- Prioriza las 2 tareas vencidas.'))
            informe = alertas.generar_informe(self.jefe)
        self.assertTrue(informe.con_ia)
        self.assertEqual(InformeIA.objects.count(), 1)
        self.assertFalse(MensajeIA.objects.exists())
