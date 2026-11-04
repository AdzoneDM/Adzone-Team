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
