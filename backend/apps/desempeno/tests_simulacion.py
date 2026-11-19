"""
Simulación de un día de empresa: gerencia, supervisor y empleados actúan por la API real, con reloj simulado.

No se detiene en el primer fallo: cada comprobación se anota y al final se imprime el informe completo
(`python manage.py test apps.desempeno.tests_simulacion`).
"""
from datetime import datetime, timedelta
from unittest import mock

from django.utils import timezone

from apps.asistencia.models import Marcaje
from .models import Notificacion, Tarea
from .tests_mejoras import Base, foto

DIA = datetime(2026, 10, 26)  # lunes
T = '/api/desempeno/tareas/'


class DiaDeEmpresa(Base):
    def setUp(self):
        super().setUp()
        self.reloj = None
        self.informe = []   # (ok, rol, qué, detalle)
        self.fallos = []

    # ---------------------------------------------------------------- utilidades
    def hora(self, hhmm):
        h, m = map(int, hhmm.split(':'))
        self.reloj = timezone.make_aware(DIA.replace(hour=h, minute=m))
        return mock.patch.object(timezone, 'now', side_effect=lambda: self.reloj)

    def chk(self, rol, que, condicion, detalle=''):
        self.informe.append((bool(condicion), rol, que))
        if not condicion:
            self.fallos.append(f'[{rol}] {que} {detalle}'.strip())

    def llamar(self, usuario, metodo, url, datos=None, formato='json'):
        self.como(usuario)
        return getattr(self.c, metodo)(url, datos, format=formato) if metodo != 'get' else self.c.get(url, datos)

    def estado_de(self, usuario, tid):
        return self.llamar(usuario, 'get', f'{T}{tid}/').json().get('estado')

    # ---------------------------------------------------------------- el día
    def test_un_dia_completo(self):
        with self.hora('07:50'):
            self.mañana()
            self.reparto_de_tareas()
        with self.hora('09:30'):
            self.trabajo_de_la_mañana()
        with self.hora('12:00'):
            self.almuerzo()
        with self.hora('13:30'):
            self.tarde()
        with self.hora('17:05'):
            self.cierre()
        self.informe_final()

    def mañana(self):
        # Entradas: Erlin a tiempo, Ashley tarde (8:40), Juli (desarrollo) a tiempo, Vladi (supervisor) a tiempo
        for quien, hhmm in ((self.vladi, '07:55'), (self.erlin, '07:58'), (self.dev, '08:02'), (self.ashley, '08:40')):
            with self.hora(hhmm):
                r = self.llamar(quien, 'post', '/api/asistencia/marcar/', {'tipo': 'ENTRADA'})
                self.chk(quien.username, 'marca entrada', r.status_code == 201, r.content[:150])
                r = self.llamar(quien, 'post', '/api/asistencia/marcar/', {'tipo': 'ENTRADA'})
                self.chk(quien.username, 'no puede marcar entrada dos veces', r.status_code == 400)
        with self.hora('09:30'):
            e = self.llamar(self.ashley, 'get', '/api/asistencia/estado/').json()
            self.chk('ashley', 'su tardanza es de 40 min', e['hoy']['tardanza'] == 40, str(e['hoy']))
            self.chk('ashley', 'trabajado sube con el reloj (50 min a las 9:30)', e['hoy']['trabajados'] == 50, str(e['hoy']['trabajados']))
            e = self.llamar(self.erlin, 'get', '/api/asistencia/estado/').json()
            self.chk('erlin', 'a tiempo, trabajado 92 min a las 9:30', e['hoy']['llegada'] == 'A_TIEMPO' and e['hoy']['trabajados'] == 92, str(e['hoy']))
            h = self.llamar(self.vladi, 'get', '/api/asistencia/hoy/')
            self.chk('vladi', 'el supervisor ve la asistencia de su equipo', h.status_code == 200, h.content[:150])
            h = self.llamar(self.erlin, 'get', '/api/asistencia/hoy/')
            self.chk('erlin', 'un empleado NO ve la asistencia del equipo', h.status_code == 403, str(h.status_code))

    def reparto_de_tareas(self):
        fin = (timezone.localdate() + timedelta(days=3)).isoformat()
        r = self.llamar(self.vladi, 'post', T, {
            'titulo': 'Campaña de Navidad', 'colaborador': self.erlin.id, 'companeros': [self.ashley.id], 'cliente': 'Plaza Bonao',
            'prioridad': 'ALTA', 'fecha_limite': fin, 'pasos_texto': ['Idea', 'Diseño', 'Publicar']})
        self.chk('vladi', 'asigna tarea compartida a Erlin y Ashley', r.status_code == 201, r.content[:200])
        self.t_campana = r.json()['id']
        r = self.llamar(self.vladi, 'post', T, {'titulo': 'Calendario de enero', 'colaborador': self.ashley.id, 'prioridad': 'MEDIA', 'fecha_limite': fin})
        self.chk('vladi', 'asigna tarea individual a Ashley', r.status_code == 201, r.content[:200])
        self.t_calendario = r.json()['id']
        r = self.llamar(self.vladi, 'post', T, {'titulo': 'Informe', 'colaborador': self.dev.id, 'fecha_limite': fin})
        self.chk('vladi', 'NO puede asignar a otro departamento', r.status_code in (403, 400), str(r.status_code))
        r = self.llamar(self.erlin, 'post', T, {'titulo': 'Me la asigno', 'colaborador': self.ashley.id, 'fecha_limite': fin})
        self.chk('erlin', 'un empleado NO asigna tareas a compañeros', r.status_code == 403, str(r.status_code))
        r = self.llamar(self.osiris, 'post', T, {'titulo': 'API de reportes', 'colaborador': self.dev.id, 'prioridad': 'ALTA', 'fecha_limite': fin})
        self.chk('osiris', 'gerencia asigna a Tecnología', r.status_code == 201, r.content[:200])
        self.t_api = r.json()['id']
        self.chk('erlin', 'recibe el aviso de tarea asignada', Notificacion.objects.filter(destinatario=self.erlin, tipo='ASIGNADA').exists())
        self.chk('ashley', 'recibe el aviso de tarea asignada', Notificacion.objects.filter(destinatario=self.ashley, tipo='ASIGNADA').exists())

    def trabajo_de_la_mañana(self):
        # Erlin trabaja con el cronómetro
        r = self.llamar(self.erlin, 'post', '/api/tiempo/iniciar/', {'tarea': self.t_campana})
        self.chk('erlin', 'inicia el cronómetro de la campaña', r.status_code == 201, r.content[:150])
        self.chk('erlin', 'la tarea pasa a En progreso al iniciar el cronómetro', self.estado_de(self.erlin, self.t_campana) == 'EN_PROGRESO')
        r = self.llamar(self.ashley, 'post', '/api/tiempo/iniciar/', {'tarea': self.t_calendario})
        self.chk('ashley', 'inicia cronómetro de su calendario', r.status_code == 201, r.content[:150])
        # El que no participa no puede cronometrar ni tocar la tarea
        r = self.llamar(self.dev, 'post', '/api/tiempo/iniciar/', {'tarea': self.t_campana})
        self.chk('dev', 'NO puede cronometrar tarea ajena', r.status_code in (400, 403, 404), str(r.status_code))
        # Pasos
        from .models import PasoTarea
        pasos = list(PasoTarea.objects.filter(tarea_id=self.t_campana).order_by('id'))
        r = self.llamar(self.erlin, 'post', f'{T}{self.t_campana}/pasos/{pasos[0].id}/', {'hecho': True})
        self.chk('erlin', 'marca el paso «Idea»', r.status_code == 200 and r.json()['progreso']['hechos'] == 1, r.content[:150])
        # Ashley se bloquea
        with self.hora('10:00'):
            r = self.llamar(self.ashley, 'post', f'{T}{self.t_calendario}/bloquear/', {'motivo': 'x'})
            self.chk('ashley', 'bloquear exige un motivo real (>=5 letras)', r.status_code == 400)
            r = self.llamar(self.ashley, 'post', f'{T}{self.t_calendario}/bloquear/', {'motivo': 'Espero fotos del cliente'})
            self.chk('ashley', 'bloquea su tarea con motivo', r.status_code == 200 and self.estado_de(self.ashley, self.t_calendario) == 'BLOQUEADA', r.content[:150])
            from apps.tiempo.models import RegistroTiempo
            corriendo = RegistroTiempo.objects.filter(usuario=self.ashley, fin__isnull=True).exists()
            self.chk('ashley', 'al bloquear se detiene su cronómetro', not corriendo)
            self.chk('vladi', 'el supervisor recibe aviso de bloqueo', Notificacion.objects.filter(destinatario=self.vladi, tipo__icontains='BLOQ').exists()
                     or Notificacion.objects.filter(destinatario=self.vladi, titulo__icontains='bloque').exists(),
                     str(list(Notificacion.objects.filter(destinatario=self.vladi).values_list('tipo', 'titulo'))))
            r = self.llamar(self.erlin, 'post', f'{T}{self.t_calendario}/desbloquear/', {})
            self.chk('erlin', 'un compañero ajeno a la tarea NO la desbloquea', r.status_code in (403, 404), str(r.status_code))
            r = self.llamar(self.vladi, 'get', '/api/desempeno/equipo/carga/')
            self.chk('vladi', 'Mi equipo · Ahora carga', r.status_code == 200, r.content[:150])
        with self.hora('10:30'):
            r = self.llamar(self.vladi, 'post', f'{T}{self.t_calendario}/desbloquear/', {'nota': 'Ya llegaron las fotos'})
            self.chk('vladi', 'el supervisor desbloquea', r.status_code == 200 and self.estado_de(self.vladi, self.t_calendario) == 'EN_PROGRESO', r.content[:150])

    def almuerzo(self):
        # Los descansos: pausa con motivo, el tiempo en pausa no cuenta, regreso
        for quien in (self.erlin, self.ashley, self.vladi):
            r = self.llamar(quien, 'post', '/api/asistencia/marcar/', {'tipo': 'PAUSA', 'motivo': 'Almuerzo'})
            self.chk(quien.username, 'marca pausa de almuerzo', r.status_code == 201, r.content[:150])
            e = self.llamar(quien, 'get', '/api/asistencia/estado/').json()
            self.chk(quien.username, 'queda En pausa', e['estado'] == 'EN_PAUSA', e['estado'])
            r = self.llamar(quien, 'post', '/api/asistencia/marcar/', {'tipo': 'PAUSA'})
            self.chk(quien.username, 'no se puede pausar dos veces', r.status_code == 400)
        with self.hora('12:30'):
            e = self.llamar(self.erlin, 'get', '/api/asistencia/estado/').json()
            self.chk('erlin', 'a las 12:30 en pausa: trabajado congelado en 4h02 (242 min), pausa 30', e['hoy']['trabajados'] == 242 and e['hoy']['pausa'] == 30, str(e['hoy']))

    def tarde(self):
        for quien in (self.erlin, self.ashley, self.vladi):
            r = self.llamar(quien, 'post', '/api/asistencia/marcar/', {'tipo': 'REGRESO'})
            self.chk(quien.username, 'regresa del almuerzo', r.status_code == 201, r.content[:150])
        e = self.llamar(self.erlin, 'get', '/api/asistencia/estado/').json()
        self.chk('erlin', 'vuelve a Trabajando y no suma la pausa (242 min a las 13:30)', e['estado'] == 'TRABAJANDO' and e['hoy']['trabajados'] == 242 + 0 and e['hoy']['pausa'] == 90, str(e['hoy']))
        # Erlin entrega con evidencia
        r = self.llamar(self.erlin, 'post', f'{T}{self.t_campana}/entregar/', {'evidencia_nota': 'Arte final listo', 'evidencia_archivos': foto()}, formato='multipart')
        self.chk('erlin', 'entrega con evidencia', r.status_code == 200 and r.json()['estado'] == 'EN_REVISION', r.content[:200])
        r = self.llamar(self.erlin, 'post', f'{T}{self.t_campana}/validar/', {'calificacion_calidad': 5})
        self.chk('erlin', 'NO puede validar su propia tarea', r.status_code == 403, str(r.status_code))
        r = self.llamar(self.dev, 'post', f'{T}{self.t_campana}/validar/', {'calificacion_calidad': 5})
        self.chk('dev', 'alguien de otra área NO valida', r.status_code in (403, 404), str(r.status_code))
        # Supervisor la devuelve, Erlin corrige, se valida
        r = self.llamar(self.vladi, 'post', f'{T}{self.t_campana}/rechazar/', {'comentario_revision': 'Falta el logo en la esquina'})
        self.chk('vladi', 'devuelve la tarea con comentario', r.status_code == 200 and r.json()['estado'] == 'EN_PROGRESO', r.content[:200])
        r = self.llamar(self.erlin, 'post', f'{T}{self.t_campana}/entregar/', {'evidencia_nota': 'Logo agregado'}, formato='multipart')
        self.chk('erlin', 'vuelve a entregar', r.status_code == 200 and r.json()['estado'] == 'EN_REVISION', r.content[:200])
        r = self.llamar(self.vladi, 'post', f'{T}{self.t_campana}/validar/', {'calificacion_calidad': 4, 'comentario_evaluacion': 'Bien'})
        self.chk('vladi', 'valida con calificación 4', r.status_code == 200 and r.json()['estado'] == 'COMPLETADA', r.content[:200])
        # Ashley termina el calendario
        r = self.llamar(self.ashley, 'post', f'{T}{self.t_calendario}/entregar/', {'evidencia_nota': 'Calendario publicado'}, formato='multipart')
        self.chk('ashley', 'entrega su calendario', r.status_code == 200, r.content[:200])
        r = self.llamar(self.vladi, 'post', f'{T}{self.t_calendario}/validar/', {'calificacion_calidad': 5})
        self.chk('vladi', 'valida el calendario', r.status_code == 200, r.content[:200])
        # Sin tareas: piden más trabajo
        r = self.llamar(self.ashley, 'post', '/api/desempeno/pedir-trabajo/')
        self.chk('ashley', 'pide más trabajo al quedar libre', r.status_code == 200, r.content[:200])
        d = self.llamar(self.ashley, 'get', '/api/desempeno/mi-disponibilidad/').json()
        self.chk('ashley', 'queda en espera de asignación', bool(d.get('en_espera') or d.get('espera')), str(d)[:200])
        # Actividad adicional + colaboración
        r = self.llamar(self.ashley, 'post', '/api/desempeno/actividades/', {'fecha': timezone.localdate().isoformat(), 'tipo': 'DOCUMENTACION',
                                                                            'descripcion': 'Ordené la carpeta de marca', 'minutos': 45})
        self.chk('ashley', 'registra actividad adicional', r.status_code == 201, r.content[:200])
        aid = r.json().get('id')
        r = self.llamar(self.erlin, 'post', f'/api/desempeno/actividades/{aid}/validar/', {})
        self.chk('erlin', 'un compañero NO valida la actividad', r.status_code in (403, 404), str(r.status_code))
        r = self.llamar(self.vladi, 'post', f'/api/desempeno/actividades/{aid}/validar/', {'comentario': 'Buen orden'})
        self.chk('vladi', 'valida la actividad adicional', r.status_code == 200 and r.json()['estado'] == 'VALIDADA', r.content[:200])
        r = self.llamar(self.ashley, 'post', '/api/desempeno/colaboraciones/', {'ayudante': self.erlin.id, 'descripcion': 'Ayuda con las medidas del banner'})
        self.chk('ashley', 'pide apoyo a Erlin', r.status_code == 201, r.content[:200])
        cid = r.json().get('id')
        for quien, accion, texto, esperado in ((self.erlin, 'aceptar', '', 'ACEPTADA'), (self.erlin, 'realizar', 'Medidas enviadas y revisadas', 'REALIZADA'),
                                              (self.vladi, 'validar', 'Ok', 'VALIDADA')):
            r = self.llamar(quien, 'post', f'/api/desempeno/colaboraciones/{cid}/accion/', {'accion': accion, 'texto': texto, 'minutos': 20})
            self.chk(quien.username, f'colaboración: {accion}', r.status_code == 200 and r.json()['estado'] == esperado, r.content[:200])
        r = self.llamar(self.ashley, 'post', '/api/desempeno/colaboraciones/', {'ayudante': self.dev.id, 'descripcion': 'Ayuda con el sitio'})
        self.chk('ashley', 'apoyo entre departamentos lo coordina el supervisor (rechaza)', r.status_code == 400, str(r.status_code))
        # Dev trabaja su tarea de gerencia
        r = self.llamar(self.dev, 'post', f'{T}{self.t_api}/iniciar/')
        self.chk('dev', 'inicia la tarea de Gerencia', r.status_code == 200, r.content[:150])

    def cierre(self):
        for quien in (self.erlin, self.ashley, self.vladi, self.dev):
            r = self.llamar(quien, 'post', '/api/asistencia/marcar/', {'tipo': 'SALIDA'})
            self.chk(quien.username, 'marca salida', r.status_code == 201, r.content[:150])
            e = self.llamar(quien, 'get', '/api/asistencia/estado/').json()
            self.chk(quien.username, 'queda Fuera con horas cerradas', e['estado'] == 'FUERA' and e['hoy']['trabajados'] > 0, str(e['hoy']['trabajados']))
        # Tiempo registrado
        r = self.llamar(self.erlin, 'get', '/api/tiempo/semana/')
        self.chk('erlin', 've su semana de tiempo', r.status_code == 200, r.content[:150])
        r = self.llamar(self.erlin, 'get', '/api/desempeno/mi-resumen/')
        self.chk('erlin', 've su resumen de desempeño', r.status_code == 200, r.content[:150])
        r = self.llamar(self.vladi, 'get', '/api/desempeno/ranking/')
        self.chk('vladi', 'el ranking es solo de administración (supervisor recibe 403)', r.status_code == 403, str(r.status_code))
        r = self.llamar(self.osiris, 'get', '/api/desempeno/ranking/')
        self.chk('osiris', 'gerencia ve el ranking', r.status_code == 200, r.content[:150])
        r = self.llamar(self.osiris, 'get', '/api/desempeno/panel/')
        self.chk('osiris', 'gerencia ve el panel', r.status_code == 200, r.content[:150])
        r = self.llamar(self.osiris, 'get', '/api/asistencia/hoy/')
        self.chk('osiris', 'gerencia ve la asistencia de todos', r.status_code == 200 and len(r.json().get('personas', r.json())) >= 4, r.content[:150])
        r = self.llamar(self.erlin, 'get', '/api/desempeno/panel/')
        self.chk('erlin', 'un empleado NO ve el panel gerencial', r.status_code == 403, str(r.status_code))
        # Datos finales
        for t, nota in ((self.t_campana, 'COMPLETADA'), (self.t_calendario, 'COMPLETADA')):
            self.chk('sistema', f'tarea {t} quedó {nota}', Tarea.objects.get(pk=t).estado == nota)
        self.chk('sistema', 'hay marcajes de todas las personas', Marcaje.objects.values('usuario').distinct().count() == 4)

    def informe_final(self):
        ok = sum(1 for o, *_ in self.informe if o)
        print(f'\n===== INFORME DEL DÍA: {ok}/{len(self.informe)} comprobaciones bien =====')
        for fallo in self.fallos:
            print('  ✗', fallo)
        if not self.fallos:
            print('  Todo funcionó.')
        self.assertEqual(self.fallos, [])
