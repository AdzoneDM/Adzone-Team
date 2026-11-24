"""Requerimiento #10, etapa 1: documentos de oficina, tipo de documento, reemplazo y descarga segura en los adjuntos de una factura."""
import os
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from apps.chat import antivirus
from .models import AdjuntoFactura
from .tests_adjuntos import AdjuntosTests as Base, MEDIA, imagen, pdf

PK = b'PK\x03\x04' + b'\0' * 40
OLE = b'\xd0\xcf\x11\xe0' + b'\0' * 40


def doc(nombre, contenido=PK):
    return SimpleUploadedFile(nombre, contenido, content_type='application/octet-stream')


@override_settings(MEDIA_ROOT=MEDIA)
class DocumentosDeFacturaTests(Base):
    def subir(self, *archivos, **extra):
        return self.c.post(self.url('adjuntos/'), {'archivos': list(archivos), **extra}, format='multipart')

    def adjunto(self):
        return AdjuntoFactura.objects.get(factura=self.f)

    # ---------------------------------------------------------------- formatos
    def test_acepta_documentos_de_oficina(self):
        r = self.subir(doc('orden.docx'), doc('presupuesto.xlsx'), doc('viejo.doc', OLE), doc('hoja.xls', OLE), doc('datos.csv', b'a,b\n1,2'), doc('nota.txt', b'hola'))
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.f.adjuntos.count(), 6)
        self.assertEqual({a['extension'] for a in r.json()['adjuntos']}, {'docx', 'xlsx', 'doc', 'xls', 'csv', 'txt'})
        self.assertTrue(all(a['vista_previa'] is None for a in r.json()['adjuntos']))                  # los documentos no tienen vista previa

    def test_imagenes_y_pdf_siguen_igual_y_tienen_vista_previa(self):
        r = self.subir(imagen(), pdf())
        self.assertEqual({a['vista_previa'] for a in r.json()['adjuntos']}, {'imagen', 'pdf'})

    def test_rechaza_un_documento_con_contenido_falso(self):
        for nombre, falso in (('trampa.docx', b'esto es texto'), ('trampa.xls', b'MZ\x90\x00 ejecutable')):
            r = self.subir(doc(nombre, falso))
            self.assertEqual(r.status_code, 400, nombre)
            self.assertIn('no es un archivo', str(r.json()))
        self.assertEqual(self.f.adjuntos.count(), 0)

    def test_rechaza_ejecutables_y_formatos_no_permitidos(self):
        for nombre in ('programa.exe', 'pagina.html', 'imagen.svg', 'comprimido.zip', 'macro.docm', 'script.js'):
            self.assertEqual(self.subir(doc(nombre, b'x' * 50)).status_code, 400, nombre)
        self.assertEqual(self.f.adjuntos.count(), 0)

    def test_un_csv_binario_no_pasa_por_texto(self):
        self.assertEqual(self.subir(doc('falso.csv', b'a,b\0\0\0c')).status_code, 400)

    def test_limites_de_tamano(self):
        grande = SimpleUploadedFile('grande.docx', PK + b'0' * (15 * 1024 * 1024))
        self.assertEqual(self.subir(grande).status_code, 400)
        mediano = SimpleUploadedFile('mediano.xlsx', PK + b'0' * (12 * 1024 * 1024))                   # entre 10 y 15 MB: los documentos sí
        self.assertEqual(self.subir(mediano).status_code, 201)
        foto = SimpleUploadedFile('foto.pdf', b'%PDF-1.4' + b'0' * (11 * 1024 * 1024))                  # un PDF sigue con su tope de 10 MB
        self.assertEqual(self.subir(foto).status_code, 400)

    def test_una_factura_admite_hasta_50_archivos(self):
        for _ in range(5):
            self.assertEqual(self.subir(*[doc(f'{i}.txt', b'x') for i in range(10)]).status_code, 201)
        self.assertEqual(self.subir(doc('uno_mas.txt', b'x')).status_code, 400)

    # ---------------------------------------------------------------- antivirus
    @override_settings(CHAT_ANTIVIRUS='exigir')
    def test_los_documentos_se_revisan_con_el_antivirus(self):
        with mock.patch.object(antivirus, 'escanear', return_value=(antivirus.INFECTADO, 'Doc.Macro.Test')):
            r = self.subir(doc('virus.docx'))
        self.assertEqual(r.status_code, 400)
        self.assertIn('antivirus detectó', str(r.json()))
        with mock.patch.object(antivirus, 'escanear', return_value=(antivirus.NO_DISPONIBLE, 'sin conexión')):
            self.assertEqual(self.subir(doc('quizas.docx')).status_code, 400)
        with mock.patch.object(antivirus, 'escanear', return_value=(antivirus.LIMPIO, '')) as esc:
            self.assertEqual(self.subir(doc('limpio.docx')).status_code, 201)
            self.assertEqual(esc.call_count, 1)
        with mock.patch.object(antivirus, 'escanear') as esc:                                           # fotos y PDF no se escanean (como antes)
            self.subir(imagen('otra.png'), pdf('otro.pdf'))
            esc.assert_not_called()
        self.assertEqual(self.f.adjuntos.count(), 1 + 2)

    # ---------------------------------------------------------------- tipo
    def test_tipo_de_documento(self):
        self.subir(doc('a.docx'))
        self.assertEqual(self.adjunto().tipo, 'OTRO')
        self.subir(pdf('b.pdf'), tipo='COMPROBANTE')
        a = self.f.adjuntos.get(nombre='b.pdf')
        self.assertEqual((a.tipo, a.get_tipo_display()), ('COMPROBANTE', 'Comprobante de pago'))
        r = self.c.get(f'/api/finanzas/facturas/{self.f.pk}/')
        self.assertEqual({x['nombre']: x['tipo_nombre'] for x in r.json()['adjuntos']}, {'a.docx': 'Otro', 'b.pdf': 'Comprobante de pago'})

    def test_un_tipo_inventado_se_rechaza(self):
        self.assertEqual(self.subir(pdf(), tipo='SECRETO').status_code, 400)
        self.assertEqual(self.f.adjuntos.count(), 0)

    def test_cambiar_tipo_nota_y_nombre(self):
        self.subir(doc('a.docx'))
        a = self.adjunto()
        r = self.c.patch(self.url(f'adjuntos/{a.pk}/'), {'tipo': 'ORDEN_COMPRA', 'nota': 'OC 4455', 'nombre': 'orden-4455.docx'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        a.refresh_from_db()
        self.assertEqual((a.tipo, a.nota, a.nombre), ('ORDEN_COMPRA', 'OC 4455', 'orden-4455.docx'))
        self.assertEqual(self.c.patch(self.url(f'adjuntos/{a.pk}/'), {'nombre': '  '}, format='json').status_code, 400)
        self.assertEqual(self.c.patch(self.url(f'adjuntos/{a.pk}/'), {'tipo': 'X'}, format='json').status_code, 400)

    # ---------------------------------------------------------------- reemplazar
    def test_reemplazar_conserva_el_lugar_y_borra_el_anterior(self):
        self.subir(pdf('v1.pdf'), tipo='COTIZACION', nota='primera')
        a = self.adjunto()
        ruta_vieja = a.archivo.path
        otro = self.otro
        self.assertTrue(os.path.exists(ruta_vieja))
        r = self.c.post(self.url(f'adjuntos/{a.pk}/reemplazar/'), {'archivo': doc('v2.docx')}, format='multipart')
        self.assertEqual(r.status_code, 200, r.content)
        a.refresh_from_db()
        self.assertEqual((a.pk, a.nombre, a.tipo, a.nota, a.es_imagen, a.subido_por), (a.pk, 'v2.docx', 'COTIZACION', 'primera', False, self.admin))
        self.assertFalse(os.path.exists(ruta_vieja))
        self.assertTrue(os.path.exists(a.archivo.path))
        self.assertEqual(self.f.adjuntos.count(), 1)
        self.assertIsNotNone(otro)

    def test_un_reemplazo_malo_deja_intacto_el_original(self):
        self.subir(pdf('v1.pdf'))
        a = self.adjunto()
        ruta = a.archivo.path
        for malo in (doc('x.exe', b'MZ' + b'0' * 50), doc('x.docx', b'texto falso'), None):
            datos = {'archivo': malo} if malo else {}
            self.assertEqual(self.c.post(self.url(f'adjuntos/{a.pk}/reemplazar/'), datos, format='multipart').status_code, 400)
        a.refresh_from_db()
        self.assertEqual(a.nombre, 'v1.pdf')
        self.assertTrue(os.path.exists(ruta))

    # ---------------------------------------------------------------- vincular a la factura
    def test_editar_la_factura_no_pierde_los_archivos(self):
        self.subir(imagen(), doc('a.docx'))
        type(self.f).objects.filter(pk=self.f.pk).update(estado='BORRADOR')                            # solo los borradores se editan
        antes = {a.pk: a.archivo.path for a in self.f.adjuntos.all()}
        r = self.c.patch(f'/api/finanzas/facturas/{self.f.pk}/', {'titulo': 'Letrero nuevo', 'notas': 'cambio'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual({a.pk: a.archivo.path for a in self.f.adjuntos.all()}, antes)
        self.assertTrue(all(os.path.exists(p) for p in antes.values()))
        self.assertEqual(len(r.json()['adjuntos']), 2)

    # ---------------------------------------------------------------- descarga segura
    def test_un_documento_siempre_se_descarga_sin_que_el_navegador_lo_interprete(self):
        self.subir(doc('a.docx'))
        r = self.c.get(self.url(f'adjuntos/{self.adjunto().pk}/'))
        self.assertEqual(r.status_code, 200)
        self.assertIn('attachment', r['Content-Disposition'])
        self.assertIn('a.docx', r['Content-Disposition'])
        self.assertEqual(r['Content-Type'], 'application/octet-stream')
        self.assertEqual(r['X-Content-Type-Options'], 'nosniff')
        self.assertIn('sandbox', r['Content-Security-Policy'])

    def test_el_pdf_y_la_imagen_se_ven_en_el_navegador_y_se_pueden_incrustar_solo_desde_la_plataforma(self):
        self.subir(pdf('x.pdf'), imagen('y.png'))
        for a in self.f.adjuntos.all():
            r = self.c.get(self.url(f'adjuntos/{a.pk}/'))
            self.assertTrue(r['Content-Disposition'].startswith('inline'), a.nombre)
            self.assertEqual((r['X-Content-Type-Options'], r['X-Frame-Options']), ('nosniff', 'SAMEORIGIN'))
            self.assertIn('attachment', self.c.get(self.url(f'adjuntos/{a.pk}/?descargar=1'))['Content-Disposition'])

    # ---------------------------------------------------------------- permisos
    def test_quien_no_es_de_finanzas_no_puede_tocar_nada(self):
        self.subir(doc('a.docx'))
        a = self.adjunto()
        self.c.force_authenticate(self.otro)
        self.assertEqual(self.c.get(self.url(f'adjuntos/{a.pk}/')).status_code, 403)
        self.assertEqual(self.c.patch(self.url(f'adjuntos/{a.pk}/'), {'tipo': 'OTRO'}, format='json').status_code, 403)
        self.assertEqual(self.c.post(self.url(f'adjuntos/{a.pk}/reemplazar/'), {'archivo': doc('b.docx')}, format='multipart').status_code, 403)
        self.assertEqual(self.c.delete(self.url(f'adjuntos/{a.pk}/')).status_code, 403)
        self.assertEqual(self.subir(doc('c.docx')).status_code, 403)
        self.assertEqual(self.f.adjuntos.count(), 1)
