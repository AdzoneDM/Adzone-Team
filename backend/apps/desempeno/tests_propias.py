"""Tareas que la persona se asigna a sí misma: las valida el revisor que elige (Helen u Osiris), no cualquiera."""
from datetime import timedelta

from django.contrib.auth.models import Group
from django.utils import timezone

from .models import ConfiguracionDesempeno, Notificacion, Tarea
from .tests_mejoras import Base

T = '/api/desempeno/tareas/'


class TareasPropiasTests(Base):
    def setUp(self):
        super().setUp()
        self.helen = self._u('helen', None, 'Helen', 'Castillo')
        self.helen.groups.add(Group.objects.get_or_create(name='Administrador')[0])
        self.rebeca = self._u('rebeca', None, 'Rebeca', 'Acosta')            # también Dirección, pero no es revisora de tareas propias
        self.rebeca.groups.add(Group.objects.get_or_create(name='Administrador')[0])
        # Osiris (ya creado en Base como Dirección) y Helen revisan las tareas propias
        ConfiguracionDesempeno.actual().revisores_propias.set([self.helen, self.osiris])
        self.vladi_perfil = Group.objects.get(name='Supervisor')

    def crear(self, quien, para=None, revisor=None, **extra):
        self.como(quien)
        datos = {'titulo': 'Mi tarea', 'colaborador': (para or quien).id, 'fecha_limite': str(timezone.localdate() + timedelta(days=2)), 'prioridad': 'MEDIA', **extra}
        if revisor is not None:
            datos['revisor'] = revisor.id
        return self.c.post(T, datos, format='json')

    def test_la_tarea_propia_exige_elegir_revisor(self):
        self.assertEqual(self.crear(self.vladi).status_code, 400)                         # sin revisor
        self.assertEqual(self.crear(self.vladi, revisor=self.rebeca).status_code, 400)     # Rebeca no es revisora configurada
        self.assertEqual(self.crear(self.vladi, revisor=self.vladi).status_code, 400)      # tampoco él mismo
        r = self.crear(self.vladi, revisor=self.helen)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.json()['revisor'], r.json()['revisor_nombre']), (self.helen.id, 'Helen Castillo'))

    def test_helen_y_osiris_se_asignan_y_se_revisan_entre_ellos(self):
        self.assertEqual(self.crear(self.helen, revisor=self.helen).status_code, 400)
        self.assertEqual(self.crear(self.helen, revisor=self.osiris).status_code, 201)
        self.assertEqual(self.crear(self.osiris, revisor=self.helen).status_code, 201)

    def test_una_tarea_asignada_por_otra_persona_ignora_el_revisor(self):
        r = self.crear(self.vladi, para=self.erlin, revisor=self.helen)
        self.assertEqual(r.status_code, 201)
        self.assertIsNone(r.json()['revisor'])

    def test_solo_los_revisores_configurados_validan(self):
        t = Tarea.objects.get(pk=self.crear(self.vladi, revisor=self.helen).json()['id'])
        Tarea.objects.filter(pk=t.pk).update(estado='EN_REVISION', evidencia_nota='listo')
        validar = lambda quien: (self.como(quien), self.c.post(f'{T}{t.id}/validar/', {'calificacion_calidad': 5, 'comentario_evaluacion': 'ok'}, format='json'))[1].status_code
        self.assertEqual(validar(self.vladi), 403)     # nunca la propia
        self.assertEqual(validar(self.rebeca), 403)    # Dirección, pero no revisora de tareas propias
        self.assertEqual(validar(self.erlin), 404)     # ni la ve
        self.assertEqual(validar(self.osiris), 200)    # el otro revisor configurado sí puede
        self.assertEqual(Tarea.objects.get(pk=t.pk).validada_por, self.osiris)

    def test_el_aviso_de_entrega_va_al_revisor_elegido(self):
        t = Tarea.objects.get(pk=self.crear(self.vladi, revisor=self.helen).json()['id'])
        self.como(self.vladi)
        r = self.c.post(f'{T}{t.id}/entregar/', {'evidencia_nota': 'Listo, revisa'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        quienes = set(Notificacion.objects.filter(tarea=t, tipo='ENTREGADA').values_list('destinatario__username', flat=True))
        self.assertEqual(quienes, {'helen'})

    def test_por_validar_solo_muestra_lo_que_puede_revisar(self):
        t = Tarea.objects.get(pk=self.crear(self.vladi, revisor=self.helen).json()['id'])
        Tarea.objects.filter(pk=t.pk).update(estado='EN_REVISION', evidencia_nota='listo')
        def ids(quien):
            self.como(quien)
            r = self.c.get(T, {'ambito': 'por_validar'}).json()
            return [x['id'] for x in (r['results'] if isinstance(r, dict) else r)]
        self.assertIn(t.id, ids(self.helen))
        self.assertIn(t.id, ids(self.osiris))
        self.assertNotIn(t.id, ids(self.rebeca))

    def test_directorio_de_revisores_sin_uno_mismo(self):
        self.como(self.helen)
        self.assertEqual([p['id'] for p in self.c.get('/api/desempeno/mis-revisores/').json()], [self.osiris.id])
        self.como(self.vladi)
        self.assertEqual({p['nombre'] for p in self.c.get('/api/desempeno/mis-revisores/').json()}, {'Helen Castillo', 'Osiris Cruz'})

    def test_sin_configurar_los_revisores_son_toda_la_direccion(self):
        ConfiguracionDesempeno.actual().revisores_propias.clear()
        self.como(self.vladi)
        self.assertEqual({p['id'] for p in self.c.get('/api/desempeno/mis-revisores/').json()}, {self.helen.id, self.osiris.id, self.rebeca.id})

    def test_la_sesion_dice_si_puede_autoasignarse(self):
        self.como(self.vladi)
        self.assertTrue(self.c.get('/api/auth/session/').json()['user']['puede_autoasignar'])
        self.como(self.dev)
        self.assertFalse(self.c.get('/api/auth/session/').json()['user']['puede_autoasignar'])
