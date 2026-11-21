"""Módulo retirado: el monitoreo de actividad se eliminó de Adzone Team.

Esta carpeta solo conserva el historial de migraciones (otras apps lo tienen como dependencia) y la migración que borra
sus tablas. Se podrá quitar del todo cuando esas migraciones se reduzcan en un futuro «squash».
"""


import uuid  # noqa: E402


def _ruta_captura(instancia, nombre):
    """La referencia a esta función está en la migración 0001 (campo que la migración final elimina)."""
    return f'monitoreo/{uuid.uuid4().hex}.jpg'
