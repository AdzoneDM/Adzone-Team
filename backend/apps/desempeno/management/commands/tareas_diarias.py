"""Tarea programada diaria (cron de Plesk): recurrentes, avisos de vencimiento y automatizaciones de vencidas.

    python manage.py tareas_diarias
"""
from django.core.management.base import BaseCommand

from apps.desempeno.servicios import avisar_bloqueadas, avisar_por_vencer, generar_recurrentes


class Command(BaseCommand):
    help = "Genera las tareas recurrentes de la próxima semana y avisa las tareas que vencen mañana."

    def handle(self, *args, **options):
        creadas = generar_recurrentes()
        avisos = avisar_por_vencer()
        bloqueadas = avisar_bloqueadas()
        from apps.desempeno.servicios import avisar_vencidas
        vencidas = avisar_vencidas()
        if vencidas:
            self.stdout.write(f'Tareas vencidas avisadas: {vencidas}.')
        try:
            from apps.finanzas.servicios import avisar_vencimientos
            cobros = avisar_vencimientos()
            if cobros:
                self.stdout.write(f'Recordatorios de cobro a Finanzas: {cobros}.')
        except Exception as e:  # noqa: BLE001 (un fallo aquí nunca detiene el resto de las tareas del día)
            self.stderr.write(f'Recordatorios de cobro no generados: {e}')
        try:
            from apps.comercial.servicios import avisar_seguimientos
            seguimientos = avisar_seguimientos()
            if seguimientos:
                self.stdout.write(f'Seguimientos comerciales avisados: {seguimientos}.')
        except Exception as e:  # noqa: BLE001
            self.stderr.write(f'Seguimientos comerciales no avisados: {e}')
        from apps.automatizaciones.motor import revisar_vencimientos
        reglas = revisar_vencimientos()
        from apps.operaciones.servicios_ot import revisar_excepciones
        excepciones = revisar_excepciones()
        from apps.core.views_respaldos import recordar_semanal
        recordar_semanal()
        from apps.desempeno.servicios import purgar_videos
        videos, bytes_liberados = purgar_videos()
        from apps.chat.servicios import purgar_videos_del_chat
        v_chat, b_chat = purgar_videos_del_chat()
        videos, bytes_liberados = videos + v_chat, bytes_liberados + b_chat
        if videos:
            self.stdout.write(f'Videos de tareas validadas borrados: {videos} ({bytes_liberados // 1024 // 1024} MB).')
        from apps.organizacion.cuentas import reactivar_suspensiones_vencidas
        reactivadas = reactivar_suspensiones_vencidas()
        if reactivadas:
            self.stdout.write(f'Suspensiones terminadas (cuentas reactivadas): {reactivadas}.')
        from apps.desempeno.inteligencia import avisar_resumen
        try:
            avisar_resumen()
        except Exception as e:  # noqa: BLE001 (el resumen nunca detiene el resto de las tareas del día)
            self.stderr.write(f'Resumen semanal no generado: {e}')
        cashflow = ''
        from django.conf import settings
        if settings.CASHFLOW_MODO == 'real':
            from apps.integraciones.cashflow.servicios import sincronizar_pendientes
            r = sincronizar_pendientes()
            cashflow = f" Cashflow: {r['facturas']} facturas, {r['pagos']} pagos nuevos, {r['errores']} errores."
        self.stdout.write(self.style.SUCCESS(
            f"Tareas recurrentes creadas: {creadas}. Avisos de vencimiento: {avisos}. Bloqueadas recordadas: {bloqueadas}. Automatizaciones ejecutadas: {reglas}. "
            f"Excepciones G0 sin regularizar: {excepciones}.{cashflow}"))
