"""Responder a un mensaje (como en WhatsApp): la cita viaja con el mensaje, solo dentro de la misma conversación."""
from django.core.files.uploadedfile import SimpleUploadedFile

from .models import Conversacion, Mensaje
from .tests import BASE, Base


class RespuestasTests(Base):
    def setUp(self):
        super().setUp()
        self.grupo = Conversacion.objects.create(tipo=Conversacion.GRUPO, nombre='Marketing', creado_por=self.ana)
        self.grupo.miembros.set([self.ana, self.luis])
        self.otro = Conversacion.objects.create(tipo=Conversacion.GRUPO, nombre='Ventas', creado_por=self.eva)
        self.otro.miembros.set([self.eva, self.luis])

    def enviar(self, quien, conv, texto, **extra):
        return self.como(quien).post(f'{BASE}/conversaciones/{conv.pk}/mensajes/', {'texto': texto, **extra}, format='json')

    def test_responder_trae_la_cita_y_se_ve_al_listar(self):
        original = self.enviar(self.ana, self.grupo, '¿Quién lleva el arte del banco?').data
        r = self.enviar(self.luis, self.grupo, 'Yo lo llevo', responde_a=original['id'])
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['responde_a']['id'], original['id'])
        self.assertEqual(r.data['responde_a']['texto'], '¿Quién lleva el arte del banco?')
        self.assertEqual(r.data['responde_a']['autor_nombre'], original['autor_nombre'])
        lista = self.como(self.ana).get(f'{BASE}/conversaciones/{self.grupo.pk}/mensajes/').data['mensajes']
        self.assertEqual(next(m for m in lista if m['id'] == r.data['id'])['responde_a']['id'], original['id'])
        self.assertIsNone(next(m for m in lista if m['id'] == original['id'])['responde_a'])

    def test_no_se_responde_a_un_mensaje_de_otra_conversacion(self):
        ajeno = self.enviar(self.eva, self.otro, 'Secreto de Ventas').data
        r = self.enviar(self.luis, self.grupo, 'Respondo', responde_a=ajeno['id'])
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Mensaje.objects.filter(texto='Respondo').exists())

    def test_si_el_original_se_borra_la_cita_no_muestra_su_texto(self):
        original = self.enviar(self.ana, self.grupo, 'Texto que luego se borra').data
        r = self.enviar(self.luis, self.grupo, 'Ok', responde_a=original['id']).data
        Mensaje.objects.filter(pk=original['id']).update(eliminado=True)
        lista = self.como(self.luis).get(f'{BASE}/conversaciones/{self.grupo.pk}/mensajes/').data['mensajes']
        cita = next(m for m in lista if m['id'] == r['id'])['responde_a']
        self.assertTrue(cita['eliminado'])
        self.assertEqual(cita['texto'], '')
        # y ya no se puede responder a un mensaje borrado
        self.assertEqual(self.enviar(self.ana, self.grupo, 'x', responde_a=original['id']).status_code, 400)

    def test_responder_con_archivo_y_citar_un_texto_largo(self):
        largo = self.enviar(self.ana, self.grupo, 'a' * 500).data
        archivo = SimpleUploadedFile('nota.txt', b'hola', content_type='text/plain')
        r = self.como(self.luis).post(f'{BASE}/conversaciones/{self.grupo.pk}/mensajes/',
                                      {'texto': '', 'archivo': archivo, 'responde_a': str(largo['id'])}, format='multipart')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(r.data['responde_a']['texto']), 301)
