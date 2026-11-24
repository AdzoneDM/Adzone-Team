"""Requerimiento #8, etapa 2: comentarios por tarea (privados, con respuestas, menciones, avisos sin saturar e historial)."""
from django.contrib.auth.models import Group

from .models import ComentarioTarea, HistorialTarea, Notificacion, Tarea
from .tests_mejoras import Base

T = '/api/desempeno/tareas/'


class ComentariosDeTareaTests(Base):
    def setUp(self):
        super().setUp()
        self.vladi.groups.add(Group.objects.get(name='Supervisor'))
        self.t = self.tarea(self.erlin, asignada_por=self.vladi)   # la hace Erlin, la asignó Vladi (su supervisora)
        self.t.companeros.add(self.ashley)

    def url(self, t=None):
        return f'{T}{(t or self.t).id}/comentarios/'

    def comentar(self, quien, texto='Hola', **extra):
        self.como(quien)
        return self.c.post(self.url(), {'texto': texto, **extra}, format='json')

    def avisos(self, quien):
        return Notificacion.objects.filter(destinatario=quien, tipo='COMENTARIO', tarea=self.t)

    # ---------------------------------------------------------------- quién ve y quién escribe
    def test_las_personas_de_la_tarea_su_supervisora_y_direccion_ven_y_escriben(self):
        for quien in (self.erlin, self.ashley, self.vladi, self.osiris):
            r = self.comentar(quien, f'Comentario de {quien.username}')
            self.assertEqual(r.status_code, 201, (quien.username, r.content))
        self.como(self.erlin)
        self.assertEqual(len(self.c.get(self.url()).json()), 4)

    def test_quien_no_ve_la_tarea_no_puede_leer_ni_escribir(self):
        self.comentar(self.erlin, 'Algo privado del cliente')
        self.como(self.dev)                                                                           # otra área, sin relación con la tarea
        self.assertEqual(self.c.get(self.url()).status_code, 404)
        self.assertEqual(self.c.post(self.url(), {'texto': 'intruso'}, format='json').status_code, 404)
        self.assertEqual(ComentarioTarea.objects.count(), 1)
        self.assertFalse(Notificacion.objects.filter(destinatario=self.dev).exists())

    def test_un_colaborador_de_otra_tarea_tampoco_la_ve(self):
        otro = self._u('otro', self.p_cm, 'Otro', 'Cm')                                              # mismo puesto y área, pero no participa ni supervisa
        self.como(otro)
        self.assertEqual(self.c.get(self.url()).status_code, 404)

    def test_exige_sesion(self):
        self.c.force_authenticate(None)
        self.assertIn(self.c.get(self.url()).status_code, (401, 403))

    # ---------------------------------------------------------------- contenido
    def test_validaciones_del_texto(self):
        self.assertEqual(self.comentar(self.erlin, '   ').status_code, 400)
        self.assertEqual(self.comentar(self.erlin, 'x' * 2001).status_code, 400)
        self.assertEqual(self.comentar(self.erlin, 'x' * 2000).status_code, 201)

    def test_se_puede_responder_a_un_comentario_de_la_misma_tarea(self):
        primero = self.comentar(self.vladi, 'Falta el logo del cliente').json()
        r = self.comentar(self.erlin, 'Listo, ya lo puse', responde_a=primero['id'])
        self.assertEqual(r.status_code, 201)
        self.assertEqual((r.json()['cita']['id'], r.json()['cita']['autor_nombre']), (primero['id'], 'Vladimir Gómez'))
        self.assertIn('logo', r.json()['cita']['texto'])

    def test_no_se_responde_a_un_comentario_de_otra_tarea(self):
        otra = self.tarea(self.erlin, asignada_por=self.vladi)
        ajeno = ComentarioTarea.objects.create(tarea=otra, autor=self.erlin, texto='de otra tarea')
        self.assertEqual(self.comentar(self.erlin, 'hola', responde_a=ajeno.id).status_code, 400)

    def test_los_comentarios_no_se_editan_ni_se_borran(self):
        c = self.comentar(self.erlin, 'Definitivo').json()
        self.como(self.erlin)
        for metodo in ('put', 'patch', 'delete'):
            self.assertEqual(getattr(self.c, metodo)(self.url(), {'texto': 'otro'}, format='json').status_code, 405, metodo)
            self.assertEqual(getattr(self.c, metodo)(f"{self.url()}{c['id']}/", format='json').status_code, 404, metodo)
        self.assertEqual(ComentarioTarea.objects.get(pk=c['id']).texto, 'Definitivo')

    def test_se_comenta_tambien_una_tarea_ya_validada(self):
        Tarea.objects.filter(pk=self.t.pk).update(estado='COMPLETADA')
        self.assertEqual(self.comentar(self.vladi, 'Buen trabajo').status_code, 201)

    # ---------------------------------------------------------------- historial
    def test_queda_en_el_historial_con_quien_y_cuando(self):
        self.comentar(self.erlin, 'Avance del 50 %')
        h = HistorialTarea.objects.get(tarea=self.t, accion='COMENTADA')
        self.assertEqual((h.usuario, h.comentario), (self.erlin, 'Avance del 50 %'))
        self.como(self.vladi)
        textos = [x['accion'] for x in self.c.get(f'{T}{self.t.id}/historial/').json()]
        self.assertIn('COMENTADA', textos)

    # ---------------------------------------------------------------- avisos
    def test_avisa_a_los_demas_involucrados_y_no_a_quien_escribe(self):
        self.comentar(self.erlin, '¿Me confirmas la fecha?')
        self.assertTrue(self.avisos(self.vladi).exists() and self.avisos(self.ashley).exists())
        self.assertFalse(self.avisos(self.erlin).exists())
        self.assertFalse(Notificacion.objects.filter(destinatario=self.dev).exists())
        n = self.avisos(self.vladi).get()
        self.assertIn('Comentario nuevo', n.titulo)
        self.assertIn('Erlin Pérez: ¿Me confirmas', n.mensaje)
        self.assertEqual(n.enlace, f'/equipo?tarea={self.t.id}')                                      # su supervisora lo abre en Mi equipo
        self.assertEqual(self.avisos(self.ashley).get().enlace, f'/mis-tareas?tarea={self.t.id}')     # quien participa, en Mis tareas

    def test_una_conversacion_larga_deja_un_solo_aviso_sin_leer_por_persona(self):
        for i in range(5):
            self.comentar(self.erlin, f'mensaje {i}')
        self.assertEqual(self.avisos(self.vladi).count(), 1)
        self.assertIn('mensaje 4', self.avisos(self.vladi).get().mensaje)                              # el más reciente
        self.avisos(self.vladi).update(leida=True)
        self.comentar(self.erlin, 'otro más')
        self.assertEqual(self.avisos(self.vladi).count(), 2)                                           # ya leído: el nuevo es otro aviso

    def test_cuando_esta_por_validar_les_llega_a_quienes_la_validan(self):
        Tarea.objects.filter(pk=self.t.pk).update(estado='EN_REVISION')
        self.comentar(self.ashley, 'Ya entregué')
        self.assertTrue(self.avisos(self.vladi).exists())

    # ---------------------------------------------------------------- menciones
    def test_mencionar_a_quien_ve_la_tarea_le_avisa_y_queda_marcado(self):
        r = self.comentar(self.vladi, 'Revisen esto @osiris por favor')
        self.assertEqual([m['username'] for m in r.json()['menciones']], ['osiris'])
        n = self.avisos(self.osiris).get()
        self.assertIn('te mencionó', n.titulo)

    def test_mencionar_a_alguien_que_no_ve_la_tarea_no_le_avisa_ni_se_revela(self):
        r = self.comentar(self.vladi, 'cc @dev')
        self.assertEqual(r.json()['menciones'], [])
        self.assertFalse(Notificacion.objects.filter(destinatario=self.dev).exists())
