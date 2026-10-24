"""Pruebas de las mejoras de octubre 2026: seguridad, evidencias, historial, avisos, recurrentes y tablero."""
import shutil
import tempfile
from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import Departamento
from apps.kpis.models import KPIAsignado, PlantillaKPI
from apps.organizacion.models import PuestoDeTrabajo
from .models import ConfiguracionDesempeno, EvidenciaArchivo, Notificacion, Tarea, TareaRecurrente
from .puntaje import calcular_ranking
from .servicios import fechas_de, generar_recurrentes

MEDIA = tempfile.mkdtemp()
JPG = (b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00' + b'\x08' * 64 + b'\xff\xd9')


def foto(nombre='foto.jpg'):
    return SimpleUploadedFile(nombre, JPG, content_type='image/jpeg')


@override_settings(MEDIA_ROOT=MEDIA)
class Base(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.mkt = Departamento.objects.create(nombre="Marketing")
        self.tec = Departamento.objects.create(nombre="Tecnología")
        self.p_gerente = PuestoDeTrabajo.objects.create(nombre="Gerente de Marketing", departamento=self.mkt)
        self.p_cm = PuestoDeTrabajo.objects.create(nombre="Community Manager", departamento=self.mkt, supervisor=self.p_gerente)
        self.p_dev = PuestoDeTrabajo.objects.create(nombre="Desarrollador", departamento=self.tec)
        self.vladi = self._u("vladi", self.p_gerente, "Vladimir", "Gómez")
        self.erlin = self._u("erlin", self.p_cm, "Erlin", "Pérez")
        self.ashley = self._u("ashley", self.p_cm, "Ashley", "Morel")
        self.dev = self._u("dev", self.p_dev, "Juli", "Dev")
        self.osiris = self._u("osiris", None, "Osiris", "Cruz")
        self.osiris.is_staff = True
        self.osiris.save()
        self.osiris.groups.add(Group.objects.get_or_create(name="Administrador")[0])
        self.c = APIClient()

    def _u(self, username, puesto, first='', last=''):
        u = User.objects.create_user(username, email=f"{username}@adzone.marketing", password="Clave-Segura-2026",
                                     first_name=first, last_name=last)
        u.perfil.puesto_trabajo = puesto
        u.perfil.save()
        return u

    def como(self, u):
        self.c.force_authenticate(u)

    def tarea(self, u, dias=3, **kw):
        return Tarea.objects.create(titulo="Post", colaborador=u, fecha_limite=timezone.localdate() + timedelta(days=dias), **kw)


class SeguridadTests(Base):
    def test_solo_admin_cambia_departamentos_puestos_y_plantillas(self):
        self.como(self.erlin)
        self.assertEqual(self.c.get('/api/departamentos/').status_code, 200)
        self.assertEqual(self.c.post('/api/departamentos/', {'nombre': 'X'}).status_code, 403)
        self.assertEqual(self.c.delete(f'/api/departamentos/{self.tec.id}/').status_code, 403)
        self.assertEqual(self.c.patch(f'/api/organizacion/puestos-trabajo/{self.p_cm.id}/', {'nombre': 'Jefe'}).status_code, 403)
        self.assertEqual(self.c.post('/api/kpis/plantillas-kpi/', {'nombre': 'X'}).status_code, 403)
        self.assertEqual(self.c.get('/api/organizacion/usuarios/').status_code, 403)
        self.como(self.osiris)
        self.assertEqual(self.c.post('/api/departamentos/', {'nombre': 'Adzone TV'}).status_code, 201)

    def test_nadie_valida_su_propia_tarea_ni_siendo_admin(self):
        propia = self.tarea(self.osiris, estado='EN_REVISION', fecha_completada=timezone.localdate())
        self.como(self.osiris)
        r = self.c.post(f'/api/desempeno/tareas/{propia.id}/validar/', {'calificacion_calidad': 5})
        self.assertEqual(r.status_code, 403)
        self.assertNotIn(propia.id, [t['id'] for t in self.c.get('/api/desempeno/tareas/?ambito=por_validar').data])

    def test_evidencia_solo_la_ven_el_colaborador_y_quien_lo_gestiona(self):
        t = self.tarea(self.erlin)
        self.como(self.erlin)
        r = self.c.post(f'/api/desempeno/tareas/{t.id}/entregar/', {'archivos': [foto('a.jpg'), foto('b.jpg')]}, format='multipart')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data['evidencias']), 2)
        url = r.data['evidencias'][0]['url']
        self.assertTrue(url.startswith('/api/desempeno/evidencias/'))
        self.assertEqual(self.c.get(url).status_code, 200)
        self.como(self.vladi)
        self.assertEqual(self.c.get(url).status_code, 200)
        self.como(self.ashley)                       # compañera, no supervisora
        self.assertEqual(self.c.get(url).status_code, 404)
        self.como(self.dev)
        self.assertEqual(self.c.get(url).status_code, 404)
        self.c.logout()
        self.c.force_authenticate(None)
        self.assertIn(self.c.get(url).status_code, (401, 403))
        # El archivo no conserva el nombre original en el disco
        self.assertNotIn('a.jpg', EvidenciaArchivo.objects.first().archivo.name)

    def test_no_acepta_archivos_peligrosos_ni_demasiados(self):
        t = self.tarea(self.erlin)
        self.como(self.erlin)
        malo = SimpleUploadedFile('virus.php', b'<?php echo 1;', content_type='image/jpeg')
        self.assertEqual(self.c.post(f'/api/desempeno/tareas/{t.id}/entregar/', {'archivos': [malo]}, format='multipart').status_code, 400)
        muchas = [foto(f'{i}.jpg') for i in range(7)]
        self.assertEqual(self.c.post(f'/api/desempeno/tareas/{t.id}/entregar/', {'archivos': muchas}, format='multipart').status_code, 400)

    def test_no_se_queda_sin_administradores(self):
        self.como(self.osiris)
        r = self.c.patch(f'/api/organizacion/usuarios/{self.osiris.id}/', {'roles_asignados': ['Colaborador']}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.c.patch(f'/api/organizacion/usuarios/{self.osiris.id}/', {'is_active': False}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.c.delete(f'/api/organizacion/usuarios/{self.osiris.id}/').status_code, 400)

    def test_usuarios_contrasena_segura_y_roles(self):
        self.como(self.osiris)
        debil = self.c.post('/api/organizacion/usuarios/', {'username': 'nuevo', 'email': 'n@a.com', 'password': '123'}, format='json')
        self.assertEqual(debil.status_code, 400)
        r = self.c.post('/api/organizacion/usuarios/', {
            'username': 'Helen', 'email': 'helen@adzone.marketing', 'password': 'Gerencia-2026!',
            'first_name': 'Helen', 'puesto_trabajo_id': self.p_gerente.id, 'roles_asignados': ['Administrador']}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        helen = User.objects.get(username='helen')
        self.assertTrue(helen.is_staff)
        repetido = self.c.post('/api/organizacion/usuarios/', {'username': 'otro', 'email': 'HELEN@adzone.marketing', 'password': 'Gerencia-2026!'}, format='json')
        self.assertEqual(repetido.status_code, 400)

    def test_login_con_correo_y_cambiar_clave(self):
        c = APIClient()
        self.assertEqual(c.post('/api/auth/login/', {'username': 'ERLIN@adzone.marketing', 'password': 'mala'}, format='json').status_code, 400)
        r = c.post('/api/auth/login/', {'username': 'erlin@adzone.marketing', 'password': 'Clave-Segura-2026'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['user']['puesto'], 'Community Manager')
        self.assertFalse(r.data['user']['es_administrador'])
        self.assertEqual(c.post('/api/auth/cambiar-clave/', {'actual': 'x', 'nueva': 'Otra-Clave-2026'}, format='json').status_code, 400)
        self.assertEqual(c.post('/api/auth/cambiar-clave/', {'actual': 'Clave-Segura-2026', 'nueva': '1234'}, format='json').status_code, 400)
        self.assertEqual(c.post('/api/auth/cambiar-clave/', {'actual': 'Clave-Segura-2026', 'nueva': 'Otra-Clave-2026'}, format='json').status_code, 200)
        self.assertTrue(c.get('/api/auth/session/').data['isAuthenticated'])  # sigue con sesión

    def test_sesion_sin_login_no_falla(self):
        r = APIClient().get('/api/auth/session/')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data['isAuthenticated'])

    def test_organigrama_sin_ciclos(self):
        self.como(self.osiris)
        r = self.c.patch(f'/api/organizacion/puestos-trabajo/{self.p_gerente.id}/', {'supervisor': self.p_cm.id}, format='json')
        self.assertEqual(r.status_code, 400)
        arbol = self.c.get('/api/organizacion/organigrama/').data
        gerente = next(n for n in arbol['raices'] if n['nombre'] == 'Gerente de Marketing')
        self.assertEqual(gerente['hijos'][0]['nombre'], 'Community Manager')
        self.assertEqual(len(gerente['hijos'][0]['personas']), 2)
        self.assertEqual(arbol['sin_puesto'], 1)


class FlujoTests(Base):
    def test_flujo_completo_con_historial_y_avisos(self):
        self.como(self.vladi)
        r = self.c.post('/api/desempeno/tareas/', {'titulo': 'Reel Zunnox', 'colaborador': self.erlin.id,
                                                   'fecha_limite': str(timezone.localdate() + timedelta(days=2)), 'prioridad': 'ALTA'})
        self.assertEqual(r.status_code, 201)
        tid = r.data['id']
        self.assertEqual(Notificacion.objects.get(destinatario=self.erlin).tipo, 'ASIGNADA')

        self.como(self.erlin)
        self.c.post(f'/api/desempeno/tareas/{tid}/iniciar/')
        self.c.post(f'/api/desempeno/tareas/{tid}/entregar/', {'evidencia_nota': 'Listo', 'archivos': [foto()]}, format='multipart')
        self.assertTrue(Notificacion.objects.filter(destinatario=self.vladi, tipo='ENTREGADA').exists())

        self.como(self.vladi)
        self.assertEqual(self.c.post(f'/api/desempeno/tareas/{tid}/rechazar/', {'comentario_revision': 'no'}).status_code, 400)
        r = self.c.post(f'/api/desempeno/tareas/{tid}/rechazar/', {'comentario_revision': 'Falta el logo'})
        self.assertEqual(r.data['rondas_revision'], 1)

        self.como(self.erlin)
        r = self.c.post(f'/api/desempeno/tareas/{tid}/entregar/', {'evidencia_nota': 'Con logo', 'archivos': [foto()]}, format='multipart')
        self.assertEqual([e['ronda'] for e in r.data['evidencias']], [0, 1])

        self.como(self.vladi)
        r = self.c.post(f'/api/desempeno/tareas/{tid}/validar/', {'calificacion_calidad': 4})
        self.assertEqual(r.data['estado'], 'COMPLETADA')
        self.assertFalse(r.data['a_la_primera'])
        historial = [h['accion'] for h in self.c.get(f'/api/desempeno/tareas/{tid}/historial/').data]
        self.assertEqual(historial, ['CREADA', 'INICIADA', 'ENTREGADA', 'DEVUELTA', 'ENTREGADA', 'VALIDADA'])
        self.assertEqual(self.c.patch(f'/api/desempeno/tareas/{tid}/', {'titulo': 'x'}).status_code, 403)
        self.assertEqual(self.c.delete(f'/api/desempeno/tareas/{tid}/').status_code, 403)

        # Reabrir por error de validación: deja de contar y vuelve a revisión
        self.assertEqual(self.c.post(f'/api/desempeno/tareas/{tid}/reabrir/', {}).status_code, 400)
        r = self.c.post(f'/api/desempeno/tareas/{tid}/reabrir/', {'motivo': 'Califiqué la tarea equivocada'})
        self.assertEqual(r.data['estado'], 'EN_REVISION')
        self.assertIsNone(r.data['calificacion_calidad'])

        self.como(self.erlin)
        avisos = self.c.get('/api/desempeno/notificaciones/').data
        self.assertEqual(avisos['no_leidas'], 4)  # asignada, devuelta, validada, reabierta
        self.c.post('/api/desempeno/notificaciones/leer/', {}, format='json')
        self.assertEqual(self.c.get('/api/desempeno/notificaciones/').data['no_leidas'], 0)

    def test_entrega_sin_supervisor_avisa_a_los_administradores(self):
        t = self.tarea(self.dev)
        self.como(self.dev)
        self.c.post(f'/api/desempeno/tareas/{t.id}/entregar/', {'evidencia_nota': 'Hecho'})
        self.assertTrue(Notificacion.objects.filter(destinatario=self.osiris, tipo='ENTREGADA').exists())

    def test_cancelar(self):
        t = self.tarea(self.erlin)
        self.como(self.erlin)
        self.assertEqual(self.c.post(f'/api/desempeno/tareas/{t.id}/cancelar/').status_code, 403)
        self.como(self.vladi)
        self.assertEqual(self.c.post(f'/api/desempeno/tareas/{t.id}/cancelar/', {'motivo': 'El cliente la canceló'}).data['estado'], 'CANCELADA')

    def test_kpi_manual_no_se_vincula_a_tareas(self):
        plantilla = PlantillaKPI.objects.create(nombre="Seguidores")
        manual = KPIAsignado.objects.create(puesto_trabajo=self.p_cm, plantilla_kpi=plantilla, ponderacion=50, objetivo_meta="100")
        self.como(self.vladi)
        r = self.c.post('/api/desempeno/tareas/', {'titulo': 'x', 'colaborador': self.erlin.id,
                                                   'fecha_limite': '2099-01-01', 'kpi_asignado': manual.id})
        self.assertEqual(r.status_code, 400)


class PuntajeTests(Base):
    def test_pesos_y_bono_configurables(self):
        hoy = timezone.localdate()
        periodo = hoy.replace(day=1)
        t = self.tarea(self.erlin, dias=0, estado='COMPLETADA', fecha_completada=hoy, calificacion_calidad=5)
        plantilla = PlantillaKPI.objects.create(nombre="Alcance")
        kpi = KPIAsignado.objects.create(puesto_trabajo=self.p_cm, plantilla_kpi=plantilla, ponderacion=100, objetivo_meta="10")
        from .models import ResultadoKPI
        ResultadoKPI.objects.create(kpi_asignado=kpi, colaborador=self.erlin, periodo=periodo, valor_meta=10, valor_real=5)
        fila = calcular_ranking(periodo)[0]
        self.assertEqual(fila['puntaje_total'], 80.0)       # 0.6*100 + 0.4*50
        self.assertFalse(fila['elegible'])                   # 1 tarea < mínimo 3
        self.assertEqual(fila['bono_sugerido'], 0)           # sin el mínimo, tampoco hay bono
        config = ConfiguracionDesempeno.actual()
        config.peso_tareas = 80
        config.minimo_tareas_empleado_mes = 1
        config.save()
        fila = calcular_ranking(periodo)[0]
        self.assertEqual(fila['puntaje_total'], 90.0)        # 0.8*100 + 0.2*50
        self.assertEqual(fila['bono_sugerido'], 10)
        self.assertTrue(fila['elegible'])
        self.assertEqual(t.a_la_primera, True)

    def test_kpi_automatico_menor_es_mejor_usa_rondas(self):
        hoy = timezone.localdate()
        plantilla = PlantillaKPI.objects.create(nombre="Rondas de revisión", menor_es_mejor=True)
        kpi = KPIAsignado.objects.create(puesto_trabajo=self.p_cm, plantilla_kpi=plantilla, ponderacion=100,
                                         objetivo_meta="3", es_entrada_manual=False, meta_numerica=3)
        for rondas in (0, 2, 5):   # 1, 3 y 6 entregas → promedio 3.33
            self.tarea(self.erlin, dias=0, estado='COMPLETADA', fecha_completada=hoy, kpi_asignado=kpi, rondas_revision=rondas)
        fila = calcular_ranking(hoy.replace(day=1))[0]
        self.assertAlmostEqual(fila['kpis'][0]['valor'], 3.33)
        self.assertAlmostEqual(fila['kpis'][0]['cumplimiento'], 90.09, places=1)

    def test_configuracion_solo_admin(self):
        self.como(self.erlin)
        self.assertEqual(self.c.get('/api/desempeno/configuracion/').data['peso_tareas'], 60)
        self.assertEqual(self.c.patch('/api/desempeno/configuracion/', {'peso_tareas': 90}, format='json').status_code, 403)
        self.como(self.osiris)
        r = self.c.patch('/api/desempeno/configuracion/', {'peso_tareas': 70, 'tramos_bono': [{'desde': 80, 'porcentaje': 5}, {'desde': 95, 'porcentaje': 12}]}, format='json')
        self.assertEqual(r.data['peso_kpis'], 30)
        self.assertEqual(r.data['tramos_bono'][0]['desde'], 95)
        self.assertEqual(self.c.patch('/api/desempeno/configuracion/', {'peso_tareas': 150}, format='json').status_code, 400)

    def test_exportar_ranking_csv(self):
        hoy = timezone.localdate()
        self.tarea(self.erlin, dias=0, estado='COMPLETADA', fecha_completada=hoy, calificacion_calidad=4)
        self.como(self.osiris)
        r = self.c.get(f'/api/desempeno/ranking/exportar/?mes={hoy:%Y-%m}')
        self.assertEqual(r.status_code, 200)
        contenido = r.content.decode('utf-8-sig')
        self.assertIn('Erlin Pérez', contenido)
        self.assertIn('Bono sugerido', contenido)
        self.como(self.vladi)
        self.assertEqual(self.c.get(f'/api/desempeno/ranking/exportar/?mes={hoy:%Y-%m}').status_code, 403)

    def test_planilla_de_kpis_manuales_en_lote(self):
        plantilla = PlantillaKPI.objects.create(nombre="Seguidores ganados")
        kpi = KPIAsignado.objects.create(puesto_trabajo=self.p_cm, plantilla_kpi=plantilla, ponderacion=40,
                                         objetivo_meta="500", meta_numerica=500)
        mes = timezone.localdate().strftime('%Y-%m')
        self.como(self.osiris)
        planilla = self.c.get(f'/api/desempeno/resultados-kpi/planilla/?mes={mes}').data
        self.assertEqual(sorted(f['nombre'] for f in planilla['filas']), ['Ashley Morel', 'Erlin Pérez'])
        self.assertEqual(planilla['filas'][0]['kpis'][0]['valor_meta'], 500)
        r = self.c.post('/api/desempeno/resultados-kpi/lote/', {'mes': mes, 'resultados': [
            {'colaborador': self.erlin.id, 'kpi_asignado': kpi.id, 'valor_meta': 500, 'valor_real': 450},
            {'colaborador': self.ashley.id, 'kpi_asignado': kpi.id, 'valor_meta': 500, 'valor_real': 'abc'},
            {'colaborador': self.dev.id, 'kpi_asignado': kpi.id, 'valor_meta': 500, 'valor_real': 1},
        ]}, format='json')
        self.assertEqual(r.data['guardados'], 1)
        self.assertEqual(len(r.data['errores']), 2)
        # Vacío borra el valor del mes
        r = self.c.post('/api/desempeno/resultados-kpi/lote/', {'mes': mes, 'resultados': [
            {'colaborador': self.erlin.id, 'kpi_asignado': kpi.id, 'valor_meta': 500, 'valor_real': ''}]}, format='json')
        self.assertEqual(r.data['borrados'], 1)

    def test_tablero_segun_rol(self):
        self.tarea(self.erlin, dias=-2)  # vencida
        self.tarea(self.ashley, estado='EN_REVISION', fecha_completada=timezone.localdate())
        self.como(self.erlin)
        t = self.c.get('/api/desempeno/tablero/').data
        self.assertEqual(t['rol'], 'colaborador')
        self.assertNotIn('equipo', t)
        self.como(self.vladi)
        t = self.c.get('/api/desempeno/tablero/').data
        self.assertEqual(t['rol'], 'supervisor')
        self.assertEqual(t['equipo']['por_validar'], 1)
        self.assertEqual(t['atencion'][0]['nombre'], 'Erlin Pérez')
        self.assertNotIn('departamentos', t)
        self.como(self.osiris)
        t = self.c.get('/api/desempeno/tablero/').data
        self.assertEqual(t['rol'], 'administrador')
        self.assertEqual({d['nombre'] for d in t['departamentos']}, {'Marketing', 'Tecnología'})


class RecurrentesTests(Base):
    def test_fechas_semanales_y_mensuales(self):
        semanal = TareaRecurrente(frecuencia='SEMANAL', dia_semana=4)
        self.assertEqual(fechas_de(semanal, date(2026, 10, 1), date(2026, 10, 31)),
                         [date(2026, 10, 2), date(2026, 10, 9), date(2026, 10, 16), date(2026, 10, 23), date(2026, 10, 30)])
        mensual = TareaRecurrente(frecuencia='MENSUAL', dia_mes=28)
        self.assertEqual(fechas_de(mensual, date(2026, 11, 1), date(2027, 2, 28)),
                         [date(2026, 11, 28), date(2026, 12, 28), date(2027, 1, 28), date(2027, 2, 28)])

    def test_genera_una_vez_y_avisa(self):
        hoy = date(2026, 10, 19)  # lunes
        rec = TareaRecurrente.objects.create(titulo="Programar Adzone TV", colaborador=self.erlin, creada_por=self.vladi,
                                             frecuencia='SEMANAL', dia_semana=4, inicio=hoy)
        self.assertEqual(generar_recurrentes(hoy), 1)        # viernes 23 (se crean hasta una semana adelante: 26)
        self.assertEqual(generar_recurrentes(hoy), 0)        # no duplica
        self.assertEqual(generar_recurrentes(hoy + timedelta(days=7)), 1)   # viernes 30
        self.assertEqual(sorted(str(t.fecha_limite) for t in rec.tareas.all()), ['2026-10-23', '2026-10-30'])
        self.assertEqual(Notificacion.objects.filter(destinatario=self.erlin, tipo='ASIGNADA').count(), 2)

    def test_solo_el_supervisor_programa(self):
        self.como(self.ashley)
        r = self.c.post('/api/desempeno/recurrentes/', {'titulo': 'x', 'colaborador': self.erlin.id, 'frecuencia': 'SEMANAL',
                                                        'dia_semana': 0, 'inicio': '2026-10-01'})
        self.assertEqual(r.status_code, 403)
        self.como(self.vladi)
        r = self.c.post('/api/desempeno/recurrentes/', {'titulo': 'Parrilla semanal', 'colaborador': self.erlin.id,
                                                        'frecuencia': 'MENSUAL', 'dia_mes': 31, 'inicio': '2026-10-01'})
        self.assertEqual(r.status_code, 400)                 # día 31 no existe en todos los meses
        r = self.c.post('/api/desempeno/recurrentes/', {'titulo': 'Parrilla semanal', 'colaborador': self.erlin.id,
                                                        'frecuencia': 'SEMANAL', 'dia_semana': 0, 'inicio': str(timezone.localdate())}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['frecuencia_texto'], 'Cada lunes')
        self.assertTrue(Tarea.objects.filter(recurrencia_id=r.data["id"]).exists())


class RecordarYPedirTrabajoTests(Base):
    def test_supervisor_recuerda_una_vez_por_hora(self):
        t = self.tarea(self.erlin)
        self.como(self.ashley)                                   # compañera: no puede
        self.assertEqual(self.c.post(f'/api/desempeno/tareas/{t.id}/recordar/').status_code, 404)
        self.como(self.vladi)
        self.assertEqual(self.c.post(f'/api/desempeno/tareas/{t.id}/recordar/', {'mensaje': 'El cliente la espera hoy'}).status_code, 200)
        self.assertEqual(self.c.post(f'/api/desempeno/tareas/{t.id}/recordar/').status_code, 429)
        aviso = Notificacion.objects.get(destinatario=self.erlin, tipo='RECORDATORIO')
        self.assertEqual(aviso.remitente, self.vladi)
        self.assertEqual(aviso.mensaje, 'El cliente la espera hoy')
        validada = self.tarea(self.erlin, estado='COMPLETADA', fecha_completada=timezone.localdate())
        self.assertEqual(self.c.post(f'/api/desempeno/tareas/{validada.id}/recordar/').status_code, 400)

    def test_pedir_trabajo_solo_sin_pendientes(self):
        t = self.tarea(self.erlin)
        self.como(self.erlin)
        self.assertEqual(self.c.post('/api/desempeno/pedir-trabajo/').status_code, 400)
        t.estado = 'EN_REVISION'
        t.save()
        r = self.c.post('/api/desempeno/pedir-trabajo/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Vladimir Gómez', r.data['message'])
        self.assertTrue(Notificacion.objects.filter(destinatario=self.vladi, tipo='PIDE_TRABAJO', remitente=self.erlin).exists())
        self.assertEqual(self.c.post('/api/desempeno/pedir-trabajo/').status_code, 400)   # no insiste en 2 h
