"""Reglas con las que arranca la plataforma. Se pueden pausar o cambiar en «Automatizaciones»."""
from django.db import migrations

BASE = [
    dict(nombre="Orden lista: avisar a quien la pidió", evento='ORDEN_ESTADO', condiciones={'estado': 'LISTA'},
         accion='AVISAR', parametros={'a': ['solicitante'], 'titulo': "{numero} está lista para entregar",
                                     'mensaje': "{titulo} para {cliente}. Coordina la entrega."}),
    dict(nombre="Orden entregada: avisar a Finanzas para facturar", evento='ORDEN_ESTADO', condiciones={'estado': 'ENTREGADA'},
         accion='AVISAR', parametros={'a': ['finanzas'], 'titulo': "Por facturar: {numero}",
                                     'mensaje': "Se entregó {titulo} a {cliente}. Monto acordado: {monto}."}),
    dict(nombre="Orden vencida: avisar al responsable y a su gerente", evento='ORDEN_VENCIDA', condiciones={},
         accion='AVISAR', parametros={'a': ['responsable', 'jefes'], 'titulo': "Vencida: {numero}",
                                     'mensaje': "{titulo} para {cliente} tenía compromiso el {fecha_compromiso}."}),
    dict(nombre="Factura vencida: avisar a Finanzas", evento='FACTURA_VENCIDA', condiciones={},
         accion='AVISAR', parametros={'a': ['finanzas'], 'titulo': "Factura vencida: {numero}",
                                     'mensaje': "{cliente} debe {saldo}. Venció el {vencimiento}."}),
]


def crear(apps, schema_editor):
    Regla = apps.get_model('automatizaciones', 'Regla')
    for r in BASE:
        Regla.objects.get_or_create(nombre=r['nombre'], defaults=r)


def quitar(apps, schema_editor):
    apps.get_model('automatizaciones', 'Regla').objects.filter(nombre__in=[r['nombre'] for r in BASE]).delete()


class Migration(migrations.Migration):
    dependencies = [('automatizaciones', '0001_initial')]
    operations = [migrations.RunPython(crear, quitar)]
