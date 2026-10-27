"""
KPIs propuestos para los puestos que agregó el Organigrama 2026 (las descripciones están en descripciones_2026.py).

`organigrama_2026 --aplicar` los asigna solo a los puestos que todavía no tienen ningún KPI. Después se ajustan en
Plantillas de KPI y en cada puesto. Los de «entrada manual» se cargan cada mes en «KPIs del mes»; los automáticos
cuentan tareas validadas.
"""

# KPI: nombre, unidad, menor es mejor, descripción (cómo se mide)
PLANTILLAS = {
    'Ventas cerradas vs. meta': ('RD$', False, "Monto vendido (cotizaciones aprobadas, sin ITBIS) contra la meta del mes."),
    'Conversión de cotizaciones': ('%', False, "Cotizaciones aprobadas ÷ cotizaciones enviadas en el mes."),
    'Clientes nuevos': ('clientes', False, "Clientes nuevos con primera OT o iguala firmada en el mes."),
    'OT aceptadas en G0 a la primera': ('%', False, "OT Maestras liberadas por Coordinación sin devolución ÷ OT entregadas a Coordinación."),
    'Cotizaciones enviadas': ('cotizaciones', False, "Cotizaciones enviadas a clientes o prospectos en el mes."),
    'Satisfacción del cliente': ('%', False, "Promedio de la encuesta de cierre (1 a 5) convertido a porcentaje."),
    'Vacantes cubiertas a tiempo': ('%', False, "Vacantes cubiertas dentro del plazo acordado con la gerencia ÷ vacantes del mes."),
    'Rotación de personal': ('%', True, "Salidas del mes ÷ promedio de colaboradores. Menor es mejor."),
    'Plan de capacitación cumplido': ('%', False, "Capacitaciones realizadas ÷ capacitaciones programadas en el mes."),
    'Facturas emitidas a tiempo': ('%', False, "Facturas emitidas en Cashflow dentro de las 24 h siguientes al acta firmada ÷ actas firmadas."),
    'Cartera vencida': ('%', True, "Saldo vencido ÷ total por cobrar al cierre del mes. Menor es mejor."),
    'Cotizaciones entregadas en 24 h': ('%', False, "Cotizaciones entregadas a Comercial en menos de 24 h ÷ solicitudes."),
    'Contratos revisados a tiempo': ('%', False, "Contratos revisados en el plazo pedido ÷ contratos recibidos."),
    'Documentación legal vigente': ('%', False, "Documentos corporativos y permisos vigentes ÷ documentos requeridos."),
    'Trabajos de herrería validados': ('trabajos', False, "Tareas de fabricación y montaje validadas por el supervisor en el mes."),
    'Rondas de revisión': ('rondas', True, "Entregas promedio por tarea (1 = aprobada a la primera). Menor es mejor."),
    'Incidentes de seguridad': ('incidentes', True, "Accidentes o incidentes de seguridad en el taller o en sitio. Meta: cero."),
    'Tickets resueltos en el tiempo acordado': ('%', False, "Solicitudes de soporte resueltas dentro del tiempo acordado ÷ solicitudes recibidas."),
    'Tiempo promedio de respuesta': ('horas', True, "Horas promedio entre la solicitud de soporte y la primera atención. Menor es mejor."),
    'Disponibilidad de equipos y servicios': ('%', False, "Horas de servicio sin caídas (internet, red, telefonía, estudios) ÷ horas laborables."),
    'Mantenimientos preventivos realizados': ('%', False, "Mantenimientos preventivos realizados ÷ programados en el mes."),
    'Metas de campañas cumplidas': ('%', False, "Promedio de cumplimiento de las metas (contactos, conversión) de las campañas activas."),
    'Nivel de servicio': ('%', False, "Llamadas atendidas dentro del tiempo objetivo ÷ llamadas recibidas."),
    'Calidad promedio de monitoreo': ('%', False, "Promedio de la ficha de calidad de las interacciones monitoreadas."),
    'Interacciones monitoreadas vs. plan': ('%', False, "Interacciones evaluadas ÷ interacciones programadas para monitoreo."),
    'Retroalimentaciones realizadas': ('%', False, "Retroalimentaciones individuales hechas ÷ agentes a cargo × frecuencia acordada."),
    'Contactos efectivos vs. meta': ('contactos', False, "Contactos efectivos registrados contra la meta de la campaña."),
    'Conversión o resolución': ('%', False, "Ventas, citas, promesas de pago o casos resueltos ÷ contactos efectivos."),
    'Adherencia al horario': ('%', False, "Tiempo conectado y en horario ÷ tiempo programado."),
}

# Puesto → [(KPI, ponderación %, meta, automático con meta numérica)]
KPIS = {
    'Director Comercial': [('Ventas cerradas vs. meta', 40, 'Meta mensual de ventas', None), ('Conversión de cotizaciones', 30, '≥ 40 %', None),
                           ('Clientes nuevos', 30, '≥ 3 al mes', None)],
    'Encargado de Ventas y Cuentas': [('OT aceptadas en G0 a la primera', 30, '≥ 90 %', None), ('Cotizaciones enviadas', 25, '≥ 20 al mes', None),
                                      ('Satisfacción del cliente', 25, '≥ 90 %', None), ('Conversión de cotizaciones', 20, '≥ 35 %', None)],
    'Encargado de Gestión del Talento': [('Vacantes cubiertas a tiempo', 35, '≥ 90 %', None), ('Rotación de personal', 35, '≤ 3 % mensual', None),
                                         ('Plan de capacitación cumplido', 30, '100 %', None)],
    'Encargado de Presupuestos, Facturación y Cobros': [('Facturas emitidas a tiempo', 35, '≥ 95 %', None), ('Cartera vencida', 35, '≤ 10 %', None),
                                                         ('Cotizaciones entregadas en 24 h', 30, '≥ 90 %', None)],
    'Legal y Contratos': [('Contratos revisados a tiempo', 50, '≥ 95 %', None), ('Documentación legal vigente', 50, '100 %', None)],
    'Herrero': [('Trabajos de herrería validados', 40, '≥ 8 al mes', 8), ('Rondas de revisión', 30, '1 ronda (a la primera)', 1),
                ('Incidentes de seguridad', 30, '0', None)],
    'Soporte Técnico (TI)': [('Tickets resueltos en el tiempo acordado', 40, '≥ 90 %', None), ('Tiempo promedio de respuesta', 30, '≤ 2 horas', None),
                             ('Disponibilidad de equipos y servicios', 15, '≥ 98 %', None), ('Mantenimientos preventivos realizados', 15, '100 %', None)],
    'Gerente de Call Center': [('Metas de campañas cumplidas', 40, '≥ 95 %', None), ('Nivel de servicio', 30, '≥ 80 % en 20 segundos', None),
                               ('Calidad promedio de monitoreo', 30, '≥ 85 %', None)],
    'Supervisor de Calidad y Monitoreo': [('Interacciones monitoreadas vs. plan', 40, '100 %', None), ('Calidad promedio de monitoreo', 30, '≥ 85 %', None),
                                          ('Retroalimentaciones realizadas', 30, '100 %', None)],
    'Agente de Call Center Bilingüe': [('Contactos efectivos vs. meta', 35, 'Meta de la campaña', None), ('Conversión o resolución', 30, 'Meta de la campaña', None),
                                       ('Calidad promedio de monitoreo', 25, '≥ 85 %', None), ('Adherencia al horario', 10, '≥ 95 %', None)],
    'Agente de Call Center Español': [('Contactos efectivos vs. meta', 35, 'Meta de la campaña', None), ('Conversión o resolución', 30, 'Meta de la campaña', None),
                                      ('Calidad promedio de monitoreo', 25, '≥ 85 %', None), ('Adherencia al horario', 10, '≥ 95 %', None)],
}
