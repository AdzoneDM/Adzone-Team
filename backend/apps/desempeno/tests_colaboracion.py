"""Pruebas de 12.4: tareas bloqueadas, espera de asignación, actividades adicionales, colaboración y avisos de cambios."""
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.utils import timezone

from apps.kpis.models import KPIAsignado, PlantillaKPI
from .models import ActividadAdicional, Colaboracion, EsperaAsignacion, Notificacion, Tarea
from .puntaje import Mediciones, rango_del_mes
from .tests_mejoras import Base


class BloqueoTests(Base):
    def test_bloquear_avisa_al_supervisor_y_desbloquear_retoma(self):
        t = self.tarea(self.erlin)
        self.como(self.erlin)
        self.assertEqual(self.c.post(f'/api/desempeno/tareas/{t.id}/bloquear/', {'motivo': ''}).status_code, 400)
        r = self.c.post(f'/api/desempeno/tareas/{t.id}/bloquear/', {'motivo': 'Espero el logo del cliente'})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['estado'], 'BLOQUEADA')
        aviso = Notificacion.objects.get(destinatario=self.vladi, tipo='BLOQUEADA')
        self.assertIn('logo', aviso.mensaje)
        # La compañera de otro equipo no puede tocarla
        self.como(self.dev)
        self.assertEqual(self.c.post(f'/api/desempeno/tareas/{t.id}/desbloquear/').status_code, 404)
        self.como(self.erlin)
        r = self.c.post(f'/api/desempeno/tareas/{t.id}/desbloquear/', {'nota': 'Llegó el logo'})
        self.assertEqual(r.json()['estado'], 'EN_PROGRESO')
        t.refresh_from_db()
        self.assertIsNone(t.bloqueada_desde)
        self.assertIsNotNone(t.fecha_inicio_trabajo)

    def test_recordatorio_diario_de_bloqueadas(self):
        t = self.tarea(self.erlin, estado='BLOQUEADA', motivo_bloqueo='Falta material',
                       bloqueada_desde=timezone.now() - timedelta(days=3))
        out = StringIO()
        call_command('tareas_diarias', stdout=out)
        self.assertIn('Bloqueadas recordadas: 1', out.getvalue())
        self.assertTrue(Notificacion.objects.filter(destinatario=self.vladi, tipo='BLOQUEADA', tarea=t).exists())
        call_command('tareas_diarias', stdout=StringIO())   # el mismo día no se repite
        self.assertEqual(Notificacion.objects.filter(destinatario=self.vladi, tipo='BLOQUEADA', tarea=t).count(), 1)

    def test_tablero_muestra_bloqueada(self):
        self.tarea(self.erlin, estado='BLOQUEADA', motivo_bloqueo='Falta material', bloqueada_desde=timezone.now())
        self.como(self.vladi)
        personas = {p['id']: p for p in self.c.get('/api/desempeno/equipo/carga/').json()['personas']}
        self.assertEqual(personas[self.erlin.id]['estado'], 'bloqueada')
        self.assertEqual(personas[self.erlin.id]['actual']['motivo_bloqueo'], 'Falta material')


class EsperaTests(Base):
    def test_espera_hasta_recibir_tarea(self):
        self.como(self.erlin)
        self.assertEqual(self.c.post('/api/desempeno/pedir-trabajo/').status_code, 200)
        d = self.c.get('/api/desempeno/mi-disponibilidad/').json()
        self.assertTrue(d['en_espera'])
        self.como(self.vladi)
        personas = {p['id']: p for p in self.c.get('/api/desempeno/equipo/carga/').json()['personas']}
        self.assertEqual(personas[self.erlin.id]['estado'], 'en_espera')
        self.assertIsNotNone(personas[self.erlin.id]['esperando_desde'])
        r = self.c.post('/api/desempeno/tareas/', {'titulo': 'Nueva', 'colaborador': self.erlin.id,
                                                   'fecha_limite': (timezone.localdate() + timedelta(days=2)).isoformat()}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        e = EsperaAsignacion.objects.get(usuario=self.erlin)
        self.assertIsNotNone(e.hasta)
        self.assertEqual(e.tarea_recibida_id, r.json()['id'])

    def test_bloqueadas_no_impiden_avisar(self):
        self.tarea(self.erlin, estado='BLOQUEADA', motivo_bloqueo='Falta material')
        self.como(self.erlin)
        self.assertEqual(self.c.post('/api/desempeno/pedir-trabajo/').status_code, 200)
        aviso = Notificacion.objects.get(destinatario=self.vladi, tipo='PIDE_TRABAJO')
        self.assertIn('bloqueada', aviso.mensaje)


class ModificacionTests(Base):
    def test_cambiar_fecha_avisa_al_colaborador(self):
        t = self.tarea(self.erlin)
        self.como(self.vladi)
        nueva = (timezone.localdate() + timedelta(days=9)).isoformat()
        r = self.c.patch(f'/api/desempeno/tareas/{t.id}/', {'fecha_limite': nueva}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        aviso = Notificacion.objects.get(destinatario=self.erlin, tipo='MODIFICADA')
        self.assertIn('fecha de entrega', aviso.mensaje)

    def test_guardar_sin_cambios_no_avisa(self):
        t = self.tarea(self.erlin)
        self.como(self.vladi)
        self.c.patch(f'/api/desempeno/tareas/{t.id}/', {'titulo': t.titulo}, format='json')
        self.assertFalse(Notificacion.objects.filter(tipo='MODIFICADA').exists())


class ActividadTests(Base):
    def test_registrar_y_validar(self):
        self.como(self.erlin)
        r = self.c.post('/api/desempeno/actividades/', {'fecha': str(timezone.localdate()), 'tipo': 'DOCUMENTACION',
                                                        'descripcion': 'Ordené la carpeta de artes del cliente', 'minutos': 45})
        self.assertEqual(r.status_code, 201, r.content)
        aid = r.json()['id']
        self.assertEqual(self.c.post(f'/api/desempeno/actividades/{aid}/validar/').status_code, 403)   # la propia no
        self.como(self.dev)                                                                               # otra área no la ve
        self.assertEqual(self.c.post(f'/api/desempeno/actividades/{aid}/validar/').status_code, 404)
        self.como(self.vladi)
        pv = self.c.get('/api/desempeno/actividades/?ambito=por_validar').json()
        lista = pv['results'] if isinstance(pv, dict) else pv
        self.assertEqual([a['id'] for a in lista], [aid])
        self.assertEqual(self.c.post(f'/api/desempeno/actividades/{aid}/validar/').status_code, 200)
        self.assertTrue(Notificacion.objects.filter(destinatario=self.erlin, tipo='ACTIVIDAD').exists())
        inicio, fin = rango_del_mes(timezone.localdate())
        self.assertEqual(Mediciones(self.erlin, inicio, fin).medir('ACTIVIDADES_EXTRA'), 1.0)

    def test_no_validar_exige_motivo(self):
        a = ActividadAdicional.objects.create(usuario=self.erlin, fecha=timezone.localdate(), tipo='ESTUDIO',
                                              descripcion='Leí la política de vacaciones')
        self.como(self.vladi)
        self.assertEqual(self.c.post(f'/api/desempeno/actividades/{a.id}/rechazar/').status_code, 400)
        self.assertEqual(self.c.post(f'/api/desempeno/actividades/{a.id}/rechazar/', {'comentario': 'Eso no es de este mes'}).status_code, 200)


class ColaboracionTests(Base):
    def test_pedir_aceptar_realizar_validar(self):
        self.como(self.erlin)
        r = self.c.post('/api/desempeno/colaboraciones/', {'ayudante': self.ashley.id,
                                                           'descripcion': 'Necesito ayuda con las fotos del evento'})
        self.assertEqual(r.status_code, 201, r.content)
        cid = r.json()['id']
        self.assertTrue(Notificacion.objects.filter(destinatario=self.ashley, tipo='COLABORACION').exists())
        self.como(self.ashley)
        self.assertEqual(self.c.post(f'/api/desempeno/colaboraciones/{cid}/accion/', {'accion': 'validar'}).status_code, 403)
        self.assertEqual(self.c.post(f'/api/desempeno/colaboraciones/{cid}/accion/', {'accion': 'aceptar'}).status_code, 200)
        r = self.c.post(f'/api/desempeno/colaboraciones/{cid}/accion/', {'accion': 'realizar', 'texto': 'Edité 30 fotos', 'minutos': 90})
        self.assertEqual(r.json()['estado'], 'REALIZADA')
        self.como(self.vladi)
        r = self.c.post(f'/api/desempeno/colaboraciones/{cid}/accion/', {'accion': 'validar'})
        self.assertEqual(r.json()['estado'], 'VALIDADA', r.content)
        inicio, fin = rango_del_mes(timezone.localdate())
        self.assertEqual(Mediciones(self.ashley, inicio, fin).medir('COLABORACIONES'), 1.0)

    def test_entre_areas_solo_lo_coordina_un_supervisor(self):
        self.como(self.erlin)
        r = self.c.post('/api/desempeno/colaboraciones/', {'ayudante': self.dev.id, 'descripcion': 'Ayuda con la web del cliente'})
        self.assertEqual(r.status_code, 400)
        nombres = [p['nombre'] for p in self.c.get('/api/desempeno/personas/').json()]
        self.assertIn('Ashley Morel', nombres)
        self.assertNotIn('Juli Dev', nombres)
        self.como(self.vladi)
        r = self.c.post('/api/desempeno/colaboraciones/', {'ayudante': self.dev.id, 'descripcion': 'Ayuda con la web del cliente'})
        self.assertEqual(r.status_code, 201, r.content)

    def test_registrar_apoyo_dado(self):
        self.como(self.ashley)
        r = self.c.post('/api/desempeno/colaboraciones/', {'solicitante': self.erlin.id, 'ya_realizada': True,
                                                           'descripcion': 'Le expliqué cómo programar en Meta',
                                                           'resultado': 'Programó sola la campaña'})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Colaboracion.objects.get().estado, 'REALIZADA')
        self.assertTrue(Notificacion.objects.filter(destinatario=self.vladi, tipo='COLABORACION').exists())


class KpiNuevosTests(Base):
    def test_fuera_de_plazo_y_dias_de_ejecucion(self):
        hoy = timezone.localdate()
        inicio, fin = rango_del_mes(hoy)
        ayer = hoy - timedelta(days=1)
        if ayer < inicio:
            return  # el día 1 no hay «ayer» dentro del mes
        self.tarea(self.erlin, dias=-1)                                         # vencida sin entregar
        ahora = timezone.now()
        self.tarea(self.erlin, dias=0, estado='COMPLETADA', fecha_completada=hoy,
                   fecha_inicio_trabajo=ahora - timedelta(days=2), fecha_entrega_real=ahora)
        m = Mediciones(self.erlin, inicio, fin)
        self.assertEqual(m.medir('FUERA_DE_PLAZO'), 1.0)
        self.assertEqual(m.medir('DIAS_EJECUCION'), 2.0)
