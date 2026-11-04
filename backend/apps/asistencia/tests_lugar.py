"""Marcaje con QR de la oficina o con ubicación (oficina, calle o donde sea)."""
from unittest import mock

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .lugar import token
from .models import AsignacionHorario, Horario, Marcaje, SitioMarcaje

OFICINA = (18.9420, -70.4090)  # Bonao (aprox.)


class LugarTests(TestCase):
    def setUp(self):
        self.h = Horario.objects.create(nombre='Oficina', dias={str(d): ['08:00', '17:00'] for d in range(5)}, por_defecto=True)
        self.ana = User.objects.create_user('ana', password='x')
        self.dir = User.objects.create_user('dir', password='x')
        self.dir.groups.set([Group.objects.get(name='Administrador')])
        self.sitio = SitioMarcaje.objects.create(nombre='Oficina Bonao', latitud=OFICINA[0], longitud=OFICINA[1], radio_m=100, clave_pantalla='clave-secreta-larga')
        self.c = APIClient()
        self.c.force_authenticate(self.ana)

    def asignar(self, donde):
        AsignacionHorario.objects.update_or_create(usuario=self.ana, defaults={'horario': self.h, 'donde_marca': donde})
        self.ana = User.objects.get(pk=self.ana.pk)
        self.c.force_authenticate(self.ana)

    def marcar(self, **extra):
        return self.c.post('/api/asistencia/marcar/', {'tipo': 'ENTRADA', **extra}, format='json')

    def test_libre_marca_como_siempre(self):
        self.assertEqual(self.marcar().status_code, 201)
        self.assertIsNone(Marcaje.objects.get().latitud)

    def test_oficina_con_qr_valido_y_vencido(self):
        self.asignar('OFICINA')
        self.assertEqual(self.marcar().status_code, 400)
        self.assertEqual(self.marcar(qr={'sitio': self.sitio.pk, 'token': 'falso'}).status_code, 400)
        r = self.marcar(qr={'sitio': self.sitio.pk, 'token': token(self.sitio)})
        self.assertEqual(r.status_code, 201, r.content)
        m = Marcaje.objects.get()
        self.assertEqual((m.origen, m.sitio_id), ('QR', self.sitio.pk))
        viejo = token(self.sitio, ventana=1)
        self.c.post('/api/asistencia/marcar/', {'tipo': 'SALIDA', 'qr': {'sitio': self.sitio.pk, 'token': viejo}}, format='json')
        self.assertEqual(Marcaje.objects.count(), 1)  # el QR de hace rato ya no sirve

    def test_oficina_por_ubicacion(self):
        self.asignar('OFICINA')
        lejos = self.marcar(latitud=18.48, longitud=-69.93, precision=20)  # Santo Domingo
        self.assertEqual(lejos.status_code, 400)
        mala = self.marcar(latitud=OFICINA[0], longitud=OFICINA[1], precision=900)  # muy imprecisa: no prueba nada
        self.assertEqual(mala.status_code, 400)
        self.assertEqual(self.marcar(latitud=OFICINA[0], longitud=OFICINA[1]).status_code, 400)  # sin precisión no vale
        self.assertEqual(self.marcar(qr='texto').status_code, 400)
        r = self.marcar(latitud=OFICINA[0] + 0.0003, longitud=OFICINA[1], precision=15)  # ~33 m
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['sitio'], 'Oficina Bonao')

    def test_calle_exige_ubicacion_y_la_guarda(self):
        self.asignar('CALLE')
        self.assertEqual(self.marcar().status_code, 400)
        self.assertEqual(self.marcar(latitud=18.48, longitud=-69.93, precision=30).status_code, 201)
        m = Marcaje.objects.get()
        self.assertEqual((float(m.latitud), m.precision_m, m.sitio_id), (18.48, 30, None))

    def test_pantalla_del_qr_sin_sesion_y_nueva_clave(self):
        p = APIClient().get('/api/asistencia/pantalla/clave-secreta-larga/')
        self.assertEqual(p.status_code, 200)
        self.assertIn('<svg', p.json()['qr'])
        self.assertEqual(APIClient().get('/api/asistencia/pantalla/otra/').status_code, 404)
        d = APIClient()
        d.force_authenticate(self.dir)
        self.assertEqual(self.c.post(f'/api/asistencia/sitios/{self.sitio.pk}/nueva-clave/').status_code, 403)
        nueva = d.post(f'/api/asistencia/sitios/{self.sitio.pk}/nueva-clave/').json()['clave_pantalla']
        self.assertNotEqual(nueva, 'clave-secreta-larga')
        self.assertEqual(APIClient().get('/api/asistencia/pantalla/clave-secreta-larga/').status_code, 404)
        r = d.post('/api/asistencia/sitios/', {'nombre': 'Estudio TV', 'latitud': '18.94', 'longitud': '-70.40', 'radio_m': 120}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(len(r.json()['clave_pantalla']) > 20)


    @override_settings(REST_FRAMEWORK={**__import__('django.conf', fromlist=['settings']).settings.REST_FRAMEWORK, 'NUM_PROXIES': 1})
    def test_con_la_red_de_la_oficina_el_qr_reenviado_no_sirve(self):
        self.asignar('OFICINA')
        SitioMarcaje.objects.filter(pk=self.sitio.pk).update(redes='190.80.1.10, 10.0.0.0/24')
        self.sitio.refresh_from_db()
        qr = {'sitio': self.sitio.pk, 'token': token(self.sitio)}
        casa = self.c.post('/api/asistencia/marcar/', {'tipo': 'ENTRADA', 'qr': qr}, format='json', HTTP_X_FORWARDED_FOR='1.2.3.4, 200.1.1.1')
        self.assertEqual(casa.status_code, 400)  # la IP real (la que agrega el proxy) no es la de la oficina
        r = self.c.post('/api/asistencia/marcar/', {'tipo': 'ENTRADA', 'qr': qr}, format='json', HTTP_X_FORWARDED_FOR='190.80.1.10')
        self.assertEqual(r.status_code, 201, r.content)
