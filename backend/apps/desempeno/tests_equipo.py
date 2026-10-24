"""Pruebas de lo que viene de Adzone Team: tareas compartidas, pasos, cliente, carga del equipo y departamentos."""
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.utils import timezone

from apps.core.models import Departamento
from apps.organizacion.models import PuestoDeTrabajo
from .models import Notificacion, PasoTarea, Tarea
from .puntaje import calcular_ranking
from .tests_mejoras import Base


class TareaCompartidaTests(Base):
    def crear(self, **extra):
        self.como(self.vladi)
        datos = {'titulo': 'Campaña de Navidad', 'colaborador': self.erlin.id, 'companeros': [self.ashley.id],
                 'cliente': 'Plaza Bonao', 'prioridad': 'ALTA',
                 'fecha_limite': (timezone.localdate() + timedelta(days=5)).isoformat(),
                 'pasos_texto': ['Idea', 'Diseño', '', 'Publicar']}
        datos.update(extra)
        return self.c.post('/api/desempeno/tareas/', datos, format='json')

    def test_crear_con_companeros_pasos_y_cliente(self):
        r = self.crear()
        self.assertEqual(r.status_code, 201, r.content)
        d = r.json()
        self.assertEqual(d['cliente'], 'Plaza Bonao')
        self.assertEqual(d['companeros'], [self.ashley.id])
        self.assertEqual([p['texto'] for p in d['pasos']], ['Idea', 'Diseño', 'Publicar'])
        self.assertEqual(d['progreso'], {'hechos': 0, 'total': 3})
        # Los dos reciben el aviso
        self.assertTrue(Notificacion.objects.filter(destinatario=self.ashley, tipo='ASIGNADA').exists())
        self.assertTrue(Notificacion.objects.filter(destinatario=self.erlin, tipo='ASIGNADA').exists())

    def test_no_se_suma_a_alguien_que_no_gestiona(self):
        r = self.crear(companeros=[self.dev.id])
        self.assertEqual(r.status_code, 403)

    def test_el_companero_ve_marca_pasos_y_entrega(self):
        tid = self.crear().json()['id']
        self.como(self.ashley)
        mias = self.c.get('/api/desempeno/tareas/?ambito=mias').json()
        ids = [t['id'] for t in (mias['results'] if isinstance(mias, dict) else mias)]
        self.assertIn(tid, ids)
        paso = PasoTarea.objects.filter(tarea_id=tid).first()
        r = self.c.post(f'/api/desempeno/tareas/{tid}/pasos/{paso.id}/', {'hecho': True}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['progreso']['hechos'], 1)
        self.assertEqual(r.json()['estado'], 'EN_PROGRESO')  # marcar un paso es empezar
        r = self.c.post(f'/api/desempeno/tareas/{tid}/entregar/', {'evidencia_nota': 'Listo'}, format='multipart')
        self.assertEqual(r.status_code, 200, r.content)
        # Nadie del equipo de la tarea puede validarla
        r = self.c.post(f'/api/desempeno/tareas/{tid}/validar/', {'calificacion_calidad': 5})
        self.assertEqual(r.status_code, 403)

    def test_quien_no_participa_no_marca_pasos(self):
        tid = self.crear().json()['id']
        paso = PasoTarea.objects.filter(tarea_id=tid).first()
        self.como(self.dev)
        self.assertEqual(self.c.post(f'/api/desempeno/tareas/{tid}/pasos/{paso.id}/', {}, format='json').status_code, 404)
        self.como(self.vladi)  # el supervisor la ve, pero no la trabaja
        self.assertEqual(self.c.post(f'/api/desempeno/tareas/{tid}/pasos/{paso.id}/', {}, format='json').status_code, 403)

    def test_editar_pasos_conserva_los_hechos(self):
        tid = self.crear().json()['id']
        primero = PasoTarea.objects.filter(tarea_id=tid).first()
        primero.hecho = True
        primero.save()
        self.como(self.vladi)
        r = self.c.patch(f'/api/desempeno/tareas/{tid}/', {'pasos_texto': ['Idea', 'Diseño']}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['progreso'], {'hechos': 1, 'total': 2})

    def test_la_tarea_validada_cuenta_para_los_dos(self):
        hace = timezone.localdate() - timedelta(days=1)
        t = Tarea.objects.create(titulo='Video', colaborador=self.erlin, fecha_limite=hace, estado='COMPLETADA',
                                 fecha_completada=hace, calificacion_calidad=5, validada_por=self.vladi)
        t.companeros.add(self.ashley)
        filas = {f['colaborador_id']: f for f in calcular_ranking(hace)}
        self.assertEqual(filas[self.erlin.id]['tareas']['completadas'], 1)
        self.assertEqual(filas[self.ashley.id]['tareas']['completadas'], 1)
        self.assertEqual(filas[self.ashley.id]['puntaje_tareas'], 100)


class CargaEquipoTests(Base):
    def test_estados_de_cada_persona(self):
        self.tarea(self.erlin, dias=-2)                         # vencida
        self.tarea(self.ashley, dias=2, estado='EN_PROGRESO')   # trabajando
        self.como(self.vladi)
        r = self.c.get('/api/desempeno/equipo/carga/')
        self.assertEqual(r.status_code, 200, r.content)
        estados = {p['id']: p['estado'] for p in r.json()['personas']}
        self.assertEqual(estados[self.erlin.id], 'vencida')
        self.assertEqual(estados[self.ashley.id], 'trabajando')
        self.assertNotIn(self.dev.id, estados)                  # no es de su equipo
        self.assertEqual(r.json()['personas'][0]['id'], self.erlin.id)  # lo urgente primero

    def test_quien_pide_trabajo_aparece_marcado(self):
        self.como(self.erlin)
        self.assertEqual(self.c.post('/api/desempeno/pedir-trabajo/').status_code, 200)
        self.como(self.vladi)
        personas = {p['id']: p for p in self.c.get('/api/desempeno/equipo/carga/').json()['personas']}
        self.assertEqual(personas[self.erlin.id]['estado'], 'pide_trabajo')
        self.assertEqual(personas[self.ashley.id]['estado'], 'libre')

    def test_un_colaborador_no_ve_la_carga(self):
        self.como(self.erlin)
        self.assertEqual(self.c.get('/api/desempeno/equipo/carga/').status_code, 403)


class DepartamentosOficialesTests(Base):
    def test_sin_aplicar_no_cambia_nada_y_con_aplicar_ubica_puestos(self):
        viejo = Departamento.objects.create(nombre='Gerencia de Eventos e Impresiones')
        rot = PuestoDeTrabajo.objects.create(nombre='Técnico de Instalación y Rotulación', departamento=viejo)
        call_command('departamentos_oficiales', stdout=StringIO())
        self.assertFalse(Departamento.objects.filter(nombre='Adzone TV').exists())
        call_command('departamentos_oficiales', '--aplicar', stdout=StringIO())
        self.assertEqual(Departamento.objects.filter(nombre__in=[
            'Gerencia', 'Marketing', 'Audiovisual', 'Adzone TV', 'Impresión', 'Administración', 'Tecnología']).count(), 7)
        rot.refresh_from_db()
        self.assertEqual(rot.departamento.nombre, 'Impresión')
        self.assertEqual(rot.departamento.color, '#8a4300')
        self.assertFalse(Departamento.objects.filter(pk=viejo.pk).exists())  # quedó vacío y se borró
        self.assertTrue(Departamento.objects.filter(pk=self.tec.pk).exists())
