"""v10: políticas con aceptación por versión, cumplimiento, documentos del expediente."""
from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.desempeno.models import Notificacion
from apps.monitoreo.models import Consentimiento
from . import politicas as pol
from .models import AceptacionPolitica, DocumentoEmpleado, Politica
from .tests import Base


class PoliticasTests(Base):
    def setUp(self):
        super().setUp()
        self.rrhh = self.como(self.dir)

    def test_iniciales_son_borradores_y_nadie_las_ve(self):
        self.assertGreaterEqual(Politica.objects.filter(borrador=True).count(), 14)
        self.assertEqual(self.como(self.ana).get('/api/talento/politicas/').json(), [])
        self.assertEqual(pol.pendientes(self.ana), [])

    def test_publicar_aceptar_y_nueva_version(self):
        p = Politica.objects.get(clave='asistencia')
        r = self.rrhh.patch(f'/api/talento/politicas/{p.pk}/', {'borrador': False}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(Notificacion.objects.filter(destinatario=self.ana, titulo__contains='Nueva política').exists())
        ana = self.como(self.ana)
        self.assertEqual(len(ana.get('/api/talento/politicas/pendientes/').json()), 1)
        self.assertEqual(ana.post(f'/api/talento/politicas/{p.pk}/aceptar/').status_code, 200)
        self.assertEqual(ana.get('/api/talento/politicas/pendientes/').json(), [])
        self.assertTrue(ana.get(f'/api/talento/politicas/{p.pk}/').json()['aceptada'])
        # Una publicada no se edita a escondidas: se versiona y vuelve a quedar pendiente
        self.assertEqual(self.rrhh.patch(f'/api/talento/politicas/{p.pk}/', {'contenido': 'otro'}, format='json').status_code, 400)
        self.rrhh.post(f'/api/talento/politicas/{p.pk}/nueva-version/', {'contenido': 'Texto v2', 'cambio': 'Tolerancia a 10 min'}, format='json')
        self.assertEqual(len(ana.get('/api/talento/politicas/pendientes/').json()), 1)
        c = ana.get(f'/api/talento/politicas/{p.pk}/constancia/').json()
        self.assertEqual(c['version'], 1)  # su constancia es de la versión que sí aceptó
        self.assertNotIn('Texto v2', c['contenido'])
        self.assertEqual(len(self.rrhh.get(f'/api/talento/politicas/{p.pk}/versiones/').json()), 2)
        self.assertEqual(self.como(self.luis).get(f'/api/talento/politicas/{p.pk}/constancia/?usuario={self.ana.pk}').status_code, 403)

    def test_alcance_por_departamento_y_cumplimiento(self):
        from apps.core.models import Departamento
        otro = Departamento.objects.create(nombre='Impresión')
        p = Politica.objects.create(clave='solo-imp', titulo='Seguridad en taller', contenido='x', para_todos=False)
        p.departamentos.add(otro)
        self.assertEqual(pol.pendientes(self.ana), [])
        p.departamentos.add(self.depto)
        self.assertEqual(len(pol.pendientes(self.ana)), 1)
        fila = next(f for f in self.rrhh.get('/api/talento/politicas/cumplimiento/').json() if f['id'] == p.pk)
        self.assertEqual((fila['personas'], fila['aceptaron']), (3, 0))
        self.assertIn('Política', self.rrhh.get('/api/talento/politicas/cumplimiento/?formato=csv').content.decode('utf-8-sig'))
        self.assertEqual(self.como(self.jefe).get('/api/talento/politicas/cumplimiento/').status_code, 403)

    def test_aceptar_la_de_monitoreo_es_el_consentimiento(self):
        p = Politica.objects.get(clave='monitoreo-privacidad')
        p.borrador = False
        p.save()
        self.como(self.ana).post(f'/api/talento/politicas/{p.pk}/aceptar/')
        self.assertTrue(Consentimiento.objects.filter(usuario=self.ana).exists())

    def test_borrador_no_se_acepta_y_solo_rrhh_crea(self):
        p = Politica.objects.get(clave='disciplina')
        self.assertEqual(self.como(self.ana).post(f'/api/talento/politicas/{p.pk}/aceptar/').status_code, 404)
        self.assertEqual(self.como(self.jefe).post('/api/talento/politicas/', {'titulo': 'x', 'contenido': 'y'}, format='json').status_code, 403)
        r = self.rrhh.post('/api/talento/politicas/', {'titulo': 'Uso del parqueo', 'contenido': 'Reglas', 'borrador': False}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['clave'], 'uso-del-parqueo')

    def test_recordatorio_semanal(self):
        p = Politica.objects.get(clave='asistencia')
        p.borrador = False
        p.vigente_desde = date.today() - timedelta(days=5)
        p.save()
        self.assertGreaterEqual(pol.revisar(), 3)
        self.assertEqual(pol.revisar(), 0)  # una vez por semana


class DocumentosTests(Base):
    def _subir(self, cliente, **extra):
        f = SimpleUploadedFile('contrato.pdf', b'%PDF-1.4 prueba', content_type='application/pdf')
        return cliente.post('/api/talento/documentos/', {'colaborador': self.ana.pk, 'tipo': 'CONTRATO', 'titulo': 'Contrato 2026',
                                                         'archivo': f, **extra}, format='multipart')

    def test_solo_rrhh_sube_y_la_persona_descarga_lo_suyo(self):
        self.assertEqual(self._subir(self.como(self.jefe)).status_code, 403)
        r = self._subir(self.como(self.dir), vence=str(date.today() + timedelta(days=10)))
        self.assertEqual(r.status_code, 201, r.content)
        pk = r.json()['id']
        self.assertEqual(len(self.como(self.ana).get('/api/talento/documentos/').json()), 1)
        self.assertEqual(self.como(self.ana).get(f'/api/talento/documentos/{pk}/archivo/').status_code, 200)
        self.assertEqual(self.como(self.luis).get(f'/api/talento/documentos/{pk}/archivo/').status_code, 404)
        self.assertEqual(self.como(self.jefe).get(f'/api/talento/documentos/{pk}/archivo/').status_code, 404)  # el supervisor no
        estado = self.como(self.dir).get('/api/talento/documentos/estado/').json()
        self.assertEqual(estado['vencen'][0]['titulo'], 'Contrato 2026')
        self.assertTrue(any(f['id'] == self.luis.pk for f in estado['faltantes']))
        self.assertGreaterEqual(pol.revisar(), 1)
        self.assertTrue(Notificacion.objects.filter(destinatario=self.dir, titulo__contains='Contrato 2026').exists())

    def test_archivo_no_permitido_y_departamento_de_talento(self):
        f = SimpleUploadedFile('x.exe', b'MZ', content_type='application/octet-stream')
        r = self.como(self.dir).post('/api/talento/documentos/', {'colaborador': self.ana.pk, 'tipo': 'OTRO', 'titulo': 'x', 'archivo': f}, format='multipart')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(pol.es_rrhh(self.luis))  # estar en el departamento no basta: hace falta el perfil
        self.luis.groups.add(Group.objects.get(name='Gestión del Talento'))
        self.luis = User.objects.get(pk=self.luis.pk)
        self.assertTrue(pol.es_rrhh(self.luis))
        self.assertEqual(self._subir(self.como(self.luis)).status_code, 201)
        doc = DocumentoEmpleado.objects.first()
        doc.visible_al_colaborador = False
        doc.save()
        self.assertEqual(self.como(self.ana).get('/api/talento/documentos/').json(), [])


class RevisionV10Tests(PoliticasTests.__bases__[0]):
    def test_publicada_no_vuelve_a_borrador_ni_se_borra_ni_cambia_titulo(self):
        rrhh = self.como(self.dir)
        p = Politica.objects.get(clave='asistencia')
        rrhh.patch(f'/api/talento/politicas/{p.pk}/', {'borrador': False}, format='json')
        self.como(self.ana).post(f'/api/talento/politicas/{p.pk}/aceptar/', {'version': 1}, format='json')
        self.assertEqual(rrhh.patch(f'/api/talento/politicas/{p.pk}/', {'borrador': True}, format='json').status_code, 400)
        self.assertEqual(rrhh.patch(f'/api/talento/politicas/{p.pk}/', {'titulo': 'Otro'}, format='json').status_code, 400)
        self.assertEqual(rrhh.delete(f'/api/talento/politicas/{p.pk}/').status_code, 400)
        self.assertEqual(rrhh.patch(f'/api/talento/politicas/{p.pk}/', {'activa': False}, format='json').status_code, 200)

    def test_aceptar_una_version_vieja_da_409(self):
        p = Politica.objects.get(clave='asistencia')
        self.como(self.dir).patch(f'/api/talento/politicas/{p.pk}/', {'borrador': False}, format='json')
        self.como(self.dir).post(f'/api/talento/politicas/{p.pk}/nueva-version/', {'contenido': 'v2'}, format='json')
        self.assertEqual(self.como(self.ana).post(f'/api/talento/politicas/{p.pk}/aceptar/', {'version': 1}, format='json').status_code, 409)
        self.assertEqual(self.como(self.ana).post(f'/api/talento/politicas/{p.pk}/aceptar/', {'version': 2}, format='json').status_code, 200)

    def test_rrhh_no_maneja_su_propio_expediente(self):
        self.luis.groups.add(Group.objects.get(name='Gestión del Talento'))
        oculto = DocumentoEmpleado.objects.create(colaborador=self.luis, tipo='ACTA', titulo='Amonestación', archivo='x.pdf', visible_al_colaborador=False)
        c = self.como(self.luis)
        self.assertEqual(c.get(f'/api/talento/documentos/?usuario={self.luis.pk}').json(), [])
        self.assertEqual(c.delete(f'/api/talento/documentos/{oculto.pk}/').status_code, 404)
        f = SimpleUploadedFile('c.pdf', b'%PDF', content_type='application/pdf')
        r = c.post('/api/talento/documentos/', {'colaborador': self.luis.pk, 'tipo': 'OTRO', 'titulo': 'x', 'archivo': f}, format='multipart')
        self.assertEqual(r.status_code, 403)
        self.assertTrue(DocumentoEmpleado.objects.filter(pk=oculto.pk).exists())
