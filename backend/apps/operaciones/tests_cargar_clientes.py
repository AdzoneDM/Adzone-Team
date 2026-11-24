"""Carga del catálogo de clientes: sin duplicar, sin tocar lo existente."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from .management.commands.cargar_clientes import CATALOGO, clave, planificar
from .models import Cliente


def correr(*args):
    salida = StringIO()
    call_command('cargar_clientes', *args, stdout=salida)
    return salida.getvalue()


class CargarClientesTests(TestCase):
    def test_el_plan_no_cambia_nada(self):
        antes = Cliente.objects.count()
        texto = correr()
        self.assertIn('Solo era el plan', texto)
        self.assertEqual(Cliente.objects.count(), antes)

    def test_crea_los_15_con_su_escritura_comercial_y_tipo(self):
        correr('--aplicar')
        self.assertEqual(Cliente.objects.count(), 15)
        nombres = set(Cliente.objects.values_list('nombre', flat=True))
        self.assertTrue({'Coopdemón', 'Cenllabo', 'Dulcería Rodríguez', 'Centro Médico Carolina de Jesús', 'Plaza Merengue', 'AdZone TV'} <= nombres)
        self.assertEqual(set(Cliente.objects.filter(tipo='INTERNO').values_list('nombre', flat=True)), {'AdZone', 'AdZone TV'})
        self.assertEqual(Cliente.objects.filter(tipo='EMPRESA').count(), 13)

    def test_repetirlo_no_duplica(self):
        correr('--aplicar')
        ids = set(Cliente.objects.values_list('id', flat=True))
        texto = correr('--aplicar')
        self.assertEqual(set(Cliente.objects.values_list('id', flat=True)), ids)
        self.assertIn('Faltan y se crearán (0)', texto)

    def test_compara_sin_importar_mayusculas_acentos_ni_espacios(self):
        previo = Cliente.objects.create(nombre='  dulceria   RODRIGUEZ ')
        coop = Cliente.objects.create(nombre='COOPDEMON')
        correr('--aplicar')
        self.assertEqual(Cliente.objects.filter(nombre__icontains='dulcer').count(), 1)               # no se creó «Dulcería Rodríguez»
        self.assertEqual(Cliente.objects.filter(nombre__icontains='coopdem').count(), 1)
        self.assertEqual(Cliente.objects.get(pk=previo.pk).nombre, '  dulceria   RODRIGUEZ ')          # y el existente quedó tal cual
        self.assertEqual(Cliente.objects.get(pk=coop.pk).nombre, 'COOPDEMON')
        self.assertEqual(Cliente.objects.count(), 15 - 2 + 2)

    def test_no_toca_los_clientes_existentes_ni_sus_ids(self):
        d = Cliente.objects.create(nombre='d', notas='importante', activo=False)
        ids = {d.pk: ('d', 'importante', False)}
        correr('--aplicar')
        d.refresh_from_db()
        self.assertEqual((d.nombre, d.notas, d.activo), ids[d.pk])
        self.assertEqual(Cliente.objects.count(), 16)

    def test_una_variante_de_un_existente_no_se_crea_sin_decision(self):
        Cliente.objects.create(nombre='Carolina de Jesús')                                              # parecido a «Centro Médico Carolina de Jesús»
        existen, nuevos, dudosos = planificar()
        self.assertEqual([n for n, _ in dudosos], ['Centro Médico Carolina de Jesús'])
        self.assertNotIn('Centro Médico Carolina de Jesús', [n for n, _ in nuevos])
        correr('--aplicar')
        self.assertFalse(Cliente.objects.filter(nombre='Centro Médico Carolina de Jesús').exists())
        correr('--aplicar', '--distintos', 'Centro Médico Carolina de Jesús')                           # si se decide que son distintos, entra
        self.assertTrue(Cliente.objects.filter(nombre='Centro Médico Carolina de Jesús').exists())

    def test_los_nombres_cortos_no_generan_falsas_variantes(self):
        Cliente.objects.create(nombre='d')                                                              # «d» está dentro de casi todo: no cuenta
        self.assertEqual(planificar()[2], [])

    def test_el_catalogo_no_trae_repetidos(self):
        self.assertEqual(len({clave(n) for n, _ in CATALOGO}), len(CATALOGO))
