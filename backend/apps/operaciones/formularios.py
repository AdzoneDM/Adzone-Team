"""
Formulario de cada tipo de orden de trabajo y los pasos de producción que se crean al aprobarla.

Cada área de ADZONE pide cosas distintas: una lona necesita medidas y material; un podcast,
fecha de grabación y estudio. Aquí se define, en un solo lugar, qué se pregunta en cada orden.
El frontend dibuja el formulario a partir de esto y el backend valida con lo mismo.

Tipos de campo: texto, largo (varias líneas), numero, dinero, fecha, fechahora,
opcion (una), multiple (varias), sino.
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


def c(clave, etiqueta, tipo='texto', opciones=None, requerido=False, ayuda='', ancho='medio'):
    return {'clave': clave, 'etiqueta': etiqueta, 'tipo': tipo, 'opciones': opciones or [],
            'requerido': requerido, 'ayuda': ayuda, 'ancho': ancho}


TIPOS = {
    'IMPRESION': {
        'nombre': 'Impresión y rotulación',
        'departamento': 'Impresión',
        'icono': 'printer',
        'descripcion': 'Volantes, tarjetas, lonas, viniles, letreros, rotulación de vehículos e instalación.',
        'campos': [
            c('trabajo', 'Qué se imprime', 'opcion', ['Volantes', 'Tarjetas de presentación', 'Lona / banner', 'Vinil adhesivo',
              'Vinil microperforado', 'Rotulación de vehículo', 'Letrero / valla', 'Roll-up', 'Gran formato', 'Etiquetas', 'Otro'], True),
            c('cantidad', 'Cantidad', 'numero', requerido=True),
            c('ancho_cm', 'Ancho (cm)', 'numero'),
            c('alto_cm', 'Alto (cm)', 'numero'),
            c('material', 'Material', 'opcion', ['Papel couché', 'Papel bond', 'Cartulina', 'Lona', 'Vinil adhesivo',
              'Vinil microperforado', 'PVC / foam', 'Acrílico', 'Metal', 'Lo decide producción', 'Otro']),
            c('caras', 'Caras', 'opcion', ['Una cara', 'Dos caras']),
            c('acabados', 'Acabados', 'multiple', ['Laminado mate', 'Laminado brillo', 'Corte a la medida', 'Ojales',
              'Bastidor', 'Troquelado', 'Barniz UV']),
            c('arte', 'Arte', 'opcion', ['Lo entrega el cliente', 'Lo diseña ADZONE', 'Ya está aprobado'], True),
            c('instalacion', '¿Lleva instalación?', 'sino'),
            c('lugar_instalacion', 'Dirección de instalación o entrega', 'largo', ancho='completo'),
        ],
        'pasos': ['Revisar el arte y las medidas', 'Prueba de color aprobada por el cliente', 'Impresión',
                  'Acabados', 'Control de calidad', 'Empaque, entrega o instalación'],
    },
    'ADZONE_TV': {
        'nombre': 'Adzone TV',
        'departamento': 'Adzone TV',
        'icono': 'tv',
        'descripcion': 'Programas, podcasts, entrevistas, transmisiones en vivo, spots y publicaciones en adzone.tv.',
        'campos': [
            c('produccion', 'Producción', 'opcion', ['Programa', 'Podcast', 'Entrevista', 'Transmisión en vivo',
              'Cobertura de evento', 'Spot / comercial', 'Nota para el periódico digital'], True),
            c('programa', 'Programa o espacio', 'texto', ayuda='Ej.: Espacio Internacional'),
            c('fecha_grabacion', 'Grabación', 'fechahora'),
            c('estudio', 'Lugar', 'opcion', ['Estudio 1', 'Estudio 2', 'Exterior / locación del cliente']),
            c('duracion_min', 'Duración (minutos)', 'numero'),
            c('invitados', 'Invitados o talento', 'largo', ancho='completo'),
            c('equipo', 'Equipo técnico', 'multiple', ['Cámaras', 'Iluminación', 'Audio / micrófonos', 'Teleprompter',
              'Transmisión en vivo', 'Drone']),
            c('plataformas', 'Dónde se publica', 'multiple', ['YouTube', 'Facebook', 'Instagram', 'TikTok', 'adzone.tv', 'Canal de TV']),
            c('patrocinador', 'Patrocinador', 'texto'),
        ],
        'pasos': ['Guion y pauta', 'Confirmar invitados y estudio', 'Grabación', 'Edición', 'Revisión final',
                  'Publicación y difusión'],
    },
    'CALL_CENTER': {
        'nombre': 'Call center',
        'departamento': 'Call Center',
        'icono': 'headset',
        'descripcion': 'Atención al cliente, ventas, cobros, soporte, encuestas y agendamiento.',
        'campos': [
            c('servicio', 'Servicio', 'opcion', ['Atención al cliente', 'Ventas / telemercadeo', 'Cobros',
              'Soporte técnico', 'Encuestas', 'Agendamiento de citas'], True),
            c('canales', 'Canales', 'multiple', ['Llamadas entrantes', 'Llamadas salientes', 'WhatsApp', 'Correo', 'Chat web'], True),
            c('agentes', 'Agentes', 'numero', requerido=True),
            c('horario', 'Horario', 'texto', ayuda='Ej.: lunes a viernes, 8:00 a. m. a 6:00 p. m.'),
            c('inicio', 'Inicio de la campaña', 'fecha'),
            c('fin', 'Fin de la campaña', 'fecha'),
            c('guion', 'Guion', 'opcion', ['Lo entrega el cliente', 'Lo prepara ADZONE', 'Ya está aprobado']),
            c('meta_contactos', 'Meta de contactos', 'numero'),
            c('meta_conversion', 'Meta de conversión (%)', 'numero'),
            c('base_datos', 'Base de datos y herramientas', 'largo', ancho='completo',
              ayuda='De dónde salen los contactos y qué sistema se usa.'),
        ],
        'pasos': ['Recibir la base de datos y el guion', 'Capacitar a los agentes', 'Configurar líneas y herramientas',
                  'Arranque de la campaña', 'Informe de resultados'],
    },
    'MARKETING': {
        'nombre': 'Marketing digital',
        'departamento': 'Marketing',
        'icono': 'megaphone',
        'descripcion': 'Redes sociales, campañas pagadas, diseño gráfico, estrategia, SEO y relaciones públicas.',
        'campos': [
            c('servicio', 'Servicio', 'opcion', ['Manejo de redes', 'Campaña pagada', 'Diseño gráfico', 'Estrategia / plan',
              'Correo masivo', 'SEO', 'Relaciones públicas', 'Campaña política'], True),
            c('redes', 'Redes', 'multiple', ['Instagram', 'Facebook', 'TikTok', 'LinkedIn', 'X', 'YouTube', 'Google', 'WhatsApp']),
            c('piezas', 'Piezas', 'numero', ayuda='Publicaciones, artes o anuncios.'),
            c('objetivo', 'Objetivo', 'opcion', ['Alcance', 'Interacción', 'Tráfico', 'Mensajes', 'Clientes potenciales', 'Ventas']),
            c('presupuesto_pauta', 'Presupuesto de pauta (RD$)', 'dinero'),
            c('publicacion', 'Primera publicación', 'fecha'),
            c('publico', 'Público objetivo', 'largo', ancho='completo'),
        ],
        'pasos': ['Brief con el cliente', 'Estrategia y calendario', 'Diseño y textos', 'Aprobación del cliente',
                  'Programación / publicación', 'Informe de resultados'],
    },
    'AUDIOVISUAL': {
        'nombre': 'Audiovisual',
        'departamento': 'Audiovisual',
        'icono': 'clapperboard',
        'descripcion': 'Videos, reels, spots, fotografía, cobertura de eventos, drone y animación 3D.',
        'campos': [
            c('pieza', 'Pieza', 'opcion', ['Video corporativo', 'Reel / video corto', 'Spot', 'Fotografía de producto',
              'Cobertura de evento', 'Animación 3D / VFX', 'Tomas con drone'], True),
            c('rodaje', 'Rodaje', 'fechahora'),
            c('locacion', 'Locación', 'texto'),
            c('duracion_seg', 'Duración final (segundos)', 'numero'),
            c('formatos', 'Formatos', 'multiple', ['Horizontal 16:9', 'Vertical 9:16', 'Cuadrado 1:1', 'Retrato 4:5']),
            c('musica', 'Música', 'opcion', ['Con licencia', 'Original', 'La entrega el cliente', 'Sin música']),
            c('rondas', 'Rondas de cambios incluidas', 'numero'),
            c('entregables', 'Entregables', 'largo', ancho='completo'),
        ],
        'pasos': ['Guion / storyboard', 'Preproducción', 'Rodaje', 'Edición y color', 'Revisión con el cliente', 'Entrega final'],
    },
    'DESARROLLO': {
        'nombre': 'Desarrollo y tecnología',
        'departamento': 'Tecnología',
        'icono': 'code',
        'descripcion': 'Sitios web, landing pages, apps, tiendas en línea, integraciones, automatizaciones y soporte.',
        'campos': [
            c('proyecto', 'Qué se desarrolla', 'opcion', ['Sitio web', 'Landing page', 'App web', 'App móvil', 'Tienda en línea',
              'Integración / automatización', 'Mantenimiento / soporte'], True),
            c('dominio', 'Dominio', 'texto', ayuda='Ej.: cliente.com.do'),
            c('hosting', 'Hosting', 'opcion', ['Servidor de ADZONE', 'Del cliente', 'Por definir']),
            c('integraciones', 'Integraciones', 'multiple', ['WhatsApp', 'Pasarela de pago', 'CRM', 'n8n', 'Google Analytics',
              'Meta Pixel', 'Correo']),
            c('contenido', '¿El contenido está listo?', 'opcion', ['Sí', 'Parcial', 'No']),
            c('lanzamiento', 'Lanzamiento', 'fecha'),
            c('funciones', 'Funciones principales', 'largo', ancho='completo'),
        ],
        'pasos': ['Requerimientos', 'Diseño (maqueta)', 'Desarrollo', 'Pruebas', 'Aprobación del cliente', 'Publicación y capacitación'],
    },
    'ADMINISTRATIVA': {
        'nombre': 'Administración y finanzas',
        'departamento': 'Administración',
        'icono': 'landmark',
        'descripcion': 'Pagos a proveedores, compras, nómina, facturación, cobros, conciliaciones e impuestos.',
        'campos': [
            c('gestion', 'Gestión', 'opcion', ['Pago a proveedor', 'Compra de materiales', 'Nómina', 'Facturación a cliente',
              'Cobro a cliente', 'Conciliación bancaria', 'Impuestos / declaración', 'Caja chica', 'Otro'], True),
            c('beneficiario', 'Proveedor o beneficiario', 'texto'),
            c('monto', 'Monto', 'dinero'),
            c('moneda', 'Moneda', 'opcion', ['RD$', 'US$']),
            c('metodo', 'Forma de pago', 'opcion', ['Transferencia', 'Cheque', 'Efectivo', 'Tarjeta']),
            c('comprobante', '¿Requiere comprobante fiscal?', 'sino'),
            c('detalle', 'Detalle', 'largo', ancho='completo'),
        ],
        'pasos': ['Revisar soporte y montos', 'Aprobación', 'Ejecutar el pago o la gestión', 'Archivar comprobante'],
    },
}

TIPO_CHOICES = [(k, v['nombre']) for k, v in TIPOS.items()]


def catalogo():
    """Lo que necesita el frontend para dibujar los formularios."""
    return [{'tipo': k, **{x: v[x] for x in ('nombre', 'departamento', 'icono', 'descripcion', 'campos', 'pasos')}}
            for k, v in TIPOS.items()]


def validar_detalles(tipo, detalles):
    """Limpia y valida los datos propios del tipo. Devuelve (limpios, errores)."""
    if tipo not in TIPOS:
        return {}, {'tipo': 'Tipo de orden desconocido.'}
    detalles = detalles if isinstance(detalles, dict) else {}
    limpios, errores = {}, {}
    for campo in TIPOS[tipo]['campos']:
        clave, t = campo['clave'], campo['tipo']
        valor = detalles.get(clave)
        vacio = valor in (None, '', []) or (isinstance(valor, str) and not valor.strip())
        if vacio:
            if campo['requerido']:
                errores[clave] = f"Falta «{campo['etiqueta']}»."
            continue
        try:
            if t in ('texto', 'largo'):
                valor = str(valor).strip()[:2000]
            elif t in ('numero', 'dinero'):
                numero = Decimal(str(valor).replace(',', ''))
                if numero < 0:
                    raise ValueError
                valor = float(numero)
            elif t == 'fecha':
                valor = date.fromisoformat(str(valor)[:10]).isoformat()
            elif t == 'fechahora':
                valor = datetime.fromisoformat(str(valor)[:16]).isoformat(timespec='minutes')
            elif t == 'opcion':
                if valor not in campo['opciones']:
                    raise ValueError
            elif t == 'multiple':
                if not isinstance(valor, list) or any(v not in campo['opciones'] for v in valor):
                    raise ValueError
            elif t == 'sino':
                valor = bool(valor) if not isinstance(valor, str) else valor.lower() in ('1', 'true', 'si', 'sí')
        except (ValueError, TypeError, InvalidOperation):
            errores[clave] = f"«{campo['etiqueta']}» no es válido."
            continue
        limpios[clave] = valor
    return limpios, errores
