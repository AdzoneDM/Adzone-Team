"""Justificación de tardanzas: solo el supervisor la registra o modifica; la tardanza sigue en el historial, marcada «justificada»."""
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient

from apps.desempeno.models import Notificacion
from . import servicios
from .models import JustificacionTardanza
from .tests import LUNES, Base, momento

API = '/api/asistencia/justificaciones/'
MARTES = LUNES + timedelta(days=1)


class JustificacionesTests(Base):
    def setUp(self):
        super().setUp()
        self.jefe.groups.add(Group.objects.get(name='Supervisor'))
        self.luis = User.objects.create_user('luis', first_name='Luis', password='Clave-segura-2026')   # compañero de Ana, sin supervisar
        self.luis.perfil.puesto_trabajo = self.p
        self.luis.perfil.save()
        self.marcas(LUNES, ('ENTRADA', '08:40'), ('SALIDA', '17:00'))   # 40 min tarde

    def como(self, u):
        c = APIClient()
        c.force_authenticate(u)
        return c

    def justificar(self, quien, **extra):
        datos = {'usuario': self.ana.pk, 'fecha': LUNES.isoformat(), 'tipo': 'PERMISO', 'nota': 'Tenía permiso para ir al médico', **extra}
        with mock.patch('django.utils.timezone.now', return_value=momento(MARTES, '09:00')):
            return self.como(quien).post(API, datos, format='json')

    def test_el_supervisor_justifica_con_nota_fecha_y_queda_quien_lo_registro(self):
        r = self.justificar(self.jefe)
        self.assertEqual(r.status_code, 201, r.data)
        j = JustificacionTardanza.objects.get()
        self.assertEqual((j.usuario, j.fecha, j.tipo, j.registrada_por), (self.ana, LUNES, 'PERMISO', self.jefe))
        self.assertTrue(Notificacion.objects.filter(destinatario=self.ana, titulo__startswith='Tu tardanza').exists())

    def test_la_tardanza_sigue_en_el_historial_marcada_como_justificada(self):
        self.justificar(self.jefe)
        dia = servicios.jornada(self.ana, LUNES, ahora=momento(MARTES, '09:00'))
        self.assertEqual((dia['llegada'], dia['tardanza']), ('TARDE', 40))
        self.assertEqual(dia['justificacion']['nota'], 'Tenía permiso para ir al médico')
        self.assertEqual(dia['justificacion']['registrada_por'], self.jefe.username)
        res = servicios.resumen(self.ana, LUNES, LUNES, ahora=momento(MARTES, '09:00'))
        self.assertEqual((res['tardanzas'], res['tardanzas_justificadas']), (1, 1))
        # y la ve la propia persona en «Mi asistencia»
        with mock.patch('django.utils.timezone.now', return_value=momento(MARTES, '09:00')):
            dias = self.como(self.ana).get('/api/asistencia/mes/?mes=2026-10').data['dias']
        self.assertTrue(next(d for d in dias if d['fecha'] == LUNES.isoformat())['justificacion'])

    def test_solo_supervisores_nunca_uno_mismo_ni_un_companero(self):
        self.assertEqual(self.justificar(self.ana).status_code, 403)    # la propia persona
        self.assertEqual(self.justificar(self.luis).status_code, 403)   # un compañero
        self.assertEqual(self.como(self.luis).get(API).data, [])
        self.assertFalse(JustificacionTardanza.objects.exists())

    def test_solo_dias_con_tardanza_y_una_por_dia(self):
        self.marcas(MARTES, ('ENTRADA', '07:55'))
        self.assertEqual(self.justificar(self.jefe, fecha=MARTES.isoformat()).status_code, 400)   # llegó a tiempo
        self.assertEqual(self.justificar(self.jefe, nota='').status_code, 400)                     # sin motivo
        self.assertEqual(self.justificar(self.jefe).status_code, 201)
        self.assertEqual(self.justificar(self.jefe).status_code, 400)                             # ya existe: se modifica

    def test_modificar_guarda_el_antes_y_quien_lo_cambio_y_no_se_borra(self):
        jid = self.justificar(self.jefe).data['id']
        self.assertIn(self.como(self.ana).patch(f'{API}{jid}/', {'nota': 'me lo invento'}, format='json').status_code, (403, 404))
        r = self.como(self.jefe).patch(f'{API}{jid}/', {'tipo': 'NOTIFICADA', 'nota': 'Avisó por WhatsApp a las 7:30'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        j = JustificacionTardanza.objects.get()
        self.assertEqual((j.tipo, j.modificada_por), ('NOTIFICADA', self.jefe))
        self.assertEqual(j.historial[0]['nota'], 'Tenía permiso para ir al médico')
        self.assertEqual(self.como(self.jefe).delete(f'{API}{jid}/').status_code, 405)
