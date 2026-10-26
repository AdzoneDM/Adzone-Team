"""Flujo del Vale de Salida de Materiales (F-11) y movimientos de inventario."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.desempeno.servicios import avisar, nombre
from apps.operaciones.permisos import es_almacen, es_coordinacion, es_finanzas, supervisa_area
from apps.operaciones.servicios_ot import ErrorFlujo, coordinadores, registrar
from .models import LineaVale, Material, MovimientoInventario, ValeMaterial


def almacenistas():
    return list(User.objects.filter(is_active=True).filter(Q(groups__name='Almacén') | Q(is_staff=True)).distinct())


def enlace(vale):
    return f"/almacen?vale={vale.pk}"


def puede_solicitar(user, oa):
    ids = {oa.responsable_id, *[c.pk for t in oa.tareas.all() for c in t.companeros.all()]}
    return user.pk in ids or supervisa_area(user, oa.area) or es_coordinacion(user)


def _decimal(valor, campo):
    try:
        d = Decimal(str(valor).replace(',', ''))
    except Exception:  # noqa: BLE001
        raise ErrorFlujo(f"{campo}: cantidad inválida.")
    if d < 0:
        raise ErrorFlujo(f"{campo}: no puede ser negativa.")
    return d


@transaction.atomic
def solicitar(oa, quien, lineas, notas=''):
    if not puede_solicitar(quien, oa):
        raise ErrorFlujo("Pide material quien trabaja en la Orden de Área o su supervisor.")
    if oa.estado not in ('RECIBIDA', 'EN_EJECUCION', 'EN_APROBACION'):
        raise ErrorFlujo("Se pide material para una Orden de Área recibida y en curso.")
    filas = []
    for i, l in enumerate(lineas or []):
        material = Material.objects.filter(pk=l.get('material'), activo=True).first()
        if material is None:
            raise ErrorFlujo(f"Línea {i + 1}: elige el material.")
        cantidad = _decimal(l.get('cantidad'), material.nombre)
        if cantidad <= 0:
            raise ErrorFlujo(f"{material.nombre}: anota la cantidad.")
        filas.append((material, cantidad))
    if not filas:
        raise ErrorFlujo("Agrega al menos un material.")
    vale = ValeMaterial.objects.create(orden=oa.orden, oa=oa, solicitado_por=quien, notas=(notas or '')[:1000])
    for material, cantidad in filas:
        LineaVale.objects.create(vale=vale, material=material, cantidad_solicitada=cantidad, costo_unitario=material.costo_unitario)
    registrar(oa.orden, quien, f"Vale {vale.numero} solicitado para {oa.numero}", ", ".join(f"{c:g} {m.unidad} {m.nombre}" for m, c in filas))
    avisar(coordinadores(), 'ORDEN', f"Vale por autorizar: {vale.numero}", f"{oa.numero} · {nombre(quien)}", enlace=enlace(vale), excepto=quien)
    return vale


def autorizar(vale, quien):
    if not es_coordinacion(quien):
        raise ErrorFlujo("Autoriza Coordinación de Producción.")
    if vale.estado != 'SOLICITADO':
        raise ErrorFlujo("Este vale ya no está por autorizar.")
    vale.estado = 'AUTORIZADO'
    vale.autorizado_por = quien
    vale.fecha_autorizado = timezone.now()
    vale.save(update_fields=['estado', 'autorizado_por', 'fecha_autorizado'])
    registrar(vale.orden, quien, f"Vale {vale.numero} autorizado")
    avisar(almacenistas(), 'ORDEN', f"Vale por despachar: {vale.numero}", f"{vale.oa.numero if vale.oa else vale.orden.codigo}",
           enlace=enlace(vale), excepto=quien)


def rechazar(vale, quien, motivo):
    if not (es_coordinacion(quien) or es_almacen(quien)):
        raise ErrorFlujo("Rechaza Coordinación o Almacén.")
    if vale.estado not in ('SOLICITADO', 'AUTORIZADO'):
        raise ErrorFlujo("Este vale ya fue despachado.")
    if len((motivo or '').strip()) < 3:
        raise ErrorFlujo("Escribe el motivo.")
    vale.estado = 'RECHAZADO'
    vale.notas = (vale.notas + f"\nRechazado: {motivo.strip()}").strip()
    vale.save(update_fields=['estado', 'notas'])
    avisar([vale.solicitado_por], 'ORDEN', f"Vale rechazado: {vale.numero}", motivo, enlace=enlace(vale), excepto=quien)


@transaction.atomic
def despachar(vale, quien, lineas):
    """Almacén entrega y descuenta la existencia en ese momento."""
    if not es_almacen(quien):
        raise ErrorFlujo("Despacha Almacén.")
    if vale.estado != 'AUTORIZADO':
        raise ErrorFlujo("Sin autorización de Coordinación no sale material.")
    datos = {int(l.get('id')): l for l in (lineas or []) if l.get('id')}
    bajos = []
    total = Decimal('0')
    for linea in vale.lineas.select_related('material'):
        d = datos.get(linea.pk, {})
        cantidad = _decimal(d.get('cantidad_despachada', linea.cantidad_solicitada), linea.material.nombre)
        material = Material.objects.select_for_update().get(pk=linea.material_id)
        if cantidad > material.existencia:
            raise ErrorFlujo(f"{material.nombre}: hay {material.existencia:g} {material.unidad} en existencia.")
        linea.cantidad_despachada = cantidad
        linea.lote = (d.get('lote') or '')[:60]
        linea.costo_unitario = material.costo_unitario
        linea.save()
        if cantidad:
            material.existencia -= cantidad
            material.save(update_fields=['existencia'])
            MovimientoInventario.objects.create(material=material, tipo='SALIDA', cantidad=-cantidad, costo_unitario=material.costo_unitario,
                                                vale=vale, usuario=quien, nota=vale.numero)
            total += cantidad
        if material.bajo_minimo:
            bajos.append(material)
    if total <= 0:
        raise ErrorFlujo("No se despachó nada.")
    vale.estado = 'DESPACHADO'
    vale.despachado_por = quien
    vale.fecha_despacho = timezone.now()
    vale.save(update_fields=['estado', 'despachado_por', 'fecha_despacho'])
    registrar(vale.orden, quien, f"Vale {vale.numero} despachado", f"Costo RD$ {vale.costo_total:,.2f}")
    avisar([vale.solicitado_por], 'ORDEN', f"Material listo: {vale.numero}", "Pasa a firmar que lo recibiste.", enlace=enlace(vale), excepto=quien)
    if bajos:
        compras = almacenistas() + [u for u in User.objects.filter(is_active=True) if es_finanzas(u)]
        avisar(compras, 'FINANZAS', "Material bajo el punto de reposición",
               ", ".join(f"{m.nombre} ({m.existencia:g} {m.unidad})" for m in bajos), enlace='/almacen?ver=materiales', excepto=None)


def recibir(vale, quien):
    if vale.estado != 'DESPACHADO':
        raise ErrorFlujo("El vale no está despachado.")
    if vale.recibido_por_id:
        raise ErrorFlujo("Ya se firmó la recepción.")
    if quien.pk == vale.despachado_por_id:
        raise ErrorFlujo("La recepción la firma otra persona, no quien despachó.")
    if not (vale.oa and puede_solicitar(quien, vale.oa)) and quien.pk != vale.solicitado_por_id:
        raise ErrorFlujo("Firma quien recibe el material en el área.")
    vale.recibido_por = quien
    vale.save(update_fields=['recibido_por'])
    registrar(vale.orden, quien, f"Vale {vale.numero}: material recibido en el área")


@transaction.atomic
def cerrar(vale, quien, lineas):
    """Devolución de sobrantes (vuelven a la existencia) y desperdicio con su causa."""
    if vale.estado != 'DESPACHADO':
        raise ErrorFlujo("Solo se cierra un vale despachado.")
    if not (es_almacen(quien) or (vale.oa and supervisa_area(quien, vale.oa.area)) or es_coordinacion(quien)):
        raise ErrorFlujo("Cierra Almacén o el supervisor del área.")
    datos = {int(l.get('id')): l for l in (lineas or []) if l.get('id')}
    for linea in vale.lineas.select_related('material'):
        d = datos.get(linea.pk, {})
        devuelta = _decimal(d.get('cantidad_devuelta') or 0, linea.material.nombre)
        desperdicio = _decimal(d.get('desperdicio') or 0, linea.material.nombre)
        if devuelta + desperdicio > linea.cantidad_despachada:
            raise ErrorFlujo(f"{linea.material.nombre}: devolución + desperdicio no puede pasar de lo despachado.")
        if desperdicio and len((d.get('causa_desperdicio') or '').strip()) < 3:
            raise ErrorFlujo(f"{linea.material.nombre}: anota la causa del desperdicio.")
        linea.cantidad_devuelta = devuelta
        linea.desperdicio = desperdicio
        linea.causa_desperdicio = (d.get('causa_desperdicio') or '')[:150]
        linea.save()
        if devuelta:
            material = Material.objects.select_for_update().get(pk=linea.material_id)
            material.existencia += devuelta
            material.save(update_fields=['existencia'])
            MovimientoInventario.objects.create(material=material, tipo='DEVOLUCION', cantidad=devuelta, costo_unitario=linea.costo_unitario,
                                                vale=vale, usuario=quien, nota=f"Sobrante {vale.numero}")
    vale.estado = 'CERRADO'
    vale.fecha_cierre = timezone.now()
    vale.save(update_fields=['estado', 'fecha_cierre'])
    registrar(vale.orden, quien, f"Vale {vale.numero} cerrado", f"Costo final RD$ {vale.costo_total:,.2f}")


@transaction.atomic
def entrada(material, quien, cantidad, costo_unitario=None, nota=''):
    """Compra o recepción: suma existencia y actualiza el costo promedio."""
    if not es_almacen(quien):
        raise ErrorFlujo("Registra entradas Almacén.")
    cantidad = _decimal(cantidad, material.nombre)
    if cantidad <= 0:
        raise ErrorFlujo("Anota la cantidad que entra.")
    material = Material.objects.select_for_update().get(pk=material.pk)
    costo = _decimal(costo_unitario, 'Costo') if costo_unitario not in (None, '') else material.costo_unitario
    existencia = max(material.existencia, Decimal('0'))
    if existencia + cantidad > 0:
        material.costo_unitario = ((existencia * material.costo_unitario + cantidad * costo) / (existencia + cantidad)).quantize(Decimal('0.01'))
    material.existencia += cantidad
    material.save(update_fields=['existencia', 'costo_unitario'])
    MovimientoInventario.objects.create(material=material, tipo='ENTRADA', cantidad=cantidad, costo_unitario=costo, usuario=quien,
                                        nota=(nota or '')[:255])
    return material


@transaction.atomic
def ajustar(material, quien, existencia_fisica, nota):
    if not es_almacen(quien):
        raise ErrorFlujo("Ajusta el inventario Almacén.")
    if len((nota or '').strip()) < 3:
        raise ErrorFlujo("Explica el ajuste (por ejemplo, conteo físico del día).")
    nueva = _decimal(existencia_fisica, material.nombre)
    material = Material.objects.select_for_update().get(pk=material.pk)
    diferencia = nueva - material.existencia
    material.existencia = nueva
    material.save(update_fields=['existencia'])
    MovimientoInventario.objects.create(material=material, tipo='AJUSTE', cantidad=diferencia, costo_unitario=material.costo_unitario,
                                        usuario=quien, nota=nota.strip()[:255])
    return material
