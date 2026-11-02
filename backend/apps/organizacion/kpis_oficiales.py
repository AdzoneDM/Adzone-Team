"""
KPIs oficiales de cada puesto, según «Descripción de Puestos – ADZONE» (sección KPIS, con su ponderación).

`python manage.py puestos_oficiales --aplicar` los asigna. Cómo se miden en la plataforma:

- Cada mes, el supervisor anota en «KPIs del mes» el valor alcanzado; la meta numérica viene llenada desde aquí
  y el texto del documento queda como «objetivo» del KPI.
- `%`: porcentaje logrado contra la meta del documento (p. ej. 95 % de entregas a tiempo).
- «menor es mejor» con meta 0 (incidentes, devoluciones, errores): 0 = 100 % de cumplimiento; cualquier caso = 0 %.
- Calificaciones (9/10, 4/5): se anota la calificación promedio del mes.
- Metas trimestrales (p. ej. 2 prototipos por trimestre): se anota el **% de avance del plan del trimestre**
  (al día con el plan = 100). Llevan periodicidad «Trimestral» para que se vean distintas.
- Lo cualitativo (políticas, trabajo en equipo, apoyo a otras áreas): % que el supervisor evalúa (100 = cumplió).
"""

PCT, PLAN, CERO, NOTA10, NOTA5 = '%', '% del plan', 'casos', 'puntos (1-10)', 'puntos (1-5)'

# Plantillas compartidas: nombre → (unidad, menor es mejor, cómo se mide)
COMUNES = {
    'Cumplimiento de políticas y procedimientos': (
        PCT, False, "Apego a las políticas, procesos y protocolos internos (sin amonestaciones ni fallas de documentación). "
                    "El supervisor evalúa de 0 a 100."),
    'Trabajo en equipo (metas del departamento)': (
        PCT, False, "Vela porque su departamento cumpla las metas asignadas y apoya a sus compañeros con los trabajos pendientes. "
                    "El supervisor evalúa de 0 a 100."),
    'Organización de archivos y protocolos del área': (
        PCT, False, "Archivos nombrados, versionados y guardados según los protocolos de diseño y audiovisuales. "
                    "El supervisor evalúa de 0 a 100."),
    'Entregas a tiempo según cronograma': (
        PCT, False, "Trabajos entregados con la calidad pedida dentro del cronograma aprobado ÷ trabajos del mes."),
    'Soporte técnico a departamentos y clientes': (
        PCT, False, "Solicitudes de soporte de los departamentos internos y de clientes atendidas ÷ recibidas."),
    'Capacitación del trimestre': (
        PLAN, False, "Capacitaciones, talleres o certificaciones del trimestre realizadas ÷ previstas (al día con el plan = 100)."),
    'Satisfacción del cliente': (
        PCT, False, "Promedio de las encuestas post servicio del mes, en porcentaje."),
    'Innovación implementada en el trimestre': (
        PLAN, False, "Mejoras, técnicas, herramientas o formatos nuevos implementados ÷ los previstos para el trimestre."),
    'Incidentes de seguridad': (
        CERO, True, "Accidentes, incidentes o brechas de seguridad del mes. Meta: cero."),
    'Mantenimiento preventivo al día': (
        PCT, False, "Mantenimientos preventivos (equipos, vehículos, máquinas, estudio) hechos ÷ programados en el mes."),
    'Rondas de revisión por trabajo': (
        'rondas', True, "Rondas promedio de cambios hasta la versión final aprobada. Menor es mejor."),
    'Errores técnicos en entregas': (
        CERO, True, "Devoluciones por errores técnicos u ortográficos (formato, resolución, audio, arte final). Meta: cero."),
    'Eficiencia del presupuesto': (
        PCT, True, "Desvío del costo real contra el presupuesto (eventos, producciones). Menor es mejor."),
    'Retención de clientes': (
        PCT, False, "Clientes o cuentas que renuevan o siguen activos ÷ clientes del período."),
    'Calidad promedio QA': (
        PCT, False, "Promedio de la ficha de calidad (QA) de las interacciones evaluadas en el mes."),
    'Adherencia al horario y puntualidad': (
        PCT, False, "Tiempo conectado y en horario ÷ tiempo programado; llegadas a tiempo."),
    'Clientes nuevos': (
        PLAN, False, "Cuentas nuevas captadas ÷ meta del trimestre (al día con el plan = 100)."),
}

# Puesto (nombre en la plataforma) → [(KPI, ponderación, unidad, menor es mejor, meta, periodicidad, objetivo del documento)]
# unidad / menor None = plantilla compartida (COMUNES). Periodicidad: 'M' mensual, 'T' trimestral, 'A' anual.
K = {}

K['CEO / Director General'] = [
    ('Crecimiento de ingresos', 25, PCT, False, 15, 'A', "Ingresos mayores en más de 15 % al año anterior."),
    ('Margen neto de utilidad', 20, PCT, False, 10, 'A', "Margen neto mayor a 10 % (rentabilidad sobre ventas)."),
    ('Satisfacción del cliente', 20, None, None, 85, 'M', "Más de 85 % de satisfacción en encuestas post servicio."),
    ('Retención de talento clave', 15, PCT, False, 90, 'A', "Más de 90 % del personal clave retenido en el año."),
    ('Iniciativas de innovación', 20, PLAN, False, 100, 'A', "Más de 2 iniciativas de innovación implementadas al año."),
]
K['Director Comercial'] = [
    ('Metas de ventas', 40, PCT, False, 100, 'T', "Cumplimiento de las metas de ventas trimestrales."),
    ('Clientes nuevos', 20, None, None, 100, 'T', "Al menos 3 cuentas nuevas de alto valor por trimestre."),
    ('Retención de clientes', 10, None, None, 85, 'T', "Retención igual o mayor a 85 % de las cuentas existentes (cartera activa y renovaciones)."),
    ('Satisfacción del cliente', 10, None, None, 80, 'M', "Más de 80 % (más de 4 de 5 en encuestas post servicio)."),
    ('Desempeño del equipo comercial', 10, PCT, False, 100, 'T', "Productividad y evaluaciones del equipo comercial."),
    ('Proyectos de cultura organizacional', 5, PCT, False, 100, 'T', "Participación activa en proyectos de cultura organizacional."),
    ('Cumplimiento de políticas y procedimientos', 5, None, None, 100, 'M', "Evaluado con KPIs internos y la retroalimentación de Gestión del Talento."),
]
K['Encargado de Gestión del Talento'] = [
    ('Tiempo de contratación', 10, 'días', True, 30, 'M', "Menos de 30 días promedio por vacante, con contrataciones de calidad."),
    ('Retención de personal clave', 15, PCT, False, 85, 'T', "Más de 85 % de retención trimestral del personal clave."),
    ('Evaluaciones de desempeño completadas', 15, PCT, False, 100, 'T', "100 % del personal evaluado por trimestre, con retroalimentación documentada."),
    ('Actividades de formación', 15, PLAN, False, 100, 'T', "Más de 2 actividades de formación internas o externas por trimestre."),
    ('Satisfacción del colaborador', 10, NOTA5, False, 4, 'T', "Encuesta de satisfacción del colaborador: promedio mayor a 4 de 5."),
    ('Acciones de cultura organizacional', 15, PLAN, False, 100, 'T', "Más de 2 acciones de cultura (actividades, campañas o reconocimientos) por trimestre."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "100 %: sin amonestaciones ni fallas en documentación."),
    ('Liderazgo y coaching', 10, PLAN, False, 100, 'T', "1 actividad o proceso de liderazgo/coaching con el personal por trimestre."),
]
K['Encargado de Ventas y Cuentas'] = [
    ('Clientes nuevos', 20, None, None, 100, 'T', "Mínimo 3 cuentas nuevas por trimestre."),
    ('Satisfacción del cliente', 20, None, None, 90, 'M', "Más de 90 % en encuestas post servicio."),
    ('Retención de clientes', 20, None, None, 95, 'T', "Retención de clientes actuales mayor a 95 %."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "100 % de cumplimiento."),
    ('Capacitación del trimestre', 5, None, None, 100, 'T', "Mínimo 1 capacitación trimestral (comercial, marketing, habilidades blandas)."),
    ('Trabajo en equipo (metas del departamento)', 5, None, None, 100, 'M', "Colaboración y apoyo a las metas del equipo."),
    ('Ventas cruzadas', 5, PLAN, False, 100, 'T', "Al menos 2 ventas cruzadas efectivas."),
    ('Gestión de cobros de la cartera', 15, PCT, False, 100, 'M', "100 % de gestión de cobros de la cartera asignada cada mes."),
]

K['Gerente de Tecnología y Desarrollo'] = [
    ('Disponibilidad de sistemas (uptime)', 10, PCT, False, 99, 'M', "Más de 99 % de tiempo activo de sistemas y plataformas críticas."),
    ('Proyectos TI a tiempo y en presupuesto', 20, PCT, False, 100, 'M', "100 % de proyectos entregados en plazo y presupuesto."),
    ('Mejoras de procesos o automatizaciones', 10, PLAN, False, 100, 'T', "Dos mejoras por trimestre (proceso, herramienta, automatización o integración)."),
    ('Incidentes de seguridad', 20, None, None, 0, 'M', "0 brechas significativas no controladas; incidentes críticos resueltos en menos de 1 hora."),
    ('Satisfacción de usuarios internos', 10, PCT, False, 90, 'T', "Más de 90 % de colaboradores satisfechos con las herramientas y el soporte TI."),
    ('Capacitación del trimestre', 5, None, None, 100, 'T', "100 % del equipo técnico con al menos 1 capacitación o certificación trimestral."),
    ('Soporte técnico a departamentos y clientes', 5, None, None, 100, 'M', "Soporte técnico a los departamentos internos y a los clientes de Adzone."),
    ('Trabajo en equipo (metas del departamento)', 10, None, None, 100, 'M', "Velar porque su departamento cumpla con las metas asignadas."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "Cumplimiento de políticas y procedimientos."),
]
K['Encargado de Innovación y Desarrollo'] = [
    ('Prototipos funcionales', 20, PLAN, False, 100, 'T', "2 prototipos o demos funcionales por trimestre (internos o para clientes potenciales)."),
    ('Innovación implementada en el trimestre', 10, None, None, 100, 'T', "1 innovación tecnológica o de proceso por trimestre que optimice la eficiencia o reduzca costos en 5 %."),
    ('Adopción de proyectos de innovación', 10, PCT, False, 80, 'T', "Al menos 80 % de los proyectos de innovación adoptados y usados por los equipos."),
    ('Procesos automatizados', 15, PLAN, False, 100, 'T', "Automatizar al menos un proceso clave por trimestre, reduciendo 5 % su tiempo."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "Cumplimiento de políticas y procedimientos."),
    ('Soporte técnico a departamentos y clientes', 20, None, None, 100, 'M', "Soporte técnico a los departamentos internos y a los clientes de Adzone."),
    ('Trabajo en equipo (metas del departamento)', 5, None, None, 100, 'M', "Velar porque su departamento cumpla con las metas asignadas."),
    ('Capacitación del trimestre', 10, None, None, 100, 'T', "Al menos una capacitación en tecnología, innovación y desarrollo por trimestre."),
]
K['Encargado de Ciberseguridad y Desarrollo'] = [
    ('Incidentes de seguridad', 20, None, None, 0, 'M', "Cero incidentes graves (acceso no autorizado, pérdida de datos, brechas)."),
    ('Proyectos sin vulnerabilidades', 20, PCT, False, 95, 'M', "Al menos 95 % de los proyectos entregados sin errores graves ni vulnerabilidades."),
    ('Estándares de desarrollo seguro', 15, PCT, False, 100, 'M', "Revisión de código, pruebas automatizadas, control de versiones."),
    ('Parches, monitoreo y certificados', 10, PCT, False, 100, 'M', "Parches aplicados, monitoreo de amenazas y certificados renovados a tiempo."),
    ('Entregas sin retrasos técnicos', 10, PCT, False, 100, 'M', "Requerimientos entregados en el tiempo estimado, sin retrasos por errores técnicos."),
    ('Soporte técnico a departamentos y clientes', 10, None, None, 100, 'M', "Soporte técnico a los departamentos internos y a los clientes de Adzone."),
    ('Capacitación del trimestre', 5, None, None, 100, 'T', "Al menos una formación o certificación trimestral en tecnología, desarrollo o ciberseguridad."),
    ('Cumplimiento de políticas y procedimientos', 5, None, None, 100, 'M', "Cumplimiento de políticas y procedimientos."),
    ('Trabajo en equipo (metas del departamento)', 5, None, None, 100, 'M', "Velar porque su departamento cumpla con las metas asignadas."),
]

K['Coordinadora Financiera y Administrativa'] = [
    ('Flujo de caja y tesorería', 15, PCT, False, 100, 'M', "Proyección actualizada cada semana; 100 % de pagos críticos alertados y programados antes del vencimiento; 0 sobregiros o penalidades evitables."),
    ('Facturación y cuentas por cobrar', 15, PCT, False, 98, 'M', "Al menos 98 % de facturas correctas y a tiempo; al menos 95 % de gestiones de cobro dentro del cronograma; cartera vencida en baja."),
    ('Cuentas por pagar y proveedores', 10, PCT, False, 95, 'M', "100 % de pagos con soporte y autorización; 0 pagos duplicados; al menos 95 % procesados en el plazo acordado."),
    ('Conciliaciones y cierres', 10, PCT, False, 100, 'M', "100 % de cuentas bancarias conciliadas cada mes y diferencias investigadas; soportes completos al contador antes del cierre."),
    ('Presupuesto y control de gastos', 10, PCT, False, 100, 'T', "Desviación operativa dentro del rango aprobado o explicada; oportunidades de ahorro identificadas cada trimestre sin afectar la calidad."),
    ('Cumplimiento fiscal y laboral', 15, PCT, False, 100, 'M', "100 % de obligaciones, informaciones y pagos coordinados antes de la fecha límite; 0 multas, recargos u omisiones."),
    ('Caja chica, activos y documentación', 10, PCT, False, 100, 'M', "100 % de caja chica conciliada y soportada; inventarios y expedientes críticos completos y localizables; 0 diferencias sin explicar."),
    ('Reportes y tiempo de respuesta', 5, PCT, False, 100, 'M', "Informes en las fechas acordadas con datos verificables; respuesta o acuse en máximo 24 horas laborables."),
    ('Controles, mejora y equipo', 10, PCT, False, 100, 'T', "Al menos una mejora de proceso por trimestre; tareas del equipo cumplidas en 95 % o más; 0 hallazgos críticos reincidentes."),
]
K['Encargado de Contabilidad y Tesorería'] = [
    ('Ajustes contables post cierre', 20, CERO, True, 0, 'M', "Contabilidad correcta a la primera: ajustes o correcciones detectados después del cierre."),
    ('Estados financieros a tiempo', 20, PCT, False, 100, 'M', "100 % de los meses, estados financieros entregados dentro del plazo definido."),
    ('Cumplimiento tributario (DGII)', 20, PCT, False, 100, 'M', "100 % de declaraciones y pagos de impuestos a tiempo, sin multas."),
    ('Cobros y pagos según política', 10, PCT, False, 100, 'M', "Días de cobro y de pago a proveedores alineados con la política, sin mora."),
    ('Días para conciliar bancos', 20, 'días', True, 5, 'M', "Conciliación bancaria completa en menos de 5 días hábiles tras el fin de mes."),
    ('Trabajo en equipo (metas del departamento)', 10, None, None, 100, 'M', "Velar porque su departamento cumpla con las metas asignadas."),
]

K['Gerente de Eventos e Impresiones'] = [
    ('Eventos con calidad dentro del presupuesto', 20, PCT, False, 100, 'M', "Eventos ejecutados con calidad y excelencia dentro del presupuesto asignado."),
    ('Montajes y desmontajes a tiempo', 20, PCT, False, 100, 'M', "100 % de montaje y desmontaje en los tiempos planificados."),
    ('Satisfacción del cliente', 15, None, None, 90, 'M', "Más de 90 % en las encuestas post evento."),
    ('Innovación implementada en el trimestre', 15, None, None, 100, 'T', "Más de 1 iniciativa innovadora o sostenible en eventos por trimestre."),
    ('Incidentes de seguridad', 10, None, None, 0, 'M', "0 incidentes mayores; 100 % de protocolos de calidad y seguridad cumplidos."),
    ('Trabajo en equipo (metas del departamento)', 10, None, None, 100, 'M', "Velar porque su departamento cumpla con las metas asignadas."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "Cumplimiento de políticas y procedimientos."),
]
K['Coordinador de Producción de Eventos y Catering'] = [
    ('Eventos sin retrasos', 20, PCT, False, 95, 'M', "Más de 95 % de los eventos con montaje y catering según el horario planificado."),
    ('Satisfacción del cliente', 20, None, None, 90, 'M', "Evaluación del cliente u organizador sobre logística y coordinación: 90/100."),
    ('Eficiencia del presupuesto', 20, None, None, 5, 'M', "Desvío menor a 5 % entre el presupuesto planificado y el costo real del evento."),
    ('Contingencias resueltas', 20, PCT, False, 100, 'M', "Imprevistos resueltos sin afectar el evento: 0 eventos con fallas logísticas graves (evalúa el Gerente)."),
    ('Trabajo en equipo (metas del departamento)', 10, None, None, 100, 'M', "Velar porque su departamento cumpla con las metas asignadas."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "Cumplimiento de políticas y procedimientos."),
]
K['Asistente de Catering y Servicios Generales'] = [
    ('Cronograma de limpieza y organización', 25, PCT, False, 100, 'M', "100 % del cronograma de limpieza y organización cumplido."),
    ('Reducción de desperdicio de insumos', 15, PCT, False, 10, 'T', "Desperdicio de insumos menor en 10 % al trimestre anterior."),
    ('Requerimientos internos atendidos', 20, PCT, False, 100, 'M', "100 % de los requerimientos de mantenimiento y catering atendidos."),
    ('Satisfacción interna', 15, PCT, False, 80, 'T', "Más de 80 % en las encuestas internas."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "100 % de cumplimiento."),
    ('Asistencia a capacitaciones y reuniones', 10, PCT, False, 100, 'M', "100 % de asistencia a capacitaciones y reuniones de seguimiento."),
    ('Trabajo en equipo (metas del departamento)', 5, None, None, 100, 'M', "Trabajo en equipo y actitud positiva."),
]
K['Técnico de Servicios Generales'] = [
    ('Tareas asignadas en tiempo y forma', 20, PCT, False, 95, 'M', "Más de 95 % de las tareas asignadas cumplidas en tiempo y forma."),
    ('Asistencia y puntualidad', 20, PCT, False, 100, 'M', "Asistencia y puntualidad mensual perfecta."),
    ('Errores críticos en montaje', 10, CERO, True, 0, 'M', "0 incidencias o errores críticos en montaje."),
    ('Evaluación del Gerente de Eventos', 10, PCT, False, 85, 'T', "Evaluación de desempeño del Gerente de Eventos mayor a 85 %."),
    ('Equipo y herramientas en buen estado', 15, PCT, False, 100, 'M', "Equipo y herramientas asignadas en estado óptimo."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "Cumplimiento de políticas y procedimientos."),
    ('Apoyo a otras áreas y mantenimiento', 10, PCT, False, 100, 'M', "Disposición para apoyar a las demás áreas, infraestructura y mantenimiento."),
    ('Trabajo en equipo (metas del departamento)', 5, None, None, 100, 'M', "Velar porque sus compañeros cumplan con la meta asignada."),
]
K['Técnico de Instalación y Rotulación'] = [
    ('Instalaciones sin retrabajo', 20, PCT, False, 100, 'M', "100 % libres de errores mayores; menos de 5 % con ajustes menores."),
    ('Montajes a tiempo', 20, PCT, False, 95, 'M', "Más de 95 % de las instalaciones dentro del tiempo estimado."),
    ('Satisfacción del cliente interno', 20, NOTA5, False, 4, 'M', "Valoración del equipo de eventos/diseño sobre la instalación: promedio 4 de 5."),
    ('Incidentes de seguridad', 20, None, None, 0, 'M', "0 incidentes; 100 % de uso de EPP y protocolos en cada trabajo."),
    ('Trabajo en equipo (metas del departamento)', 10, None, None, 100, 'M', "Velar porque su departamento cumpla con las metas asignadas."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "Cumplimiento de políticas y procedimientos."),
]
K['Chofer de Transporte'] = [
    ('Entregas puntuales', 20, PCT, False, 95, 'M', "Más de 95 % de los viajes llegan a tiempo o antes al evento o cliente."),
    ('Incidentes de seguridad', 20, None, None, 0, 'M', "0 accidentes de tránsito prevenibles; récord de conducción segura."),
    ('Mantenimiento preventivo al día', 20, None, None, 100, 'M', "100 % de los mantenimientos del vehículo según cronograma."),
    ('Satisfacción del cliente interno', 20, NOTA5, False, 4, 'M', "Calificación del equipo de eventos sobre apoyo y actitud: más de 4 de 5."),
    ('Trabajo en equipo (metas del departamento)', 10, None, None, 100, 'M', "Velar porque su departamento cumpla con las metas asignadas."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "Cumplimiento de políticas y procedimientos."),
]
K['Encargado de Impresiones'] = [
    ('Impresiones a la primera', 25, PCT, False, 98, 'M', "Más de 98 % de impresiones sin reimpresión por errores (reprocesos menores a 2 %)."),
    ('Impresiones a tiempo', 20, PCT, False, 100, 'M', "100 % de las órdenes de impresión entregadas a tiempo a montaje o evento."),
    ('Desperdicio de material', 20, PCT, True, 3, 'M', "Menos de 3 % de desperdicio (papel, vinil) con cortes e impresiones agrupadas."),
    ('Disponibilidad de máquinas', 10, PCT, False, 95, 'M', "Paradas no planificadas menores a 5 % del tiempo laboral (95 %+ de disponibilidad)."),
    ('Fidelidad de impresión al diseño', 10, NOTA10, False, 9, 'M', "Evaluación del equipo creativo sobre la fidelidad al diseño original: 9 de 10."),
    ('Trabajo en equipo (metas del departamento)', 5, None, None, 100, 'M', "Velar porque su departamento cumpla con las metas asignadas."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "Cumplimiento de políticas y procedimientos."),
]
K['Operador de Maquinarias'] = [
    ('Trabajos entregados en plazo', 20, PCT, False, 95, 'M', "Al menos 95 % de los proyectos entregados dentro del plazo."),
    ('Errores o reclamos de impresión y acabado', 20, PCT, True, 2, 'M', "Tasa de errores o reclamos por fallas de impresión o acabado menor a 2 %."),
    ('Mantenimiento preventivo al día', 15, None, None, 100, 'M', "100 % del mantenimiento preventivo y limpieza mensual."),
    ('Desperdicio de material', 15, PCT, True, 10, 'M', "Menos de 10 % de desperdicio de insumos sobre lo previsto."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "100 % de cumplimiento."),
    ('Trabajo en equipo (metas del departamento)', 10, None, None, 100, 'M', "Velar porque su departamento cumpla con las metas asignadas."),
    ('Asistencia a capacitaciones técnicas', 10, PCT, False, 100, 'M', "100 % de asistencia a capacitaciones técnicas de impresión y seguridad."),
]

K['Gerente de Marketing y Audiovisuales'] = [
    ('Campañas que cumplen sus metas', 20, PCT, False, 90, 'M', "Más de 90 % de campañas que alcanzan los objetivos acordados con el cliente (leads, alcance)."),
    ('Entregas a tiempo según cronograma', 25, None, None, 100, 'M', "100 % de proyectos y campañas lanzados a tiempo, con calidad y sin errores."),
    ('Satisfacción del cliente', 20, None, None, 85, 'M', "Más de 85 % de satisfacción con el trabajo de marketing y audiovisual."),
    ('Crecimiento de audiencia digital', 10, PCT, False, 15, 'T', "Más de 15 % trimestral de crecimiento promedio (seguidores, engagement o tráfico)."),
    ('Innovación implementada en el trimestre', 10, None, None, 100, 'T', "Más de 1 iniciativa, herramienta o formato creativo nuevo por trimestre."),
    ('Organización de archivos y protocolos del área', 10, None, None, 100, 'M', "Que todo su equipo cumpla la organización de archivos y los protocolos de diseño y audiovisuales."),
    ('Trabajo en equipo (metas del departamento)', 5, None, None, 100, 'M', "Velar porque su departamento cumpla con las metas asignadas."),
]
K['Encargado de Creatividad'] = [
    ('Conceptos creativos aprobados', 35, 'conceptos', False, 3, 'M', "Más de 3 conceptos o campañas creativas aprobadas por clientes al mes (9 en el trimestre)."),
    ('Entregas a tiempo según cronograma', 25, None, None, 90, 'M', "Más de 90 % de los proyectos creativos entregados a tiempo."),
    ('Satisfacción del cliente', 20, None, None, 80, 'M', "Más de 80 % en originalidad y calidad creativa."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "Respeto de los procesos y protocolos (brief, revisiones, aprobaciones internas)."),
    ('Trabajo en equipo (metas del departamento)', 10, None, None, 100, 'M', "Velar porque su departamento cumpla con las metas asignadas."),
]
K['Encargado de Medios Digitales'] = [
    ('Entregas a tiempo según cronograma', 15, None, None, 100, 'M', "Cumplimiento del cronograma de producción en campañas clave."),
    ('Calidad visual de entregas', 10, PCT, False, 100, 'M', "Evaluación interna más la retroalimentación del cliente."),
    ('Coordinación entre departamentos', 15, PCT, False, 100, 'M', "Flujo sin cuellos de botella entre departamentos."),
    ('Errores técnicos en entregas', 15, None, None, 0, 'M', "Cero errores técnicos en piezas entregadas (formatos, resolución, ortografía)."),
    ('Mejora continua del equipo', 10, PCT, False, 100, 'M', "Participación en iniciativas de mejora continua del equipo."),
    ('Organización de archivos y protocolos del área', 15, None, None, 100, 'M', "Organización de archivos y protocolos de marketing y audiovisuales."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "Cumplimiento de políticas internas y colaboración en cultura."),
    ('Trabajo en equipo (metas del departamento)', 10, None, None, 100, 'M', "Aporte al trabajo en equipo."),
]
K['Community Manager'] = [
    ('Crecimiento del engagement', 20, PCT, False, 10, 'M', "Engagement en redes 10 % mayor cada mes (30 % trimestral)."),
    ('Respuestas en menos de 24 h', 10, PCT, False, 90, 'M', "90 % de comentarios y mensajes respondidos en menos de 24 horas."),
    ('Contenidos publicados', 20, 'contenidos', False, 20, 'M', "Al menos 20 contenidos al mes que cumplan calidad, alcance y formato."),
    ('Contenido viral', 10, PLAN, False, 100, 'T', "Al menos 1 contenido viral por trimestre (150 %+ del alcance promedio mensual)."),
    ('Entregas a tiempo según cronograma', 20, None, None, 100, 'M', "Cumplimiento con la calidad y los cronogramas de entrega."),
    ('Trabajo en equipo (metas del departamento)', 10, None, None, 100, 'M', "Velar porque su departamento cumpla con las metas asignadas."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "Cumplimiento de políticas y procedimientos."),
]
K['Diseñador Gráfico Senior'] = [
    ('Entregas a tiempo según cronograma', 15, None, None, 100, 'M', "Cumplimiento con la calidad y los cronogramas de entrega."),
    ('Propuestas aprobadas en primera ronda', 20, PCT, False, 100, 'M', "Propuestas gráficas seleccionadas en concursos o aprobadas en primera ronda."),
    ('Artes finales sin correcciones mayores', 15, PCT, False, 100, 'M', "Proyectos entregados sin correcciones mayores en el arte final."),
    ('Organización de archivos y protocolos del área', 10, None, None, 100, 'M', "Organización de archivos y protocolos de diseño."),
    ('Capacitación del trimestre', 10, None, None, 100, 'T', "Al menos 1 capacitación creativa o taller de actualización por trimestre."),
    ('Apoyo al diseñador junior', 10, PCT, False, 100, 'M', "Orientación y apoyo al crecimiento del diseñador junior."),
    ('Trabajo en equipo (metas del departamento)', 10, None, None, 100, 'M', "Apoyar al equipo con los trabajos pendientes."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "Cumplimiento de políticas y procedimientos."),
]
K['Diseñador Gráfico Junior'] = [
    ('Entregas a tiempo según cronograma', 20, None, None, 95, 'M', "Más de 95 % de entregas puntuales según el cronograma aprobado."),
    ('Errores técnicos en entregas', 20, None, None, 0, 'M', "Piezas sin errores de ortografía, formato o resolución."),
    ('Evaluación del gerente de marketing', 20, NOTA10, False, 8, 'M', "Retroalimentación del gerente de marketing y audiovisuales: 8 de 10 o más."),
    ('Capacitación del trimestre', 10, None, None, 100, 'T', "Al menos 1 capacitación trimestral interna o externa."),
    ('Organización de archivos y protocolos del área', 10, None, None, 100, 'M', "Organización de archivos y protocolos de diseño."),
    ('Trabajo en equipo (metas del departamento)', 10, None, None, 100, 'M', "Trabajo en equipo y apoyo a colegas de Marketing y Audiovisuales."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "Cumplimiento de políticas y procedimientos."),
]

K['Encargado de Producción Audiovisual'] = [
    ('Entregas a tiempo según cronograma', 20, None, None, 100, 'M', "100 % de proyectos audiovisuales a tiempo, salvo cambios de alcance justificados."),
    ('Satisfacción del cliente', 20, None, None, 90, 'M', "Más de 90 % de retroalimentación positiva de clientes o gerencia sobre los videos."),
    ('Eficiencia del presupuesto', 10, None, None, 5, 'M', "Excedente máximo de 5 % del costo real contra el presupuesto de cada producción."),
    ('Organización de archivos y protocolos del área', 10, None, None, 100, 'M', "Organización de archivos y protocolos de marketing y audiovisuales."),
    ('Rondas de revisión por trabajo', 10, None, None, 2, 'M', "Menos de 2 rondas de cambios hasta la versión final aprobada."),
    ('Innovación implementada en el trimestre', 10, None, None, 100, 'T', "Al menos 1 recurso técnico innovador por trimestre (drones, cámara 360°, animación)."),
    ('Trabajo en equipo (metas del departamento)', 10, None, None, 100, 'M', "Apoyar a sus compañeros para sacar los trabajos pendientes."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "Cumplimiento de políticas y procedimientos."),
]
K['Coordinador de Estudio de TV y Contenido'] = [
    ('Grabaciones según el calendario maestro', 20, PCT, False, 95, 'M', "Al menos 95 % de grabaciones según el calendario maestro, sin cruces ni retrasos atribuibles a la coordinación."),
    ('Episodios publicados a tiempo', 15, PCT, False, 100, 'M', "Episodios publicados en todas las plataformas en la fecha establecida."),
    ('Grabaciones sin fallas técnicas', 15, PCT, False, 95, 'M', "Al menos 95 % de las grabaciones sin fallas técnicas mayores."),
    ('Bitácora y material entregado a posproducción', 10, PCT, False, 100, 'M', "Bitácora completa de cada grabación y material entregado a posproducción organizado y etiquetado."),
    ('Satisfacción de invitados y productores', 10, NOTA10, False, 9, 'M', "Experiencia en el estudio evaluada en 9 de 10."),
    ('Presupuesto del estudio', 10, PCT, False, 100, 'M', "Ejecución del presupuesto del estudio dentro de lo asignado."),
    ('Innovación implementada en el trimestre', 10, None, None, 100, 'T', "Al menos una mejora técnica o de formato por trimestre."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "Cumplimiento de políticas y procedimientos."),
]
K['Control Master'] = [
    ('Transmisiones y grabaciones sin fallas técnicas', 25, PCT, False, 95, 'M', "Al menos 95 % de transmisiones y grabaciones sin fallas técnicas atribuibles al puesto."),
    ('Programas en horario', 15, PCT, False, 100, 'M', "Programas iniciados y finalizados en el horario establecido."),
    ('Reclamos por derechos de autor', 15, CERO, True, 0, 'M', "Cero reclamos, bloqueos o sanciones por derechos de autor en las plataformas."),
    ('Respaldo de grabaciones en 24 h', 15, PCT, False, 100, 'M', "Archivos de grabación respaldados y entregados al productor en máximo 24 horas."),
    ('Reporte técnico por programa', 10, PCT, False, 100, 'M', "Reporte técnico después de cada programa (fallas y sugerencias de mejora)."),
    ('Equipo técnico y estudio en orden', 10, PCT, False, 100, 'M', "Organización y mantenimiento del equipo técnico y del estudio."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "Cumplimiento de políticas y procedimientos."),
]
K['Especialista en Fotografía y Video'] = [
    ('Material aprobado en la primera revisión', 20, PCT, False, 85, 'M', "Más de 85 % de tomas útiles aprobadas a la primera, sin rehacer sesiones."),
    ('Entrega del material preliminar a tiempo', 20, PCT, False, 100, 'M', "Dentro de 48 h para fotos de eventos; 5 días hábiles para shootings planificados."),
    ('Variedad y creatividad del material', 10, NOTA10, False, 9, 'M', "Evaluación del equipo creativo sobre diversidad y calidad de tomas: 9 de 10."),
    ('Organización de archivos y protocolos del área', 10, None, None, 100, 'M', "Organización de archivos y protocolos de marketing y audiovisuales."),
    ('Mantenimiento preventivo al día', 10, None, None, 100, 'M', "0 sesiones canceladas por fallas de equipo; 100 % del mantenimiento preventivo."),
    ('Material usado en piezas finales', 10, PCT, False, 70, 'M', "Más de 70 % de las fotos y videos capturados se usan en piezas finales."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "Cumplimiento de políticas y procedimientos."),
    ('Trabajo en equipo (metas del departamento)', 10, None, None, 100, 'M', "Apoyar a sus compañeros para sacar los trabajos pendientes."),
]
K['Editor Audiovisual'] = [
    ('Innovación implementada en el trimestre', 20, None, None, 100, 'T', "Innovar en al menos 2 proyectos con nuevas técnicas de edición."),
    ('Entregas a tiempo según cronograma', 20, None, None, 100, 'M', "Cumplimiento con la calidad y los cronogramas de entrega."),
    ('Rondas de revisión por trabajo', 10, None, None, 3, 'M', "Menos de 3 rondas de revisión para llegar a la versión final."),
    ('Organización de archivos y protocolos del área', 10, None, None, 100, 'M', "Organización de archivos y protocolos de ediciones."),
    ('Errores técnicos en entregas', 10, None, None, 0, 'M', "0 devoluciones por errores técnicos u ortografía (audio mal mezclado, formato incorrecto)."),
    ('Satisfacción con el montaje', 5, NOTA10, False, 9, 'M', "Clientes y equipo valoran en 9 de 10 cómo el video o las fotos cuentan la historia."),
    ('Trabajo en equipo (metas del departamento)', 5, None, None, 100, 'M', "Velar porque su departamento cumpla con las metas asignadas."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "Cumplimiento de políticas y procedimientos."),
]
K['Editor de Animación, 3D y VFX'] = [
    ('Piezas animadas entregadas', 10, PLAN, False, 100, 'T', "Mínimo 9 piezas animadas por trimestre."),
    ('Organización de archivos y protocolos del área', 15, None, None, 100, 'M', "Organización de archivos y protocolos de marketing y audiovisuales."),
    ('Entregas a tiempo según cronograma', 20, None, None, 95, 'M', "Más de 95 % de entregas puntuales según el cronograma aprobado."),
    ('Calidad técnica del render', 10, PCT, False, 100, 'M', "Render sin errores, alta resolución, arte final aprobado."),
    ('Rondas de revisión por trabajo', 10, None, None, 2, 'M', "Máximo 2 iteraciones para llegar a la versión final."),
    ('Innovación implementada en el trimestre', 10, None, None, 100, 'T', "Técnicas nuevas o efectos innovadores aplicados por trimestre."),
    ('Retos y campañas creativas', 10, PCT, False, 100, 'M', "Participación en retos o campañas creativas internas y externas."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "Cumplimiento de políticas y orden documental de archivos."),
    ('Trabajo en equipo (metas del departamento)', 5, None, None, 100, 'M', "Trabajo en equipo y colaboración transversal."),
]

K['Herrero'] = [
    ('Fabricación sin retrabajos', 20, PCT, False, 95, 'M', "Trabajos entregados sin correcciones por errores de medida, soldadura o acabado (95 % o más)."),
    ('Estructuras a tiempo', 20, PCT, False, 95, 'M', "Estructuras fabricadas e instaladas en la fecha acordada (95 % o más)."),
    ('Reclamos por calidad estructural', 15, CERO, True, 0, 'M', "Estructuras firmes, niveladas y sin fallas ni reclamos durante su uso: 0 reclamos."),
    ('Incidentes de seguridad', 15, None, None, 0, 'M', "0 accidentes y uso de EPP en el 100 % de los trabajos."),
    ('Equipo y herramientas en buen estado', 10, PCT, False, 100, 'M', "Herramientas y maquinarias en buen estado, sin pérdidas ni daños por mal uso."),
    ('Trabajo en equipo (metas del departamento)', 10, None, None, 100, 'M', "Trabajo en equipo y apoyo al montaje con impresiones y eventos."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "Cumplimiento de políticas y procedimientos."),
]

K['Gerente de Call Center'] = [
    ('Metas comerciales por campaña', 30, PCT, False, 100, 'M', "Cumplimiento de las metas comerciales de cada campaña."),
    ('Calidad promedio QA', 15, None, None, 90, 'M', "Calidad promedio QA del call center: más de 90 %."),
    ('SLA, ASA y abandono', 15, PCT, False, 100, 'M', "Nivel de servicio, tiempo de respuesta y abandono dentro de la meta."),
    ('Conversión de leads', 20, PCT, False, 80, 'M', "Conversión de leads: 80 % o más de la meta."),
    ('Productividad por agente', 10, PCT, False, 100, 'M', "Productividad por agente contra la meta de la campaña."),
    ('Rotación y ausentismo', 5, PCT, False, 100, 'M', "Rotación y ausentismo dentro de la meta."),
    ('Cumplimiento de políticas y procedimientos', 5, None, None, 100, 'M', "Cumplimiento de políticas y procesos."),
]
K['Analista de Calidad y Monitoreo'] = [
    ('Cobertura de monitoreo', 20, PCT, False, 95, 'M', "Monitoreo conforme al plan: más de 95 %."),
    ('Calidad promedio QA', 20, None, None, 90, 'M', "Calidad promedio del call center: más de 90 %."),
    ('Mejora después del coaching', 15, PCT, False, 100, 'M', "Mejora de los agentes evaluados después del coaching."),
    ('Errores críticos y reclamos', 15, CERO, True, 0, 'M', "Reducción de errores críticos y reclamos."),
    ('Consistencia de calibración', 10, PCT, False, 100, 'M', "Calibración consistente entre evaluadores (baja variabilidad)."),
    ('Reportes a tiempo y con calidad', 10, PCT, False, 100, 'M', "Tiempo y calidad en la entrega de reportes."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "Cumplimiento de políticas y confidencialidad."),
]
K['Agente de Call Center Bilingüe'] = [
    ('Calidad promedio QA', 25, None, None, 90, 'M', "Calidad promedio en llamadas evaluadas por QA: más de 90 %."),
    ('Satisfacción del cliente', 20, None, None, 85, 'M', "Satisfacción del cliente: más de 85 %."),
    ('Conversión o resolución efectiva', 20, PCT, False, 100, 'M', "Conversión o resolución efectiva según la meta de la campaña."),
    ('AHT y ACW en rango', 15, PCT, False, 100, 'M', "Tiempo promedio de llamada (AHT) y de trabajo posterior (ACW) dentro de los rangos establecidos."),
    ('Adherencia al horario y puntualidad', 10, None, None, 100, 'M', "Adherencia al horario y puntualidad."),
    ('Scripts, políticas y CRM', 10, PCT, False, 100, 'M', "Cumplimiento de scripts, políticas y registro correcto en el CRM."),
]
K['Agente de Call Center Español'] = [
    ('Objetivo de la campaña', 30, PCT, False, 100, 'M', "Cumplimiento del objetivo de la campaña (ventas, citas, atención)."),
    ('Calidad promedio QA', 25, None, None, 90, 'M', "Calidad promedio QA: más de 90 %."),
    ('Satisfacción del cliente', 20, None, None, 85, 'M', "Satisfacción del cliente: más de 85 %."),
    ('Adherencia al horario y puntualidad', 10, None, None, 100, 'M', "Adherencia al horario y puntualidad."),
    ('Cumplimiento de políticas y procedimientos', 10, None, None, 100, 'M', "Cumplimiento de políticas y procedimientos."),
    ('Uso correcto del CRM', 5, PCT, False, 100, 'M', "Registro completo y correcto de cada contacto en el CRM."),
]

KPIS_OFICIALES = K

# KPIs que la plataforma mide sola (no se anotan a mano): nombre → fuente (ver PlantillaKPI.FUENTES).
AUTOMATICOS = {
    'Asistencia y puntualidad': 'ADHERENCIA',
    'Adherencia al horario y puntualidad': 'ADHERENCIA',
    'Entregas a tiempo según cronograma': 'ENTREGAS_A_TIEMPO',
    'Tareas asignadas en tiempo y forma': 'ENTREGAS_A_TIEMPO',
    'Trabajos entregados en plazo': 'ENTREGAS_A_TIEMPO',
    'Impresiones a tiempo': 'ENTREGAS_A_TIEMPO',
    'Estructuras a tiempo': 'ENTREGAS_A_TIEMPO',
    'Entrega del material preliminar a tiempo': 'ENTREGAS_A_TIEMPO',
    'Rondas de revisión por trabajo': 'RONDAS',
    'Propuestas aprobadas en primera ronda': 'PRIMERA',
    'Material aprobado en la primera revisión': 'PRIMERA',
    'Impresiones a la primera': 'PRIMERA',
    'Fabricación sin retrabajos': 'PRIMERA',
    'Instalaciones sin retrabajo': 'PRIMERA',
}
COMO_SE_MIDE = {
    'ADHERENCIA': 'Automático: promedio de puntualidad, asistencia y horas cumplidas del control de horario.',
    'ENTREGAS_A_TIEMPO': 'Automático: tareas validadas en el mes que se entregaron a tiempo ÷ tareas validadas.',
    'RONDAS': 'Automático: rondas promedio de entrega de las tareas validadas (1 = aprobada a la primera).',
    'PRIMERA': 'Automático: tareas validadas sin devoluciones ÷ tareas validadas.',
}
PERIODICIDAD = {'M': 'MENSUAL', 'T': 'TRIMESTRAL', 'A': 'ANUAL'}


def objetivo(meta, unidad, menor, texto):
    """Lo que pide el documento para este KPI en este puesto (máx. 255). La meta numérica va aparte."""
    return texto[:255]


def plantilla_de(nombre, unidad, menor):
    """(unidad, menor_es_mejor, descripción) de un KPI, sea compartido o propio del puesto."""
    if unidad is None:
        return COMUNES[nombre]
    return unidad, menor, None


# ---------------------------------------------------------------- KPIs de seguimiento (peso 0)
# Se miden solos con los datos de la plataforma, tienen historial y umbral de alerta, pero no cambian la ponderación
# oficial del documento. Así cada puesto queda con 8 a 15 indicadores. Las metas son de arranque: se ajustan con los
# datos de los primeros meses (Puestos → KPI → Editar).
# (fuente, unidad, menor es mejor, meta o None, fórmula)
_GEN = {
    'TAREAS_COMPLETADAS': ('tareas', False, None, 'Tareas validadas en el mes (sin meta fija: referencia para comparar meses).'),
    'PRIMERA': ('%', False, 80, 'Tareas validadas sin devoluciones ÷ tareas validadas × 100.'),
    'RETRABAJO': ('%', True, 20, 'Tareas devueltas al menos una vez ÷ tareas validadas × 100. Menor es mejor.'),
    'HORAS_POR_TAREA': ('horas', True, None, 'Horas del cronómetro ÷ tareas validadas con tiempo registrado.'),
    'DENTRO_ESTIMADO': ('%', False, 80, 'Tareas con horas reales ≤ estimadas + 10 % ÷ tareas con estimado × 100.'),
    'UTILIZACION': ('%', False, 60, 'Minutos del cronómetro en tareas ÷ minutos trabajados en la jornada × 100.'),
    'PUNTUALIDAD': ('%', False, 95, 'Días que llegó a tiempo ÷ días presentes × 100 (control de horario).'),
    'ASISTENCIA': ('%', False, 100, 'Días presentes ÷ días laborables sin permiso × 100 (control de horario).'),
    'HORAS_EXTRA': ('horas', True, 10, 'Horas trabajadas por encima de lo programado en el mes. Más de 10 = riesgo de sobrecarga.'),
}
_NOMBRES = {  # cómo se llama el conteo de trabajo en cada departamento
    'Marketing': ('Piezas producidas y validadas', 'Piezas aprobadas sin corrección', 'Tasa de retrabajo creativo', 'Horas por pieza'),
    'Audiovisual': ('Producciones completadas', 'Producciones aprobadas en primera ronda', 'Retrabajos audiovisuales', 'Horas por producción'),
    'Adzone TV': ('Producciones completadas', 'Producciones aprobadas en primera ronda', 'Retrabajos audiovisuales', 'Horas por producción'),
    'Impresión': ('Trabajos completados', 'Trabajos aprobados a la primera', 'Retrabajos de producción', 'Horas por trabajo'),
    'Tecnología': ('Incidencias y tareas resueltas', 'Resueltas sin reincidencia', 'Reincidencia', 'Horas por incidencia o tarea'),
}
_NOMBRE_GENERAL = ('Tareas completadas', 'Tareas aprobadas a la primera', 'Tareas con correcciones', 'Horas por tarea')
_COMUNES_SEG = {'DENTRO_ESTIMADO': 'Trabajo dentro de las horas estimadas', 'UTILIZACION': 'Jornada registrada en tareas',
                'PUNTUALIDAD': 'Puntualidad de llegada', 'ASISTENCIA': 'Asistencia a la jornada', 'HORAS_EXTRA': 'Horas extra del mes'}


def seguimiento_de(departamento, puesto):
    """Lista de (nombre, fuente, unidad, menor, meta, fórmula) de seguimiento para un puesto."""
    if puesto in ('Presidente del Consejo', 'Vicepresidente y Secretario del Consejo'):
        return []
    if departamento == 'Call Center':
        fuentes = ['PUNTUALIDAD', 'ASISTENCIA', 'HORAS_EXTRA']
    elif puesto == 'CEO / Director General':
        fuentes = ['PUNTUALIDAD', 'HORAS_EXTRA']
    else:
        # en orden de importancia: si el puesto ya tiene muchos KPIs oficiales, se toman los primeros (máximo 15 en total)
        fuentes = ['TAREAS_COMPLETADAS', 'PRIMERA', 'RETRABAJO', 'DENTRO_ESTIMADO', 'PUNTUALIDAD', 'UTILIZACION', 'HORAS_EXTRA', 'HORAS_POR_TAREA']
    oficiales = {AUTOMATICOS.get(k[0]) for k in KPIS_OFICIALES.get(puesto, [])}
    nombres = _NOMBRES.get(departamento, _NOMBRE_GENERAL)
    por_fuente = {'TAREAS_COMPLETADAS': nombres[0], 'PRIMERA': nombres[1], 'RETRABAJO': nombres[2], 'HORAS_POR_TAREA': nombres[3], **_COMUNES_SEG}
    lista = []
    for f in fuentes:
        if f in oficiales or (f == 'RETRABAJO' and 'PRIMERA' in oficiales) or (f == 'PUNTUALIDAD' and 'ADHERENCIA' in oficiales):
            continue  # ya lo mide un KPI oficial del puesto
        unidad, menor, meta, formula = _GEN[f]
        lista.append((por_fuente[f], f, unidad, menor, meta, formula))
    return lista[:max(0, MAXIMO_KPIS - len(KPIS_OFICIALES.get(puesto, [])))] if puesto in KPIS_OFICIALES else lista


MAXIMO_KPIS = 15


# Ficha técnica de cada KPI oficial: fórmula, de dónde sale el dato y quién lo valida.
RESPONSABLE_POR_DEPTO = {
    'Administración': 'Coordinadora Financiera y Administrativa', 'Call Center': 'Analista de Calidad y Monitoreo / Gerente de Call Center',
    'Gerencia': 'Consejo de socios', 'Comercial': 'Director General', 'Gestión del Talento': 'Director General',
}


def ficha_tecnica(nombre, unidad, menor, fuente, departamento):
    """(fórmula, fuente de datos, responsable de validación) de un KPI oficial."""
    if fuente:
        formula = COMO_SE_MIDE.get(fuente, '')
        datos = 'Control de horario de Adzone Team' if fuente == 'ADHERENCIA' else 'Tareas validadas en Adzone Team'
    elif unidad == '% del plan':
        formula, datos = 'Avance logrado del plan del período ÷ plan × 100 (al día = 100).', 'Registro del supervisor en «KPIs del mes»'
    elif unidad == 'casos':
        formula, datos = 'Casos ocurridos en el mes. Meta 0: cualquier caso = 0 % de cumplimiento.', 'Bitácora de incidencias del área'
    elif unidad.startswith('puntos'):
        formula, datos = 'Promedio de las calificaciones del mes.', 'Encuestas o evaluación del supervisor'
    elif unidad == '%':
        formula = ('Valor ÷ base × 100; menor es mejor.' if menor else 'Logrado ÷ total esperado × 100.')
        datos = 'Registro del supervisor en «KPIs del mes» con su evidencia'
    else:
        formula, datos = f'Cantidad de {unidad} en el período.', 'Registro del supervisor en «KPIs del mes»'
    return formula, datos, RESPONSABLE_POR_DEPTO.get(departamento, 'Supervisor directo')
