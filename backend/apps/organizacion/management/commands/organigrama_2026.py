"""
Aplica el Organigrama 2026 de ADZONE D. M. (estructural y nominal): crea los puestos que faltan, renombra los que
cambiaron de nombre (las personas se quedan en su puesto) y deja a cada puesto con su supervisor.

    python manage.py organigrama_2026            # muestra lo que haría, sin cambiar nada
    python manage.py organigrama_2026 --aplicar  # lo hace

Corre antes `departamentos_oficiales --aplicar` (crea Comercial y Gestión del Talento). Es seguro repetirlo.
Los puestos que no están en el organigrama no se tocan: se listan al final para revisarlos.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import Departamento
from apps.organizacion.models import PuestoDeTrabajo

# Nombre anterior en la plataforma → nombre del organigrama 2026
RENOMBRAR = {
    'Gerente Financiero y Administrativo': 'Coordinadora Financiera y Administrativa',
    'Encargado de Impresiones (Especialista en Impresión Digital)': 'Encargado de Impresiones',
    'Encargado de Eventos y Catering': 'Coordinador de Producción de Eventos y Catering',
    'Coordinador de Estudio de Contenido y Podcast': 'Coordinador de Contenido y Podcast',
    'Editor / Animador 3D VFX': 'Editor de Animación, 3D y VFX',
    'Encargado Ciberseguridad y Desarrollo': 'Encargado de Ciberseguridad y Desarrollo',
    'Encargado en Innovación y Desarrollo': 'Encargado de Innovación y Desarrollo',
    'Coordinador de Medios': 'Encargado de Medios Digitales',
    'Supervisor de Call Center': 'Gerente de Call Center',
    'Agente de Call Center': 'Agente de Call Center Español',
}

# Puesto, departamento, supervisor (None = cabeza). En orden: cada supervisor aparece antes que su gente.
# Donde el organigrama nominal apila cajas que el estructural muestra en paralelo, se sigue el estructural.
ORGANIGRAMA = [
    ('Presidente del Consejo', 'Gerencia', None),
    ('Vicepresidente y Secretario del Consejo', 'Gerencia', 'Presidente del Consejo'),
    ('CEO / Director General', 'Gerencia', 'Vicepresidente y Secretario del Consejo'),
    # Dirección Comercial y Gestión del Talento
    ('Director Comercial', 'Comercial', 'CEO / Director General'),
    ('Encargado de Ventas y Cuentas', 'Comercial', 'Director Comercial'),
    ('Encargado de Gestión del Talento', 'Gestión del Talento', 'CEO / Director General'),
    # Dirección Financiera y Administrativa
    ('Coordinadora Financiera y Administrativa', 'Administración', 'CEO / Director General'),
    ('Encargado de Contabilidad y Tesorería', 'Administración', 'Coordinadora Financiera y Administrativa'),
    ('Encargado de Presupuestos, Facturación y Cobros', 'Administración', 'Encargado de Contabilidad y Tesorería'),
    ('Legal y Contratos', 'Administración', 'Coordinadora Financiera y Administrativa'),
    # Gerencia de Eventos e Impresiones
    ('Gerente de Eventos e Impresiones', 'Impresión', 'CEO / Director General'),
    ('Coordinador de Producción de Eventos y Catering', 'Impresión', 'Gerente de Eventos e Impresiones'),
    ('Asistente de Catering y Servicios Generales', 'Impresión', 'Coordinador de Producción de Eventos y Catering'),
    ('Encargado de Impresiones', 'Impresión', 'Gerente de Eventos e Impresiones'),
    ('Operador de Maquinarias', 'Impresión', 'Encargado de Impresiones'),
    ('Técnico de Instalación y Rotulación', 'Impresión', 'Encargado de Impresiones'),
    ('Herrero', 'Impresión', 'Encargado de Impresiones'),
    ('Chofer de Transporte', 'Impresión', 'Encargado de Impresiones'),
    # Gerencia de Marketing y Audiovisuales
    ('Gerente de Marketing y Audiovisuales', 'Marketing', 'CEO / Director General'),
    ('Encargado de Creatividad', 'Marketing', 'Gerente de Marketing y Audiovisuales'),
    ('Diseñador Gráfico Senior', 'Marketing', 'Encargado de Creatividad'),
    ('Diseñador Gráfico Junior', 'Marketing', 'Encargado de Creatividad'),
    ('Encargado de Medios Digitales', 'Marketing', 'Encargado de Creatividad'),
    ('Community Manager', 'Marketing', 'Encargado de Medios Digitales'),
    ('Coordinador de Contenido y Podcast', 'Adzone TV', 'Gerente de Marketing y Audiovisuales'),
    ('Especialista en Fotografía y Video', 'Audiovisual', 'Coordinador de Contenido y Podcast'),
    ('Editor Audiovisual', 'Audiovisual', 'Coordinador de Contenido y Podcast'),
    ('Editor de Animación, 3D y VFX', 'Audiovisual', 'Coordinador de Contenido y Podcast'),
    # Gerencia de Tecnología y Desarrollo
    ('Gerente de Tecnología y Desarrollo', 'Tecnología', 'CEO / Director General'),
    ('Encargado de Innovación y Desarrollo', 'Tecnología', 'Gerente de Tecnología y Desarrollo'),
    ('Encargado de Ciberseguridad y Desarrollo', 'Tecnología', 'Encargado de Innovación y Desarrollo'),
    ('Soporte Técnico (TI)', 'Tecnología', 'Encargado de Ciberseguridad y Desarrollo'),
    # Gerencia de Call Center
    ('Gerente de Call Center', 'Call Center', 'CEO / Director General'),
    ('Supervisor de Calidad y Monitoreo', 'Call Center', 'Gerente de Call Center'),
    ('Agente de Call Center Bilingüe', 'Call Center', 'Supervisor de Calidad y Monitoreo'),
    ('Agente de Call Center Español', 'Call Center', 'Supervisor de Calidad y Monitoreo'),
]


class Command(BaseCommand):
    help = 'Aplica el Organigrama 2026: puestos, nombres y a quién reporta cada uno.'

    def add_arguments(self, parser):
        parser.add_argument('--aplicar', action='store_true', help='Hacer los cambios (sin esto solo se muestran).')

    def handle(self, *args, aplicar=False, **opciones):
        deptos = {d.nombre: d for d in Departamento.objects.all()}
        faltan = sorted({d for _, d, _ in ORGANIGRAMA} - set(deptos))
        if faltan:
            raise CommandError(f"Faltan departamentos: {', '.join(faltan)}. Corre antes: python manage.py departamentos_oficiales --aplicar")
        with transaction.atomic():
            for viejo, nuevo in RENOMBRAR.items():
                p = PuestoDeTrabajo.objects.filter(nombre=viejo).first()
                if p and not PuestoDeTrabajo.objects.filter(nombre=nuevo).exists():
                    self.stdout.write(f"  ✎ {viejo} ⇒ {nuevo}")
                    p.nombre = nuevo
                    p.save(update_fields=['nombre'])
            puestos = {}
            for nombre, depto, jefe in ORGANIGRAMA:
                p, creado = PuestoDeTrabajo.objects.get_or_create(nombre=nombre, defaults={'departamento': deptos[depto]})
                if creado:
                    self.stdout.write(f"  + {nombre} ({depto})")
                elif p.departamento_id != deptos[depto].pk:
                    self.stdout.write(f"  → {nombre}: {p.departamento} ⇒ {depto}")
                    p.departamento = deptos[depto]
                    p.save(update_fields=['departamento'])
                supervisor = puestos[jefe] if jefe else None
                if p.supervisor_id != (supervisor.pk if supervisor else None):
                    self.stdout.write(f"  ↳ {nombre} reporta a {jefe or '— (cabeza)'}")
                    p.supervisor = supervisor
                    p.save(update_fields=['supervisor'])
                puestos[nombre] = p
            otros = PuestoDeTrabajo.objects.exclude(nombre__in=[n for n, _, _ in ORGANIGRAMA]).order_by('nombre')
            for p in otros:
                self.stdout.write(self.style.WARNING(f"  No está en el organigrama 2026 (se deja igual): {p.nombre} · {p.departamento}"))
            if not aplicar:
                transaction.set_rollback(True)
                self.stdout.write(self.style.NOTICE('\nNo se cambió nada. Repite con --aplicar para hacerlo.'))
            else:
                self.stdout.write(self.style.SUCCESS('\nOrganigrama 2026 aplicado.'))
