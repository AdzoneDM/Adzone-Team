"""Requerimiento #8, etapa 3: trazabilidad detallada (antes → después), motivo obligatorio y prioridad Urgente."""
from datetime import timedelta

from django.utils import timezone

from .models import HistorialTarea, Notificacion, Tarea
from .puntaje import PESO_PRIORIDAD
from .tests_mejoras import Base

T = '/api/desempeno/tareas/'


class TrazabilidadTests(Base):
    def setUp(self):
        super().setUp()
        self.t = self.tarea(self.erlin, asignada_por=self.vladi)
        self.hoy = timezone.localdate()

    def editar(self, quien, **datos):
        self.como(quien)
        return self.c.patch(f'{T}{self.t.id}/', datos, format='json')

    def ultimo(self):
        return HistorialTarea.objects.filter(tarea=self.t, accion='EDITADA').order_by('-id').first()

    # ---------------------------------------------------------------- motivo obligatorio
    def test_cambiar_fecha_prioridad_o_responsable_exige_motivo(self):
        nueva = (self.hoy + timedelta(days=8)).isoformat()
        for datos in ({'fecha_limite': nueva}, {'prioridad': 'ALTA'}, {'colaborador': self.ashley.id}, {'fecha_inicio': self.hoy.isoformat()}):
            r = self.editar(self.vladi, **datos)
            self.assertEqual(r.status_code, 400, (datos, r.content))
            self.assertIn('motivo', r.json())
        for vacio in ('', '   ', 'ok'):
            self.assertEqual(self.editar(self.vladi, prioridad='ALTA', motivo=vacio).status_code, 400, repr(vacio))
        self.t.refresh_from_db()
        self.assertEqual(self.t.prioridad, 'MEDIA')                                                   # nada se guardó
        self.assertFalse(HistorialTarea.objects.filter(tarea=self.t, accion='EDITADA').exists())
        self.assertFalse(Notificacion.objects.filter(tipo='MODIFICADA').exists())

    def test_con_motivo_se_guarda_y_queda_el_antes_y_el_despues(self):
        nueva = self.hoy + timedelta(days=8)
        vieja = self.t.fecha_limite
        r = self.editar(self.vladi, fecha_limite=nueva.isoformat(), prioridad='ALTA', motivo='Cambió la campaña del cliente')
        self.assertEqual(r.status_code, 200, r.content)
        h = self.ultimo()
        self.assertEqual(h.usuario, self.vladi)
        self.assertIn(f"Fecha de entrega: {vieja:%d/%m/%Y} → {nueva:%d/%m/%Y}", h.comentario)
        self.assertIn('Prioridad: Media → Alta', h.comentario)
        self.assertIn('Motivo: Cambió la campaña del cliente', h.comentario)

    def test_cambio_de_responsable_registra_nombres(self):
        r = self.editar(self.vladi, colaborador=self.ashley.id, motivo='Erlin sale de vacaciones')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('Responsable: Erlin Pérez → Ashley Morel', self.ultimo().comentario)

    def test_el_motivo_le_llega_a_quien_participa(self):
        self.editar(self.vladi, prioridad='ALTA', motivo='Sale al aire mañana')
        self.assertIn('Sale al aire mañana', Notificacion.objects.get(destinatario=self.erlin, tipo='MODIFICADA').mensaje)

    def test_el_motivo_no_hace_falta_si_el_valor_no_cambia(self):
        self.assertEqual(self.editar(self.vladi, prioridad='MEDIA').status_code, 200)               # misma prioridad
        self.assertEqual(self.editar(self.vladi, titulo='Nuevo título').status_code, 200)           # el título no exige motivo
        self.assertIn('Título: ', self.ultimo().comentario)
        self.assertNotIn('Motivo', self.ultimo().comentario)

    def test_textos_largos_se_registran_sin_copiarlos(self):
        self.editar(self.vladi, descripcion='x' * 500)
        self.assertEqual(self.ultimo().comentario, 'Descripción: actualizada')            # y no copia los 500 caracteres

    def test_reenviar_la_descripcion_y_los_pasos_sin_cambios_no_los_registra(self):
        self.editar(self.vladi, descripcion='Texto fijo', pasos_texto=['Idea', 'Diseño'])
        self.editar(self.vladi, descripcion='Texto fijo', pasos_texto=['Idea', 'Diseño'], titulo='Otro nombre')   # el formulario reenvía todo
        c = self.ultimo().comentario
        self.assertIn('Título: ', c)
        self.assertNotIn('Descripción', c)
        self.assertNotIn('Pasos', c)

    def test_cambiar_los_pasos_si_se_registra(self):
        self.editar(self.vladi, pasos_texto=['Idea'])
        self.editar(self.vladi, pasos_texto=['Idea', 'Diseño'])
        self.assertEqual(self.ultimo().comentario, 'Pasos: actualizados')

    def test_el_motivo_no_se_guarda_en_la_tarea_ni_se_cuela_en_otros_campos(self):
        self.editar(self.vladi, prioridad='ALTA', motivo='Urgente por el cliente')
        self.assertFalse(hasattr(Tarea, 'motivo'))
        self.assertEqual(Tarea.objects.get(pk=self.t.pk).prioridad, 'ALTA')

    def test_el_historial_lo_ven_quienes_ven_la_tarea_y_nadie_mas(self):
        self.editar(self.vladi, prioridad='ALTA', motivo='Cambio de plan')
        self.como(self.erlin)
        textos = [x['comentario'] for x in self.c.get(f'{T}{self.t.id}/historial/').json()]
        self.assertTrue(any('Prioridad: Media → Alta' in x for x in textos))
        self.como(self.dev)
        self.assertEqual(self.c.get(f'{T}{self.t.id}/historial/').status_code, 404)

    def test_una_tarea_validada_sigue_sin_poder_editarse(self):
        Tarea.objects.filter(pk=self.t.pk).update(estado='COMPLETADA')
        self.assertEqual(self.editar(self.vladi, prioridad='ALTA', motivo='Cambio de plan').status_code, 403)

    # ---------------------------------------------------------------- prioridad urgente
    def test_urgente_es_una_prioridad_valida_con_peso_4(self):
        self.assertEqual(PESO_PRIORIDAD, {'BAJA': 1, 'MEDIA': 2, 'ALTA': 3, 'URGENTE': 4})
        r = self.editar(self.vladi, prioridad='URGENTE', motivo='El cliente lo necesita hoy')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['prioridad'], 'URGENTE')
        self.assertIn('Prioridad: Media → Urgente', self.ultimo().comentario)

    def test_una_prioridad_inventada_se_rechaza(self):
        self.assertEqual(self.editar(self.vladi, prioridad='CRITICA', motivo='Por probar').status_code, 400)
