"""Expediente del cliente: tareas vinculadas (también las de antes, por nombre), filtros, trazabilidad, reporte PDF/Excel y logo."""
from datetime import timedelta
from io import BytesIO

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from openpyxl import load_workbook
from rest_framework.test import APIClient

from apps.core.models import Departamento
from apps.desempeno.models import Tarea
from apps.organizacion.models import PuestoDeTrabajo

from .models import Cliente, Proyecto

API = '/api/operaciones/clientes'
PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 64


class ExpedienteTests(TestCase):
    def setUp(self):
        cache.clear()
        mkt = Departamento.objects.get_or_create(nombre='Marketing')[0]
        ger = Departamento.objects.get_or_create(nombre='Gerencia')[0]
        ceo = PuestoDeTrabajo.objects.create(nombre='CEO', departamento=ger)
        jefe = PuestoDeTrabajo.objects.create(nombre='Gerente MKT', departamento=mkt, supervisor=ceo)
        cm = PuestoDeTrabajo.objects.create(nombre='CM', departamento=mkt, supervisor=jefe)
        self.jefe = self._u('jefe', jefe, ['Supervisor'])
        self.ana = self._u('ana', cm)
        self.luis = self._u('luis', cm)
        self.cliente = Cliente.objects.create(nombre='Banco Popular')
        self.otro = Cliente.objects.create(nombre='Plaza Bonao')
        self.proyecto = Proyecto.objects.create(nombre='Campaña Navidad', cliente=self.cliente, departamento=mkt)
        hoy = timezone.localdate()
        self.t1 = Tarea.objects.create(titulo='Arte del banner', cliente='banco popular', colaborador=self.ana, asignada_por=self.jefe, fecha_limite=hoy)
        self.t2 = Tarea.objects.create(titulo='Video', proyecto=self.proyecto, colaborador=self.luis, asignada_por=self.jefe, fecha_limite=hoy,
                                       estado='COMPLETADA', fecha_completada=hoy, validada_por=self.jefe, fecha_validacion=timezone.now())
        Tarea.objects.create(titulo='Otra cosa', cliente='Plaza Bonao', colaborador=self.ana, asignada_por=self.jefe, fecha_limite=hoy)

    def _u(self, n, puesto, grupos=('Colaborador',)):
        u = User.objects.create_user(n, password='Clave-Segura-2026', first_name=n.capitalize())
        u.perfil.puesto_trabajo = puesto
        u.perfil.save()
        u.groups.set([Group.objects.get(name=g) for g in grupos])
        return u

    def como(self, u):
        c = APIClient()
        c.force_authenticate(u)
        return c

    def test_las_tareas_se_vinculan_solas_por_nombre_proyecto_y_no_se_duplican_clientes(self):
        self.assertEqual(Tarea.objects.get(pk=self.t1.pk).cliente_ref, self.cliente)   # por nombre (sin distinguir mayúsculas)
        self.assertEqual(Tarea.objects.get(pk=self.t2.pk).cliente_ref, self.cliente)   # por el proyecto
        self.assertEqual(Cliente.objects.count(), 2)
        Tarea.objects.create(titulo='Nueva', cliente='Cliente que no existe', colaborador=self.ana, fecha_limite=timezone.localdate())
        self.assertEqual(Cliente.objects.count(), 2)   # nunca crea clientes

    def test_proyecto_de_otro_cliente_se_rechaza(self):
        r = self.como(self.jefe).post('/api/desempeno/tareas/', {'titulo': 'X', 'colaborador': self.ana.id, 'prioridad': 'MEDIA',
                                                                 'fecha_limite': timezone.localdate().isoformat(), 'cliente_ref': self.otro.id,
                                                                 'proyecto': self.proyecto.id}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        r = self.como(self.jefe).post('/api/desempeno/tareas/', {'titulo': 'Y', 'colaborador': self.ana.id, 'prioridad': 'MEDIA',
                                                                 'fecha_limite': timezone.localdate().isoformat(), 'proyecto': self.proyecto.id}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.json()['cliente_ref'], r.json()['cliente']), (self.cliente.id, 'Banco Popular'))

    def test_expediente_con_trazabilidad_y_filtros(self):
        self.como(self.jefe).patch(f'/api/desempeno/tareas/{self.t1.pk}/', {'colaborador': self.luis.id, 'motivo': 'Ana está de vacaciones'}, format='json')
        d = self.como(self.jefe).get(f'{API}/{self.cliente.pk}/expediente/').json()
        self.assertEqual({t['titulo'] for t in d['tareas']}, {'Arte del banner', 'Video'})
        video = next(t for t in d['tareas'] if t['titulo'] == 'Video')
        self.assertEqual((video['responsable'], video['asignada_por'], video['resuelta_por']), ('Luis', 'Jefe', 'Jefe'))
        arte = next(t for t in d['tareas'] if t['titulo'] == 'Arte del banner')
        self.assertTrue(any('Ana' in m['detalle'] and 'Luis' in m['detalle'] for m in arte['modificaciones']))   # la reasignación queda
        self.assertEqual(d['proyectos'][0]['tareas'], 1)
        f = self.como(self.jefe).get(f'{API}/{self.cliente.pk}/expediente/?estado=COMPLETADA').json()
        self.assertEqual([t['titulo'] for t in f['tareas']], ['Video'])
        f = self.como(self.jefe).get(f'{API}/{self.cliente.pk}/expediente/?proyecto={self.proyecto.pk}').json()
        self.assertEqual([t['titulo'] for t in f['tareas']], ['Video'])
        f = self.como(self.jefe).get(f'{API}/{self.cliente.pk}/expediente/?empleado={self.luis.pk}').json()
        self.assertEqual(len(f['tareas']), 2)
        ayer = (timezone.localdate() - timedelta(days=30)).isoformat()
        f = self.como(self.jefe).get(f'{API}/{self.cliente.pk}/expediente/?desde={ayer}&hasta={ayer}').json()
        self.assertEqual(f['tareas'], [])   # no se trabajó en esa fecha

    def test_cada_quien_ve_solo_las_tareas_que_ya_podia_ver(self):
        d = self.como(self.ana).get(f'{API}/{self.cliente.pk}/expediente/').json()
        self.assertEqual([t['titulo'] for t in d['tareas']], ['Arte del banner'])   # la de Luis no es suya ni de su equipo

    def test_reporte_pdf_y_excel(self):
        r = self.como(self.jefe).get(f'{API}/{self.cliente.pk}/reporte/?formato=pdf')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))
        r = self.como(self.jefe).get(f'{API}/{self.cliente.pk}/reporte/?formato=xlsx&desde=2026-01-01&hasta=2026-12-31')
        ws = load_workbook(BytesIO(r.content))['Trabajos realizados']
        self.assertIn('Banco Popular', ws['A1'].value)
        self.assertEqual(ws['E5'].value, 'Responsable')

    def test_logo_solo_lo_cambia_quien_puede_editar(self):
        archivo = SimpleUploadedFile('logo.png', PNG, content_type='image/png')
        self.assertEqual(self.como(self.ana).post(f'{API}/{self.cliente.pk}/logo/', {'logo': archivo}, format='multipart').status_code, 403)
        archivo = SimpleUploadedFile('logo.png', PNG, content_type='image/png')
        r = self.como(self.jefe).post(f'{API}/{self.cliente.pk}/logo/', {'logo': archivo}, format='multipart')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['logo_url'])
        self.assertEqual(self.como(self.ana).get(f'{API}/{self.cliente.pk}/logo/').status_code, 200)
        malo = SimpleUploadedFile('x.png', b'MZ\x90programa', content_type='image/png')
        self.assertEqual(self.como(self.jefe).post(f'{API}/{self.cliente.pk}/logo/', {'logo': malo}, format='multipart').status_code, 400)


class DiasTrabajadosTests(ExpedienteTests):
    def test_dias_trabajados_del_cronometro_en_expediente_y_reporte(self):
        from datetime import datetime
        from apps.tiempo.models import RegistroTiempo
        z = timezone.get_current_timezone()
        dia = timezone.localdate() - timedelta(days=40)
        RegistroTiempo.objects.create(usuario=self.ana, tarea=self.t1, inicio=timezone.make_aware(datetime.combine(dia, datetime.min.time()).replace(hour=9), z),
                                      fin=timezone.make_aware(datetime.combine(dia, datetime.min.time()).replace(hour=11), z), minutos=120)
        d = self.como(self.jefe).get(f'{API}/{self.cliente.pk}/expediente/?dia={dia.isoformat()}').json()
        self.assertEqual([t['titulo'] for t in d['tareas']], ['Arte del banner'])   # se trabajó ese día (cronómetro)
        self.assertEqual(d['tareas'][0]['dias_trabajados'][0]['minutos'], 120)
        r = self.como(self.jefe).get(f'{API}/{self.cliente.pk}/reporte/?formato=xlsx')
        ws = load_workbook(BytesIO(r.content))['Trabajos realizados']
        self.assertIn('2 h 0 min', ' '.join(str(ws.cell(row=f, column=15).value or '') for f in range(6, 9)))
