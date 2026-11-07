"""Seguridad de las cuentas: dos pasos, inactividad y dispositivo nuevo."""
import time
from unittest import mock

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.core import seguridad as seg
from apps.core.models import DosPasos
from apps.desempeno.models import Notificacion

CLAVE = 'Clave-Segura-2026'


class Base(TestCase):
    def setUp(self):
        self.dir = User.objects.create_user('dir', password=CLAVE, first_name='Dir')
        self.dir.groups.set([Group.objects.get(name='Administrador')])
        self.ana = User.objects.create_user('ana', password=CLAVE, first_name='Ana')
        self.ana.groups.set([Group.objects.get(name='Colaborador')])

    def entrar(self, u, c=None):
        c = c or APIClient()
        r = c.post('/api/auth/login/', {'username': u.username, 'password': CLAVE}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        return c, r.json()

    def activar(self, c):
        d = c.post('/api/cuenta/dos-pasos/iniciar/').json()
        self.assertIn('<svg', d['qr'])
        r = c.post('/api/cuenta/dos-pasos/confirmar/', {'codigo': seg._codigo(d['secreto'], int(time.time() // 30))}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        return d['secreto'], r.json()['codigos_respaldo']


class TotpTests(TestCase):
    def test_vector_rfc6238(self):
        # Secreto «12345678901234567890» en base32, t=59 → 287082 (RFC 6238, SHA1, 6 dígitos)
        self.assertEqual(seg._codigo('GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ', 59 // 30), '287082')
        self.assertEqual(seg.paso_valido('GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ', '287082', ahora=59), 1)
        self.assertIsNone(seg.paso_valido('GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ', '287082', ultimo=1, ahora=59))  # no se repite


class DosPasosTests(Base):
    def test_por_defecto_es_opcional_incluso_para_la_direccion(self):
        c, d = self.entrar(self.dir)
        self.assertFalse(d['user']['debe_activar_dos_pasos'])
        self.assertFalse(d['user']['dos_pasos']['exige'])
        self.assertTrue(d['user']['dos_pasos']['recomendada'])  # se le recomienda con un aviso
        self.assertEqual(c.get('/api/desempeno/tareas/').status_code, 200)
        self.activar(c)  # la puede activar desde Mi cuenta
        self.assertTrue(c.get('/api/cuenta/dos-pasos/').json()['activo'])
        # y desactivar, porque no es obligatoria
        r = c.post('/api/cuenta/dos-pasos/desactivar/', {'clave': CLAVE}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(r.json()['activo'])

    @override_settings(DOS_PASOS_OBLIGATORIA=True)
    def test_direccion_debe_activarla_antes_de_usar_la_plataforma(self):
        c, d = self.entrar(self.dir)
        self.assertTrue(d['user']['debe_activar_dos_pasos'])
        r = c.get('/api/desempeno/tareas/')
        self.assertEqual(r.status_code, 403)
        self.assertTrue(r.json()['activar_dos_pasos'])
        secreto, codigos = self.activar(c)
        self.assertEqual(len(codigos), 10)
        self.assertEqual(c.get('/api/desempeno/tareas/').status_code, 200)
        # siguiente entrada: pide el código
        c2 = APIClient()
        r = c2.post('/api/auth/login/', {'username': 'dir', 'password': CLAVE}, format='json')
        self.assertTrue(r.json()['dos_pasos'])
        self.assertEqual(c2.get('/api/desempeno/tareas/').status_code, 403)  # todavía sin sesión
        self.assertEqual(c2.post('/api/auth/dos-pasos/', {'codigo': '000000'}, format='json').status_code, 400)
        r = c2.post('/api/auth/dos-pasos/', {'codigo': codigos[0]}, format='json')  # código de respaldo
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(c2.get('/api/desempeno/tareas/').status_code, 200)
        self.assertEqual(len(DosPasos.objects.get(usuario=self.dir).respaldo), 9)  # se gastó
        # no se puede desactivar siendo obligatoria
        self.assertEqual(c2.post('/api/cuenta/dos-pasos/desactivar/', {'clave': CLAVE}, format='json').status_code, 403)

    def test_cinco_intentos_y_vuelve_a_empezar(self):
        c, _ = self.entrar(self.dir)
        self.activar(c)
        c2 = APIClient()
        c2.post('/api/auth/login/', {'username': 'dir', 'password': CLAVE}, format='json')
        for _ in range(5):
            c2.post('/api/auth/dos-pasos/', {'codigo': '123456'}, format='json')
        r = c2.post('/api/auth/dos-pasos/', {'codigo': '123456'}, format='json')
        self.assertTrue(r.json().get('reiniciar'))

    def test_colaborador_no_la_necesita_pero_puede_activarla(self):
        c, d = self.entrar(self.ana)
        self.assertFalse(d['user']['debe_activar_dos_pasos'])
        self.assertEqual(c.get('/api/desempeno/tareas/').status_code, 200)
        self.activar(c)
        self.assertEqual(c.post('/api/cuenta/dos-pasos/desactivar/', {'clave': 'mala'}, format='json').status_code, 400)
        self.assertEqual(c.post('/api/cuenta/dos-pasos/desactivar/', {'clave': CLAVE}, format='json').status_code, 200)

    def test_el_panel_de_django_tambien_pide_el_codigo(self):
        c, _ = self.entrar(self.dir)
        self.activar(c)
        c2 = APIClient()
        c2.force_login(self.dir)  # como si entrara por /admin/login sin el código
        r = c2.get('/api/desempeno/tareas/')
        self.assertEqual(r.status_code, 401)

    def test_reiniciar_la_de_otra_persona(self):
        c, _ = self.entrar(self.ana)
        self.activar(c)
        cd, _ = self.entrar(self.dir)
        self.activar(cd)
        self.assertEqual(cd.delete(f'/api/accesos/personas/{self.ana.pk}/dos-pasos/').status_code, 204)
        self.assertFalse(DosPasos.objects.filter(usuario=self.ana).exists())
        self.assertEqual(cd.delete(f'/api/accesos/personas/{self.dir.pk}/dos-pasos/').status_code, 403)


class InactividadYDispositivoTests(Base):
    @override_settings(INACTIVIDAD_MIN=60)
    def test_se_cierra_por_inactividad_y_los_avisos_no_la_mantienen(self):
        c, _ = self.entrar(self.ana)
        ahora = time.time()
        with mock.patch('apps.core.seguridad.time.time', return_value=ahora + 30 * 60):
            self.assertEqual(c.get('/api/desempeno/tareas/').status_code, 200)  # GET sin X-Actividad: no renueva
        with mock.patch('apps.core.seguridad.time.time', return_value=ahora + 61 * 60):
            r = c.get('/api/desempeno/tareas/')
        self.assertEqual(r.status_code, 401)
        self.assertTrue(r.json()['inactividad'])

    @override_settings(INACTIVIDAD_MIN=60)
    def test_usar_la_app_renueva(self):
        c, _ = self.entrar(self.ana)
        ahora = time.time()
        with mock.patch('apps.core.seguridad.time.time', return_value=ahora + 50 * 60):
            c.get('/api/desempeno/tareas/', HTTP_X_ACTIVIDAD='1')
        with mock.patch('apps.core.seguridad.time.time', return_value=ahora + 100 * 60):
            self.assertEqual(c.get('/api/desempeno/tareas/').status_code, 200)

    def test_aviso_de_dispositivo_nuevo(self):
        self.entrar(self.ana)
        self.assertFalse(Notificacion.objects.filter(destinatario=self.ana, tipo='SEGURIDAD').exists())  # el primero no avisa
        c = APIClient()
        c.cookies[seg.COOKIE] = 'otro'
        self.entrar(self.ana, c)
        self.assertTrue(Notificacion.objects.filter(destinatario=self.ana, tipo='SEGURIDAD').exists())
        n = Notificacion.objects.filter(destinatario=self.ana, tipo='SEGURIDAD').count()
        self.entrar(self.ana, c)  # mismo navegador: no repite
        self.assertEqual(Notificacion.objects.filter(destinatario=self.ana, tipo='SEGURIDAD').count(), n)


class RespaldosTests(Base):
    def test_lista_descarga_y_permiso(self):
        import tempfile
        from pathlib import Path
        from datetime import date
        with tempfile.TemporaryDirectory() as d:
            with override_settings(RESPALDOS_DIR=Path(d)):
                hoy = date.today().isoformat()
                (Path(d) / f'base_{hoy}_0230.sql.gz.enc').write_bytes(b'x' * 10)
                (Path(d) / 'otra_cosa.txt').write_text('no')
                c, _ = self.entrar(self.dir)
                self.activar(c)
                r = c.get('/api/respaldos/').json()
                self.assertEqual([x['nombre'] for x in r['respaldos']], [f'base_{hoy}_0230.sql.gz.enc'])
                self.assertFalse(r['atrasado'])
                self.assertEqual(c.get(f'/api/respaldos/base_{hoy}_0230.sql.gz.enc/').status_code, 200)
                self.assertEqual(c.get('/api/respaldos/otra_cosa.txt/').status_code, 404)
                self.assertEqual(c.get('/api/respaldos/..%2F..%2Fetc%2Fpasswd/').status_code, 404)
                ca, _ = self.entrar(self.ana)
                self.assertEqual(ca.get('/api/respaldos/').status_code, 403)


class EndurecimientoTests(Base):
    """Casos de la revisión de seguridad de v12."""

    def test_bloqueo_por_persona_aunque_cambie_de_sesion(self):
        c, _ = self.entrar(self.dir)
        self.activar(c)
        for _ in range(2):  # dos sesiones distintas, cada una con su propio contador
            c2 = APIClient()
            c2.post('/api/auth/login/', {'username': 'dir', 'password': CLAVE}, format='json')
            for _ in range(3):
                c2.post('/api/auth/dos-pasos/', {'codigo': '123456'}, format='json')
        dp = DosPasos.objects.get(usuario=self.dir)
        self.assertTrue(seg.bloqueado(dp))
        self.assertTrue(Notificacion.objects.filter(destinatario=self.dir, tipo='SEGURIDAD', titulo__contains='equivocados').exists())
        c3 = APIClient()
        c3.post('/api/auth/login/', {'username': 'dir', 'password': CLAVE}, format='json')
        self.assertEqual(c3.post('/api/auth/dos-pasos/', {'codigo': '123456'}, format='json').status_code, 429)

    @override_settings(DOS_PASOS_OBLIGATORIA=True)
    def test_sin_activar_no_cambia_la_clave_del_equipo(self):
        c, _ = self.entrar(self.dir)
        self.assertEqual(c.post('/api/auth/clave-equipo/', {'nueva': 'otra-clave-larga'}, format='json').status_code, 403)

    def test_cambiar_de_celular_pide_la_contrasena(self):
        c, _ = self.entrar(self.dir)
        self.activar(c)
        self.assertEqual(c.post('/api/cuenta/dos-pasos/iniciar/').status_code, 400)
        self.assertEqual(c.post('/api/cuenta/dos-pasos/iniciar/', {'clave': CLAVE}, format='json').status_code, 200)

    def test_reiniciar_cierra_sus_sesiones_y_superusuario_solo_por_superusuario(self):
        ca, _ = self.entrar(self.ana)
        self.activar(ca)
        cd, _ = self.entrar(self.dir)
        self.activar(cd)
        self.assertEqual(cd.delete(f'/api/accesos/personas/{self.ana.pk}/dos-pasos/').status_code, 204)
        self.assertIn(ca.get('/api/desempeno/tareas/').status_code, (401, 403))  # su sesión se cerró
        sup = User.objects.create_superuser('root', password=CLAVE)
        DosPasos.objects.create(usuario=sup, secreto=seg.nuevo_secreto(), activo=True)
        self.assertEqual(cd.delete(f'/api/accesos/personas/{sup.pk}/dos-pasos/').status_code, 403)
        self.assertEqual(cd.patch(f'/api/organizacion/usuarios/{sup.pk}/', {'password': 'Otra-Clave-Larga-2026'}, format='json').status_code, 400)

    def test_entrar_con_otra_cuenta_cierra_la_sesion_abierta(self):
        c, _ = self.entrar(self.ana)
        cd, _ = self.entrar(self.dir)
        self.activar(cd)
        r = c.post('/api/auth/login/', {'username': 'dir', 'password': CLAVE}, format='json')
        self.assertTrue(r.json()['dos_pasos'])
        self.assertIn(c.get('/api/desempeno/tareas/').status_code, (401, 403))  # Ana ya no está en este navegador


class PushTests(Base):
    @override_settings(VAPID_PUBLICA='pub', VAPID_PRIVADA='priv', PUSH_SINCRONO=True)
    def test_suscribirse_y_cada_aviso_llega_al_celular(self):
        from apps.core.models import SuscripcionPush
        from apps.desempeno.servicios import avisar
        c, _ = self.entrar(self.ana)
        self.assertEqual(c.post('/api/cuenta/push/', {'suscripcion': {'endpoint': 'http://inseguro'}}, format='json').status_code, 400)
        sus = {'endpoint': 'https://fcm.googleapis.com/fcm/send/abc', 'keys': {'p256dh': 'k', 'auth': 'a'}}
        with mock.patch('pywebpush.webpush') as w:
            self.assertEqual(c.post('/api/cuenta/push/', {'suscripcion': {**sus, 'endpoint': 'https://evil.example/x'}}, format='json').status_code, 400)
            self.assertEqual(c.post('/api/cuenta/push/', {'suscripcion': sus}, format='json').status_code, 201)
            self.assertEqual(c.get('/api/cuenta/push/').json()['suscripciones'], 1)
            with self.captureOnCommitCallbacks(execute=True):
                avisar([self.ana], 'ASIGNADA', 'Nueva tarea', 'Diseño del brochure', enlace='/mis-tareas')
        self.assertTrue(any('Nueva tarea' in str(call) for call in w.call_args_list))
        # un celular que ya no existe se borra solo
        from pywebpush import WebPushException
        resp = mock.Mock(status_code=410)
        with mock.patch('pywebpush.webpush', side_effect=WebPushException('gone', response=resp)):
            with self.captureOnCommitCallbacks(execute=True):
                avisar([self.ana], 'ASIGNADA', 'Otra')
        self.assertFalse(SuscripcionPush.objects.exists())

    def test_sin_claves_no_se_suscribe(self):
        c, _ = self.entrar(self.ana)
        r = c.post('/api/cuenta/push/', {'suscripcion': {'endpoint': 'https://x', 'keys': {'p256dh': 'k', 'auth': 'a'}}}, format='json')
        self.assertEqual(r.status_code, 400)



class PushRevisionTests(Base):
    @override_settings(VAPID_PUBLICA='pub', VAPID_PRIVADA='priv', PUSH_SINCRONO=True)
    def test_no_se_roba_la_suscripcion_ajena_y_salir_la_borra(self):
        from apps.core.models import SuscripcionPush
        sus = {'endpoint': 'https://fcm.googleapis.com/fcm/send/xyz', 'keys': {'p256dh': 'k', 'auth': 'a'}}
        ca, _ = self.entrar(self.ana)
        with mock.patch('pywebpush.webpush'):
            self.assertEqual(ca.post('/api/cuenta/push/', {'suscripcion': sus}, format='json').status_code, 201)
            otro = User.objects.create_user('otro', password=CLAVE)
            co, _ = self.entrar(otro)
            self.assertEqual(co.post('/api/cuenta/push/', {'suscripcion': sus}, format='json').status_code, 400)
        self.assertEqual(SuscripcionPush.objects.get().usuario, self.ana)
        ca.post('/api/auth/logout/', {'push_endpoint': sus['endpoint']}, format='json')
        self.assertFalse(SuscripcionPush.objects.exists())

    def test_redirecciones_desactivadas(self):
        from apps.core.push import _SinRedirecciones
        s = _SinRedirecciones()
        with mock.patch.object(s._s, 'post') as p:
            s.post('https://fcm.googleapis.com/x', data=b'')
        self.assertFalse(p.call_args.kwargs['allow_redirects'])
