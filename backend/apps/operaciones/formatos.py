"""
Los formatos controlados de ADZONE (F-01 a F-15), en digital.

Cada Orden de Área (F-02 a F-10, más Call Center y Administración) tiene:
  - g1: compuerta de entrada (el área no inicia si falta una casilla)
  - especificacion: los datos propios del área
  - requiere_g4: si el trabajo necesita aprobación escrita del cliente antes de seguir
  - etapas: el seguimiento de la ejecución (se vuelven los pasos de la tarea)
  - g3: control de calidad interno (firma el supervisor antes de entregar)
  - g2: compuerta de salida (traspaso a la siguiente área, con doble firma)

Cambiar un formato es cambiar este archivo; la base de datos no se toca.
Tipos de campo: texto, largo, numero, dinero, fecha, fechahora, opcion, multiple, sino, tabla.
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


def c(clave, etiqueta, tipo='texto', opciones=None, requerido=False, ayuda='', ancho='medio', columnas=None):
    d = {'clave': clave, 'etiqueta': etiqueta, 'tipo': tipo, 'opciones': opciones or [], 'requerido': requerido,
         'ayuda': ayuda, 'ancho': ancho}
    if columnas:
        d['columnas'] = columnas
    return d


def col(clave, etiqueta, tipo='texto'):
    return {'clave': clave, 'etiqueta': etiqueta, 'tipo': tipo}


PIEZAS_COLUMNAS = [col('pieza', 'Producto / pieza'), col('cantidad', 'Cantidad', 'numero'), col('ancho', 'Ancho', 'numero'),
                   col('alto', 'Alto', 'numero'), col('unidad', 'Unidad')]

# ---------------------------------------------------------------------------------------------
# F-01 · OT Maestra (Comercial → Coordinación)
# ---------------------------------------------------------------------------------------------
G0 = [
    ('cotizacion_aprobada', 'Cotización aprobada por escrito (adjunta)'),
    ('condicion_pago', 'Condición de pago definida'),
    ('anticipo', 'Anticipo confirmado por Administración'),
    ('sin_deuda', 'Cliente sin deuda vencida bloqueante'),
    ('brief', 'Brief completo, sin campos vacíos'),
    ('textos', 'Textos finales recibidos del cliente'),
    ('logo_fotos', 'Logo vectorial y fotos en resolución recibidos'),
    ('medidas', 'Medidas y cantidades confirmadas'),
    ('fecha_hora', 'Fecha y hora requerida definidas'),
    ('direccion', 'Dirección exacta y condiciones de acceso'),
    ('permisos', 'Permisos necesarios identificados'),
]
TIPOS_CLIENTE = [('NUEVO', 'Nuevo'), ('RECURRENTE', 'Recurrente'), ('IGUALA', 'Iguala')]
PRIORIDADES = [('N', 'Normal'), ('U', 'Urgente'), ('E', 'Emergencia')]
COLCHON = {'N': 20, 'U': 20, 'E': 30}  # % de colchón según prioridad (sección 4 del F-01)

# ---------------------------------------------------------------------------------------------
# F-02 a F-10 · Órdenes de Área
# ---------------------------------------------------------------------------------------------
G4_CANALES = ['WhatsApp archivado', 'Correo', 'Firma física', 'Prueba impresa firmada']

# Checklist de validación final (Uso estratégico de herramientas · Gerencia de Marketing y Audiovisuales).
# «Si no hay revisión humana, no hay publicación»: el Gerente de Marketing la firma antes de enviar al cliente (G4).
VALIDACION_FINAL = [
    'Marca: respeta logo, colores, tono y Brand Kit',
    'Mensaje: el objetivo y el llamado a la acción están claros',
    'Calidad: visual, audio, subtítulos y portada listos',
    'Trazabilidad: hay versión identificada y responsable',
    'Conversión: la pieza puede generar acción, atención o confianza',
    'Calendario: cliente, fecha, hora y formato correctos',
]
CHECK_IA = 'Prototipos o piezas hechas con IA identificados y aclarados al cliente'
HERRAMIENTAS = ['Claude', 'Gemini', 'ChatGPT', 'Canva', 'Nano Banana', 'Adobe', 'Veo 3', 'Runway', 'Flow', 'CapCut', 'n8n', 'Otra']

# Ventanas de anticipación para contenido (días entre la solicitud y la fecha requerida).
VENTANAS = {'ideal': 15, 'seguro': 10, 'emergencia_habiles': 7}
AREAS_CONTENIDO = ['MKT', 'DIS', 'AUD']

AREAS = {
    'DIS': {
        'nombre': 'Diseño', 'formato': 'F-02', 'departamento': 'Marketing', 'supervisor': 'Supervisor de Diseño',
        'icono': 'palette', 'requiere_g4': True,
        'g1': ['OT Maestra liberada (E1)', 'Tipo de trabajo definido', 'Medidas y formato final', 'Cantidad de piezas',
               'Textos definitivos del cliente', 'Logo vectorial recibido', 'Fotografías en resolución', 'Referencias visuales',
               'Manual de marca del cliente', 'Destino de la pieza definido', 'Fecha interna aceptada'],
        'especificacion': [
            c('tipo_trabajo', 'Tipo de trabajo', 'multiple', ['Diseño nuevo', 'Rediseño', 'Adaptación', 'Corrección', 'Vectorización',
              'Arte final', 'Diagramación', 'Mockup', 'Plan de contenido'], True),
            c('pieza', 'Pieza', 'multiple', ['Post 4:5', 'Historia 9:16', 'Feed 12 piezas', 'Banner', 'Flyer', 'Logo', 'Manual de marca',
              'Empaque', 'Menú', 'Tarjeta', 'Letrero', 'Rotulación', 'Fachada', 'Presentación', 'Otro'], True),
            c('formato', 'Formato / dimensiones'), c('resolucion', 'Resolución / sangrado'), c('color', 'Perfil de color / códigos'),
            c('destino', 'Destino', 'multiple', ['Digital', 'Impresión', 'Letrero', 'Fabricación']),
            c('instrucciones', 'Instrucciones creativas, concepto, colores, tipografías, referencias y restricciones', 'largo', ancho='completo'),
            c('archivos_salida', 'Archivos de salida requeridos', 'multiple', ['PDF', 'AI', 'EPS', 'CDR', 'PSD', 'JPG', 'PNG', 'SVG', 'Canva', 'Otro']),
            c('nombre_archivo', 'Nombre del archivo (inicia con No. OT)'), c('version', 'Versión entregada'),
            c('herramientas', 'Herramientas usadas', 'multiple', HERRAMIENTAS),
        ],
        'etapas': ['Recepción del brief y del plan de contenido de Marketing',
                   'Revisión de requerimientos (reunión con el cliente si hace falta)',
                   'Desarrollo de la propuesta gráfica (cronómetro activo, arte subido a la plataforma)',
                   'Revisión interna del Gerente de Marketing', 'Validación del cliente', 'Correcciones',
                   'Arte final entregado al Community Manager para publicación'],
        'revision_interna': True,
        'herramientas': 'Canva (Brand Kit) · Adobe · Nano Banana para mockups y variantes · ChatGPT para racionales y revisar contra marca · Runway',
        'g3': ['Ortografía revisada', 'Teléfonos correctos', 'Dirección correcta', 'Redes sociales', 'Código QR probado', 'Precios y fechas',
               'Logo en versión correcta', 'Medidas contra la OT', 'Resolución de imágenes', 'Sangrado y márgenes', 'Perfil de color',
               'Archivo nombrado con No. OT', 'Respaldo guardado', CHECK_IA],
        'g2': ['Arte final en el formato que exige el área receptora', 'Archivo editable respaldado', 'Aprobación del cliente adjunta',
               'Medidas confirmadas', 'Cantidad de piezas confirmada'],
        'nota_g4': 'No se produce sin esta aprobación por escrito. Las rondas adicionales a las cotizadas requieren Solicitud de Cambio F-14.',
    },
    'MKT': {
        'nombre': 'Marketing digital y contenido', 'formato': 'F-03', 'departamento': 'Marketing', 'supervisor': 'Gerente de Marketing',
        'icono': 'megaphone', 'requiere_g4': True,
        'g1': ['OT o iguala vigente', 'Accesos a las cuentas del cliente', 'Manual de marca del cliente', 'Objetivos de la campaña definidos',
               'Público objetivo definido', 'Calendario de fechas clave', 'Presupuesto de pauta confirmado', 'Fecha interna aceptada'],
        'especificacion': [
            c('periodo', 'Período que cubre', requerido=True), c('posts', 'No. de posts', 'numero'), c('historias', 'No. de historias', 'numero'),
            c('reels', 'No. de reels / videos', 'numero'),
            c('plataformas', 'Plataformas', 'multiple', ['Instagram', 'Facebook', 'TikTok', 'YouTube', 'LinkedIn', 'WhatsApp Business', 'Google', 'Otro'], True),
            c('eje_branding', 'Ejes temáticos · Branding %', 'numero'), c('eje_servicios', 'Servicios %', 'numero'), c('eje_ofertas', 'Ofertas %', 'numero'),
            c('eje_educacion', 'Educación %', 'numero'), c('eje_otro', 'Otro %', 'numero'),
            c('estrategia', 'Estrategia, mensajes clave, tono y llamados a la acción', 'largo', ancho='completo'),
            c('piezas_otras_areas', 'Piezas solicitadas a otras áreas', 'tabla', ancho='completo', columnas=[
                col('area', 'Área'), col('pieza', 'Pieza'), col('cantidad', 'Cantidad', 'numero'), col('fecha', 'Fecha requerida', 'fecha'),
                col('oa', 'No. OA emitida')]),
            c('presupuesto_pauta', 'Presupuesto de pauta (RD$)', 'dinero'),
            c('herramientas', 'Herramientas usadas', 'multiple', HERRAMIENTAS),
        ],
        'etapas': ['Recepción del brief: objetivos y estrategia', 'Creación del plan de contenido alineado al brief',
                   'Revisión interna y aprobación del cliente', 'Envío del plan a Diseño / Audiovisuales (coordinar fecha de grabación)',
                   'Recepción de artes y videos aprobados', 'Programación y publicación (Community Manager)', 'Monitoreo y comunidad',
                   'Reporte de resultados'],
        'revision_interna': True,
        'herramientas': 'Claude para briefs y racionales · Gemini para investigación y benchmarking · ChatGPT para copys y control de calidad · Canva · n8n para alertas y aprobaciones',
        'g3': ['Plan aprobado antes de producir', 'Piezas revisadas contra el manual de marca', 'Copys revisados y sin errores',
               'Hashtags y menciones correctos', 'Horarios de publicación definidos', 'Pauta configurada y verificada', 'Enlaces probados',
               'Reporte con métricas del período', CHECK_IA],
        'g2': ['Checklist de validación final aprobado antes de publicar', 'Piezas publicadas según calendario', 'Evidencia de publicación adjunta', 'Reporte de resultados entregado al cliente',
               'Pauta liquidada y conciliada con Administración'],
        'nota_g4': 'Diseño y Audiovisuales no inician hasta que el plan de contenido esté aprobado.',
    },
    'AUD': {
        'nombre': 'Audiovisuales', 'formato': 'F-04', 'departamento': 'Audiovisual', 'supervisor': 'Supervisor de Audiovisuales',
        'icono': 'clapperboard', 'requiere_g4': True,
        'g1': ['OT Maestra liberada', 'Plan de contenido o guion recibido', 'Fecha y hora de grabación confirmada con el cliente',
               'Locación y acceso confirmados', 'Lista de tomas definida', 'Formato y duración de salida definidos',
               'Equipo disponible y reservado', 'Fecha interna aceptada'],
        'especificacion': [
            c('tipo_trabajo', 'Tipo de trabajo', 'multiple', ['Video sencillo', 'Video complejo', 'Spot publicitario', 'Cobertura de evento',
              'Fotografía', 'Edición de fotos', 'Animación', 'Render', 'Plano arquitectónico', 'Dron'], True),
            c('grabacion', 'Fecha y hora de grabación', 'fechahora'), c('locacion', 'Locación / dirección'), c('duracion', 'Duración final'),
            c('formatos', 'Formatos de salida', 'multiple', ['16:9', '9:16', '4:5', '1:1']),
            c('equipo', 'Equipo requerido', 'multiple', ['Cámara principal', 'Cámara secundaria', 'Dron', 'Trípode / gimbal', 'Micrófono de solapa',
              'Micrófono boom', 'Luces', 'Fondo / croma', 'Teleprompter', 'Generador']),
            c('guion', 'Guion, lista de tomas, personas o productos que aparecen, música y referencias', 'largo', ancho='completo'),
            c('respaldo_1', 'Respaldo del material (ubicación 1)'), c('respaldo_2', 'Respaldo del material (ubicación 2)'),
            c('herramientas', 'Herramientas usadas', 'multiple', HERRAMIENTAS),
        ],
        'etapas': ['Recepción del brief, plan de contenido y fecha de grabación', 'Estudio del plan y preparación del equipo',
                   'Grabación del contenido (fotos y videos)', 'Respaldo del material (mismo día)',
                   'Desarrollo de la propuesta visual / edición (cronómetro activo, subida a la plataforma)',
                   'Revisión interna del Gerente de Marketing', 'Validación del cliente', 'Correcciones',
                   'Exportación final y entrega al Community Manager'],
        'revision_interna': True,
        'herramientas': 'Claude para guiones, escaletas y shot lists · Gemini para hooks · Nano Banana para miniaturas · Veo 3 para teasers demo · Flow para storyboard · Runway y CapCut / Adobe para el acabado',
        'g3': ['Audio nivelado y sin ruido', 'Colorimetría consistente', 'Logos y textos correctos', 'Duración exacta por plataforma',
               'Subtítulos si aplica', 'Derechos de música verificados', 'Exportado en todos los formatos', 'Doble respaldo confirmado',
               'Miniatura generada', 'Hook claro en los primeros segundos', CHECK_IA],
        'g2': ['Piezas exportadas y nombradas con No. OT', 'Aprobación del cliente adjunta', 'Material bruto respaldado y ubicado',
               'Entregado a Marketing para publicación'],
    },
    'POD': {
        'nombre': 'Podcast · Adzone TV', 'formato': 'F-05', 'departamento': 'Adzone TV', 'supervisor': 'Supervisor de Podcast',
        'icono': 'mic', 'requiere_g4': False,
        'g1': ['OT Maestra liberada', 'Tema y escaleta recibidos', 'Invitados confirmados con hora de llegada', 'Consentimiento de uso de imagen previsto',
               'Duración objetivo definida', 'Cantidad de clips derivados definida', 'Arte de portada disponible o solicitado', 'Estudio reservado'],
        'especificacion': [
            c('episodio', 'Episodio No.'), c('titulo', 'Título / tema', requerido=True), c('grabacion', 'Fecha y hora de grabación', 'fechahora'),
            c('duracion', 'Duración objetivo'), c('clips', 'Clips derivados', 'numero'),
            c('invitados', 'Invitado(s) · nombre y cargo exactos para rótulos', 'largo', ancho='completo'), c('moderador', 'Moderador / host'),
            c('montaje', 'Montaje técnico', 'multiple', ['1 cámara', '2 cámaras', '3 cámaras', 'Micrófonos de mesa', 'Solapas', 'Mezcladora',
              'Grabación de audio separado', 'Luces de estudio', 'Escenografía', 'Transmisión en vivo']),
            c('escaleta', 'Escaleta / bloques del episodio', 'largo', ancho='completo'),
            c('plataformas', 'Plataformas de destino', 'multiple', ['YouTube', 'Spotify', 'Instagram', 'TikTok', 'Sitio web', 'Otro']),
        ],
        'etapas': ['Preparación y prueba de estudio', 'Grabación', 'Respaldo del material', 'Edición del episodio', 'Generación de clips',
                   'Revisión interna', 'Aprobación', 'Publicación / entrega'],
        'g3': ['Niveles de audio por canal', 'Sincronía entre cámaras', 'Nombres y cargos correctos en rótulos', 'Duración de clips por plataforma',
               'Portada y miniatura listas', 'Descripción y capítulos redactados', 'Consentimientos firmados archivados', 'Doble respaldo confirmado'],
        'g2': ['Episodio máster exportado', 'Clips exportados por plataforma', 'Portada y descripción entregadas', 'Entregado a Marketing para publicación'],
        'nota': 'Antes de grabar: prueba de audio, luz y encuadre 30 minutos antes; consentimiento de uso de imagen firmado por cada invitado.',
    },
    'IMP': {
        'nombre': 'Impresión', 'formato': 'F-06', 'departamento': 'Impresión', 'supervisor': 'Supervisor de Impresión',
        'icono': 'printer', 'requiere_g4': False, 'sale_al_cliente': True,
        'g1': ['Arte final aprobado por el cliente (adjunto)', 'PDF en curvas, escala declarada', 'Sangrado correcto para el equipo',
               'Perfil de color definido', 'Medidas confirmadas contra la OT', 'Cantidad y caras definidas', 'Material y acabados especificados',
               'Existencia confirmada con Almacén', 'Vale de material emitido', 'Fecha interna aceptada'],
        'especificacion': [
            c('piezas', 'Producto, medidas y material', 'tabla', requerido=True, ancho='completo', columnas=PIEZAS_COLUMNAS + [col('caras', 'Caras')]),
            c('material', 'Material / sustrato', 'multiple', ['Banner / lona', 'Vinil adhesivo', 'Vinil de corte', 'Microperforado', 'Frost',
              'Papel / cartulina', 'PVC', 'ACM', 'Acrílico', 'Foam', 'Otro'], True),
            c('marca', 'Marca / referencia'), c('espesor', 'Espesor / gramaje'), c('color', 'Color'),
            c('equipo', 'Equipo asignado', 'opcion', ['Roland UV 640', 'Plotter Platinum 126"', 'Konica Minolta C458', 'Router CNC', 'Láser 4 × 8',
              'Proveedor externo']),
            c('perfil', 'Perfil / modo'), c('pasadas', 'Pasadas'), c('resolucion', 'Resolución'), c('secado', 'Secado / curado'),
            c('tinta_blanca', 'Tinta blanca / barniz'), c('prueba_color', 'Prueba de color', 'sino'),
            c('acabados', 'Corte y acabados', 'multiple', ['Corte recto', 'Contorno', 'Troquelado', 'Laminado mate', 'Laminado brillo', 'Antigrafiti',
              'Ojales', 'Doblez', 'Bolsillos', 'Soldadura de lona', 'Pegado', 'Remachado', 'Montaje', 'Empaque']),
        ],
        'etapas': ['Preprensa y verificación del archivo', 'Prueba de color', 'Impresión', 'Corte / acabado', 'Empaque', 'Entrega'],
        'g3': ['Medidas verificadas con cinta', 'Cantidad completa', 'Color contra prueba aprobada', 'Sin bandas, rayas ni marcas',
               'Laminado sin burbujas', 'Ojales y dobleces según especificación', 'Piezas limpias', 'Empaque protegido', 'Identificado con No. OT',
               'Fotografías tomadas'],
        'g2': ['Piezas contadas e identificadas con No. OT', 'Empacadas y protegidas', 'Sobrante de material devuelto a almacén',
               'Consumo y desperdicio registrados', 'Liberación de Administración si sale al cliente (G5)'],
        'nota': 'Prohibido corregir el arte en máquina. Todo error de archivo se devuelve a Diseño con el vale de traspaso marcado como rechazado.',
    },
    'LET': {
        'nombre': 'Letreros', 'formato': 'F-07', 'departamento': 'Impresión', 'supervisor': 'Supervisor de Letreros',
        'icono': 'signpost', 'requiere_g4': False, 'sale_al_cliente': True,
        'g1': ['Arte final aprobado con medidas reales', 'Levantamiento del sitio con fotografías', 'Tipo de letrero e iluminación definidos',
               'Superficie de instalación confirmada', 'Voltaje y punto eléctrico confirmados', 'Altura y medio de acceso definidos',
               'Permisos gestionados si aplica', 'Material disponible en almacén', 'Fecha interna aceptada'],
        'especificacion': [
            c('tipo_trabajo', 'Tipo de trabajo', 'multiple', ['Exterior', 'Interior', 'Señalización', 'Directorio', 'Tótem', 'Caja de luz',
              'Letras planas', 'Letras corpóreas', 'Letras encajonadas', 'Mantenimiento', 'Desinstalación'], True),
            c('iluminacion', 'Iluminación', 'opcion', ['Frontal', 'Posterior', 'Neón LED', 'Sin iluminación']),
            c('piezas', 'Piezas y medidas', 'tabla', ancho='completo', columnas=[col('pieza', 'Pieza / identificación'), col('cantidad', 'Cant.', 'numero'),
              col('ancho', 'Ancho', 'numero'), col('alto', 'Alto', 'numero'), col('prof', 'Prof.', 'numero'), col('unidad', 'Unidad')]),
            c('materiales', 'Materiales principales', 'multiple', ['ACM', 'Acrílico', 'PVC', 'Aluminio', 'Acero galvanizado', 'Acero inoxidable',
              'MDF / madera', 'Vinil', 'Poliestireno']),
            c('frente', 'Frente'), c('retorno', 'Retorno'), c('espesor', 'Espesor / calibre'), c('estructura', 'Estructura / bastidor'),
            c('acabado', 'Acabado / color'), c('led', 'Tipo de LED'), c('temperatura', 'Temperatura de color'), c('fuente', 'Fuente de poder'),
            c('voltaje', 'Voltaje', 'opcion', ['110 V', '220 V']), c('registro', 'Registro / acceso de mantenimiento'),
            c('superficie', 'Superficie', 'multiple', ['Concreto', 'Cristal', 'ACM', 'Metal', 'Madera', 'Drywall']),
            c('acceso', 'Medio de acceso', 'multiple', ['Escalera', 'Andamio', 'Grúa / elevador', 'Permiso especial', 'Cierre de vía']),
            c('epp', 'Equipo de protección obligatorio', 'multiple', ['Casco', 'Arnés', 'Línea de vida', 'Guantes', 'Gafas', 'Señalización del área']),
            c('fijacion', 'Sistema de fijación / plantilla'), c('horario', 'Horario permitido de instalación'),
        ],
        'etapas': ['Diseño técnico y despiece', 'Corte / conformado', 'Encajonamiento', 'Pintura / acabado', 'Ensamble e iluminación',
                   'Pruebas de encendido', 'Embalaje', 'Instalación'],
        'g3': ['Estructura firme', 'Soldaduras revisadas', 'LED probados por bloque', 'Fuente probada bajo carga', 'Cableado protegido',
               'Iluminación uniforme', 'Acabado sin golpes', 'Medidas contra el levantamiento', 'Plantilla de fijación lista', 'Fotografías tomadas'],
        'g2': ['Letrero probado encendido antes de salir', 'Piezas protegidas para transporte', 'Herramientas y equipo de seguridad cargados',
               'Plantilla y tornillería incluidas', 'Liberación de Administración (G5)'],
    },
    'FAB': {
        'nombre': 'Fabricación', 'formato': 'F-08', 'departamento': 'Impresión', 'supervisor': 'Supervisor de Fabricación',
        'icono': 'hammer', 'requiere_g4': False,
        'g1': ['Plano o archivo de corte recibido', 'Material, espesor y calibre definidos', 'Tolerancias definidas', 'Tipo de unión y acabado definidos',
               'Cantidad confirmada', 'Existencia de material confirmada', 'Vale de almacén emitido', 'Fecha interna aceptada'],
        'especificacion': [
            c('piezas', 'Pieza, medidas y materiales', 'tabla', requerido=True, ancho='completo', columnas=[col('pieza', 'Producto / pieza'),
              col('cantidad', 'Cant.', 'numero'), col('ancho', 'Ancho', 'numero'), col('alto', 'Alto', 'numero'), col('prof', 'Prof.', 'numero'), col('unidad', 'Unidad')]),
            c('material', 'Material principal', 'multiple', ['ACM', 'Acrílico', 'PVC', 'MDF / madera', 'Aluminio', 'Acero galvanizado',
              'Acero inoxidable', 'Lámina metálica', 'Poliestireno'], True),
            c('espesor', 'Espesor / calibre'), c('marca', 'Marca / referencia'), c('color', 'Color'),
            c('procesos', 'Procesos requeridos', 'multiple', ['Diseño técnico', 'Router CNC', 'Corte láser', 'Cizalla', 'Doblado', 'Perforado',
              'Soldadura', 'Esmerilado', 'Pulido', 'Pegado', 'Remachado', 'Ensamblaje', 'Pintura', 'Pintura electrostática', 'Rotulación', 'Empaque']),
            c('maquina', 'Equipo / máquina'), c('plano', 'Plano / archivo'), c('tolerancia', 'Tolerancia / precisión'), c('union', 'Tipo de unión / acabado'),
            c('seguridad', 'Seguridad obligatoria', 'multiple', ['Casco', 'Guantes', 'Gafas', 'Protección auditiva', 'Extractor', 'Ventilación',
              'Extintor', 'Señalización']),
        ],
        'etapas': ['Preparación / trazado', 'Corte / mecanizado', 'Doblado / perforado', 'Soldadura / ensamble', 'Pintura / terminación',
                   'Empaque / entrega'],
        'g3': ['Medidas dentro de tolerancia', 'Escuadra y nivelación', 'Soldaduras sin porosidad', 'Sin rebabas ni filos cortantes',
               'Acabado uniforme', 'Cantidad completa', 'Empaque protegido para transporte', 'Identificado con No. OT', 'Fotografías tomadas'],
        'g2': ['Piezas contadas y protegidas', 'Consumo y desperdicio registrados', 'Sobrante devuelto a almacén', 'Herrajes y tornillería incluidos',
               'Entregado a Letreros / Eventos / Instalación'],
    },
    'EVT': {
        'nombre': 'Producción de eventos', 'formato': 'F-09', 'departamento': 'Impresión', 'supervisor': 'Gerente de Eventos',
        'icono': 'tent', 'requiere_g4': False, 'sale_al_cliente': True,
        'g1': ['OT Maestra liberada', 'Fecha, hora de montaje y de inicio confirmadas', 'Dirección y contacto del local',
               'Levantamiento del sitio con fotos y medidas', 'Cantidad de invitados', 'Listado de piezas y estructuras definido',
               'Requerimientos eléctricos confirmados', 'Permisos y accesos gestionados', 'Hora límite de desmontaje acordada',
               'Fecha de corte de producción fijada (48 h antes)'],
        'especificacion': [
            c('tipo_evento', 'Tipo de evento', requerido=True), c('fecha_evento', 'Fecha del evento', 'fecha', requerido=True),
            c('hora_montaje', 'Hora de montaje'), c('hora_inicio', 'Hora de inicio'), c('invitados', 'Invitados', 'numero'),
            c('local', 'Local / dirección exacta', ancho='completo'), c('contacto_sitio', 'Contacto en sitio (nombre y teléfono)'),
            c('elementos', 'Elementos del montaje', 'multiple', ['Tarima', 'Backdrop', 'Photo call', 'Tótem', 'Banderolas', 'Mesas y sillas', 'Carpa',
              'Alfombra', 'Estructura truss', 'Pantalla LED', 'Sonido', 'Iluminación', 'Generador', 'Señalización', 'Branding de área']),
            c('piezas_otras_areas', 'Piezas solicitadas a otras áreas (fecha de corte: 48 h antes del montaje)', 'tabla', ancho='completo', columnas=[
                col('area', 'Área'), col('pieza', 'Pieza'), col('cantidad', 'Cant.', 'numero'), col('corte', 'Fecha de corte', 'fecha'),
                col('oa', 'No. OA'), col('recibido', 'Recibido en almacén')]),
            c('vehiculos', 'Vehículos asignados'), c('cuadrilla', 'Cuadrilla (cantidad y nombres)'), c('supervisor_sitio', 'Supervisor en sitio'),
            c('salida', 'Hora de salida del taller'),
            c('herramientas', 'Herramientas y equipo', 'multiple', ['Taladros', 'Escalera', 'Andamio', 'Extensiones', 'Cintas y amarres', 'Nivel',
              'Kit de emergencia', 'Extintor', 'Radios', 'EPP completo']),
            c('contingencia', 'Plan de contingencia (lluvia, falla eléctrica, retraso del local)', 'largo', ancho='completo'),
        ],
        'etapas': ['Levantamiento del sitio', 'Plan de montaje por hora', 'Emisión de OA a las áreas', 'Recepción de piezas en almacén',
                   'Carga y traslado', 'Montaje', 'Supervisión durante el evento', 'Desmontaje', 'Retorno e inventario'],
        'g3': ['Montaje conforme al plano', 'Estructuras aseguradas y ancladas', 'Pruebas eléctricas realizadas', 'Prueba de sonido y video',
               'Branding alineado al manual del cliente', 'Área limpia antes de la entrega', 'Rutas de evacuación despejadas',
               'Reporte fotográfico completo', 'Inventario de retorno verificado'],
        'g2': ['Evento montado y aprobado por el cliente', 'Acta de conformidad firmada', 'Reporte fotográfico entregado',
               'Material devuelto e inventariado', 'Daños o faltantes reportados a Coordinación'],
    },
    'SOF': {
        'nombre': 'Desarrollo de software y apps', 'formato': 'F-10', 'departamento': 'Tecnología', 'supervisor': 'Líder de Desarrollo',
        'icono': 'code', 'requiere_g4': True,
        'g1': ['OT Maestra liberada', 'Documento de alcance funcional firmado', 'Criterios de aceptación escritos', 'Accesos y credenciales recibidos',
               'Identidad visual del cliente recibida', 'Hosting, dominio y correo definidos', 'Responsable técnico del cliente identificado',
               'Cronograma de entregas acordado'],
        'especificacion': [
            c('solucion', 'Tipo de solución', 'multiple', ['Sitio web', 'Landing page', 'Tienda en línea', 'Aplicación móvil', 'Sistema web',
              'Integración / API', 'Automatización', 'Mantenimiento', 'Soporte'], True),
            c('stack', 'Tecnología / stack'), c('hosting', 'Hosting / servidor'), c('dominio', 'Dominio'), c('repositorio', 'Repositorio'),
            c('modulos', 'Módulos y entregas', 'tabla', ancho='completo', columnas=[col('modulo', 'Módulo / entrega'), col('criterio', 'Criterio de aceptación'),
              col('fecha', 'Fecha', 'fecha'), col('aprobado', 'Aprobado (fecha / firma)')]),
            c('puesta_produccion', 'Fecha de puesta en producción', 'fecha'), c('capacitacion', 'Capacitación al cliente', 'fecha'),
            c('manual', 'Manual entregado', 'sino'), c('garantia', 'Período de garantía'), c('credenciales_a', 'Credenciales entregadas a (nombre y cargo)'),
            c('respaldo', 'Respaldo automático configurado (frecuencia)'),
        ],
        'etapas': ['Levantamiento funcional', 'Arquitectura y estimación', 'Desarrollo por entregas', 'Pruebas funcionales',
                   'Despliegue a ambiente de prueba', 'Aprobación del cliente', 'Despliegue a producción', 'Capacitación y entrega'],
        'g3': ['Criterios de aceptación cumplidos uno por uno', 'Probado en móvil y escritorio', 'Velocidad de carga aceptable',
               'Formularios probados con datos reales', 'Certificado SSL activo', 'Respaldo automático configurado', 'Accesos administrativos entregados',
               'Código versionado en el repositorio', 'Manual de usuario entregado'],
        'g2': ['Sistema en producción y funcionando', 'Acta de aceptación firmada por el cliente', 'Credenciales entregadas y registradas',
               'Capacitación realizada', 'Garantía y soporte explicados por escrito'],
        'nota': 'Cada entrega tiene su propio G4. Todo cambio pedido después de aceptada una entrega es cambio de alcance cobrable (F-14), no corrección.',
    },
    'INS': {
        'nombre': 'Instalación', 'formato': 'F-12', 'departamento': 'Impresión', 'supervisor': 'Supervisor de Instalación',
        'icono': 'truck', 'requiere_g4': False, 'sale_al_cliente': True,
        'g1': ['OT Maestra liberada', 'Piezas listas y liberadas por las áreas', 'Dirección del sitio y contacto confirmados',
               'Acceso y horario confirmados con el cliente', 'Ruta, vehículo y chofer asignados', 'Permisos en mano si aplica'],
        'especificacion': [
            c('modalidad', 'Modalidad', 'opcion', ['Entrega', 'Instalación', 'Retiro en taller'], True),
            c('direccion', 'Dirección del sitio', ancho='completo'), c('contacto', 'Contacto en sitio'), c('fecha', 'Fecha y hora', 'fechahora'),
        ],
        'etapas': ['Carga y verificación', 'Traslado', 'Instalación / entrega', 'Verificación con el cliente', 'Acta firmada'],
        'g3': ['Medidas verificadas', 'Cantidad completa', 'Color y acabado correctos', 'Sin defectos ni golpes', 'Fijación segura y nivelada',
               'Pruebas eléctricas realizadas', 'Iluminación probada', 'Funcionamiento verificado con el cliente', 'Área limpia',
               'Material sobrante retirado', 'Fotografías antes / durante / después'],
        'g2': ['Acta de entrega firmada por el cliente', 'Fotografías adjuntas', 'Material sobrante devuelto a almacén'],
    },
    'CCT': {
        'nombre': 'Call Center', 'formato': 'CC-01', 'departamento': 'Call Center', 'supervisor': 'Supervisor de Call Center',
        'icono': 'headset', 'requiere_g4': True,
        'g1': ['OT Maestra liberada', 'Base de datos de contactos recibida', 'Guion aprobado por el cliente', 'Líneas y herramientas configuradas',
               'Agentes asignados y capacitados', 'Metas de contacto y conversión definidas', 'Fecha interna aceptada'],
        'especificacion': [
            c('servicio', 'Servicio', 'opcion', ['Atención al cliente', 'Ventas / telemercadeo', 'Cobros', 'Soporte técnico', 'Encuestas',
              'Agendamiento de citas'], True),
            c('canales', 'Canales', 'multiple', ['Llamadas entrantes', 'Llamadas salientes', 'WhatsApp', 'Correo', 'Chat web'], True),
            c('agentes', 'Agentes', 'numero', requerido=True), c('horario', 'Horario'), c('inicio', 'Inicio de la campaña', 'fecha'),
            c('fin', 'Fin de la campaña', 'fecha'), c('meta_contactos', 'Meta de contactos', 'numero'), c('meta_conversion', 'Meta de conversión (%)', 'numero'),
            c('base_datos', 'Base de datos y herramientas', 'largo', ancho='completo'),
        ],
        'etapas': ['Recepción de base de datos y guion', 'Capacitación de agentes', 'Configuración de líneas', 'Arranque de la campaña',
                   'Seguimiento diario', 'Informe de resultados'],
        'g3': ['Guion seguido en llamadas monitoreadas', 'Registro completo de cada contacto', 'Metas del período medidas',
               'Quejas atendidas y documentadas', 'Datos del cliente protegidos'],
        'g2': ['Informe de resultados entregado al cliente', 'Base de datos actualizada devuelta', 'Grabaciones respaldadas'],
    },
    'ADM': {
        'nombre': 'Gestión administrativa', 'formato': 'AD-01', 'departamento': 'Administración', 'supervisor': 'Gerente Administrativo',
        'icono': 'landmark', 'requiere_g4': False,
        'g1': ['Soporte del gasto o gestión recibido', 'Monto y beneficiario confirmados', 'Presupuesto disponible', 'Fecha límite definida'],
        'especificacion': [
            c('gestion', 'Gestión', 'opcion', ['Pago a proveedor', 'Compra de materiales', 'Nómina', 'Facturación a cliente', 'Cobro a cliente',
              'Conciliación bancaria', 'Impuestos / declaración', 'Caja chica', 'Otro'], True),
            c('beneficiario', 'Proveedor o beneficiario'), c('monto', 'Monto', 'dinero'), c('moneda', 'Moneda', 'opcion', ['RD$', 'US$']),
            c('metodo', 'Forma de pago', 'opcion', ['Transferencia', 'Cheque', 'Efectivo', 'Tarjeta']),
            c('comprobante', '¿Requiere comprobante fiscal?', 'sino'), c('detalle', 'Detalle', 'largo', ancho='completo'),
        ],
        'etapas': ['Revisar soporte y montos', 'Aprobación', 'Ejecutar la gestión', 'Archivar comprobante'],
        'g3': ['Montos verificados contra el soporte', 'Aprobación registrada', 'Comprobante archivado'],
        'g2': ['Gestión registrada en el sistema contable', 'Soporte digital adjunto'],
    },
}
AREA_CHOICES = [(k, v['nombre']) for k, v in AREAS.items()]

# Retrabajo (todas las Órdenes de Área)
CAUSAS_RETRABAJO = ['Brief incompleto', 'Error de diseño', 'Error de producción', 'Material defectuoso', 'Cambio del cliente',
                    'Especificación mal transmitida', 'Aprobación no obtenida']

# F-12 · Acta de Entrega / Instalación
G5_ACTA = [
    ('saldo', 'Estado de cuenta revisado: saldo pagado'),
    ('autorizacion', 'O autorización escrita de Gerencia General'),
    ('piezas', 'Piezas contadas y verificadas contra la OT'),
    ('empaque', 'Empacadas y protegidas'),
    ('herramientas', 'Herramientas y tornillería cargadas'),
    ('epp', 'Equipo de protección personal completo'),
    ('ruta', 'Ruta, vehículo y chofer asignados'),
    ('acceso', 'Acceso y horario confirmados con el cliente'),
    ('permisos', 'Permisos en mano si aplica'),
]
VERIFICACION_SITIO = ['Medidas verificadas', 'Cantidad completa', 'Color y acabado correctos', 'Sin defectos ni golpes',
                      'Fijación segura y nivelada', 'Pruebas eléctricas realizadas', 'Iluminación probada',
                      'Funcionamiento verificado con el cliente', 'Área limpia', 'Material sobrante retirado',
                      'Fotografías antes / durante / después']

# F-13 · Vale de traspaso entre áreas
VERIFICACION_TRASPASO = ['Completo según especificación', 'Formato / archivo correcto', 'Medidas y cantidad verificadas',
                         'Aprobación del cliente adjunta', 'Sin daños', 'Identificado con No. OT']

# F-14 · Solicitud de Cambio y Registro de Retrabajo
CORRECCIONES = ['Error de diseño', 'Error de producción', 'Especificación mal transmitida', 'Material defectuoso']  # las asume AdZone
CAMBIOS_ALCANCE = ['Nuevo requerimiento', 'Cambio de medidas', 'Cambio de material', 'Ronda adicional de cambios', 'Cambio de fecha']  # las paga el cliente
AUTORIZACIONES_CAMBIO = ['Cliente informado del costo y la nueva fecha', 'Aprobación del cliente por escrito adjunta',
                         'Nueva versión de la OA emitida', 'Áreas notificadas']


def catalogo():
    """Lo que necesita el frontend para dibujar los formatos."""
    return {
        'areas': [{'codigo': k, **{x: v.get(x) for x in ('nombre', 'formato', 'departamento', 'supervisor', 'icono', 'requiere_g4',
                                                        'sale_al_cliente', 'g1', 'especificacion', 'etapas', 'g3', 'g2', 'nota', 'nota_g4',
                                                        'revision_interna', 'herramientas')}}
                  for k, v in AREAS.items()],
        'g0': [{'clave': k, 'texto': t} for k, t in G0],
        'tipos_cliente': [{'valor': k, 'nombre': t} for k, t in TIPOS_CLIENTE],
        'prioridades': [{'valor': k, 'nombre': t} for k, t in PRIORIDADES],
        'g4_canales': G4_CANALES,
        'validacion_final': VALIDACION_FINAL,
        'ventanas': VENTANAS,
        'causas_retrabajo': CAUSAS_RETRABAJO,
        'g5_acta': [{'clave': k, 'texto': t} for k, t in G5_ACTA],
        'verificacion_sitio': VERIFICACION_SITIO,
        'verificacion_traspaso': VERIFICACION_TRASPASO,
        'correcciones': CORRECCIONES,
        'cambios_alcance': CAMBIOS_ALCANCE,
        'autorizaciones_cambio': AUTORIZACIONES_CAMBIO,
    }


def _limpiar_valor(campo, valor):
    t = campo['tipo']
    if t in ('texto', 'largo'):
        return str(valor).strip()[:3000]
    if t in ('numero', 'dinero'):
        n = Decimal(str(valor).replace(',', ''))
        if n < 0:
            raise ValueError
        return float(n)
    if t == 'fecha':
        return date.fromisoformat(str(valor)[:10]).isoformat()
    if t == 'fechahora':
        return datetime.fromisoformat(str(valor)[:16]).isoformat(timespec='minutes')
    if t == 'opcion':
        if valor not in campo['opciones']:
            raise ValueError
        return valor
    if t == 'multiple':
        if not isinstance(valor, list) or any(v not in campo['opciones'] for v in valor):
            raise ValueError
        return valor
    if t == 'sino':
        return bool(valor) if not isinstance(valor, str) else valor.lower() in ('1', 'true', 'si', 'sí')
    if t == 'tabla':
        if not isinstance(valor, list):
            raise ValueError
        filas = []
        for fila in valor[:50]:
            if not isinstance(fila, dict):
                raise ValueError
            limpia = {}
            for columna in campo['columnas']:
                v = fila.get(columna['clave'])
                if v in (None, ''):
                    continue
                limpia[columna['clave']] = _limpiar_valor({**columna, 'opciones': []}, v)
            if limpia:
                filas.append(limpia)
        return filas
    raise ValueError


def validar_especificacion(area, datos, exigir=True):
    """Limpia y valida la especificación de un área. Devuelve (limpios, errores)."""
    if area not in AREAS:
        return {}, {'area': 'Área desconocida.'}
    datos = datos if isinstance(datos, dict) else {}
    limpios, errores = {}, {}
    for campo in AREAS[area]['especificacion']:
        valor = datos.get(campo['clave'])
        vacio = valor in (None, '', []) or (isinstance(valor, str) and not valor.strip())
        if vacio:
            if campo['requerido'] and exigir:
                errores[campo['clave']] = f"Falta «{campo['etiqueta']}»."
            continue
        try:
            v = _limpiar_valor(campo, valor)
        except (ValueError, TypeError, InvalidOperation):
            errores[campo['clave']] = f"«{campo['etiqueta']}» no es válido."
            continue
        if campo['tipo'] == 'tabla' and not v:
            if campo['requerido'] and exigir:
                errores[campo['clave']] = f"Falta «{campo['etiqueta']}»."
            continue
        limpios[campo['clave']] = v
    return limpios, errores


def checklist(lista, marcados):
    """Normaliza una lista de verificación: {texto: bool} solo con los textos del formato."""
    marcados = marcados if isinstance(marcados, dict) else {}
    return {t: bool(marcados.get(t)) for t in lista}


def faltan(lista, marcados):
    marcados = marcados or {}
    return [t for t in lista if not marcados.get(t)]
