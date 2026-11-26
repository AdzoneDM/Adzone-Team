"""Requerimiento «Control y seguimiento operativo»: flujo completo de un caso operativo y de uno técnico, accesos y vencidos."""
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import Departamento, ExcepcionPermiso
from apps.desempeno.models import Notificacion
from apps.organizacion.models import PuestoDeTrabajo

from .models import Caso
from .servicios import avisar_vencidos

API = '/api/casos'


class Base(TestCase):
    def setUp(self):
        cache.clear()
        d = {n: Departamento.objects.get_or_create(nombre=n)[0] for n in ('Gerencia', 'Operaciones', 'Marketing', 'Tecnología', 'Impresión')}
        self.d = d
        ceo = PuestoDeTrabajo.objects.create(nombre='CEO', departamento=d['Gerencia'])
        dir_ops = PuestoDeTrabajo.objects.create(nombre='Director de Operaciones', departamento=d['Operaciones'], supervisor=ceo)
        g_mkt = PuestoDeTrabajo.objects.create(nombre='Gerente de Marketing', departamento=d['Marketing'], supervisor=dir_ops)
        g_tec = PuestoDeTrabajo.objects.create(nombre='Gerente de Tecnología', departamento=d['Tecnología'], supervisor=dir_ops)
        g_imp = PuestoDeTrabajo.objects.create(nombre='Gerente de Impresiones', departamento=d['Impresión'], supervisor=dir_ops)
        self.ops = self._u('ops', dir_ops, ['Supervisor'])
        self.gm = self._u('gm', g_mkt, ['Supervisor'])
        self.cm = self._u('cm', PuestoDeTrabajo.objects.create(nombre='CM', departamento=d['Marketing'], supervisor=g_mkt))
        self.gtec = self._u('gtec', g_tec, ['Supervisor'])
        self.dev = self._u('dev', PuestoDeTrabajo.objects.create(nombre='Soporte', departamento=d['Tecnología'], supervisor=g_tec))
        self.gimp = self._u('gimp', g_imp, ['Supervisor'])
        self.operador = self._u('operador', PuestoDeTrabajo.objects.create(nombre='Operador', departamento=d['Impresión'], supervisor=g_imp))
        self.permisos_antes = (list(ExcepcionPermiso.objects.values_list('usuario_id', 'permiso')),
                               sorted(User.groups.through.objects.values_list('user_id', 'group_id')))

    def _u(self, usuario, puesto, grupos=('Colaborador',)):
        u = User.objects.create_user(usuario, password='Clave-Segura-2026', first_name=usuario.capitalize())
        u.perfil.puesto_trabajo = puesto
        u.perfil.save()
        u.groups.set([Group.objects.get(name=g) for g in grupos])
        return u

    def como(self, u):
        c = APIClient()
        c.force_authenticate(u)
        return c

    def accion(self, u, caso, **datos):
        return self.como(u).post(f'{API}/{caso}/accion/', datos, format='json')

    def reportar(self, u, **extra):
        datos = {'titulo': 'La impresora grande se atasca', 'descripcion': 'Desde ayer se atasca con vinil de 1.5 m.', 'impacto': 'ALTO', **extra}
        r = self.como(u).post(f'{API}/', datos, format='multipart')
        self.assertEqual(r.status_code, 201, r.data)
        return r.data['id']


class FlujoTests(Base):
    def test_caso_operativo_de_la_recepcion_al_cierre(self):
        foto = SimpleUploadedFile('atasco.png', b'\x89PNG\r\n\x1a\nxxxx', content_type='image/png')
        r = self.como(self.operador).post(f'{API}/', {'titulo': 'Se atasca la impresora', 'descripcion': 'Desde ayer con vinil de 1.5 m.',
                                                      'impacto': 'ALTO', 'referencia': 'OT-26-0012', 'evidencias': [foto]}, format='multipart')
        self.assertEqual(r.status_code, 201, r.data)
        caso = r.data['id']
        self.assertTrue(r.data['codigo'].startswith('CAS-'))
        self.assertEqual((r.data['estado'], r.data['area_origen'], len(r.data['evidencias'])), ('RECIBIDO', 'Impresión', 1))
        self.assertTrue(Notificacion.objects.filter(destinatario=self.ops, tipo='CASO').exists())
        # Operaciones prioriza y deriva
        r = self.accion(self.ops, caso, accion='clasificar', prioridad='ALTA', area=self.d['Impresión'].pk, categoria='EQUIPOS')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['estado'], r.data['proxima_revision']), ('EN_ATENCION', timezone.localdate() + timedelta(days=1)))
        self.assertTrue(Notificacion.objects.filter(destinatario=self.gimp, tipo='CASO', titulo__contains='designa').exists())
        # El área designa al responsable (queda confirmado)
        r = self.accion(self.gimp, caso, accion='designar', responsable=self.operador.pk)
        self.assertTrue(r.data['responsable_confirmado'])
        # Bloqueo con motivo y fecha; avance; solución
        self.assertEqual(self.accion(self.operador, caso, accion='bloquear', nota='Falta el repuesto').status_code, 400)
        manana = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.assertEqual(self.accion(self.operador, caso, accion='bloquear', nota='Falta el repuesto', proxima_revision=manana).status_code, 200)
        self.assertEqual(self.accion(self.operador, caso, accion='avance', nota='Llegó el repuesto, se instala hoy').status_code, 200)
        r = self.accion(self.operador, caso, accion='solucion', nota='Se cambió el rodillo')
        self.assertEqual(r.data['estado'], 'PENDIENTE_VALIDACION')
        # No se cierra sin validación; quien reportó valida; Operaciones cierra
        self.assertEqual(self.accion(self.ops, caso, accion='cerrar', resultado='Rodillo cambiado').status_code, 400)
        self.assertEqual(self.accion(self.operador, caso, accion='validar', conforme=True, nota='Funciona').status_code, 200)
        r = self.accion(self.ops, caso, accion='cerrar', resultado='Rodillo cambiado; se programa mantenimiento.')
        self.assertEqual((r.data['estado'], r.data['validado_por']), ('CERRADO', 'Operador'))
        tipos = [m['tipo'] for m in r.data['movimientos']]
        for t in ('RECIBIDO', 'DERIVADO', 'RESPONSABLE', 'BLOQUEO', 'AVANCE', 'SOLUCION', 'VALIDADO', 'CERRADO'):
            self.assertIn(t, tipos)
        # Si la situación persiste, se reabre y conserva el historial
        r = self.accion(self.operador, caso, accion='reabrir', nota='Volvió a atascarse')
        self.assertEqual((r.data['estado'], r.data['reaperturas']), ('EN_ATENCION', 1))
        self.assertIn('CERRADO', [m['tipo'] for m in r.data['movimientos']])

    def test_caso_tecnico_con_respuesta_de_tecnologia(self):
        caso = self.reportar(self.cm, titulo='No puedo entrar a Finanzas', descripcion='Me sale que no tengo acceso al reporte de cobros.', categoria='ACCESOS')
        self.accion(self.ops, caso, accion='clasificar', prioridad='MEDIA', area=self.d['Tecnología'].pk)
        r = self.accion(self.ops, caso, accion='designar', responsable=self.dev.pk)
        self.assertFalse(r.data['responsable_confirmado'])   # lo propuso Operaciones: el área confirma
        self.assertEqual(self.accion(self.gtec, caso, accion='confirmar').status_code, 200)
        r = self.accion(self.dev, caso, accion='tecnica', resultado='PENDIENTE', nota='Requiere autorización de Dirección', autorizacion='Dirección General')
        self.assertEqual(r.data['estado'], 'EN_ATENCION')
        r = self.accion(self.dev, caso, accion='tecnica', resultado='REALIZADA', nota='Se le dio acceso de lectura autorizado')
        self.assertEqual(r.data['estado'], 'PENDIENTE_VALIDACION')
        self.accion(self.cm, caso, accion='validar', conforme=True)
        r = self.accion(self.ops, caso, accion='cerrar', resultado='')
        self.assertEqual(r.data['estado'], 'CERRADO')
        self.assertEqual([m['datos'].get('accion') for m in r.data['movimientos'] if m['tipo'] == 'TECNICA'], ['PENDIENTE', 'REALIZADA'])
        # Tecnología solo responde casos técnicos de su área: otra área no puede
        otro = self.reportar(self.cm)
        self.accion(self.ops, otro, accion='clasificar', prioridad='BAJA', area=self.d['Impresión'].pk)
        self.assertEqual(self.accion(self.gimp, otro, accion='tecnica', resultado='REALIZADA', nota='x').status_code, 403)

    def test_quien_ve_que(self):
        caso = self.reportar(self.operador)
        self.assertEqual(self.como(self.cm).get(f'{API}/{caso}/').status_code, 404)      # otra área, no lo reportó
        self.assertEqual(self.como(self.ops).get(f'{API}/{caso}/').status_code, 200)     # Operaciones ve todo
        self.accion(self.ops, caso, accion='clasificar', prioridad='MEDIA', area=self.d['Marketing'].pk)
        self.assertEqual(self.como(self.cm).get(f'{API}/{caso}/').status_code, 200)      # ahora es de su área
        # Solo Operaciones clasifica y cierra; un colaborador no
        self.assertEqual(self.accion(self.cm, caso, accion='clasificar', prioridad='ALTA', area=self.d['Marketing'].pk).status_code, 403)
        self.assertEqual(self.accion(self.cm, caso, accion='cerrar', resultado='x', validacion='y').status_code, 403)
        lista = self.como(self.operador).get(f'{API}/?vista=mios').data['casos']
        self.assertEqual([c['id'] for c in lista], [caso])
        self.assertNotIn('resumen', self.como(self.cm).get(f'{API}/').data)

    def test_vencido_aviso_y_resumen_por_area(self):
        caso = self.reportar(self.operador)
        self.accion(self.ops, caso, accion='clasificar', prioridad='ALTA', area=self.d['Impresión'].pk)
        Caso.objects.filter(pk=caso).update(proxima_revision=timezone.localdate() - timedelta(days=2))
        self.assertEqual(self.como(self.ops).get(f'{API}/?estado=vencidos').data['casos'][0]['id'], caso)
        self.assertEqual(avisar_vencidos(), 1)
        self.assertEqual(avisar_vencidos(), 0)   # una vez al día
        self.assertTrue(Notificacion.objects.filter(destinatario=self.ops, titulo__contains='vencido').exists())
        # Documentar el seguimiento lo saca de vencidos
        self.accion(self.gimp, caso, accion='avance', nota='Se pidió el repuesto')
        self.assertEqual(self.como(self.ops).get(f'{API}/?estado=vencidos').data['casos'], [])
        for _ in range(3):
            self.reportar(self.operador, categoria='EQUIPOS')
        res = self.como(self.ops).get(f'{API}/').data['resumen']
        self.assertIn({'area': 'Impresión', 'abiertos': 1, 'vencidos': 0, 'cerrados': 0}, res['por_area'])
        self.assertEqual(res['recurrentes'][0], {'categoria': 'Equipos e infraestructura', 'area_origen': 'Impresión', 'casos': 3})

    def test_unir_reporte_repetido_y_permisos_intactos(self):
        a = self.reportar(self.operador)
        b = self.reportar(self.gimp, titulo='Impresora atascada otra vez')
        r = self.accion(self.ops, b, accion='unir', destino=Caso.objects.get(pk=a).codigo)
        self.assertEqual(r.data['estado'], 'CERRADO')
        destino = self.como(self.ops).get(f'{API}/{a}/').data
        self.assertTrue(any(m['tipo'] == 'UNIDO' and 'Impresora atascada otra vez' in m['nota'] for m in destino['movimientos']))
        self.assertEqual((list(ExcepcionPermiso.objects.values_list('usuario_id', 'permiso')),
                          sorted(User.groups.through.objects.values_list('user_id', 'group_id'))), self.permisos_antes)

    def test_evidencia_peligrosa_se_rechaza(self):
        malo = SimpleUploadedFile('foto.png', b'MZ\x90\x00programa', content_type='image/png')
        r = self.como(self.cm).post(f'{API}/', {'titulo': 'x', 'descripcion': 'Descripción suficiente', 'evidencias': [malo]}, format='multipart')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Caso.objects.exists())
