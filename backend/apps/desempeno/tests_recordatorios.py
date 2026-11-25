"""Recordatorios personales: notas que avisan a la hora elegida. No son tareas ni suman KPI."""
from datetime import datetime, timedelta
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from . import servicios_recordatorios as srv
from . import views_recordatorios
from .models import Notificacion, Recordatorio, ResultadoKPI, Tarea
from .tests_mejoras import Base

R = '/api/desempeno/recordatorios/'


def en(**kw):
    return timezone.now() + timedelta(**kw)


class RecordatoriosTests(Base):
    def crear(self, quien=None, **datos):
        self.como(quien or self.erlin)
        return self.c.post(R, {'titulo': 'Reunión con el cliente', 'recordar_en': en(hours=2).isoformat(), **datos}, format='json')

    def hacer(self, quien=None, **kw):
        base = {'usuario': quien or self.erlin, 'titulo': 'Ir al banco', 'recordar_en': en(minutes=-1)}
        base.update(kw)
        return Recordatorio.objects.create(**base)

    def avisos(self, quien=None):
        return Notificacion.objects.filter(tipo='MI_RECORDATORIO', **({'destinatario': quien} if quien else {}))

    # ---------------------------------------------------------------- crear y validar
    def test_cualquier_persona_crea_un_recordatorio(self):
        r = self.crear(nota='Llevar la propuesta impresa')
        self.assertEqual(r.status_code, 201, r.content)
        d = r.json()
        self.assertEqual((d['titulo'], d['nota'], d['estado'], d['repetir']), ('Reunión con el cliente', 'Llevar la propuesta impresa', 'PENDIENTE', 'NO'))
        self.assertEqual(Recordatorio.objects.get().usuario, self.erlin)

    def test_validaciones(self):
        for datos in ({'titulo': '   '}, {'titulo': 'x' * 121}, {'nota': 'x' * 1001}, {'repetir': 'CADA_HORA'}, {'recordar_en': en(hours=-3).isoformat()}, {'recordar_en': 'ayer'}):
            self.assertEqual(self.crear(**datos).status_code, 400, datos)
        self.assertEqual(Recordatorio.objects.count(), 0)
        self.assertEqual(self.crear(recordar_en=en(seconds=-30).isoformat()).status_code, 201)                # hasta un minuto de tolerancia

    def test_el_titulo_se_limpia(self):
        self.assertEqual(self.crear(titulo='  Dentista  ').json()['titulo'], 'Dentista')

    def test_hay_un_tope_de_recordatorios_activos(self):
        self.crear()
        original = views_recordatorios.MAX_ACTIVOS
        views_recordatorios.MAX_ACTIVOS = 2
        try:
            self.assertEqual(self.crear().status_code, 201)
            self.assertEqual(self.crear().status_code, 400)
            Recordatorio.objects.filter(usuario=self.erlin).update(hecho=True)
            self.assertEqual(self.crear().status_code, 201)                                                # los hechos no cuentan
        finally:
            views_recordatorios.MAX_ACTIVOS = original

    # ---------------------------------------------------------------- privacidad
    def test_cada_persona_ve_solo_los_suyos_ni_siquiera_direccion(self):
        mio = self.crear(titulo='Mío').json()['id']
        self.crear(quien=self.ashley, titulo='De Ashley')
        self.como(self.erlin)
        self.assertEqual([x['titulo'] for x in self.c.get(R).json()], ['Mío'])
        for quien in (self.ashley, self.vladi, self.osiris, self.dev):
            self.como(quien)
            self.assertNotIn(mio, [x['id'] for x in self.c.get(R).json()], quien.username)
            self.assertEqual(self.c.get(f'{R}{mio}/').status_code, 404, quien.username)
            self.assertEqual(self.c.patch(f'{R}{mio}/', {'titulo': 'Robado'}, format='json').status_code, 404)
            self.assertEqual(self.c.delete(f'{R}{mio}/').status_code, 404)
            for accion in ('hecho', 'reabrir', 'posponer'):
                self.assertEqual(self.c.post(f'{R}{mio}/{accion}/', {'minutos': 10}, format='json').status_code, 404, accion)
        self.assertEqual(Recordatorio.objects.get(pk=mio).titulo, 'Mío')

    def test_exige_sesion(self):
        self.c.force_authenticate(None)
        self.assertIn(self.c.get(R).status_code, (401, 403))
        self.assertIn(self.c.post(R, {'titulo': 'x', 'recordar_en': en(hours=1).isoformat()}, format='json').status_code, (401, 403))

    def test_el_dueno_no_puede_cambiar_el_estado_a_mano(self):
        i = self.crear().json()['id']
        self.c.patch(f'{R}{i}/', {'hecho': True, 'avisado': True, 'usuario': self.ashley.pk}, format='json')
        r = Recordatorio.objects.get(pk=i)
        self.assertEqual((r.hecho, r.avisado, r.usuario), (False, False, self.erlin))

    # ---------------------------------------------------------------- no es una tarea ni suma KPI
    def test_no_es_una_tarea_ni_suma_a_kpi_ni_cambia_quien_esta_libre(self):
        self.como(self.erlin)
        antes = self.c.get('/api/desempeno/disponibilidad/').json()
        tareas, kpis = Tarea.objects.count(), ResultadoKPI.objects.count()
        for _ in range(3):
            self.crear()
        srv.avisar_recordatorios(en(days=1))
        self.assertEqual((Tarea.objects.count(), ResultadoKPI.objects.count()), (tareas, kpis))
        self.assertEqual(self.c.get('/api/desempeno/disponibilidad/').json(), antes)
        self.assertFalse(Tarea.objects.filter(titulo__icontains='Reunión').exists())

    # ---------------------------------------------------------------- avisos
    def test_avisa_a_su_hora_una_sola_vez(self):
        r = self.hacer(nota='Llevar la cédula')
        self.assertEqual(srv.avisar_recordatorios(), 1)
        n = self.avisos(self.erlin).get()
        self.assertEqual((n.titulo, n.enlace, n.tipo), ('Ir al banco', '/recordatorios', 'MI_RECORDATORIO'))
        self.assertIn('Llevar la cédula', n.mensaje)
        r.refresh_from_db()
        self.assertTrue(r.avisado and r.ultimo_aviso)
        self.assertEqual(srv.avisar_recordatorios(), 0)                                                   # el cron corrió otra vez: no repite
        self.assertEqual(self.avisos().count(), 1)

    def test_no_avisa_antes_de_hora_ni_lo_hecho_ni_a_cuentas_inactivas(self):
        self.hacer(recordar_en=en(minutes=10), titulo='Futuro')
        self.hacer(hecho=True, titulo='Hecho')
        inactivo = User.objects.create_user('baja', password='x', is_active=False)
        self.hacer(quien=inactivo, titulo='De alguien dado de baja')
        self.assertEqual(srv.avisar_recordatorios(), 0)
        self.assertFalse(self.avisos().exists())

    def test_cada_quien_recibe_solo_el_suyo(self):
        self.hacer(quien=self.erlin, titulo='De Erlin')
        self.hacer(quien=self.ashley, titulo='De Ashley')
        srv.avisar_recordatorios()
        self.assertEqual([n.titulo for n in self.avisos(self.erlin)], ['De Erlin'])
        self.assertEqual([n.titulo for n in self.avisos(self.ashley)], ['De Ashley'])
        self.assertFalse(self.avisos(self.vladi).exists())

    def test_si_sale_con_mucho_atraso_aclara_la_hora_original(self):
        hora = timezone.localtime(en(hours=-3)).replace(minute=30)
        self.hacer(recordar_en=hora)
        srv.avisar_recordatorios()
        self.assertIn('Era para las', self.avisos().get().mensaje)
        self.assertIn(srv.hora12(hora), self.avisos().get().mensaje)

    def test_a_tiempo_solo_dice_la_hora(self):
        self.hacer(recordar_en=en(seconds=-20))
        srv.avisar_recordatorios()
        self.assertNotIn('Era para', self.avisos().get().mensaje)

    def test_el_aviso_aparece_en_la_campanita(self):
        self.hacer()
        srv.avisar_recordatorios()
        self.como(self.erlin)
        tipos = [n['tipo'] for n in self.c.get('/api/desempeno/notificaciones/').json()['avisos']]
        self.assertIn('MI_RECORDATORIO', tipos)

    def test_formato_de_hora(self):
        tz = timezone.get_current_timezone()
        self.assertEqual(srv.hora12(datetime(2026, 11, 25, 0, 5, tzinfo=tz)), '12:05 a. m.')
        self.assertEqual(srv.hora12(datetime(2026, 11, 25, 12, 0, tzinfo=tz)), '12:00 p. m.')
        self.assertEqual(srv.hora12(datetime(2026, 11, 25, 15, 30, tzinfo=tz)), '3:30 p. m.')

    # ---------------------------------------------------------------- repeticiones
    def test_los_que_se_repiten_avanzan_y_no_se_marcan_como_avisados(self):
        base = timezone.localtime(en(minutes=-1))
        for rep, dias in (('DIARIO', 1), ('SEMANAL', 7)):
            r = self.hacer(recordar_en=base, repetir=rep, titulo=rep)
            srv.avisar_recordatorios()
            r.refresh_from_db()
            self.assertFalse(r.avisado)
            self.assertEqual(r.recordar_en, base + timedelta(days=dias), rep)
        self.assertEqual(self.avisos().count(), 2)
        self.assertEqual(srv.avisar_recordatorios(), 0)

    def test_un_recordatorio_diario_vuelve_a_sonar_al_dia_siguiente(self):
        r = self.hacer(recordar_en=en(minutes=-1), repetir='DIARIO')
        srv.avisar_recordatorios()
        srv.avisar_recordatorios(en(days=1, minutes=5))
        self.assertEqual(self.avisos().count(), 2)
        r.refresh_from_db()
        self.assertGreater(r.recordar_en, en(days=1))

    def test_mensual_respeta_fines_de_mes(self):
        tz = timezone.get_current_timezone()
        r = self.hacer(recordar_en=datetime(2027, 1, 31, 9, 0, tzinfo=tz), repetir='MENSUAL')
        srv.avisar_recordatorios(datetime(2027, 1, 31, 9, 1, tzinfo=tz))
        r.refresh_from_db()
        self.assertEqual(timezone.localtime(r.recordar_en).date().isoformat(), '2027-02-28')
        self.assertEqual(timezone.localtime(r.recordar_en).hour, 9)
        srv.avisar_recordatorios(datetime(2027, 2, 28, 9, 1, tzinfo=tz))
        r.refresh_from_db()
        self.assertEqual(timezone.localtime(r.recordar_en).date().isoformat(), '2027-03-28')

    def test_mensual_cruza_el_fin_de_anio(self):
        tz = timezone.get_current_timezone()
        r = self.hacer(recordar_en=datetime(2026, 12, 15, 8, 0, tzinfo=tz), repetir='MENSUAL')
        srv.avisar_recordatorios(datetime(2026, 12, 15, 8, 1, tzinfo=tz))
        r.refresh_from_db()
        self.assertEqual(timezone.localtime(r.recordar_en).date().isoformat(), '2027-01-15')

    def test_si_el_servidor_estuvo_apagado_avisa_una_vez_y_salta_lo_perdido(self):
        r = self.hacer(recordar_en=en(days=-5, minutes=-1), repetir='DIARIO')
        self.assertEqual(srv.avisar_recordatorios(), 1)                                                   # un aviso, no cinco
        r.refresh_from_db()
        self.assertGreater(r.recordar_en, timezone.now())
        self.assertLessEqual(r.recordar_en, timezone.now() + timedelta(days=1))

    # ---------------------------------------------------------------- acciones
    def test_marcar_como_hecho_y_reabrir(self):
        r = self.hacer()
        srv.avisar_recordatorios()
        self.como(self.erlin)
        d = self.c.post(f'{R}{r.pk}/hecho/').json()
        self.assertEqual(d['estado'], 'HECHO')
        d = self.c.post(f'{R}{r.pk}/reabrir/').json()
        self.assertEqual(d['estado'], 'PENDIENTE')
        self.assertEqual(srv.avisar_recordatorios(), 1)                                                   # su hora ya pasó: avisa de nuevo

    def test_marcar_hecho_uno_que_se_repite_no_lo_apaga(self):
        r = self.hacer(repetir='SEMANAL')
        self.como(self.erlin)
        self.assertEqual(self.c.post(f'{R}{r.pk}/hecho/').json()['estado'], 'PENDIENTE')

    def test_posponer(self):
        r = self.hacer()
        srv.avisar_recordatorios()
        self.como(self.erlin)
        d = self.c.post(f'{R}{r.pk}/posponer/', {'minutos': 60}, format='json')
        self.assertEqual(d.status_code, 200, d.content)
        r.refresh_from_db()
        self.assertFalse(r.avisado)
        self.assertAlmostEqual((r.recordar_en - timezone.now()).total_seconds(), 3600, delta=30)
        self.assertEqual(srv.avisar_recordatorios(), 0)                                                   # todavía no es la hora
        self.assertEqual(srv.avisar_recordatorios(en(minutes=61)), 1)

    def test_posponer_valida(self):
        r = self.hacer()
        self.como(self.erlin)
        for minutos in (0, -5, 'mucho', None, 60 * 24 * 31):
            self.assertEqual(self.c.post(f'{R}{r.pk}/posponer/', {'minutos': minutos}, format='json').status_code, 400, minutos)
        repetido = self.hacer(repetir='DIARIO')
        self.assertEqual(self.c.post(f'{R}{repetido.pk}/posponer/', {'minutos': 10}, format='json').status_code, 400)

    def test_cambiar_la_hora_lo_reactiva_y_cambiar_el_titulo_no(self):
        r = self.hacer()
        srv.avisar_recordatorios()
        self.como(self.erlin)
        self.c.patch(f'{R}{r.pk}/', {'titulo': 'Otro nombre'}, format='json')
        r.refresh_from_db()
        self.assertTrue(r.avisado)
        self.c.patch(f'{R}{r.pk}/', {'recordar_en': en(hours=3).isoformat()}, format='json')
        r.refresh_from_db()
        self.assertFalse(r.avisado or r.hecho)

    def test_borrar(self):
        r = self.hacer()
        self.como(self.erlin)
        self.assertEqual(self.c.delete(f'{R}{r.pk}/').status_code, 204)
        self.assertFalse(Recordatorio.objects.exists())

    # ---------------------------------------------------------------- tarea programada
    def test_el_comando_avisa_y_limpia_los_hechos_viejos(self):
        self.hacer()
        viejo = self.hacer(hecho=True, recordar_en=en(days=-120), titulo='Viejo')
        reciente = self.hacer(hecho=True, recordar_en=en(days=-10), titulo='Reciente')
        salida = StringIO()
        call_command('revisar_recordatorios', stdout=salida)
        self.assertIn('Recordatorios avisados: 1', salida.getvalue())
        self.assertFalse(Recordatorio.objects.filter(pk=viejo.pk).exists())
        self.assertTrue(Recordatorio.objects.filter(pk=reciente.pk).exists())
        salida = StringIO()
        call_command('revisar_recordatorios', stdout=salida)
        self.assertEqual(salida.getvalue(), '')                                                           # sin novedades, sin ruido
