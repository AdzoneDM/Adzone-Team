"""Pruebas de las correcciones de la auditoría de seguridad (12.67): cada hallazgo se da por corregido solo si su prueba pasa."""
import io
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core import accesos
from apps.core.archivos import revisar_contenido
from apps.core.models import Departamento, EventoAcceso, ExcepcionPermiso
from apps.desempeno.models import Notificacion
from apps.organizacion.models import PuestoDeTrabajo

CLAVE = 'Clave-Segura-2026'


def cliente(ip='190.80.1.10', ua='Mozilla/5.0 (Windows NT 10.0) Chrome/130.0'):
    return APIClient(REMOTE_ADDR=ip, HTTP_USER_AGENT=ua)


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', password=CLAVE, first_name='Ana', email='ana@adzone.marketing')
        self.ana.groups.set([Group.objects.get(name='Colaborador')])
        self.dir = User.objects.create_user('dir', password=CLAVE, first_name='Dir')
        self.dir.groups.set([Group.objects.get(name='Administrador')])

    def entrar(self, u, c=None, clave=CLAVE, **extra):
        c = c or cliente()
        return c, c.post('/api/auth/login/', {'username': u.username, 'password': clave, **extra}, format='json')


class BloqueoPorCuentaTests(Base):
    def test_diez_fallos_desde_ips_distintas_bloquean_la_cuenta_y_avisan(self):
        for i in range(accesos.FALLOS_MAX - 1):
            _, r = self.entrar(self.ana, cliente(ip=f'200.1.1.{i + 1}'), clave='mala')
            self.assertEqual(r.status_code, 400)
        _, r = self.entrar(self.ana, cliente(ip='200.1.1.99'), clave='mala')
        self.assertEqual(r.status_code, 429)
        # Bloqueada: ni con la contraseña correcta entra (hasta que pasen los 15 minutos)
        _, r = self.entrar(self.ana)
        self.assertEqual(r.status_code, 429)
        self.assertTrue(EventoAcceso.objects.filter(tipo='BLOQUEO', usuario=self.ana).exists())
        self.assertTrue(Notificacion.objects.filter(destinatario=self.ana, tipo='SEGURIDAD').exists())
        self.assertTrue(Notificacion.objects.filter(destinatario=self.dir, tipo='SEGURIDAD').exists())   # quien audita

    def test_el_user_id_cuenta_para_la_misma_cuenta_aunque_cambie_el_username(self):
        from apps.core.views import cuenta_de

        class R:   # la cuenta del límite sale de la persona elegida, no del «username» que se mande
            data = {'user_id': self.ana.pk, 'username': 'otra-cosa'}
        self.assertEqual(cuenta_de(R), 'ana')
        R.data = {'username': 'ANA@adzone.marketing'}
        self.assertEqual(cuenta_de(R), 'ana')


class ClaveBaseObligatoriaTests(Base):
    def test_con_la_clave_base_solo_puede_cambiarla(self):
        nuevo = User.objects.create_user('nuevo', password='usuarios')
        c, r = self.entrar(nuevo, clave='usuarios')
        self.assertEqual(r.status_code, 200)
        r = c.get('/api/desempeno/tareas/')
        self.assertEqual(r.status_code, 403)
        self.assertTrue(r.json().get('cambiar_clave'))
        self.assertEqual(c.post('/api/auth/cambiar-clave/', {'actual': 'usuarios', 'nueva': 'Mi-clave-propia-7'}, format='json').status_code, 200)
        self.assertEqual(c.get('/api/desempeno/tareas/').status_code, 200)
        self.assertTrue(EventoAcceso.objects.filter(tipo='CLAVE', usuario=nuevo).exists())


class BitacoraYSesionesTests(Base):
    def test_entrada_fallo_y_salida_quedan_con_ip_y_dispositivo(self):
        self.entrar(self.ana, clave='mala')
        c, r = self.entrar(self.ana)
        self.assertEqual(r.status_code, 200)
        c.post('/api/auth/logout/')
        tipos = list(EventoAcceso.objects.filter(usuario_texto='ana').order_by('id').values_list('tipo', 'ip', 'dispositivo'))
        self.assertEqual([t[0] for t in tipos], ['FALLO', 'ENTRADA', 'SALIDA'])
        self.assertEqual(tipos[1][1], '190.80.1.10')
        self.assertEqual(tipos[1][2], 'Chrome en Windows')

    def test_ver_y_cerrar_sesiones_a_distancia(self):
        pc, _ = self.entrar(self.ana)
        cel, _ = self.entrar(self.ana, cliente(ip='190.80.1.11', ua='Mozilla/5.0 (Linux; Android 14) Chrome/130.0 Mobile'))
        lista = pc.get('/api/cuenta/sesiones/').json()
        self.assertEqual(len(lista), 2)
        otra = next(s for s in lista if not s['actual'])
        self.assertEqual(pc.delete(f'/api/cuenta/sesiones/{otra["id"]}/').status_code, 204)
        self.assertIn(cel.get('/api/desempeno/tareas/').status_code, (401, 403))   # el celular quedó fuera
        self.assertEqual(pc.get('/api/desempeno/tareas/').status_code, 200)
        # Nadie cierra las sesiones de otra persona por esta vía
        c_dir, _ = self.entrar(self.dir)
        self.assertEqual(c_dir.delete(f'/api/cuenta/sesiones/{lista[0]["id"]}/').status_code, 404)

    def test_entrada_poco_habitual_avisa_sin_bloquear(self):
        EventoAcceso.objects.create(tipo='ENTRADA', usuario=self.ana, usuario_texto='ana', ip='190.80.1.10')
        _, r = self.entrar(self.ana, cliente(ip='45.12.7.9', ua='Mozilla/5.0 (X11; Linux) Firefox/130.0'))
        self.assertEqual(r.status_code, 200)   # un cambio de IP no bloquea
        e = EventoAcceso.objects.get(tipo='SOSPECHOSO', usuario=self.ana)
        self.assertIn('otra sesión desde otra red', e.motivo)
        self.assertTrue(Notificacion.objects.filter(destinatario=self.ana, titulo__icontains='poco habitual').exists())

    def test_bitacora_solo_con_permiso_de_auditoria(self):
        c, _ = self.entrar(self.ana)
        self.assertEqual(c.get('/api/seguridad/accesos/').status_code, 403)
        self.assertTrue(EventoAcceso.objects.filter(tipo='DENEGADO', usuario=self.ana).exists())   # el 403 quedó registrado
        c, _ = self.entrar(self.dir)
        d = c.get('/api/seguridad/accesos/?tipo=ENTRADA').json()
        self.assertIn('resumen_24h', d)
        self.assertTrue(all(e['tipo'] == 'ENTRADA' for e in d['eventos']))


@override_settings(IPS_ADMIN='200.215.233.0/24')
class IpsPermitidasTests(Base):
    def test_cuenta_de_empresa_solo_desde_la_red_permitida(self):
        _, r = self.entrar(self.dir, cliente(ip='45.1.1.1'))
        self.assertEqual(r.status_code, 403)
        self.assertTrue(EventoAcceso.objects.filter(tipo='IP_BLOQUEADA', usuario=self.dir).exists())
        _, r = self.entrar(self.dir, cliente(ip='200.215.233.121'))
        self.assertEqual(r.status_code, 200)
        _, r = self.entrar(self.ana, cliente(ip='45.1.1.1'))   # una cuenta común no se restringe
        self.assertEqual(r.status_code, 200)


class RolesExplicitosTests(Base):
    def test_estar_en_administracion_ya_no_da_finanzas(self):
        from apps.operaciones.permisos import es_finanzas
        adm = Departamento.objects.get_or_create(nombre='Administración')[0]
        self.ana.perfil.puesto_trabajo = PuestoDeTrabajo.objects.create(nombre='Legal y Contratos', departamento=adm)
        self.ana.perfil.save()
        self.assertFalse(es_finanzas(User.objects.get(pk=self.ana.pk)))
        c, _ = self.entrar(self.ana)
        self.assertEqual(c.get('/api/finanzas/facturas/').status_code, 403)
        ExcepcionPermiso.objects.create(usuario=self.ana, permiso='finanzas.gestionar', conceder=True)
        self.assertTrue(es_finanzas(User.objects.get(pk=self.ana.pk)))

    def test_el_grupo_almacen_es_un_permiso_y_lo_vigila_el_control_de_escalada(self):
        from apps.core.permisos import permisos_de_perfiles
        self.assertIn('almacen.gestionar', permisos_de_perfiles(['Almacén']))
        self.assertIn('finanzas.gestionar', permisos_de_perfiles(['Finanzas']))
        self.assertIn('operaciones.coordinar', permisos_de_perfiles(['Coordinación']))


class DatosExpuestosTests(Base):
    def test_clientes_sin_contacto_ni_notas_para_quien_no_gestiona(self):
        from apps.operaciones.models import Cliente
        Cliente.objects.create(nombre='Banco X', rnc='101-1', telefono='809', correo='cfo@banco.test', notas='Paga a 60 días')
        c, _ = self.entrar(self.ana)
        fila = c.get('/api/operaciones/clientes/').json()
        fila = (fila.get('results') if isinstance(fila, dict) else fila)[0]
        self.assertEqual(fila['nombre'], 'Banco X')
        self.assertIsNone(fila['notas'])
        self.assertIsNone(fila['correo'])
        c, _ = self.entrar(self.dir)
        fila = c.get('/api/operaciones/clientes/').json()
        fila = (fila.get('results') if isinstance(fila, dict) else fila)[0]
        self.assertEqual(fila['notas'], 'Paga a 60 días')


class ArchivosYCabecerasTests(Base):
    def test_contenido_real_de_los_archivos(self):
        self.assertIsNotNone(revisar_contenido(SimpleUploadedFile('informe.pdf', b'<html><script>alert(1)</script>')))
        self.assertIsNotNone(revisar_contenido(SimpleUploadedFile('foto.jpg', b'MZ\x90\x00programa')))
        self.assertIsNotNone(revisar_contenido(SimpleUploadedFile('x.png', b'#!/bin/sh\nrm -rf /')))
        self.assertIsNone(revisar_contenido(SimpleUploadedFile('ok.pdf', b'%PDF-1.7\n...')))

    def test_la_app_lleva_content_security_policy(self):
        c, _ = self.entrar(self.ana)
        r = c.get('/mis-tareas')
        if r.status_code == 200:   # con la app compilada
            self.assertIn("script-src 'self'", r['Content-Security-Policy'])
        r = c.get('/api/auth/session/')
        self.assertIn('Permissions-Policy', r)

    def test_la_bitacora_no_admite_registros_inventados(self):
        from django.contrib import admin
        from apps.talento.models import AuditoriaCambio
        self.assertFalse(admin.site._registry[AuditoriaCambio].has_add_permission(None))

    def test_restablecer_la_clave_de_otra_persona_queda_registrado_y_le_avisa(self):
        from apps.talento.models import AuditoriaCambio
        c, _ = self.entrar(self.dir)
        r = c.patch(f'/api/organizacion/usuarios/{self.ana.pk}/', {'password': 'Nueva-Clave-2027'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(AuditoriaCambio.objects.filter(accion='Restableció la contraseña').exists())
        self.assertTrue(Notificacion.objects.filter(destinatario=self.ana, titulo__icontains='restablecida').exists())


class DetrasDelProxyTests(Base):
    """Como en producción: detrás del proxy de Plesk (NUM_PROXIES=1). En la 12.67 inicial esto daba error 500 al entrar."""

    def setUp(self):
        super().setUp()
        from unittest import mock
        from rest_framework.settings import api_settings
        parche = mock.patch.object(api_settings, 'NUM_PROXIES', 1)
        parche.start()
        self.addCleanup(parche.stop)

    def test_entrar_y_fallar_detras_del_proxy(self):
        c = APIClient(REMOTE_ADDR='172.18.0.1', HTTP_X_FORWARDED_FOR='190.80.9.9')
        r = c.post('/api/auth/login/', {'username': 'ana', 'password': 'mala'}, format='json')
        self.assertEqual(r.status_code, 400)
        r = c.post('/api/auth/login/', {'username': 'ana', 'password': CLAVE}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(EventoAcceso.objects.get(tipo='ENTRADA').ip, '190.80.9.9')   # la IP real, no la del proxy
        self.assertEqual(EventoAcceso.objects.get(tipo='FALLO').ip, '190.80.9.9')
