"""Acciones que dejan rastro: historial de la tarea, avisos y tareas recurrentes."""
import calendar
import logging
import re
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import EsperaAsignacion, EvidenciaArchivo, HistorialTarea, Notificacion, Tarea, TareaRecurrente
from .permisos import administradores, revisores_de, revisores_de_tarea

log = logging.getLogger('adzone')


def nombre(usuario):
    return (usuario.get_full_name() or usuario.username) if usuario else 'Alguien'


def registrar(tarea, usuario, accion, comentario=''):
    HistorialTarea.objects.create(tarea=tarea, usuario=usuario, accion=accion, comentario=comentario or '')


def avisar(destinatarios, tipo, titulo, mensaje='', tarea=None, enlace='', excepto=None):
    """Crea un aviso por persona. Nunca se avisa a quien provocó la acción."""
    vistos = set()
    for usuario in destinatarios:
        if usuario is None or usuario.pk in vistos or (excepto and usuario.pk == excepto.pk):
            continue
        vistos.add(usuario.pk)
        Notificacion.objects.create(destinatario=usuario, remitente=excepto, tipo=tipo, titulo=titulo[:255],
                                    mensaje=mensaje, tarea=tarea, enlace=enlace)


def tras_cambio(tarea, quien, evento=None):
    """La orden de trabajo sigue a su tarea y las automatizaciones se enteran."""
    from apps.operaciones.servicios import sincronizar_desde_tareas
    sincronizar_desde_tareas(tarea, quien)
    if evento:
        from apps.automatizaciones.motor import disparar
        disparar(evento, tarea, quien=quien)


def cerrar_esperas(usuarios, tarea):
    """Llegó trabajo nuevo: termina la «espera de asignación» de esas personas."""
    ids = [u.pk for u in usuarios if u is not None]
    if ids:
        EsperaAsignacion.objects.filter(usuario_id__in=ids, hasta__isnull=True).update(hasta=timezone.now(), tarea_recibida=tarea)


def al_asignar(tarea, quien):
    registrar(tarea, quien, 'CREADA')
    cerrar_esperas([tarea.colaborador, *tarea.companeros.all()], tarea)
    avisar([tarea.colaborador, *tarea.companeros.all()], 'ASIGNADA', f"Nueva tarea: {tarea.titulo}",
           f"{nombre(quien)} te la asignó. Entrega: {tarea.fecha_limite:%d/%m/%Y}.",
           tarea=tarea, enlace='/mis-tareas', excepto=quien)


def al_entregar(tarea, quien):
    registrar(tarea, quien, 'ENTREGADA', tarea.evidencia_nota)
    ronda = f" (entrega n.º {tarea.rondas_revision + 1})" if tarea.rondas_revision else ''
    archivos = EvidenciaArchivo.objects.filter(tarea=tarea).count()  # sin la caché de la tarea: los archivos son recién subidos
    partes = [f"{archivos} archivo(s)" if archivos else '', 'enlace' if tarea.evidencia_enlace else '',
              'nota' if tarea.evidencia_nota else '']
    evidencia = ', '.join(p for p in partes if p)  # entregar exige evidencia: siempre hay algo
    # Su supervisor y también la administración: cualquiera de los dos la valida desde «Por validar».
    avisar([*revisores_de_tarea(tarea), *([] if tarea.revisor_id else administradores())], 'ENTREGADA', f"Por validar: {tarea.titulo}",
           f"{nombre(quien)} la entregó{ronda} con evidencia: {evidencia}.", tarea=tarea, enlace=f'/validar?tarea={tarea.pk}', excepto=quien)
    tras_cambio(tarea, quien, 'TAREA_ENTREGADA')


def al_validar(tarea, quien):
    estrellas = f" · {tarea.calificacion_calidad}/5" if tarea.calificacion_calidad else ''
    auto = quien.pk == tarea.colaborador_id
    registrar(tarea, quien, 'VALIDADA', (f"Calidad {tarea.calificacion_calidad}/5. {tarea.comentario_evaluacion}".strip())
              + (" · Autovalidada por quien la hizo (la había creado para sí)." if auto else ""))
    avisar([tarea.colaborador, *tarea.companeros.all()], 'VALIDADA', f"Validada: {tarea.titulo}",
           f"{nombre(quien)} validó tu entrega{estrellas}. Ya cuenta para tu puntaje.",
           tarea=tarea, enlace='/mis-tareas?ver=validadas', excepto=quien)
    tras_cambio(tarea, quien, 'TAREA_VALIDADA')


def _archivos_texto(n):
    return f"{n} archivo{'s' if n != 1 else ''} de referencia"


def al_devolver(tarea, quien, referencias=0):
    registrar(tarea, quien, 'DEVUELTA', tarea.comentario_revision + (f" (adjuntó {_archivos_texto(referencias)})" if referencias else ''))
    mensaje = tarea.comentario_revision + (f"\n📎 Adjuntó {_archivos_texto(referencias)} para la corrección." if referencias else '')
    avisar([tarea.colaborador, *tarea.companeros.all()], 'DEVUELTA', f"Para corregir: {tarea.titulo}",
           mensaje, tarea=tarea, enlace='/mis-tareas', excepto=quien)
    tras_cambio(tarea, quien)


def al_referenciar(tarea, quien, n):
    """Se adjuntaron bocetos o imágenes de referencia a una tarea: queda en el historial y le llega a quien la trabaja.
    Si justo se acaba de avisar de esa tarea (asignada o devuelta) y el aviso sigue sin leer, el archivo se suma a ese
    mismo aviso: no le salen dos alertas por lo mismo."""
    registrar(tarea, quien, 'EDITADA', f"Adjuntó {_archivos_texto(n)}")
    destinatarios = [tarea.colaborador, *tarea.companeros.all()]
    reciente = timezone.now() - timedelta(minutes=5)
    pendientes = {x.destinatario_id: x for x in Notificacion.objects.filter(
        tarea=tarea, remitente=quien, tipo__in=('ASIGNADA', 'DEVUELTA'), leida=False, fecha__gte=reciente)}
    sin_aviso = []
    for u in destinatarios:
        previo = pendientes.get(u.pk)
        if previo and u.pk != quien.pk:
            previo.mensaje = f"{previo.mensaje}\n📎 Adjuntó {_archivos_texto(n)}.".strip()
            previo.save(update_fields=['mensaje'])
        else:
            sin_aviso.append(u)
    avisar(sin_aviso, 'MODIFICADA', f"Nueva referencia: {tarea.titulo}",
           f"{nombre(quien)} adjuntó {_archivos_texto(n)} a tu tarea.", tarea=tarea, enlace='/mis-tareas', excepto=quien)


CAMPOS_AVISO = {'titulo': 'el título', 'descripcion': 'la descripción', 'fecha_limite': 'la fecha de entrega',
                'prioridad': 'la prioridad', 'fecha_inicio': 'la fecha de inicio', 'horas_estimadas': 'las horas estimadas',
                'cliente': 'el cliente', 'proyecto': 'el proyecto', 'pasos_texto': 'los pasos'}


# Cambios que exigen un motivo y quedan con «antes → después» en el historial.
CAMPOS_CON_MOTIVO = {'fecha_limite': 'Fecha de entrega', 'fecha_inicio': 'Fecha de inicio', 'prioridad': 'Prioridad', 'colaborador': 'Responsable'}
CAMPOS_DETALLE = {**CAMPOS_CON_MOTIVO, 'titulo': 'Título', 'cliente': 'Cliente', 'horas_estimadas': 'Horas estimadas', 'proyecto': 'Proyecto'}
CAMPOS_LARGOS = {'descripcion', 'pasos_texto'}   # se registra que cambiaron, sin copiar el texto


def valor_legible(campo, valor):
    if valor in (None, ''):
        return 'sin definir'
    if campo in ('fecha_limite', 'fecha_inicio'):
        return valor.strftime('%d/%m/%Y') if hasattr(valor, 'strftime') else str(valor)
    if campo == 'prioridad':
        return dict(Tarea.PRIORIDAD_CHOICES).get(valor, str(valor))
    if campo == 'colaborador':
        return nombre(valor)
    return str(valor)


def detalle_de_cambios(previos, tarea, campos, motivo='', pasos_antes=None, pasos_despues=None):
    """Texto del historial: una línea por campo con el valor anterior y el nuevo, y el motivo si lo hay."""
    lineas = []
    for c in campos:
        if c in CAMPOS_DETALLE:
            antes, ahora = valor_legible(c, previos.get(c)), valor_legible(c, getattr(tarea, c, None))
            if antes != ahora:
                lineas.append(f"{CAMPOS_DETALLE[c]}: {antes} → {ahora}")
        elif c == 'descripcion' and (previos.get(c) or '') != (tarea.descripcion or ''):
            lineas.append("Descripción: actualizada")
        elif c == 'pasos_texto' and pasos_antes != pasos_despues:
            lineas.append("Pasos: actualizados")
    if motivo:
        lineas.append(f"Motivo: {motivo}")
    return '\n'.join(lineas)


def al_modificar(tarea, quien, campos, motivo=''):
    """Aviso a los participantes cuando cambia algo que les importa (no por cada guardado sin cambios)."""
    cambios = [CAMPOS_AVISO[c] for c in campos if c in CAMPOS_AVISO]
    if not cambios or tarea.estado in ('COMPLETADA', 'CANCELADA'):
        return
    texto = ', '.join(cambios)
    extra = f" Nueva entrega: {tarea.fecha_limite:%d/%m/%Y}." if 'fecha_limite' in campos else ''
    extra += f" Motivo: {motivo}" if motivo else ''
    avisar([tarea.colaborador, *tarea.companeros.all()], 'MODIFICADA', f"Cambió una tarea: {tarea.titulo}",
           f"{nombre(quien)} cambió {texto}.{extra}", tarea=tarea, enlace=f'/mis-tareas?tarea={tarea.pk}', excepto=quien)


def al_bloquear(tarea, quien):
    registrar(tarea, quien, 'BLOQUEADA', tarea.motivo_bloqueo)
    avisar([*revisores_de_tarea(tarea), tarea.colaborador, *tarea.companeros.all()], 'BLOQUEADA',
           f"Bloqueada: {tarea.titulo}", f"{nombre(quien)}: {tarea.motivo_bloqueo}",
           tarea=tarea, enlace=f'/equipo?colaborador={tarea.colaborador_id}', excepto=quien)
    tras_cambio(tarea, quien)


def al_desbloquear(tarea, quien, nota=''):
    registrar(tarea, quien, 'DESBLOQUEADA', nota)
    avisar([*revisores_de_tarea(tarea), tarea.colaborador, *tarea.companeros.all()], 'BLOQUEADA',
           f"Se puede seguir: {tarea.titulo}", nota or f"{nombre(quien)} la desbloqueó.",
           tarea=tarea, enlace='/mis-tareas', excepto=quien)
    tras_cambio(tarea, quien)


DIAS_BLOQUEO_AVISO = 2


def avisar_bloqueadas(ahora=None):
    """Tareas bloqueadas hace más de 2 días: recordatorio diario al supervisor (para el cron)."""
    ahora = ahora or timezone.now()
    limite = ahora - timedelta(days=DIAS_BLOQUEO_AVISO)
    hoy0 = ahora - timedelta(hours=20)
    n = 0
    for tarea in Tarea.objects.filter(estado='BLOQUEADA', bloqueada_desde__lte=limite).select_related('colaborador'):
        if Notificacion.objects.filter(tarea=tarea, tipo='BLOQUEADA', fecha__gte=hoy0).exists():
            continue
        dias = (ahora - tarea.bloqueada_desde).days
        avisar(revisores_de_tarea(tarea), 'BLOQUEADA', f"Sigue bloqueada ({dias} días): {tarea.titulo}",
               f"{nombre(tarea.colaborador)}: {tarea.motivo_bloqueo}", tarea=tarea,
               enlace=f'/equipo?colaborador={tarea.colaborador_id}')
        n += 1
    return n


def al_reabrir(tarea, quien, motivo):
    registrar(tarea, quien, 'REABIERTA', motivo)
    avisar([tarea.colaborador, *tarea.companeros.all()], 'REABIERTA', f"Reabierta: {tarea.titulo}",
           motivo or f"{nombre(quien)} la volvió a poner en revisión.", tarea=tarea, enlace='/mis-tareas', excepto=quien)
    tras_cambio(tarea, quien)


# ---------------------------------------------------------------------------
# Tareas recurrentes
# ---------------------------------------------------------------------------
DIAS_ADELANTE = 7  # se crean con una semana de anticipación para que el colaborador las vea venir


def fechas_de(recurrente, desde, hasta):
    """Fechas de entrega de la recurrente entre `desde` y `hasta` (incluidas)."""
    fechas = []
    if recurrente.frecuencia == 'SEMANAL':
        dia = desde + timedelta(days=(recurrente.dia_semana - desde.weekday()) % 7)
        while dia <= hasta:
            fechas.append(dia)
            dia += timedelta(days=7)
    else:
        anio, mes = desde.year, desde.month
        while True:
            ultimo = calendar.monthrange(anio, mes)[1]
            dia = date(anio, mes, min(recurrente.dia_mes, ultimo))
            if dia > hasta:
                break
            if dia >= desde:
                fechas.append(dia)
            mes += 1
            if mes > 12:
                anio, mes = anio + 1, 1
    return fechas


def generar_recurrentes(hoy=None):
    """Crea las tareas de las recurrentes activas hasta una semana adelante. Se puede llamar las veces que sea."""
    hoy = hoy or timezone.localdate()
    hasta = hoy + timedelta(days=DIAS_ADELANTE)
    creadas = 0
    for rec in TareaRecurrente.objects.filter(activa=True, colaborador__is_active=True).select_related('colaborador'):
        desde = max(rec.inicio, (rec.generada_hasta + timedelta(days=1)) if rec.generada_hasta else rec.inicio)
        if desde > hasta:
            continue
        with transaction.atomic():
            for fecha in fechas_de(rec, desde, hasta):
                if Tarea.objects.filter(recurrencia=rec, fecha_limite=fecha).exists():
                    continue
                tarea = Tarea.objects.create(
                    titulo=rec.titulo, descripcion=rec.descripcion, colaborador=rec.colaborador,
                    asignada_por=rec.creada_por, kpi_asignado=rec.kpi_asignado, prioridad=rec.prioridad,
                    fecha_limite=fecha, recurrencia=rec,
                )
                registrar(tarea, rec.creada_por, 'CREADA', 'Generada automáticamente por una tarea recurrente.')
                avisar([rec.colaborador], 'ASIGNADA', f"Nueva tarea: {tarea.titulo}",
                       f"Tarea recurrente. Entrega: {fecha:%d/%m/%Y}.", tarea=tarea, enlace='/mis-tareas')
                creadas += 1
            rec.generada_hasta = hasta
            rec.save(update_fields=['generada_hasta'])
    if creadas:
        log.info("Tareas recurrentes generadas: %s", creadas)
    return creadas


_ultima_generacion = {'dia': None}


def generar_recurrentes_si_toca():
    """Sin cron en el servidor, se generan la primera vez que alguien abre sus tareas cada día."""
    hoy = timezone.localdate()
    if _ultima_generacion['dia'] == hoy:
        return
    _ultima_generacion['dia'] = hoy
    try:
        generar_recurrentes(hoy)
    except Exception:  # nunca debe impedir que se vea la lista de tareas
        log.exception("No se pudieron generar las tareas recurrentes")


def avisar_por_vencer(hoy=None):
    """Aviso del día anterior a la fecha límite (para el cron diario)."""
    hoy = hoy or timezone.localdate()
    manana = hoy + timedelta(days=1)
    n = 0
    for tarea in Tarea.objects.filter(fecha_limite=manana, estado__in=['PENDIENTE', 'EN_PROGRESO']).select_related('colaborador'):
        if Notificacion.objects.filter(tarea=tarea, tipo='VENCE').exists():
            continue
        avisar([tarea.colaborador], 'VENCE', f"Vence mañana: {tarea.titulo}", '', tarea=tarea, enlace='/mis-tareas')
        n += 1
    return n


# ---------------------------------------------------------------------------
# Recordar y pedir trabajo (ideas traídas de Adzone Team)
# ---------------------------------------------------------------------------
ESPERA_PEDIR_TRABAJO = timedelta(hours=2)


def recordatorios_enviados(tarea):
    """Cuántas veces se ha recordado esta tarea (un envío = un aviso a quien la trabaja)."""
    return Notificacion.objects.filter(tarea=tarea, tipo='RECORDATORIO', destinatario=tarea.colaborador).count()


def recordar(tarea, quien, mensaje=''):
    """El supervisor le recuerda una tarea abierta al colaborador. Dos límites, ambos configurables en Reglas del puntaje:
    una espera corta entre recordatorios (por defecto 2 min, solo evita enviarlo dos veces sin querer) y un máximo de
    recordatorios por tarea (por defecto 15)."""
    from .models import ConfiguracionDesempeno
    config = ConfiguracionDesempeno.actual()
    if config.max_recordatorios and recordatorios_enviados(tarea) >= config.max_recordatorios:
        return f"Ya se envió el máximo de {config.max_recordatorios} recordatorios de esta tarea. Habla con la persona o cámbiale la fecha."
    espera = timedelta(minutes=config.espera_recordatorio_min)
    ultimo = Notificacion.objects.filter(tarea=tarea, tipo='RECORDATORIO', fecha__gte=timezone.now() - espera).order_by('-fecha').first() if espera else None
    if ultimo:
        faltan = max(1, int((ultimo.fecha + espera - timezone.now()).total_seconds()))
        return f"Ya se le recordó esta tarea. Podrás volver a recordársela en {faltan // 60} min {faltan % 60:02d} s." if faltan >= 60 else f"Ya se le recordó esta tarea. Podrás volver a recordársela en {faltan} s."
    avisar([tarea.colaborador, *tarea.companeros.all()], 'RECORDATORIO', f"{nombre(quien)} te pide avanzar: {tarea.titulo}",
           mensaje or f"Entrega: {tarea.fecha_limite:%d/%m/%Y}.", tarea=tarea, enlace=f'/mis-tareas?tarea={tarea.id}',
           excepto=quien)
    return None


def espera_abierta(usuario):
    return EsperaAsignacion.objects.filter(usuario=usuario, hasta__isnull=True).first()


def pedir_trabajo(quien):
    """
    El colaborador sin tareas por hacer avisa a su supervisor: queda «en espera de asignación» hasta que le llegue
    una tarea. Las tareas bloqueadas no cuentan como trabajo por hacer (no puede avanzarlas).
    """
    abiertas = Tarea.objects.filter(Q(colaborador=quien) | Q(companeros=quien), estado__in=['PENDIENTE', 'EN_PROGRESO']).distinct().count()
    if abiertas:
        return f"Todavía tienes {abiertas} tarea(s) por hacer. Avisa cuando termines."
    bloqueadas = Tarea.objects.filter(Q(colaborador=quien) | Q(companeros=quien), estado='BLOQUEADA').distinct().count()
    hace_poco = timezone.now() - ESPERA_PEDIR_TRABAJO
    if espera_abierta(quien) and Notificacion.objects.filter(remitente=quien, tipo='PIDE_TRABAJO', fecha__gte=hace_poco).exists():
        return "Ya avisaste hace poco. Tu supervisor ya lo sabe: mientras tanto puedes registrar actividades adicionales."
    if not espera_abierta(quien):
        EsperaAsignacion.objects.create(usuario=quien)
    jefes = revisores_de(quien)
    extra = f" Tiene {bloqueadas} tarea(s) bloqueada(s)." if bloqueadas else ''
    avisar(jefes, 'PIDE_TRABAJO', f"{nombre(quien)} terminó sus tareas: en espera de asignación",
           f"No tiene tareas por hacer.{extra}", enlace=f'/equipo?colaborador={quien.id}', excepto=quien)
    return [nombre(j) for j in jefes]


MENCION = re.compile(r'(?<![\w.@])@([\w.-]+)')


def ven_la_tarea(u, tarea):
    """Quién puede ver una tarea (y por tanto su conversación): quien la hace, quien colabora, quien la asignó, su supervisor y Dirección."""
    from .permisos import es_administrador, puede_gestionar
    return bool(u.is_active and (es_administrador(u) or u.pk in tarea.participantes_ids() or tarea.asignada_por_id == u.pk
                                 or puede_gestionar(u, tarea.colaborador, 'equipo.ver')))


def comentar_tarea(tarea, autor, texto, responde_a=None):
    """Agrega un comentario a la tarea: queda en el historial, le avisa a las personas involucradas (y a quien se mencione) sin llenar la campanita."""
    from .models import ComentarioTarea
    texto = (texto or '').strip()
    nombres = {m.rstrip('.-').lower() for m in MENCION.findall(texto)}
    nombres.discard('')
    mencionados = [u for u in User.objects.filter(is_active=True).exclude(pk=autor.pk) if u.username.lower() in nombres and ven_la_tarea(u, tarea)]
    c = ComentarioTarea.objects.create(tarea=tarea, autor=autor, texto=texto, responde_a=responde_a,
                                       menciones=[{'id': u.pk, 'username': u.username, 'nombre': nombre(u)} for u in mencionados])
    registrar(tarea, autor, 'COMENTADA', texto[:300])
    involucrados = {u.pk: u for u in [tarea.colaborador, *tarea.companeros.all(), tarea.asignada_por] if u and u.is_active}
    if tarea.estado == 'EN_REVISION':
        involucrados.update({u.pk: u for u in revisores_de_tarea(tarea)})
    for u in mencionados:
        involucrados.setdefault(u.pk, u)
    ya_mencionados = {u.pk for u in mencionados}
    for u in involucrados.values():
        if u.pk == autor.pk or not ven_la_tarea(u, tarea):
            continue
        enlace = f'/mis-tareas?tarea={tarea.pk}' if u.pk in tarea.participantes_ids() else f'/equipo?tarea={tarea.pk}'
        _avisar_comentario(u, tarea, autor, texto, enlace, mencion=u.pk in ya_mencionados)
    return c


def _avisar_comentario(u, tarea, autor, texto, enlace, mencion=False):
    """Un solo aviso sin leer por tarea: si ya hay uno, se reemplaza por el más reciente (así una conversación larga no llena la campanita)."""
    Notificacion.objects.filter(destinatario=u, tarea=tarea, tipo='COMENTARIO', leida=False).delete()
    titulo = f"{nombre(autor)} te mencionó en: {tarea.titulo}" if mencion else f"Comentario nuevo en: {tarea.titulo}"
    Notificacion.objects.create(destinatario=u, remitente=autor, tipo='COMENTARIO', titulo=titulo[:255], mensaje=f"{nombre(autor)}: {texto[:280]}", tarea=tarea, enlace=enlace)


DIAS_AVISO_VENCIDA = 14   # solo se avisa de lo que venció hace poco (no de tareas viejas olvidadas)


def avisar_vencidas(hoy=None):
    """Una sola vez por tarea: avisa a quien la tiene que ya venció (y a quien la supervisa). Para el cron diario; devuelve cuántas avisó."""
    hoy = hoy or timezone.localdate()
    n = 0
    tareas = Tarea.objects.filter(estado__in=('PENDIENTE', 'EN_PROGRESO'), fecha_limite__lt=hoy, fecha_limite__gte=hoy - timedelta(days=DIAS_AVISO_VENCIDA)
                                  ).select_related('colaborador').prefetch_related('companeros')
    for t in tareas:
        if Notificacion.objects.filter(tarea=t, tipo='VENCE', titulo__startswith='Venció').exists():
            continue
        limite = f"{t.fecha_limite:%d/%m/%Y}"
        avisar([t.colaborador, *t.companeros.all()], 'VENCE', f"Venció: {t.titulo}", f"Su fecha límite era el {limite}. Entrégala o pídele a tu supervisor una nueva fecha.",
               tarea=t, enlace='/mis-tareas')
        avisar([u for u in revisores_de_tarea(t) if u.pk != t.colaborador_id], 'VENCE', f"Vencida: {t.titulo}",
               f"{nombre(t.colaborador)} no la entregó a tiempo (límite {limite}).", tarea=t, enlace=f'/equipo?colaborador={t.colaborador_id}')
        n += 1
    return n


def purgar_videos(hoy=None):
    """Borra los videos (evidencias y referencias) de las tareas ya validadas, pasados `dias_conservar_videos` desde la validación.
    El archivo se elimina del disco (pesan mucho); la fila queda marcada para mostrar «se borró solo» y no perder el historial."""
    from datetime import timedelta
    from django.utils import timezone
    from .models import ConfiguracionDesempeno, EvidenciaArchivo, ReferenciaArchivo
    hoy = hoy or timezone.localdate()
    corte = hoy - timedelta(days=ConfiguracionDesempeno.actual().dias_conservar_videos)
    borrados = liberado = 0
    for modelo in (EvidenciaArchivo, ReferenciaArchivo):
        for f in modelo.objects.filter(purgado=False, tarea__estado='COMPLETADA', tarea__fecha_completada__lte=corte).exclude(archivo=''):
            if not f.es_video:
                continue
            liberado += f.tamano or 0
            try:
                f.archivo.delete(save=False)
            except OSError:
                pass
            f.purgado, f.purgado_en = True, timezone.now()
            f.save(update_fields=['archivo', 'purgado', 'purgado_en'])
            borrados += 1
    return borrados, liberado
