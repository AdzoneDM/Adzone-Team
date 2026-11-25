"""Refresco silencioso: el «pulso» de las notificaciones cambia cuando alguien entrega, valida, devuelve, reabre o cancela una tarea."""
from .models import Tarea
from .tests_mejoras import Base

N = '/api/desempeno/notificaciones/'
T = '/api/desempeno/tareas/'


class PulsoTests(Base):
    def pulso(self, quien):
        self.como(quien)
        return self.c.get(N).json()['pulso']

    def entregada(self):
        t = self.tarea(self.erlin, asignada_por=self.vladi)
        Tarea.objects.filter(pk=t.pk).update(estado='EN_REVISION')
        return t

    def test_validar_cambia_el_pulso_para_todos(self):
        t = self.entregada()
        antes = {u.username: self.pulso(u) for u in (self.erlin, self.vladi, self.osiris, self.dev)}
        self.como(self.vladi)
        self.assertEqual(self.c.post(f'{T}{t.id}/validar/', {'calificacion_calidad': 4}, format='json').status_code, 200)
        for u in (self.erlin, self.vladi, self.osiris, self.dev):
            self.assertGreater(self.pulso(u), antes[u.username], u.username)

    def test_devolver_tambien_lo_cambia(self):
        t = self.entregada()
        antes = self.pulso(self.erlin)
        self.como(self.vladi)
        self.assertEqual(self.c.post(f'{T}{t.id}/rechazar/', {'comentario_revision': 'Falta el logo en la esquina'}, format='json').status_code, 200)
        self.assertGreater(self.pulso(self.erlin), antes)

    def test_un_comentario_no_cambia_el_pulso(self):
        t = self.entregada()
        antes = self.pulso(self.vladi)
        self.como(self.erlin)
        self.assertEqual(self.c.post(f'{T}{t.id}/comentarios/', {'texto': 'Hola'}, format='json').status_code, 201)
        self.assertEqual(self.pulso(self.vladi), antes)

    def test_sin_movimientos_el_pulso_es_cero_y_no_revela_nada_mas(self):
        d = self.c.get(N).json() if self.como(self.erlin) is None else None
        self.assertEqual(d['pulso'], 0)
        self.assertIsInstance(d['pulso'], int)

    def test_rechazar_sin_explicacion_o_validar_sin_calificar_no_mueve_nada(self):
        t = self.entregada()
        antes = self.pulso(self.vladi)
        self.como(self.vladi)
        self.assertEqual(self.c.post(f'{T}{t.id}/rechazar/', {'comentario_revision': 'no'}, format='json').status_code, 400)
        self.assertEqual(self.c.post(f'{T}{t.id}/validar/', {}, format='json').status_code, 400)
        self.assertEqual(self.c.post(f'{T}{t.id}/validar/', {'calificacion_calidad': 0}, format='json').status_code, 400)
        self.assertEqual(self.c.post(f'{T}{t.id}/validar/', {'calificacion_calidad': 6}, format='json').status_code, 400)
        self.assertEqual(self.pulso(self.vladi), antes)
        t.refresh_from_db()
        self.assertEqual(t.estado, 'EN_REVISION')

    def test_nadie_valida_su_propio_trabajo(self):
        t = self.entregada()
        self.como(self.erlin)
        self.assertEqual(self.c.post(f'{T}{t.id}/validar/', {'calificacion_calidad': 5}, format='json').status_code, 403)
        self.assertEqual(self.c.post(f'{T}{t.id}/rechazar/', {'comentario_revision': 'Me lo devuelvo yo'}, format='json').status_code, 403)

    def test_una_tarea_devuelta_no_cuenta_hasta_ser_validada(self):
        from .puntaje import _tareas_validadas
        t = self.entregada()
        self.como(self.vladi)
        self.c.post(f'{T}{t.id}/rechazar/', {'comentario_revision': 'Cambia el color del fondo'}, format='json')
        t.refresh_from_db()
        self.assertEqual((t.estado, t.rondas_revision), ('EN_PROGRESO', 1))
        self.assertIsNone(t.calificacion_calidad)
