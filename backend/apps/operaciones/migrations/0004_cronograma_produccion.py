"""Carga el «Cronograma estimado de producción por tipo de proyecto» de Diseño Gráfico y Producción Audiovisual.

Las horas son de trabajo; los días (hábiles de 8 h) son los que usa la fecha comprometida. En los rangos se toma el máximo.
«72 horas» se toma como 3 días de trabajo.
"""
from decimal import Decimal

from django.db import migrations

D = Decimal
# área, trabajo, horas de trabajo, días hábiles, como lo dice el cronograma
CRONOGRAMA = [
    ('DIS', 'Logotipo corporativo', 8, None, '8 horas'),
    ('DIS', 'Manual de identidad visual (completo)', 40, 5, '3 a 5 días'),
    ('DIS', 'Manual de identidad visual (para redes sociales)', 8, None, '8 horas'),
    ('DIS', 'Feed de 12 publicaciones para redes', 8, None, '8 horas'),
    ('DIS', 'Diseño gráfico unitario digital (post informativo, días festivos…)', 1, None, '1 hora'),
    ('DIS', 'Tarjeta de presentación', D('0.5'), None, '30 minutos'),
    ('DIS', 'Menú general', 2, None, '2 horas'),
    ('DIS', 'Menú diario (una semana completa)', 2, None, '2 horas'),
    ('DIS', 'Letrero publicitario', 1, None, '1 hora'),
    ('DIS', 'Flyer o volante publicitario', 1, None, '1 hora'),
    ('DIS', 'Diseño para rotulación vehicular', 5, None, '3 a 5 horas'),
    ('DIS', 'Fachada comercial', 2, None, '1–2 horas'),
    ('DIS', 'Presentación en diapositivas', 2, None, '1 a 2 horas'),
    ('DIS', 'Íconos para historias destacadas', D('0.5'), None, '15–30 minutos'),
    ('DIS', 'Suéter personalizado', 1, None, '1 hora (según complejidad)'),
    ('DIS', 'Diseños de supermercados', 24, 3, '1 a 3 días'),
    ('AUD', 'Edición de video sencillo (tutoriales, reels con texto…)', 2, None, '2 horas'),
    ('AUD', 'Edición de video complejo (resumen de evento, documental…)', 6, None, '6 horas'),
    ('AUD', 'Edición de spot publicitario', 6, None, '6 horas'),
    ('AUD', 'Edición básica de 50 fotografías (colorimetría)', 1, None, '1 hora'),
    ('AUD', 'Edición completa de 25 fotografías (retoque avanzado)', 2, None, '2 horas'),
    ('AUD', 'Animación de publicaciones con texto', D('0.42'), None, '25 minutos'),
    ('AUD', 'Render de escenario básico con modelos predefinidos', 24, 3, '72 horas'),
    ('AUD', 'Render de escenario sin modelos predefinidos (incluye stands)', 64, 8, '8 días'),
    ('AUD', 'Render de exterior complejo (estructural y arquitectónico)', 120, 15, '7 a 15 días según complejidad'),
    ('AUD', 'Plano arquitectónico (vista aérea)', 80, 10, '5 a 10 días'),
]


def cargar(apps, schema_editor):
    T = apps.get_model('operaciones', 'TiempoEstandar')
    for area, trabajo, horas, dias, ref in CRONOGRAMA:
        horas = D(str(horas))
        dias = D(str(dias)) if dias is not None else (horas / 8).quantize(D('0.01'))
        T.objects.update_or_create(area=area, trabajo=trabajo, defaults={'horas': horas, 'dias': dias, 'referencia': ref})


class Migration(migrations.Migration):
    dependencies = [('operaciones', '0003_revision_interna_y_horas')]
    operations = [migrations.RunPython(cargar, migrations.RunPython.noop)]
