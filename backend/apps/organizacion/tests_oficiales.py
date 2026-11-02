"""Descripciones de puesto y KPIs oficiales, carga del personal con salario y bono proporcional."""
import json
import os
import tempfile
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.desempeno.models import ConfiguracionDesempeno
from apps.kpis.models import KPIAsignado, PlantillaKPI
from apps.organizacion.kpis_oficiales import COMUNES, KPIS_OFICIALES
from apps.organizacion.management.commands.puestos_oficiales import descripciones
from apps.organizacion.models import PerfilUsuario, PuestoDeTrabajo

NULO = open(os.devnull, 'w')


def preparar_puestos():
    call_command('departamentos_oficiales', '--aplicar', stdout=NULO)
    call_command('cargar_puestos', 'datos_iniciales/organigrama_adzone.json', stdout=NULO)
    call_command('organigrama_2026', '--aplicar', stdout=NULO)


class DatosOficialesTests(TestCase):
    def test_los_datos_cubren_los_34_puestos_del_documento(self):
        docs = descripciones()
        self.assertEqual(len(docs), 35)
        self.assertEqual(set(docs), set(KPIS_OFICIALES))
        for puesto, kpis in KPIS_OFICIALES.items():
            nombres = [k[0] for k in kpis]
            self.assertEqual(len(nombres), len(set(nombres)), puesto)
            for nombre, peso, unidad, menor, meta, periodo, texto in kpis:
                self.assertIn(periodo, 'MTA')
                if unidad is None:
                    self.assertIn(nombre, COMUNES, f'{puesto}: {nombre}')
            total = sum(k[1] for k in kpis)
            # El documento del Editor Audiovisual suma 90 %; la plataforma normaliza por la suma de los pesos.
            self.assertEqual(total, 90 if puesto == 'Editor Audiovisual' else 100, puesto)


class PuestosOficialesTests(TestCase):
    def setUp(self):
        preparar_puestos()

    def test_sin_aplicar_no_cambia_nada(self):
        call_command('puestos_oficiales', stdout=NULO)
        self.assertEqual(PuestoDeTrabajo.objects.exclude(perfil_ideal='').count(), 0)

    def test_carga_descripciones_y_kpis_y_desactiva_los_propuestos(self):
        puesto = PuestoDeTrabajo.objects.get(nombre='Encargado de Gestión del Talento')
        viejo = PlantillaKPI.objects.create(nombre='KPI viejo', unidad_medida='%')
        KPIAsignado.objects.create(puesto_trabajo=puesto, plantilla_kpi=viejo, ponderacion=100, objetivo_meta='100')
        call_command('puestos_oficiales', '--aplicar', stdout=NULO)
        puesto.refresh_from_db()
        self.assertIn('atracción, desarrollo, bienestar y retención del talento', puesto.objetivo)
        self.assertIn('Psicología Industrial', puesto.perfil_ideal)
        self.assertIn('10% del salario base', puesto.compensacion_variable)
        activos = KPIAsignado.objects.filter(puesto_trabajo=puesto, activo=True, ponderacion__gt=0)
        self.assertEqual(activos.count(), 8)
        todos = KPIAsignado.objects.filter(puesto_trabajo=puesto, activo=True)
        self.assertTrue(8 < todos.count() <= 15)  # más los de seguimiento (peso 0), con ficha técnica
        seg = todos.filter(ponderacion=0).first()
        self.assertTrue(seg.plantilla_kpi.formula and seg.plantilla_kpi.responsable_validacion)
        self.assertEqual(sum(k.ponderacion for k in activos), 100)
        self.assertFalse(KPIAsignado.objects.get(plantilla_kpi=viejo).activo)  # desactivado, no borrado
        tiempo = activos.get(plantilla_kpi__nombre='Tiempo de contratación')
        self.assertTrue(tiempo.plantilla_kpi.menor_es_mejor)
        self.assertEqual(tiempo.meta_numerica, Decimal('30'))
        self.assertIn('30 días', tiempo.objetivo_meta)
        formacion = activos.get(plantilla_kpi__nombre='Actividades de formación')
        self.assertEqual(formacion.periodicidad_objetivo, 'TRIMESTRAL')

    def test_se_puede_repetir_y_los_puestos_nuevos_quedan_en_el_organigrama(self):
        call_command('puestos_oficiales', '--aplicar', stdout=NULO)
        total = KPIAsignado.objects.count()
        call_command('puestos_oficiales', '--aplicar', stdout=NULO)
        self.assertEqual(KPIAsignado.objects.count(), total)
        estudio = PuestoDeTrabajo.objects.get(nombre='Coordinador de Estudio de TV y Contenido')  # antes «Contenido y Podcast»
        self.assertEqual(estudio.supervisor.nombre, 'Gerente de Marketing y Audiovisuales')
        self.assertEqual(estudio.departamento.nombre, 'Adzone TV')
        self.assertFalse(PuestoDeTrabajo.objects.filter(nombre='Coordinador de Contenido y Podcast').exists())
        master = PuestoDeTrabajo.objects.get(nombre='Control Master')
        self.assertEqual(master.supervisor, estudio)
        self.assertEqual(KPIAsignado.objects.filter(puesto_trabajo=master, activo=True, ponderacion__gt=0).count(), 7)
        analista = PuestoDeTrabajo.objects.get(nombre='Analista de Calidad y Monitoreo')
        self.assertEqual(PuestoDeTrabajo.objects.get(nombre='Agente de Call Center Español').supervisor, analista)
        herrero = KPIAsignado.objects.filter(puesto_trabajo__nombre='Herrero', activo=True)
        self.assertEqual(sum(k.ponderacion for k in herrero), 100)
        self.assertFalse(PuestoDeTrabajo.objects.filter(nombre__startswith='Encargado(a)').exists())
        compartida = PlantillaKPI.objects.get(nombre='Cumplimiento de políticas y procedimientos')
        self.assertGreater(compartida.asignaciones.count(), 20)  # una sola plantilla para todos los puestos

    def test_api_del_puesto_trae_la_descripcion_completa(self):
        call_command('puestos_oficiales', '--aplicar', stdout=NULO)
        admin = User.objects.create_superuser('jefa', 'j@x.com', 'Clave-segura-2026')
        c = APIClient()
        c.force_authenticate(admin)
        puesto = PuestoDeTrabajo.objects.get(nombre='Community Manager')
        r = c.get(f'/api/organizacion/puestos-trabajo/{puesto.pk}/')
        self.assertEqual(r.status_code, 200)
        for campo in ('objetivo', 'perfil_ideal', 'compensacion_variable', 'beneficios', 'alineacion_cultural'):
            self.assertIn(campo, r.data)
        self.assertTrue(r.data['perfil_ideal'])


class PersonalTests(TestCase):
    def setUp(self):
        preparar_puestos()

    def _cargar(self, personas, aplicar=True):
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump({'personas': personas}, f)
        args = [f.name] + (['--aplicar'] if aplicar else [])
        call_command('cargar_equipo', *args, stdout=NULO)
        os.unlink(f.name)

    def test_carga_salario_nomina_accesos_y_agentes(self):
        self._cargar([
            {'usuario': 'ana.diaz', 'nombre': 'Ana', 'apellido': 'Díaz', 'puesto': 'Gerente de Marketing y Audiovisuales',
             'accesos': ['Gerente de Departamento'], 'salario_mensual': 25000, 'nomina': 'ADZONE'},
            {'usuario': 'luis.paz', 'nombre': 'Luis', 'apellido': 'Paz', 'puesto': 'Agente de Call Center Español',
             'salario_mensual': 18422, 'nomina': 'Call Center'},
            {'usuario': 'sin.puesto', 'nombre': 'Sin', 'apellido': 'Puesto', 'puesto': '', 'salario_mensual': 20000},
        ])
        ana = User.objects.get(username='ana.diaz')
        self.assertEqual(ana.perfil.salario_mensual, Decimal('25000'))
        self.assertEqual(ana.perfil.nomina, 'ADZONE')
        self.assertEqual(ana.perfil.costo_hora, Decimal('131.14'))  # 25,000 ÷ 23.83 ÷ 8, como en la nómina
        self.assertTrue(ana.groups.filter(name='Gerente de Departamento').exists())
        luis = User.objects.get(username='luis.paz')
        self.assertEqual(luis.perfil.costo_hora, Decimal('96.63'))
        self.assertTrue(luis.groups.filter(name='Agente Call Center').exists())
        self.assertTrue(User.objects.get(username='sin.puesto').groups.filter(name='Colaborador').exists())

    def test_quien_sale_se_desactiva_y_no_se_crea(self):
        User.objects.create_user('ya.estaba', password='Clave-segura-2026')
        self._cargar([{'usuario': 'ya.estaba', 'nombre': 'Ya', 'activo': False},
                      {'usuario': 'nunca.estuvo', 'nombre': 'Nunca', 'activo': False}])
        self.assertFalse(User.objects.get(username='ya.estaba').is_active)
        self.assertFalse(User.objects.filter(username='nunca.estuvo').exists())

    def test_el_archivo_privado_carga_si_existe(self):
        from pathlib import Path
        archivo = Path('datos_privados/personal_adzone_2026.json')
        if not archivo.exists():
            self.skipTest('Sin archivo privado del personal')
        call_command('puestos_oficiales', '--aplicar', stdout=NULO)
        call_command('cargar_equipo', str(archivo), '--aplicar', stdout=NULO)
        activos = User.objects.filter(is_active=True)
        self.assertEqual(activos.count(), 37)
        self.assertFalse(activos.filter(perfil__puesto_trabajo__isnull=True).exists())  # todos con puesto
        self.assertEqual(activos.filter(perfil__puesto_trabajo__nombre='Agente de Call Center Español').count(), 14)

    def test_sin_aplicar_no_crea_cuentas(self):
        self._cargar([{'usuario': 'x.y', 'nombre': 'X', 'puesto': 'Herrero'}], aplicar=False)
        self.assertFalse(User.objects.filter(username='x.y').exists())

    def test_api_salario_calcula_costo_por_hora_y_solo_admin(self):
        admin = User.objects.create_superuser('jefa', 'j@x.com', 'Clave-segura-2026')
        admin.groups.add(Group.objects.get_or_create(name='Administrador')[0])
        persona = User.objects.create_user('pepe', password='Clave-segura-2026')
        c = APIClient()
        c.force_authenticate(admin)
        r = c.patch(f'/api/organizacion/usuarios/{persona.pk}/', {'salario_mensual': '20000', 'nomina': 'ADZONE', 'costo_hora': None}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        persona.perfil.refresh_from_db()
        self.assertEqual(persona.perfil.costo_hora, Decimal('104.91'))
        r = c.patch(f'/api/organizacion/usuarios/{persona.pk}/', {'salario_mensual': '20000', 'costo_hora': '150'}, format='json')
        persona.perfil.refresh_from_db()
        self.assertEqual(persona.perfil.costo_hora, Decimal('150'))  # un costo propio no se pisa
        otro = APIClient()
        otro.force_authenticate(persona)
        self.assertEqual(otro.get('/api/organizacion/usuarios/').status_code, 403)

    def test_costo_hora_de_salario(self):
        self.assertIsNone(PerfilUsuario.costo_hora_de_salario(None))
        self.assertEqual(PerfilUsuario.costo_hora_de_salario(Decimal('18422')), Decimal('96.63'))


class BonoProporcionalTests(TestCase):
    def test_politica_de_las_descripciones_de_puesto(self):
        config = ConfiguracionDesempeno.actual()
        config.tramos_bono = ConfiguracionDesempeno.TRAMOS_POR_DEFECTO
        self.assertEqual(config.bono_para(100), 10)
        self.assertEqual(config.bono_para(85), 8.5)
        self.assertEqual(config.bono_para(80), 8)
        self.assertEqual(config.bono_para(79.9), 0)
        self.assertEqual(config.bono_para(None), 0)

    def test_la_configuracion_guarda_el_tramo_proporcional(self):
        admin = User.objects.create_superuser('jefa', 'j@x.com', 'Clave-segura-2026')
        admin.groups.add(Group.objects.get_or_create(name='Administrador')[0])
        c = APIClient()
        c.force_authenticate(admin)
        r = c.patch('/api/desempeno/configuracion/', {'tramos_bono': [{'desde': 80, 'porcentaje': 10, 'proporcional': True},
                                                                      {'desde': 100, 'porcentaje': 10}]}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['tramos_bono'], [{'desde': 100, 'porcentaje': 10}, {'desde': 80, 'porcentaje': 10, 'proporcional': True}])
