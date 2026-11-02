"""
Políticas iniciales de ADZONE. Entran como BORRADOR: la administración las revisa (idealmente con su abogado laboral),
las ajusta y las publica. Hasta publicarlas, nadie tiene que aceptarlas.
"""
NOTA = "\n\nBorrador preparado como punto de partida. Debe revisarlo la dirección y su asesor legal antes de publicarlo."

POLITICAS = [
    ('reglamento-interno', 'Reglamento interno de trabajo', 'REGLAMENTO',
     "Normas generales de convivencia, horario, conducta y uso de los recursos de ADZONE.",
     """1. Objeto. Este reglamento regula las relaciones de trabajo en ADZONE Digital Marketing SRL y complementa el Código de Trabajo de la República Dominicana y el contrato de cada colaborador.
2. Jornada. El horario de cada puesto está en Adzone Team (Asistencia → Horarios). Se marca entrada, pausas y salida en la plataforma.
3. Conducta. Se espera respeto, puntualidad, confidencialidad con la información de clientes y cuidado de los equipos.
4. Uso de recursos. Computadoras, cuentas, vehículos, materiales y herramientas son para el trabajo; su uso se rige por las políticas específicas.
5. Comunicación. Los avisos oficiales se publican en Adzone Team. Cada colaborador debe revisarlos.
6. Faltas. Los incumplimientos se documentan según la Política disciplinaria, con derecho a presentar descargo."""),
    ('asistencia', 'Política de asistencia, puntualidad y ausencias', 'ASISTENCIA',
     "Cómo se marca la jornada, la tolerancia de llegada y qué hacer ante una ausencia.",
     """1. Marcaje. Cada colaborador marca su entrada, pausas y salida en Adzone Team (web, celular o agente). Nadie marca por otra persona.
2. Tolerancia. Cada horario tiene minutos de tolerancia; pasada la tolerancia, la llegada cuenta como tardanza.
3. Ausencias. Toda ausencia se avisa al supervisor lo antes posible y se registra en Asistencia → Permisos con su soporte cuando aplique.
4. Correcciones. Un marcaje olvidado lo corrige el supervisor con una nota; queda registrado quién lo hizo.
5. Seguimiento. Tres tardanzas en el mes generan un aviso al supervisor. La asistencia pesa 10 % en el puntaje mensual.
6. Horas extra. Se trabajan con autorización del supervisor y se reconocen según el Código de Trabajo."""),
    ('permisos-vacaciones', 'Política de permisos, vacaciones y licencias', 'PERMISOS',
     "Cómo pedir vacaciones, permisos y licencias en la plataforma.",
     """1. Solicitud. Vacaciones y permisos se piden en Asistencia → Permisos con al menos 15 días de anticipación para vacaciones y 2 días para permisos, salvo emergencias.
2. Aprobación. Los aprueba el supervisor directo; los días aprobados no cuentan como ausencia.
3. Vacaciones. Se disfrutan según el Código de Trabajo, coordinando con el área para no afectar las entregas.
4. Licencias. Las licencias legales (maternidad, paternidad, enfermedad, matrimonio, duelo) se conceden según la ley con su documento soporte.
5. Permisos personales. Pueden ser con o sin disfrute de salario según el caso; queda indicado en la aprobación."""),
    ('uso-tecnologia', 'Política de uso de computadoras, internet y correo', 'TECNOLOGIA',
     "Los equipos y cuentas de ADZONE son para el trabajo.",
     """1. Uso laboral. Las computadoras, el internet y el correo de ADZONE se usan para el trabajo. El uso personal breve se hace en pausa.
2. Software. Solo se instala software con licencia y aprobado por Tecnología. No se usan programas de descarga P2P ni de acceso remoto sin autorización.
3. Sitios. No se accede a contenido para adultos, apuestas o sitios que pongan en riesgo los equipos.
4. Correo. El correo corporativo no se usa para registrarse en servicios personales.
5. Reglas de comportamiento. La plataforma registra el uso de ciertos sitios y aplicaciones definidos en sus reglas; la lista está disponible para todos."""),
    ('monitoreo-privacidad', 'Política de monitoreo de actividad y privacidad', 'MONITOREO',
     "Qué mide el agente de Adzone Team, cuándo, quién lo ve y qué nunca se registra.",
     None),  # el texto sale de la configuración del monitoreo
    ('proteccion-datos', 'Política de protección de datos y confidencialidad', 'DATOS',
     "Cómo se cuida la información de clientes, colaboradores y de la empresa (Ley 172-13).",
     """1. Confidencialidad. La información de clientes, campañas, precios, contraseñas y datos personales es confidencial, durante y después de la relación laboral.
2. Datos personales. Se tratan según la Ley 172-13: solo lo necesario, para fines legítimos y con acceso restringido.
3. Archivos. Los archivos de clientes se guardan en las carpetas y servicios aprobados, no en cuentas personales ni en servicios de envío no aprobados.
4. Salida de información. No se comparten datos de clientes con terceros ni con herramientas de IA no aprobadas.
5. Derechos. Cada colaborador puede pedir acceso, corrección o explicación de sus datos a la administración."""),
    ('seguridad-informatica', 'Política de contraseñas y seguridad informática', 'SEGURIDAD',
     "Contraseñas, accesos y qué hacer ante un incidente.",
     """1. Contraseñas. Personales, de al menos 12 caracteres, sin repetirlas entre servicios; nunca se comparten ni se anotan a la vista.
2. Doble factor. Se activa en correo, redes sociales de clientes y sistemas que lo permitan.
3. Bloqueo. La computadora se bloquea al levantarse del puesto.
4. Incidentes. Correos sospechosos, pérdida de un equipo o un acceso indebido se reportan de inmediato a Tecnología.
5. Accesos. Tecnología da y retira los accesos; al salir de la empresa se desactivan el mismo día."""),
    ('equipos-empresa', 'Política de uso de dispositivos y equipos de la empresa', 'EQUIPOS',
     "Asignación, cuidado y devolución de computadoras, cámaras y herramientas.",
     """1. Asignación. Cada equipo asignado queda registrado en Adzone Team (Activos) con su estado.
2. Cuidado. El colaborador cuida el equipo y reporta cualquier daño o falla a Tecnología o a su supervisor.
3. Traslado. Los equipos salen de la oficina solo con autorización y quedan registrados.
4. Devolución. Al cambiar de puesto o salir de la empresa, los equipos se devuelven en buen estado.
5. Daños por negligencia. Se evalúan caso a caso según la ley y el reglamento."""),
    ('trabajo-remoto', 'Política de trabajo remoto', 'REMOTO',
     "Cuándo y cómo se trabaja fuera de la oficina.",
     """1. Autorización. El trabajo remoto se autoriza por la dirección para puestos y días concretos.
2. Jornada. Se marca igual en Adzone Team y se está disponible en el horario acordado.
3. Equipos y red. Se trabaja con equipos de la empresa o autorizados y redes seguras (no redes públicas abiertas).
4. Confidencialidad. Se aplican las mismas reglas de protección de datos que en la oficina."""),
    ('inteligencia-artificial', 'Política de uso de inteligencia artificial', 'IA',
     "Qué herramientas de IA se pueden usar y con qué información.",
     """1. Herramientas aprobadas. Se usan las herramientas de IA que apruebe la empresa; la lista está en Monitoreo → Reglas.
2. Datos. No se pegan en herramientas de IA datos personales, contraseñas, contratos ni información confidencial de clientes sin autorización.
3. Revisión. Todo contenido generado con IA lo revisa una persona antes de entregarlo al cliente.
4. Transparencia. Se informa al cliente cuando el contrato lo requiera.
5. Propiedad. El trabajo hecho con IA para ADZONE pertenece a ADZONE o al cliente según el contrato."""),
    ('redes-sociales', 'Política de redes sociales y representación de ADZONE', 'REDES',
     "Cómo se representa a ADZONE y a sus clientes en redes.",
     """1. Cuentas de clientes. Se publican solo contenidos aprobados y desde las herramientas autorizadas.
2. Cuentas personales. No se publica información de clientes ni contenidos internos sin autorización.
3. Imagen. Quien hable en nombre de ADZONE lo hace con autorización de la dirección.
4. Crisis. Un comentario negativo o una crisis en la cuenta de un cliente se escala de inmediato al supervisor."""),
    ('vehiculos-herramientas', 'Política de uso de vehículos, materiales y herramientas', 'VEHICULOS',
     "Uso responsable de vehículos, materiales de producción y herramientas.",
     """1. Vehículos. Solo los conduce personal autorizado con licencia vigente, para diligencias de trabajo registradas.
2. Materiales. Los materiales se piden con vale de almacén vinculado a la OT; los sobrantes se devuelven.
3. Herramientas. Se registran al prestarse y se devuelven al terminar el trabajo.
4. Seguridad. En instalaciones y montajes se usa el equipo de protección indicado."""),
    ('calidad-entregas', 'Política de calidad, entregas y revisiones', 'CALIDAD',
     "Cómo se entrega y se revisa el trabajo antes de llegar al cliente.",
     """1. Brief. Ningún trabajo empieza sin brief o alcance claro en la OT.
2. Revisión interna. Toda pieza pasa por la revisión del supervisor antes de enviarse al cliente.
3. Correcciones. Se distingue la corrección pedida por el cliente del error de producción; las de producción cuentan como retrabajo.
4. Plazos. Las entregas se hacen en la fecha comprometida; un riesgo de retraso se avisa con anticipación.
5. Evidencia. Cada entrega queda con su evidencia en la tarea u OT."""),
    ('disciplina', 'Política disciplinaria y medidas correctivas', 'DISCIPLINA',
     "Cómo se documentan las faltas, con derecho a descargo y proporcionalidad.",
     """1. Principios. Las medidas son proporcionales, se documentan y se aplican igual para todos.
2. Escala. Llamado de atención verbal, amonestación escrita, plan de mejora y, en faltas graves, las medidas previstas en el Código de Trabajo.
3. Descargo. Toda observación o amonestación registrada en el expediente permite al colaborador escribir su descargo.
4. Alertas. Una alerta automática de la plataforma (monitoreo, asistencia, KPIs) nunca es por sí sola una sanción: la revisa una persona.
5. Registro. Cada medida queda en el expediente con fecha, responsable y evidencia."""),
]


def sembrar_politicas(autor=None):
    from apps.monitoreo.models import POLITICA
    from .models import Politica, VersionPolitica
    creadas = 0
    for clave, titulo, cat, resumen, contenido in POLITICAS:
        texto = (contenido or POLITICA) + NOTA
        p, nueva = Politica.objects.get_or_create(clave=clave, defaults={
            'titulo': titulo, 'categoria': cat, 'resumen': resumen, 'contenido': texto, 'borrador': True, 'creada_por': autor})
        if nueva:
            VersionPolitica.objects.create(politica=p, version=1, titulo=titulo, contenido=texto, cambio='Versión inicial', por=autor)
            creadas += 1
    return creadas
