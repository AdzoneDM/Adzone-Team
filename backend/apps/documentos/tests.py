"""Documentos compartidos: subir, enviar a personas y áreas, privacidad, avisos y borrado."""
import io
import os
import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from apps.core.models import Departamento
from apps.desempeno.models import Notificacion
from apps.organizacion.models import PuestoDeTrabajo
from .models import DocumentoCompartido

MEDIA = tempfile.mkdtemp()
URL = '/api/documentos/'


def pdf(nombre='contrato.pdf', tam=50):
    return SimpleUploadedFile(nombre, b'%PDF-1.4 ' + b'0' * tam, content_type='application/pdf')


def imagen(nombre='logo.png'):
    b = io.BytesIO()
    Image.new('RGB', (10, 10), 'green').save(b, 'PNG')
    return SimpleUploadedFile(nombre, b.getvalue(), content_type='image/png')


@override_settings(MEDIA_ROOT=MEDIA)
class DocumentosTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.mkt = Departamento.objects.create(nombre='Marketing')
        self.ti = Departamento.objects.create(nombre='Tecnología')
        def persona(usuario, depto=None):
            u = User.objects.create_user(usuario, password='x', first_name=usuario.capitalize())
            if depto:
                u.perfil.puesto_trabajo = PuestoDeTrabajo.objects.create(nombre=f'Puesto {usuario}', departamento=depto)
                u.perfil.save()
            return u
        self.ana, self.beto, self.cris, self.dani = persona('ana', self.mkt), persona('beto', self.mkt), persona('cris', self.ti), persona('dani')

    def como(self, u):
        c = APIClient()
        c.force_authenticate(u)
        return c

    def subir(self, quien, archivo=None, **datos):
        return self.como(quien).post(URL, {'archivo': archivo or pdf(), **datos}, format='multipart')

    def ids(self, quien, **params):
        return [d['id'] for d in self.como(quien).get(URL, params).json()['documentos']]

    def test_sube_un_archivo_personal_que_nadie_mas_ve(self):
        r = self.subir(self.ana, titulo='Mi borrador', carpeta='Personal')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.data['titulo'], r.data['carpeta'], r.data['personal'], r.data['mio']), ('Mi borrador', 'Personal', True, True))
        self.assertEqual(self.ids(self.ana), [r.data['id']])
        for otro in (self.beto, self.cris, self.dani):
            self.assertEqual(self.ids(otro), [])

    def test_envia_a_personas(self):
        r = self.subir(self.ana, imagen(), titulo='Logo', destinatarios=[self.cris.id, self.dani.id], nota='Para la web')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.data['es_imagen'])
        self.assertEqual({d['id'] for d in r.data['destinatarios']}, {self.cris.id, self.dani.id})
        self.assertEqual(len(self.ids(self.cris)), 1)
        self.assertEqual(len(self.ids(self.dani)), 1)
        self.assertEqual(self.ids(self.beto), [])                      # Beto no estaba incluido
        self.assertEqual(Notificacion.objects.filter(tipo='DOCUMENTO').count(), 2)
        self.assertEqual(Notificacion.objects.get(destinatario=self.cris).titulo, 'Ana te compartió un documento')

    def test_envia_a_un_area_completa(self):
        r = self.subir(self.cris, titulo='Calendario', areas=[self.mkt.id])
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(len(self.ids(self.ana)), 1)                   # todo Marketing lo recibe
        self.assertEqual(len(self.ids(self.beto)), 1)
        self.assertEqual(self.ids(self.dani), [])                      # quien no es de esa área, no
        self.assertEqual({n.destinatario_id for n in Notificacion.objects.filter(tipo='DOCUMENTO')}, {self.ana.id, self.beto.id})

    def test_recibidos_enviados_carpetas_y_busqueda(self):
        self.subir(self.ana, titulo='Presupuesto 2026', carpeta='Finanzas', destinatarios=[self.cris.id])
        self.subir(self.cris, titulo='Manual de marca', carpeta='Marketing', destinatarios=[self.ana.id])
        d = self.como(self.ana).get(URL).json()
        self.assertEqual(sorted(d['carpetas']), ['Finanzas', 'Marketing'])
        self.assertEqual(len(self.ids(self.ana, vista='recibidos')), 1)
        self.assertEqual(len(self.ids(self.ana, vista='enviados')), 1)
        self.assertEqual(len(self.ids(self.ana, carpeta='finanzas')), 1)
        self.assertEqual(len(self.ids(self.ana, q='manual')), 1)
        self.assertEqual(self.ids(self.ana, q='zzzz'), [])

    def test_descarga_solo_quien_tiene_acceso_y_lo_recibido_deja_de_ser_nuevo(self):
        doc = self.subir(self.ana, titulo='Acuerdo', destinatarios=[self.cris.id]).data['id']
        self.assertTrue(next(d for d in self.como(self.cris).get(URL).json()['documentos'])['nuevo'])
        self.assertEqual(self.como(self.cris).get('/api/documentos/resumen/').json()['nuevos'], 1)
        r = self.como(self.cris).get(f'{URL}{doc}/archivo/')
        self.assertEqual((r.status_code, r['Content-Type']), (200, 'application/pdf'))
        self.assertEqual(self.como(self.cris).get('/api/documentos/resumen/').json()['nuevos'], 0)
        self.assertIn('attachment', self.como(self.cris).get(f'{URL}{doc}/archivo/?descargar=1')['Content-Disposition'])
        for ajeno in (self.beto, self.dani):
            self.assertEqual(self.como(ajeno).get(f'{URL}{doc}/archivo/').status_code, 404)

    def test_solo_quien_lo_subio_cambia_o_elimina(self):
        doc = self.subir(self.ana, titulo='Plan', destinatarios=[self.cris.id]).data['id']
        c = self.como(self.cris)
        self.assertEqual(c.patch(f'{URL}{doc}/', {'titulo': 'Mío ahora'}, format='json').status_code, 403)
        self.assertEqual(c.delete(f'{URL}{doc}/').status_code, 403)
        self.assertEqual(self.como(self.dani).delete(f'{URL}{doc}/').status_code, 404)
        r = self.como(self.ana).patch(f'{URL}{doc}/', {'titulo': 'Plan v2', 'carpeta': 'Planes', 'destinatarios': [self.cris.id, self.dani.id]}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.data['titulo'], r.data['carpeta'], len(r.data['destinatarios'])), ('Plan v2', 'Planes', 2))
        self.assertEqual(len(self.ids(self.dani)), 1)                  # Dani ya lo recibe, y le llegó el aviso
        self.assertTrue(Notificacion.objects.filter(destinatario=self.dani, tipo='DOCUMENTO').exists())

    def test_eliminar_borra_el_archivo(self):
        doc = DocumentoCompartido.objects.get(pk=self.subir(self.ana, titulo='Temporal').data['id'])
        ruta = doc.archivo.path
        self.assertTrue(os.path.exists(ruta))
        self.assertEqual(self.como(self.ana).delete(f'{URL}{doc.pk}/').status_code, 204)
        self.assertFalse(os.path.exists(ruta))

    def test_rechaza_ejecutables_imagenes_falsas_archivos_grandes_y_sin_archivo(self):
        c = self.como(self.ana)
        malo = SimpleUploadedFile('virus.exe', b'MZ', content_type='application/octet-stream')
        falsa = SimpleUploadedFile('rota.png', b'nada', content_type='image/png')
        grande = SimpleUploadedFile('enorme.pdf', b'0' * (25 * 1024 * 1024 + 1), content_type='application/pdf')
        for f in (malo, falsa, grande):
            self.assertEqual(c.post(URL, {'archivo': f}, format='multipart').status_code, 400)
        self.assertEqual(c.post(URL, {'titulo': 'sin archivo'}, format='multipart').status_code, 400)
        self.assertEqual(DocumentoCompartido.objects.count(), 0)

    def test_exige_sesion(self):
        self.assertIn(APIClient().get(URL).status_code, (401, 403))
