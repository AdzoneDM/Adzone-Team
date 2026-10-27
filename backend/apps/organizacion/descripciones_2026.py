"""
Funciones principales de los puestos que crea el Organigrama 2026 y que no tenían descripción.
`organigrama_2026 --aplicar` las carga solo en los puestos que están vacíos: nunca pisa una descripción ya escrita.
Se revisan y ajustan después en Departamentos y puestos.
"""

CIERRE = [
    "Manejo adecuado y eficiente de los recursos, materiales, financieros y tecnológicos asignados.",
    "(En caso de descuido o daño en el inventario asignado bajo su custodia se cobrará el 15% del costo del producto al colaborador "
    "responsable, esto no aplica cuando el producto se deteriora por vida útil).",
    "Manejo con debida confidencialidad y seguridad de las informaciones de los clientes y de todo lo relacionado con Adzone Digital Marketing.",
]

FUNCIONES = {
    'Presidente del Consejo': [
        "Presidir el Consejo de Socios: convocar y dirigir sus sesiones, fijar la agenda y velar por que las decisiones queden registradas en actas.",
        "Definir con el Consejo la visión, la estrategia de largo plazo y las metas anuales de la empresa, y aprobar el plan y el presupuesto anual.",
        "Nombrar, evaluar y supervisar a la Dirección General (CEO), revisando sus resultados de forma periódica.",
        "Aprobar las decisiones de alto impacto: inversiones, préstamos, nuevas líneas de negocio, alianzas, entrada o salida de socios y contratos relevantes.",
        "Representar a la empresa ante socios estratégicos, instituciones y la comunidad, cuidando su reputación y su marca.",
        "Velar por el buen gobierno corporativo: control interno, transparencia financiera, cumplimiento legal y manejo de conflictos de interés.",
    ],
    'Vicepresidente y Secretario del Consejo': [
        "Sustituir al Presidente del Consejo en su ausencia, con sus mismas atribuciones.",
        "Preparar las convocatorias, la agenda y los documentos de cada sesión del Consejo de Socios.",
        "Redactar, firmar y custodiar las actas, el libro de socios y los acuerdos del Consejo; certificar sus decisiones cuando se requiera.",
        "Dar seguimiento al cumplimiento de los acuerdos del Consejo e informar a sus miembros sobre su avance.",
        "Coordinar con Legal y Contratos los asuntos societarios: asambleas, cambios de capital, registro mercantil y documentos ante las instituciones.",
        "Apoyar a la Dirección General en la relación con los socios y en la presentación de resultados al Consejo.",
    ],
    'Director Comercial': [
        "Diseñar y ejecutar la estrategia comercial de la empresa: mercados, clientes objetivo, portafolio de servicios y metas de venta por línea de negocio.",
        "Dirigir al equipo de Ventas y Cuentas, asignar clientes y prospectos, y dar seguimiento semanal al embudo de ventas y a las metas.",
        "Aprobar las propuestas y cotizaciones de mayor valor junto con Administración, cuidando precio, margen y condiciones de pago.",
        "Asegurar que cada venta cerrada entre a producción con su OT Maestra (F-01) completa: alcance, exclusiones, áreas, monto, anticipo y compuerta G0.",
        "Mantener la relación con los clientes clave y las igualas: renovaciones, ventas cruzadas entre áreas y atención de quejas de alto nivel.",
        "Analizar la competencia, los precios del mercado y la satisfacción de los clientes para proponer nuevos servicios y ajustes de precios.",
        "Presentar a la Dirección General reportes de ventas, cartera de clientes, pronóstico de ingresos y cumplimiento de metas.",
    ],
    'Encargado de Ventas y Cuentas': [
        "Prospectar y atender clientes nuevos y recurrentes: levantar sus necesidades, preparar propuestas y dar seguimiento hasta el cierre.",
        "Elaborar las cotizaciones con apoyo de Administración y, al aprobarse, llenar la OT Maestra (F-01) con datos completos, alcance, exclusiones y la lista G0.",
        "Ser el enlace entre el cliente y el equipo interno: convertir el feedback del cliente en tareas claras y llevar el registro de cambios y aprobaciones.",
        "Gestionar expectativas, acuerdos, cambios de alcance (F-14) y aprobaciones por escrito, evitando que el equipo trabaje sobre pedidos verbales.",
        "Preparar minutas de reuniones, correos de seguimiento, reportes de estado por cliente y presentaciones de avance, con apoyo de las herramientas de IA aprobadas.",
        "Dar seguimiento a los anticipos y pagos de sus clientes junto con Administración para que las OT puedan liberarse y entregarse a tiempo.",
        "Medir la satisfacción del cliente al cierre de cada trabajo y reportar oportunidades de nuevas ventas.",
    ],
    'Encargado de Gestión del Talento': [
        "Gestionar el reclutamiento y la selección: publicar vacantes, filtrar candidatos, coordinar entrevistas y pruebas, y preparar la contratación.",
        "Coordinar la inducción del personal nuevo: empresa, puesto, manual de funciones, uso de la plataforma Adzone Team y normas internas.",
        "Mantener actualizado el expediente de cada colaborador, el organigrama y las descripciones de puesto.",
        "Administrar la asistencia, vacaciones, permisos y licencias, y entregar a Administración la información para la nómina.",
        "Acompañar la evaluación de desempeño mensual (puntaje, KPIs, Empleado del Mes) y los planes de mejora de quien lo necesite.",
        "Organizar capacitaciones, incluido el uso estratégico de las herramientas de IA y producción, y medir su aprovechamiento.",
        "Promover el buen clima laboral, la comunicación interna y el cumplimiento del reglamento y de la normativa laboral vigente.",
    ],
    'Encargado de Presupuestos, Facturación y Cobros': [
        "Elaborar presupuestos y cotizaciones de proyectos y campañas en coordinación con Comercial, calculando costos de horas, producción e insumos para asegurar el margen.",
        "Emitir las facturas en Cashflow con su comprobante fiscal (NCF / e-CF): anticipos antes de liberar la OT y facturas finales solo con el acta de entrega firmada.",
        "Confirmar los anticipos de las OT en la compuerta G0 y liberar la salida (G5) solo con el saldo pagado o con autorización escrita de Gerencia.",
        "Registrar y conciliar los pagos recibidos, y mantener al día el saldo de cada cliente y cada OT.",
        "Controlar las cuentas por cobrar por antigüedad: recordatorios, acuerdos de pago con clientes morosos y escalamiento a Legal cuando proceda.",
        "Dar seguimiento a los cambios de alcance cobrables (F-14) para que se facturen.",
        "Preparar reportes de facturación contra metas, cobros del período y flujo de ingresos proyectado para la Coordinación Financiera.",
    ],
    'Legal y Contratos': [
        "Redactar, revisar y custodiar los contratos con clientes, proveedores, colaboradores y aliados, cuidando alcance, plazos, pagos y penalidades.",
        "Asesorar a la Dirección y a Comercial en las condiciones de cotizaciones, igualas, licitaciones y acuerdos de confidencialidad.",
        "Velar por el cumplimiento legal de la empresa: registro mercantil, permisos, obligaciones laborales, protección de datos y derechos de imagen y de autor.",
        "Gestionar los permisos que requieren los trabajos: instalaciones en la vía pública, letreros, eventos y uso de imagen de personas.",
        "Dar seguimiento a los cobros en vía legal, reclamaciones y conflictos, y representar o coordinar la representación de la empresa.",
        "Apoyar al Secretario del Consejo en los asuntos societarios y en la documentación ante las instituciones.",
    ],
    'Herrero': [
        "Fabricar estructuras metálicas para letreros, vallas, stands, soportes y montajes de eventos según los planos y la Orden de Área.",
        "Cortar, doblar, soldar, pulir y pintar perfiles, tubos y láminas, cuidando medidas, nivel y acabado.",
        "Verificar contra el plano las medidas y la resistencia de cada estructura antes de entregarla a Instalación.",
        "Apoyar al Técnico de Instalación y Rotulación en el montaje y anclaje de estructuras en sitio.",
        "Pedir los materiales con vale de salida (F-11) y registrar sobrantes y desperdicio al terminar.",
        "Mantener en buen estado las herramientas y equipos de soldadura y corte, y usar siempre el equipo de protección personal.",
    ],
    'Soporte Técnico (TI)': [
        "Atender las solicitudes de soporte del personal (computadoras, impresoras, red, correo, cuentas y la plataforma Adzone Team) y registrar cada caso hasta resolverlo.",
        "Instalar, configurar y mantener los equipos de cómputo, periféricos, la red y la telefonía del call center y del estudio.",
        "Hacer el mantenimiento preventivo de los equipos y llevar el inventario de equipos, licencias y accesos asignados a cada colaborador.",
        "Crear, cambiar y desactivar usuarios y accesos según las instrucciones de Gestión del Talento y el principio de mínimo privilegio.",
        "Verificar que los respaldos se ejecuten y escalar al Encargado de Ciberseguridad cualquier incidente o actividad sospechosa.",
        "Brindar soporte técnico de primer nivel a los clientes de software y servicios tecnológicos de ADZONE.",
        "Documentar soluciones y guías para que los problemas frecuentes se resuelvan más rápido.",
    ],
    'Gerente de Call Center': [
        "Dirigir la operación del call center: campañas de atención, ventas, cobros, encuestas, agendamiento y soporte técnico para los clientes.",
        "Planificar turnos, agentes y metas de cada campaña según la Orden de Área de Call Center (contactos, conversión, horario y canales).",
        "Supervisar los indicadores de la operación: llamadas atendidas y realizadas, tiempo de espera, conversión, calidad y satisfacción.",
        "Coordinar con Gestión del Talento el reclutamiento y la capacitación de agentes, y con Tecnología la telefonía y los sistemas.",
        "Presentar a los clientes y a la Dirección los reportes de resultados de cada campaña.",
        "Preparar la expansión del call center (nuevas posiciones, soporte técnico y servicios bilingües) y proponer nuevos servicios.",
    ],
    'Supervisor de Calidad y Monitoreo': [
        "Monitorear llamadas y conversaciones de los agentes con una ficha de evaluación de calidad, y dar retroalimentación diaria.",
        "Verificar el cumplimiento de guiones, protocolos, tiempos de atención y registro correcto de cada contacto.",
        "Validar las tareas de los agentes y reportar los indicadores de calidad por agente y por campaña.",
        "Detectar necesidades de capacitación y entrenar a los agentes nuevos y a los que necesiten mejorar.",
        "Atender los casos escalados y las quejas de clientes que los agentes no pueden resolver.",
        "Proponer mejoras a los guiones y procesos de cada campaña.",
    ],
    'Agente de Call Center Bilingüe': [
        "Atender y realizar llamadas, chats y mensajes en español e inglés según la campaña asignada (atención, ventas, cobros, soporte, encuestas o citas).",
        "Seguir el guion y los protocolos de la campaña, con trato amable y profesional.",
        "Registrar cada contacto, su resultado y los datos del cliente en el sistema de la campaña.",
        "Cumplir las metas diarias de contactos, conversión y calidad.",
        "Escalar al Supervisor de Calidad los casos que no pueda resolver.",
        "Apoyar la traducción y adaptación de guiones y materiales al inglés cuando se requiera.",
    ],
    'Agente de Call Center Español': [
        "Atender y realizar llamadas, chats y mensajes según la campaña asignada (atención, ventas, cobros, soporte, encuestas o citas).",
        "Seguir el guion y los protocolos de la campaña, con trato amable y profesional.",
        "Registrar cada contacto, su resultado y los datos del cliente en el sistema de la campaña.",
        "Cumplir las metas diarias de contactos, conversión y calidad.",
        "Escalar al Supervisor de Calidad los casos que no pueda resolver.",
    ],
}


def funciones(nombre):
    """Texto listo para el campo «Funciones principales», o '' si el puesto no tiene descripción propuesta."""
    lineas = FUNCIONES.get(nombre)
    return "\n".join(lineas + CIERRE) if lineas else ''
