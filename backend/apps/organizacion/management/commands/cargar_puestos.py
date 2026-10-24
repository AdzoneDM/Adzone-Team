import json
from django.core.management.base import BaseCommand, CommandError
from apps.organizacion.models import PuestoDeTrabajo
from apps.core.models import Departamento # Asumiendo que Departamento está en core.models
from django.db import transaction

class Command(BaseCommand):
    help = 'Carga Puestos de Trabajo desde un archivo JSON especificado.'

    def add_arguments(self, parser):
        parser.add_argument('json_file_path', type=str, help='La ruta completa al archivo JSON con los datos de los puestos.')

    @transaction.atomic # Para asegurar que toda la operación sea una transacción atómica
    def handle(self, *args, **options):
        json_file_path = options['json_file_path']
        self.stdout.write(self.style.SUCCESS(f'Iniciando carga de puestos desde: {json_file_path}'))

        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            raise CommandError(f'Archivo no encontrado en la ruta: {json_file_path}')
        except json.JSONDecodeError:
            raise CommandError(f'Error al decodificar el archivo JSON. Asegúrate de que el formato es válido.')

        puestos_creados_count = 0
        puestos_actualizados_count = 0
        puestos_con_error_count = 0

        # Diccionario para mapear nombres de puestos a sus objetos creados (para asignar supervisores)
        puestos_mapeados = {}

        # Primera pasada: Crear todos los puestos sin asignar supervisor
        self.stdout.write(self.style.NOTICE('--- Primera Pasada: Creando Puestos (sin supervisor) ---'))
        for item in data:
            nombre_puesto = item.get('nombre_puesto')
            nombre_departamento = item.get('nombre_departamento')
            funciones_str = "\n".join(item.get('funciones_principales', [])) # Unir lista de funciones en un string

            if not nombre_puesto or not nombre_departamento:
                self.stderr.write(self.style.ERROR(f'Error: "nombre_puesto" y "nombre_departamento" son obligatorios. Saltando item: {item}'))
                puestos_con_error_count += 1
                continue

            try:
                departamento_obj = Departamento.objects.get(nombre=nombre_departamento)
            except Departamento.DoesNotExist:
                self.stderr.write(self.style.ERROR(f'Error: Departamento "{nombre_departamento}" no encontrado para el puesto "{nombre_puesto}". Saltando.'))
                puestos_con_error_count += 1
                continue

            puesto_obj, created = PuestoDeTrabajo.objects.update_or_create(
                nombre=nombre_puesto,
                defaults={
                    'departamento': departamento_obj,
                    'funciones_principales': funciones_str,
                    # El supervisor se asignará en la segunda pasada
                }
            )

            puestos_mapeados[nombre_puesto] = puesto_obj # Guardar el objeto para la segunda pasada

            if created:
                puestos_creados_count += 1
                self.stdout.write(f'Creado Puesto: "{puesto_obj.nombre}" en Departamento "{departamento_obj.nombre}"')
            else:
                puestos_actualizados_count += 1
                self.stdout.write(f'Actualizado Puesto: "{puesto_obj.nombre}" en Departamento "{departamento_obj.nombre}"')

        # Segunda pasada: Asignar supervisores
        self.stdout.write(self.style.NOTICE('--- Segunda Pasada: Asignando Supervisores ---'))
        for item in data:
            nombre_puesto = item.get('nombre_puesto')
            nombre_puesto_supervisor = item.get('supervisado_por_nombre_puesto')

            if not nombre_puesto_supervisor: # Si no tiene supervisor (ej. CEO)
                continue

            puesto_actual_obj = puestos_mapeados.get(nombre_puesto)
            puesto_supervisor_obj = puestos_mapeados.get(nombre_puesto_supervisor)

            if not puesto_actual_obj:
                self.stderr.write(self.style.WARNING(f'Advertencia: Puesto "{nombre_puesto}" no encontrado en el mapeo para asignar supervisor. Puede que haya fallado su creación.'))
                continue

            if not puesto_supervisor_obj:
                self.stderr.write(self.style.ERROR(f'Error: Puesto supervisor "{nombre_puesto_supervisor}" no encontrado para el puesto "{nombre_puesto}". Saltando asignación de supervisor.'))
                puestos_con_error_count += 1 # Contar como error si el supervisor no se encuentra
                continue

            if puesto_actual_obj.supervisor != puesto_supervisor_obj:
                puesto_actual_obj.supervisor = puesto_supervisor_obj
                puesto_actual_obj.save()
                self.stdout.write(f'Asignado supervisor "{puesto_supervisor_obj.nombre}" al puesto "{puesto_actual_obj.nombre}"')

        self.stdout.write(self.style.SUCCESS('--- Resumen de la Carga ---'))
        self.stdout.write(self.style.SUCCESS(f'Puestos creados: {puestos_creados_count}'))
        self.stdout.write(self.style.SUCCESS(f'Puestos actualizados (en primera pasada): {puestos_actualizados_count}'))
        self.stdout.write(self.style.WARNING(f'Puestos con error (saltados o supervisor no asignado): {puestos_con_error_count}'))
        self.stdout.write(self.style.SUCCESS('Carga de puestos completada.'))