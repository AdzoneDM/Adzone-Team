"""
Carga las descripciones de puesto oficiales de ADZONE y sus KPIs con la ponderación del documento
«Descripción de Puestos – ADZONE».

    python manage.py puestos_oficiales            # muestra lo que haría, sin cambiar nada
    python manage.py puestos_oficiales --aplicar  # lo hace

Corre antes `organigrama_2026 --aplicar` (crea y nombra los puestos). Es seguro repetirlo.

- Descripción: objetivo, funciones, perfil ideal, compensación variable, beneficios y alineación cultural salen del
  documento (datos_iniciales/descripciones_puestos_adzone.json) y reemplazan lo que tenga el puesto.
- KPIs: cada puesto queda con los KPIs del documento (kpis_oficiales.py), con su ponderación, meta y periodicidad.
  Los KPIs que el puesto tenía y no están en el documento se **desactivan** (no se borran: su historial queda).
"""
import json
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.kpis.models import KPIAsignado, PlantillaKPI
from apps.organizacion.kpis_oficiales import (AUTOMATICOS, COMO_SE_MIDE, COMUNES, KPIS_OFICIALES, PERIODICIDAD, ficha_tecnica, objetivo,
                                              seguimiento_de)
from apps.organizacion.models import PuestoDeTrabajo

ARCHIVO = Path(settings.BASE_DIR) / 'datos_iniciales' / 'descripciones_puestos_adzone.json'
CAMPOS = {  # campo del puesto ← clave del documento
    'objetivo': 'objetivo', 'funciones_principales': 'funciones', 'perfil_ideal': 'perfil_ideal',
    'compensacion_variable': 'compensacion_variable', 'beneficios': 'beneficios', 'alineacion_cultural': 'alineacion_cultural',
}


def texto(valor):
    return '\n'.join(valor) if isinstance(valor, list) else (valor or '')


def descripciones():
    with open(ARCHIVO, encoding='utf-8') as f:
        return {d['puesto']: d for d in json.load(f)['puestos']}


class Command(BaseCommand):
    help = 'Carga las descripciones de puesto oficiales de ADZONE y sus KPIs con ponderación.'

    def add_arguments(self, parser):
        parser.add_argument('--aplicar', action='store_true', help='Hacer los cambios (sin esto solo se muestran).')

    def _ficha(self, plantilla, unidad, menor, fuente, departamento):
        """Llena fórmula, fuente de datos y responsable si la plantilla no los tiene."""
        if plantilla.formula and plantilla.fuente_datos and plantilla.responsable_validacion:
            return
        formula, datos, responsable = ficha_tecnica(plantilla.nombre, unidad, menor, fuente, departamento)
        plantilla.formula = plantilla.formula or formula[:255]
        plantilla.fuente_datos = plantilla.fuente_datos or datos[:200]
        plantilla.responsable_validacion = plantilla.responsable_validacion or responsable[:120]
        plantilla.save(update_fields=['formula', 'fuente_datos', 'responsable_validacion', 'fecha_modificacion'])

    def _seguimiento(self, puesto):
        """Asigna los KPIs de seguimiento (peso 0) del departamento. No toca la meta si alguien la ajustó."""
        ids = []
        for nombre, fuente, unidad, menor, meta, formula in seguimiento_de(puesto.departamento.nombre, puesto.nombre):
            plantilla, _ = PlantillaKPI.objects.get_or_create(nombre=nombre, defaults={
                'descripcion': formula, 'unidad_medida': unidad, 'menor_es_mejor': menor, 'fuente': fuente, 'formula': formula[:255],
                'fuente_datos': 'Control de horario de Adzone Team' if fuente in ('PUNTUALIDAD', 'ASISTENCIA', 'HORAS_EXTRA') else 'Tareas y cronómetro de Adzone Team',
                'responsable_validacion': 'Automático (lo revisa el supervisor directo)'})
            asignado, creado = KPIAsignado.objects.get_or_create(puesto_trabajo=puesto, plantilla_kpi=plantilla, defaults={
                'ponderacion': Decimal(0), 'objetivo_meta': f'De seguimiento · {formula}'[:255], 'periodicidad_objetivo': 'MENSUAL',
                'es_entrada_manual': False, 'meta_numerica': Decimal(str(meta)) if meta is not None else None, 'activo': True})
            if not creado and not asignado.activo and asignado.ponderacion == 0:
                asignado.activo = True
                asignado.save(update_fields=['activo'])
            ids.append(plantilla.pk)
        return ids

    def handle(self, *args, aplicar=False, **opciones):
        docs = descripciones()
        puestos = {p.nombre: p for p in PuestoDeTrabajo.objects.all()}
        faltan = sorted((set(docs) | set(KPIS_OFICIALES)) - set(puestos))
        with transaction.atomic():
            for nombre, doc in docs.items():
                p = puestos.get(nombre)
                if p is None:
                    continue
                cambios = [campo for campo, clave in CAMPOS.items() if (getattr(p, campo) or '') != texto(doc.get(clave))]
                if cambios:
                    for campo in cambios:
                        setattr(p, campo, texto(docs[nombre].get(CAMPOS[campo])))
                    p.save(update_fields=cambios + ['fecha_modificacion'])
                    self.stdout.write(f"  ✎ {nombre}: descripción de puesto ({len(cambios)} secciones)")

            for nombre, kpis in KPIS_OFICIALES.items():
                p = puestos.get(nombre)
                if p is None:
                    continue
                usados = []
                for kpi, peso, unidad, menor, meta, periodo, detalle in kpis:
                    unidad, menor, como = (COMUNES[kpi] if unidad is None else (unidad, menor, detalle))
                    fuente = AUTOMATICOS.get(kpi, '')
                    plantilla, creada = PlantillaKPI.objects.get_or_create(
                        nombre=kpi, defaults={'descripcion': COMO_SE_MIDE.get(fuente) or como, 'unidad_medida': unidad,
                                              'menor_es_mejor': menor, 'fuente': fuente})
                    if fuente and plantilla.fuente != fuente:
                        plantilla.fuente, plantilla.descripcion = fuente, COMO_SE_MIDE[fuente]
                        plantilla.save(update_fields=['fuente', 'descripcion', 'fecha_modificacion'])
                    self._ficha(plantilla, unidad, menor, fuente, p.departamento.nombre)
                    valores = {'ponderacion': Decimal(peso), 'objetivo_meta': objetivo(meta, unidad, menor, detalle),
                               'periodicidad_objetivo': PERIODICIDAD[periodo], 'es_entrada_manual': not fuente,
                               'meta_numerica': Decimal(str(meta)), 'activo': True}
                    asignado = KPIAsignado.objects.filter(puesto_trabajo=p, plantilla_kpi=plantilla).first()
                    if asignado is None:
                        KPIAsignado.objects.create(puesto_trabajo=p, plantilla_kpi=plantilla, **valores)
                    elif any(getattr(asignado, c) != v for c, v in valores.items()):
                        for c, v in valores.items():
                            setattr(asignado, c, v)
                        asignado.save()
                    usados.append(plantilla.pk)
                usados += self._seguimiento(p)
                viejos = KPIAsignado.objects.filter(puesto_trabajo=p, activo=True).exclude(plantilla_kpi_id__in=usados)
                for v in viejos:
                    self.stdout.write(self.style.WARNING(f"    − se desactiva «{v.plantilla_kpi.nombre}» en {nombre}"))
                viejos.update(activo=False)
                autos = sum(1 for k in kpis if k[0] in AUTOMATICOS)
                self.stdout.write(f"  ★ {nombre}: {len(kpis)} KPIs ({autos} automáticos) · {sum(k[1] for k in kpis)} % de ponderación")

            for p in puestos.values():
                if p.nombre not in KPIS_OFICIALES:
                    self._seguimiento(p)  # los puestos sin KPIs en el documento también reciben los de seguimiento
            total = KPIAsignado.objects.filter(activo=True).count()
            seg = KPIAsignado.objects.filter(activo=True, ponderacion=0).count()
            self.stdout.write(f"\n  {total} KPIs activos en los puestos; {seg} de seguimiento (peso 0, se miden solos).")
            for nombre in faltan:
                self.stdout.write(self.style.WARNING(f"  No existe el puesto «{nombre}». Corre antes: python manage.py organigrama_2026 --aplicar"))
            sin_doc = sorted(set(puestos) - set(docs))
            if sin_doc:
                self.stdout.write(self.style.NOTICE(f"\nPuestos que no están en el documento (se dejan igual): {', '.join(sin_doc)}"))
            if not aplicar:
                transaction.set_rollback(True)
                self.stdout.write(self.style.NOTICE('\nNo se cambió nada. Repite con --aplicar para hacerlo.'))
            else:
                self.stdout.write(self.style.SUCCESS('\nDescripciones de puesto y KPIs oficiales cargados.'))
