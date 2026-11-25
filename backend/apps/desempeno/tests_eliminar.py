"""Borrar tareas solo con el permiso «Eliminar tareas» (Dirección siempre). Sin él, quien gestiona la tarea puede cancelarla."""
from apps.core.models import ExcepcionPermiso
from .models import Tarea
from .tests_mejoras import Base


class EliminarTareasTests(Base):
    def borrar(self, t):
        return self.c.delete(f'/api/desempeno/tareas/{t.id}/').status_code

    def test_supervisor_sin_permiso_no_borra_pero_puede_cancelar(self):
        t = self.tarea(self.erlin)
        self.como(self.vladi)
        r = self.c.get(f'/api/desempeno/tareas/{t.id}/')
        self.assertTrue(r.data['puedo_gestionar'])
        self.assertFalse(r.data['puedo_eliminar'])
        self.assertEqual(self.borrar(t), 403)
        self.assertTrue(Tarea.objects.filter(pk=t.pk).exists())
        self.assertEqual(self.c.post(f'/api/desempeno/tareas/{t.id}/cancelar/', {'motivo': 'Ya no hace falta'}).status_code, 200)

    def test_con_permiso_borra_solo_a_su_equipo(self):
        ExcepcionPermiso.objects.create(usuario=self.vladi, permiso='tareas.eliminar', conceder=True)
        propia_del_equipo, ajena = self.tarea(self.erlin), self.tarea(self.dev)
        self.como(self.vladi)
        self.assertTrue(self.c.get(f'/api/desempeno/tareas/{propia_del_equipo.id}/').data['puedo_eliminar'])
        self.assertEqual(self.borrar(propia_del_equipo), 204)
        self.assertIn(self.borrar(ajena), (403, 404))
        self.assertTrue(Tarea.objects.filter(pk=ajena.pk).exists())

    def test_direccion_borra_y_nadie_borra_una_validada(self):
        t, validada = self.tarea(self.dev), self.tarea(self.erlin, estado='COMPLETADA', calificacion_calidad=4)
        self.como(self.osiris)
        self.assertEqual(self.borrar(t), 204)
        self.assertEqual(self.borrar(validada), 403)

    def test_el_colaborador_no_borra_la_suya(self):
        t = self.tarea(self.erlin)
        self.como(self.erlin)
        self.assertFalse(self.c.get(f'/api/desempeno/tareas/{t.id}/').data['puedo_eliminar'])
        self.assertEqual(self.borrar(t), 403)

    def test_el_permiso_aparece_en_el_catalogo(self):
        from apps.core.permisos import CODIGOS, DE_EQUIPO
        self.assertIn('tareas.eliminar', CODIGOS)
        self.assertIn('tareas.eliminar', DE_EQUIPO)
