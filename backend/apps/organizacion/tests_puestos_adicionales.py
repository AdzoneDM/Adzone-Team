"""Puestos adicionales: quien cubre también otro puesto recibe el equipo de ese puesto (y solo la Dirección lo asigna)."""
from datetime import timedelta

from django.utils import timezone

from apps.desempeno.permisos import puede_asignar, revisores_de, subordinados
from apps.desempeno.tests_mejoras import Base


class PuestosAdicionalesTests(Base):
    def dar_gerencia_a_erlin(self):
        self.como(self.osiris)
        return self.c.patch(f'/api/organizacion/usuarios/{self.erlin.id}/',
                            {'puestos_adicionales_ids': [self.p_gerente.id]}, format='json')

    def test_la_direccion_asigna_y_la_persona_recibe_el_equipo_del_puesto(self):
        self.assertFalse(puede_asignar(self.erlin, self.ashley))
        r = self.dar_gerencia_a_erlin()
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual([p['nombre'] for p in r.json()['puestos_adicionales']], ['Gerente de Marketing'])
        from django.contrib.auth.models import User
        self.erlin = User.objects.get(pk=self.erlin.pk)  # los permisos se calculan una vez por objeto (por petición)
        self.assertEqual(self.erlin.perfil.puesto_trabajo, self.p_cm)  # el puesto principal no cambia
        self.assertIn('Supervisor', self.erlin.groups.values_list('name', flat=True))
        self.assertIn(self.ashley, subordinados(self.erlin))
        self.assertNotIn(self.erlin, subordinados(self.erlin))
        self.assertTrue(puede_asignar(self.erlin, self.ashley))
        self.assertFalse(puede_asignar(self.erlin, self.dev))  # solo el equipo de ese puesto
        # Cuando Ashley entrega, avisa a los dos que cubren la gerencia
        self.assertEqual({u.pk for u in revisores_de(self.ashley)}, {self.vladi.pk, self.erlin.pk})

    def test_puede_asignar_tareas_por_la_api(self):
        self.dar_gerencia_a_erlin()
        self.como(self.erlin)
        r = self.c.post('/api/desempeno/tareas/', {'titulo': 'Parrilla', 'colaborador': self.ashley.id, 'prioridad': 'MEDIA',
                                                   'fecha_limite': (timezone.localdate() + timedelta(days=3)).isoformat()},
                        format='json')
        self.assertEqual(r.status_code, 201, r.content)

    def test_solo_la_direccion_asigna_puestos_adicionales(self):
        from django.contrib.auth.models import Group
        self.vladi.groups.add(Group.objects.get_or_create(name='Administrador del sistema')[0])  # maneja personas, no es Dirección
        self.como(self.vladi)
        r = self.c.patch(f'/api/organizacion/usuarios/{self.dev.id}/', {'puestos_adicionales_ids': [self.p_gerente.id]}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertFalse(self.dev.perfil.puestos_adicionales.exists())

    def test_quitar_el_puesto_adicional_quita_el_equipo(self):
        self.dar_gerencia_a_erlin()
        r = self.c.patch(f'/api/organizacion/usuarios/{self.erlin.id}/', {'puestos_adicionales_ids': []}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertNotIn(self.ashley, subordinados(self.erlin))


class BajaYContrasenaTests(Base):
    """Cuando alguien se va: la Dirección le cambia la contraseña o lo da de baja, y su sesión abierta deja de servir."""
    def sesion_de(self, u):
        from rest_framework.test import APIClient
        c = APIClient()
        self.assertTrue(c.login(username=u.username, password='Clave-Segura-2026'))
        self.assertEqual(c.get('/api/desempeno/tareas/?ambito=mias').status_code, 200)
        return c

    def test_cambiar_la_contrasena_cierra_sus_sesiones(self):
        suya = self.sesion_de(self.erlin)
        self.como(self.osiris)
        r = self.c.patch(f'/api/organizacion/usuarios/{self.erlin.id}/', {'password': 'Nueva-Clave-Larga-2026'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn(suya.get('/api/desempeno/tareas/?ambito=mias').status_code, (401, 403))
        self.erlin.refresh_from_db()
        self.assertTrue(self.erlin.check_password('Nueva-Clave-Larga-2026'))

    def test_dar_de_baja_bloquea_la_entrada_y_conserva_el_historial(self):
        tarea = self.tarea(self.erlin)
        suya = self.sesion_de(self.erlin)
        self.como(self.osiris)
        r = self.c.patch(f'/api/organizacion/usuarios/{self.erlin.id}/', {'is_active': False}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn(suya.get('/api/desempeno/tareas/?ambito=mias').status_code, (401, 403))
        from rest_framework.test import APIClient
        self.assertFalse(APIClient().login(username='erlin', password='Clave-Segura-2026'))
        tarea.refresh_from_db()
        self.assertEqual(tarea.colaborador_id, self.erlin.id)  # su historial queda

    def test_un_supervisor_no_cambia_la_contrasena_de_nadie(self):
        self.como(self.vladi)
        r = self.c.patch(f'/api/organizacion/usuarios/{self.erlin.id}/', {'password': 'Nueva-Clave-Larga-2026'}, format='json')
        self.assertEqual(r.status_code, 403)
