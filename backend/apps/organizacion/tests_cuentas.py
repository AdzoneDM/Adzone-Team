"""Suspender, dar de baja, eliminar y reactivar cuentas sin perder información; reasignar pendientes; borrado definitivo solo de la Dirección."""
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.contrib.sessions.models import Session
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import Departamento, PermisosDePerfil
from apps.desempeno.models import HistorialTarea, Notificacion, Tarea
from apps.talento.models import AuditoriaCambio
from .cuentas import reactivar_suspensiones_vencidas

URL = '/api/organizacion/usuarios/'
CLAVE = 'Clave-segura-2026-x'


def persona(username, *perfiles, **extra):
    u = User.objects.create_user(username, password=CLAVE, email=f'{username}@adzone.test', **extra)
    for nombre in perfiles:
        u.groups.add(Group.objects.get(name=nombre))
    return u


class CuentasTests(TestCase):
    def setUp(self):
        g = Group.objects.create(name='Directorio')
        PermisosDePerfil.objects.create(grupo=g, descripcion='Solo directorio', permisos=['personal.directorio'], orden=5)
        self.dir = persona('dir', 'Administrador')                       # Dirección
        self.sistema = persona('sistema', 'Administrador del sistema')   # «Personas y accesos», sin Dirección
        self.rrhh = persona('rrhh', 'Directorio')                        # solo «Personas»
        self.ana = persona('ana', 'Colaborador', first_name='Ana')
        self.luis = persona('luis', 'Colaborador', first_name='Luis')
        self.c = APIClient()

    def como(self, u):
        self.c.force_authenticate(u)
        return self.c

    def estado(self, quien, persona_, estado, **extra):
        return self.como(quien).post(f'{URL}{persona_.id}/estado/', {'estado': estado, **extra}, format='json')

    def tarea(self, u, **kw):
        return Tarea.objects.create(titulo='Informe', colaborador=u, fecha_limite=timezone.localdate() + timedelta(days=3), **kw)

    # ---------------------------------------------------------------- suspender y reactivar
    def test_suspender_no_borra_nada_bloquea_el_acceso_y_queda_registrado(self):
        t = self.tarea(self.ana, asignada_por=self.dir)
        r = self.estado(self.sistema, self.ana, 'SUSPENDIDA', motivo='Licencia', dejar_pendientes=True)
        self.assertEqual(r.status_code, 200, r.content)
        self.ana.refresh_from_db()
        p = self.ana.perfil
        self.assertFalse(self.ana.is_active)
        self.assertEqual((p.estado_cuenta, p.estado_motivo, p.estado_por), ('SUSPENDIDA', 'Licencia', self.sistema))
        self.assertIsNotNone(p.estado_desde)
        self.assertTrue(Tarea.objects.filter(pk=t.pk, colaborador=self.ana).exists())          # la información sigue ahí
        self.assertTrue(AuditoriaCambio.objects.filter(accion__icontains='Suspendida', usuario=self.sistema).exists())
        self.assertEqual(r.json()['estado_por_nombre'], 'sistema')

    def test_una_cuenta_apartada_no_entra_ni_conserva_sesiones(self):
        cliente = APIClient()
        self.assertTrue(cliente.login(username='ana', password=CLAVE))
        n = Session.objects.count()
        self.assertGreaterEqual(n, 1)
        self.estado(self.sistema, self.ana, 'INACTIVA', motivo='Ya no trabaja aquí', dejar_pendientes=True)
        self.assertEqual(Session.objects.count(), n - 1)                                        # su sesión se cerró
        self.assertFalse(cliente.get('/api/auth/session/').json()['isAuthenticated'])                 # su pestaña abierta ya no la reconoce
        self.assertEqual(cliente.get('/api/desempeno/tareas/').status_code, 403)                          # y la API le niega todo
        self.assertFalse(APIClient().login(username='ana', password=CLAVE))                      # y no puede volver a entrar

    def test_reactivar_la_deja_como_nueva(self):
        self.estado(self.sistema, self.ana, 'SUSPENDIDA', motivo='Licencia', dejar_pendientes=True)
        r = self.estado(self.sistema, self.ana, 'ACTIVA')
        self.assertEqual(r.status_code, 200)
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.is_active)
        self.assertEqual((self.ana.perfil.estado_cuenta, self.ana.perfil.estado_motivo), ('ACTIVA', ''))
        self.assertTrue(APIClient().login(username='ana', password=CLAVE))

    def test_la_suspension_con_fecha_termina_sola(self):
        hasta = (timezone.localdate() + timedelta(days=2)).isoformat()
        self.assertEqual(self.estado(self.sistema, self.ana, 'SUSPENDIDA', motivo='Vacaciones', hasta=hasta, dejar_pendientes=True).status_code, 200)
        self.assertEqual(reactivar_suspensiones_vencidas(timezone.localdate() + timedelta(days=1)), 0)
        self.assertEqual(reactivar_suspensiones_vencidas(timezone.localdate() + timedelta(days=2)), 1)
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.is_active)

    def test_validaciones_del_estado(self):
        self.assertEqual(self.estado(self.sistema, self.ana, 'INACTIVA').status_code, 400)                        # sin motivo
        self.assertEqual(self.estado(self.sistema, self.ana, 'SUSPENDIDA', motivo='x' * 5, hasta='2020-01-01', dejar_pendientes=True).status_code, 400)
        self.assertEqual(self.estado(self.sistema, self.ana, 'ACTIVA').status_code, 400)                          # ya está activa
        self.assertEqual(self.estado(self.sistema, self.sistema, 'INACTIVA', motivo='probar').status_code, 400)   # ni la propia

    # ---------------------------------------------------------------- pendientes y reasignación
    def test_con_pendientes_pide_decidir_antes_de_apartar(self):
        self.tarea(self.ana)
        r = self.estado(self.sistema, self.ana, 'INACTIVA', motivo='Baja')
        self.assertEqual(r.status_code, 409)
        self.assertEqual((r.json()['pendientes']['tareas'], r.json()['requiere_decision']), (1, True))
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.is_active)                                                                       # no se tocó nada

    def test_reasigna_las_tareas_a_otra_persona_y_deja_historial_y_aviso(self):
        t = self.tarea(self.ana, asignada_por=self.dir)
        r = self.estado(self.sistema, self.ana, 'INACTIVA', motivo='Baja', reasignar_a=self.luis.id)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['reasignado']['tareas'], 1)
        t.refresh_from_db()
        self.assertEqual((t.colaborador, t.asignada_por), (self.luis, self.dir))                                   # se conserva quién la asignó
        h = HistorialTarea.objects.filter(tarea=t, accion='EDITADA').get()
        self.assertEqual(h.usuario, self.sistema)
        self.assertIn('Reasignada de', h.comentario)
        self.assertTrue(Notificacion.objects.filter(destinatario=self.luis, tarea=t).exists())

    def test_endpoint_de_pendientes_para_la_pantalla(self):
        self.tarea(self.ana)
        self.tarea(self.ana, estado='COMPLETADA')                                                                  # las validadas no cuentan
        r = self.como(self.sistema).get(f'{URL}{self.ana.id}/pendientes/')
        self.assertEqual((r.status_code, r.json()['tareas'], len(r.json()['lista'])), (200, 1, 1))

    def test_el_destino_de_la_reasignacion_debe_estar_activo(self):
        self.tarea(self.ana)
        self.luis.is_active = False
        self.luis.save()
        self.assertEqual(self.estado(self.sistema, self.ana, 'INACTIVA', motivo='Baja', reasignar_a=self.luis.id).status_code, 400)

    # ---------------------------------------------------------------- quién puede qué
    def test_personas_suspende_y_da_de_baja_pero_no_elimina(self):
        self.assertEqual(self.estado(self.rrhh, self.ana, 'SUSPENDIDA', motivo='Licencia', dejar_pendientes=True).status_code, 200)
        self.assertEqual(self.estado(self.rrhh, self.luis, 'ELIMINADA', motivo='Error', dejar_pendientes=True).status_code, 403)
        self.assertEqual(self.estado(self.rrhh, self.ana, 'ACTIVA').status_code, 200)

    def test_un_colaborador_no_administra_cuentas(self):
        self.assertEqual(self.estado(self.ana, self.luis, 'INACTIVA', motivo='Broma', dejar_pendientes=True).status_code, 403)

    def test_siempre_queda_un_administrador(self):
        self.assertEqual(self.estado(self.sistema, self.dir, 'INACTIVA', motivo='Prueba').status_code, 400)

    # ---------------------------------------------------------------- eliminar (oculta) y borrado definitivo
    def test_eliminar_oculta_sin_borrar_y_se_puede_restaurar(self):
        t = self.tarea(self.ana)
        self.assertEqual(self.estado(self.sistema, self.ana, 'ELIMINADA', motivo='Duplicada', dejar_pendientes=True).status_code, 200)
        self.ana.refresh_from_db()
        self.assertEqual((self.ana.perfil.estado_cuenta, self.ana.is_active), ('ELIMINADA', False))
        self.assertTrue(Tarea.objects.filter(pk=t.pk).exists())
        self.assertTrue(any(u['id'] == self.ana.id and u['estado_cuenta'] == 'ELIMINADA' for u in self.como(self.sistema).get(URL).json()))
        self.assertEqual(self.estado(self.sistema, self.ana, 'ACTIVA').status_code, 200)

    def test_borrado_definitivo_solo_direccion_y_solo_si_ya_esta_eliminada_y_sin_historial(self):
        sin_historial = persona('nuevo', 'Colaborador')
        self.assertEqual(self.como(self.sistema).delete(f'{URL}{sin_historial.id}/').status_code, 403)             # «Personas y accesos» no basta
        self.assertEqual(self.como(self.dir).delete(f'{URL}{sin_historial.id}/').status_code, 400)                 # primero «Eliminada»
        self.estado(self.sistema, sin_historial, 'ELIMINADA', motivo='Creada por error')
        self.assertEqual(self.como(self.dir).delete(f'{URL}{sin_historial.id}/').status_code, 204)
        self.tarea(self.ana)
        self.estado(self.sistema, self.ana, 'ELIMINADA', motivo='Baja', dejar_pendientes=True)
        self.assertEqual(self.como(self.dir).delete(f'{URL}{self.ana.id}/').status_code, 400)                      # con historial: no se borra
        self.assertTrue(User.objects.filter(pk=self.ana.pk).exists())

    def test_desactivar_con_la_casilla_del_formulario_tambien_deja_registro_y_cierra_sesiones(self):
        cliente = APIClient()
        cliente.login(username='luis', password=CLAVE)
        n = Session.objects.count()
        r = self.como(self.sistema).patch(f'{URL}{self.luis.id}/', {'is_active': False}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.luis.refresh_from_db()
        self.assertEqual((self.luis.perfil.estado_cuenta, self.luis.perfil.estado_por), ('INACTIVA', self.sistema))
        self.assertEqual(Session.objects.count(), n - 1)
