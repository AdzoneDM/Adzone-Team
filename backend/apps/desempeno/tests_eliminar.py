"""Edición, eliminación (lógica) y reapertura de tareas en cualquier estado, con permisos individuales, historial y avisos."""
from django.contrib.auth.models import Group

from apps.core.models import ExcepcionPermiso, PermisosDePerfil
from .models import HistorialTarea, Notificacion, Tarea
from .tests_mejoras import Base


class EliminarTareasTests(Base):
    def eliminar(self, t, motivo='Se creó duplicada'):
        return self.c.post(f'/api/desempeno/tareas/{t.id}/eliminar/', {'motivo': motivo}, format='json')

    def test_sin_permiso_no_elimina_pero_puede_cancelar(self):
        t = self.tarea(self.erlin)
        ExcepcionPermiso.objects.create(usuario=self.vladi, permiso='tareas.eliminar', conceder=False)
        self.como(self.vladi)
        r = self.c.get(f'/api/desempeno/tareas/{t.id}/')
        self.assertTrue(r.data['puedo_gestionar'])
        self.assertFalse(r.data['puedo_eliminar'])
        self.assertEqual(self.eliminar(t).status_code, 403)
        self.assertTrue(Tarea.objects.filter(pk=t.pk).exists())
        self.assertEqual(self.c.post(f'/api/desempeno/tareas/{t.id}/cancelar/', {'motivo': 'Ya no hace falta'}).status_code, 200)

    def test_eliminacion_logica_con_motivo_en_cualquier_estado(self):
        validada = self.tarea(self.erlin, estado='COMPLETADA', calificacion_calidad=4, validada_por=self.vladi)
        self.como(self.vladi)
        self.assertEqual(self.eliminar(validada, motivo='no').status_code, 400)   # el motivo es obligatorio
        r = self.eliminar(validada)
        self.assertEqual(r.status_code, 200, r.data)
        # No aparece ni cuenta, pero se conserva con su historial, quién y por qué
        self.assertFalse(Tarea.objects.filter(pk=validada.pk).exists())
        self.assertFalse(self.erlin.tareas.filter(pk=validada.pk).exists())
        guardada = Tarea.todas.get(pk=validada.pk)
        self.assertEqual(guardada.eliminada_por, self.vladi)
        self.assertEqual(guardada.motivo_eliminacion, 'Se creó duplicada')
        h = HistorialTarea.objects.get(tarea=validada, accion='ELIMINADA')
        self.assertEqual((h.estado_antes, h.usuario), ('COMPLETADA', self.vladi))
        self.assertTrue(Notificacion.objects.filter(destinatario=self.erlin, tipo='ELIMINADA').exists())
        self.assertEqual(self.c.get(f'/api/desempeno/tareas/{validada.id}/').status_code, 404)
        self.assertNotIn(validada.id, [t['id'] for t in self.c.get('/api/desempeno/tareas/?ambito=equipo').data])
        # Auditoría: se lista con su historial y se puede recuperar tal como estaba
        lista = self.c.get('/api/desempeno/tareas/eliminadas/').data
        fila = next(x for x in lista if x['id'] == validada.id)
        self.assertEqual(fila['motivo_eliminacion'], 'Se creó duplicada')
        self.assertTrue(fila['puedo_restaurar'])
        self.assertIn('ELIMINADA', [x['accion'] for x in fila['historial']])
        self.assertEqual(self.c.post(f'/api/desempeno/tareas/{validada.id}/restaurar/').status_code, 200)
        self.assertEqual(Tarea.objects.get(pk=validada.pk).estado, 'COMPLETADA')

    def test_la_eliminada_no_cuenta_para_el_puntaje(self):
        from django.utils import timezone
        from .puntaje import calcular_ranking
        t = self.tarea(self.erlin, dias=0, estado='COMPLETADA', calificacion_calidad=5, validada_por=self.vladi)
        Tarea.objects.filter(pk=t.pk).update(fecha_completada=t.fecha_limite)
        periodo = timezone.localdate().replace(day=1)

        def tareas_de_erlin():
            fila = next((f for f in calcular_ranking(periodo) if f['colaborador_id'] == self.erlin.pk), None)
            return fila['tareas']['total'] if fila else 0
        self.assertEqual(tareas_de_erlin(), 1)
        self.como(self.vladi)
        self.eliminar(t)
        self.assertEqual(tareas_de_erlin(), 0)

    def test_solo_sobre_su_equipo_y_el_colaborador_no_elimina_la_suya(self):
        del_equipo, ajena = self.tarea(self.erlin), self.tarea(self.dev)
        self.como(self.vladi)
        self.assertEqual(self.eliminar(del_equipo).status_code, 200)
        self.assertIn(self.eliminar(ajena).status_code, (403, 404))
        suya = self.tarea(self.erlin)
        self.como(self.erlin)
        self.assertFalse(self.c.get(f'/api/desempeno/tareas/{suya.id}/').data['puedo_eliminar'])
        self.assertEqual(self.eliminar(suya).status_code, 403)
        self.assertEqual(self.c.get('/api/desempeno/tareas/eliminadas/').data, [])

    def test_los_permisos_aparecen_en_el_catalogo_y_en_los_perfiles(self):
        from apps.core.permisos import CODIGOS, DE_EQUIPO
        for p in ('tareas.editar', 'tareas.eliminar', 'tareas.reabrir'):
            self.assertIn(p, CODIGOS)
            self.assertIn(p, DE_EQUIPO)
        for perfil in ('Supervisor', 'Gerente de Departamento', 'Coordinación', 'Operaciones'):
            permisos = PermisosDePerfil.objects.get(grupo__name=perfil).permisos
            self.assertTrue({'tareas.editar', 'tareas.eliminar', 'tareas.reabrir'} <= set(permisos), perfil)
        self.assertTrue(Group.objects.filter(name='Operaciones').exists())


class EditarYReabrirTests(Base):
    def test_editar_una_validada_ajusta_la_calidad_y_deja_el_antes_y_despues(self):
        t = self.tarea(self.erlin, estado='COMPLETADA', calificacion_calidad=3, validada_por=self.vladi)
        self.como(self.vladi)
        r = self.c.patch(f'/api/desempeno/tareas/{t.id}/', {'titulo': 'Post corregido', 'calificacion_calidad': 5}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        t.refresh_from_db()
        self.assertEqual((t.titulo, t.calificacion_calidad, t.estado), ('Post corregido', 5, 'COMPLETADA'))
        h = HistorialTarea.objects.filter(tarea=t, accion='EDITADA').last()
        self.assertIn('Calidad: 3/5 → 5/5', h.comentario)
        self.assertIn('Título: Post → Post corregido', h.comentario)
        self.assertTrue(Notificacion.objects.filter(destinatario=self.erlin, tipo='MODIFICADA').exists())

    def test_sin_permiso_de_editar_no_edita(self):
        t = self.tarea(self.erlin)
        ExcepcionPermiso.objects.create(usuario=self.vladi, permiso='tareas.editar', conceder=False)
        self.como(self.vladi)
        self.assertFalse(self.c.get(f'/api/desempeno/tareas/{t.id}/').data['puedo_gestionar'])
        self.assertEqual(self.c.patch(f'/api/desempeno/tareas/{t.id}/', {'titulo': 'X'}, format='json').status_code, 403)

    def test_reabrir_una_validada_para_corregir_con_fecha_e_instrucciones_nuevas(self):
        t = self.tarea(self.erlin, estado='COMPLETADA', calificacion_calidad=4, validada_por=self.vladi, descripcion='Viejas')
        self.como(self.vladi)
        nueva = (t.fecha_limite.replace(day=1)).isoformat()
        r = self.c.post(f'/api/desempeno/tareas/{t.id}/reabrir/', {'motivo': 'El cliente pidió otro logo', 'a': 'CORREGIR',
                                                                   'fecha_limite': nueva, 'descripcion': 'Nuevas'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        t.refresh_from_db()
        self.assertEqual((t.estado, t.calificacion_calidad, t.validada_por, t.descripcion), ('EN_PROGRESO', None, None, 'Nuevas'))
        h = HistorialTarea.objects.get(tarea=t, accion='REABIERTA')
        self.assertEqual((h.estado_antes, h.estado_despues), ('COMPLETADA', 'EN_PROGRESO'))
        self.assertIn('El cliente pidió otro logo', h.comentario)
        aviso = Notificacion.objects.get(destinatario=self.erlin, tipo='REABIERTA')
        self.assertIn('corrijas', aviso.mensaje)

    def test_reabrir_por_defecto_una_validada_vuelve_a_revision(self):
        t = self.tarea(self.erlin, estado='COMPLETADA', calificacion_calidad=4, validada_por=self.vladi)
        self.como(self.vladi)
        self.assertEqual(self.c.post(f'/api/desempeno/tareas/{t.id}/reabrir/', {'motivo': 'Validé la equivocada'}, format='json').status_code, 200)
        t.refresh_from_db()
        self.assertEqual(t.estado, 'EN_REVISION')

    def test_reabrir_una_cancelada_o_una_entregada(self):
        cancelada = self.tarea(self.erlin, estado='CANCELADA')
        entregada = self.tarea(self.erlin, estado='EN_REVISION')
        self.como(self.vladi)
        self.assertEqual(self.c.post(f'/api/desempeno/tareas/{cancelada.id}/reabrir/', {'motivo': 'Sí hacía falta'}, format='json').status_code, 200)
        self.assertEqual(Tarea.objects.get(pk=cancelada.pk).estado, 'PENDIENTE')
        r = self.c.post(f'/api/desempeno/tareas/{cancelada.id}/reabrir/', {'motivo': 'Revisar otra vez', 'a': 'REVISION'}, format='json')
        self.assertEqual(r.status_code, 400)   # no tiene entrega que revisar
        self.assertEqual(self.c.post(f'/api/desempeno/tareas/{entregada.id}/reabrir/', {'motivo': 'Falta el texto'}, format='json').status_code, 200)
        entregada.refresh_from_db()
        self.assertEqual((entregada.estado, entregada.rondas_revision), ('EN_PROGRESO', 0))   # reabrir no cuenta como devolución

    def test_nadie_reabre_la_suya_y_sin_permiso_tampoco(self):
        t = self.tarea(self.erlin, estado='COMPLETADA', calificacion_calidad=4, validada_por=self.vladi)
        self.como(self.erlin)
        self.assertFalse(self.c.get(f'/api/desempeno/tareas/{t.id}/').data['puedo_reabrir'])
        self.assertEqual(self.c.post(f'/api/desempeno/tareas/{t.id}/reabrir/', {'motivo': 'Quiero mejorarla'}, format='json').status_code, 403)
        ExcepcionPermiso.objects.create(usuario=self.vladi, permiso='tareas.reabrir', conceder=False)
        self.como(self.vladi)
        self.assertEqual(self.c.post(f'/api/desempeno/tareas/{t.id}/reabrir/', {'motivo': 'Validé la equivocada'}, format='json').status_code, 403)
