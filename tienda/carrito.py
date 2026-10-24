"""
Lógica de negocio del carrito y del pedido (todo se calcula en el SERVIDOR).

Principio: el navegador solo envía {id_producto, cantidad}. Precios, subtotales,
totales y existencia del producto se leen siempre de la base de datos.
"""
import hashlib
from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import CarritoCliente, DetallePedido, Pedido, PedidoToken, Producto

MAX_CANTIDAD = getattr(settings, "CARRITO_MAX_POR_PRODUCTO", 99)
MAX_LINEAS = getattr(settings, "CARRITO_MAX_LINEAS", 50)
CENT = Decimal("0.01")


class CarritoError(Exception):
    """Error controlado que se devuelve al cliente como JSON."""

    def __init__(self, codigo, mensaje, status=400, detalle=None):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.status = status
        self.detalle = detalle or {}


def es_entero(valor):
    # bool es subclase de int en Python: se rechaza explícitamente.
    return isinstance(valor, int) and not isinstance(valor, bool)


def parsear_items(crudo, estricto=True):
    """
    Convierte [{"id": 3, "qty": 2}, ...] en {3: 2}.

    - id y qty deben ser enteros (no decimales, no texto, no booleanos).
    - qty < 1 -> error (nunca se acepta 0 ni negativos).
    - qty > MAX_CANTIDAD -> error si `estricto` (compra); si no, se recorta
      (solo para mostrar/sincronizar el carrito).
    - Las líneas repetidas del mismo producto se SUMAN en una sola.
    """
    if not isinstance(crudo, list):
        raise CarritoError("solicitud_invalida", "El formato del carrito no es válido.")
    if len(crudo) > MAX_LINEAS:
        raise CarritoError(
            "demasiadas_lineas", f"El carrito admite como máximo {MAX_LINEAS} productos distintos."
        )
    items = {}
    for fila in crudo:
        if not isinstance(fila, dict):
            raise CarritoError("solicitud_invalida", "El formato del carrito no es válido.")
        pid, qty = fila.get("id"), fila.get("qty")
        if not es_entero(pid) or pid < 1:
            raise CarritoError("producto_invalido", "Hay un producto con identificador inválido.")
        if not es_entero(qty) or qty < 1:
            raise CarritoError(
                "cantidad_invalida",
                "La cantidad debe ser un número entero mayor o igual a 1.",
                detalle={"id": pid},
            )
        items[pid] = items.get(pid, 0) + qty
    for pid, qty in list(items.items()):
        if qty > MAX_CANTIDAD:
            if estricto:
                raise CarritoError(
                    "cantidad_excedida",
                    f"La cantidad máxima por producto es {MAX_CANTIDAD}.",
                    detalle={"id": pid, "max": MAX_CANTIDAD},
                )
            items[pid] = MAX_CANTIDAD
    return items


def fusionar(a, b):
    """Une dos carritos {id: qty}. Mismo producto en ambos -> el MAYOR (no la suma),
    para que sincronizar dos veces no duplique cantidades."""
    resultado = dict(a)
    for pid, qty in b.items():
        resultado[pid] = min(MAX_CANTIDAD, max(resultado.get(pid, 0), qty))
    return resultado


def construir_lineas(items):
    """
    Consulta los productos y devuelve (lineas, no_disponibles, total).
    `no_disponibles` = ids que ya no existen en la tabla `productos`.
    """
    productos = Producto.objects.in_bulk(list(items.keys()))
    lineas, no_disponibles = [], []
    total = Decimal("0.00")
    for pid, qty in items.items():
        p = productos.get(pid)
        if p is None:
            no_disponibles.append(pid)
            continue
        subtotal = (p.precio * qty).quantize(CENT)
        total += subtotal
        lineas.append(
            {
                "id": p.pk,
                "nombre": p.nombre,
                "precio": str(p.precio.quantize(CENT)),
                "qty": qty,
                "subtotal": str(subtotal),
                "imagen": p.imagen_url,
                "url": p.get_absolute_url(),
            }
        )
    return lineas, no_disponibles, total.quantize(CENT)


def resumen(items):
    """Estructura JSON estándar con líneas y totales calculados por el servidor."""
    lineas, no_disponibles, total = construir_lineas(items)
    return {
        "lineas": lineas,
        "no_disponibles": no_disponibles,
        "total": str(total),
        "unidades": sum(l["qty"] for l in lineas),
    }


def _huella(items):
    texto = ",".join(f"{pid}:{qty}" for pid, qty in sorted(items.items()))
    return hashlib.sha256(texto.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Carrito persistente del cliente autenticado
# ---------------------------------------------------------------------------
def items_de_datos(datos):
    """Limpia el JSON guardado ({"id": qty}) devolviendo {int: int} válido."""
    limpio = {}
    if isinstance(datos, dict):
        for k, v in datos.items():
            try:
                pid = int(k)
            except (TypeError, ValueError):
                continue
            if es_entero(v) and v >= 1 and pid >= 1:
                limpio[pid] = min(v, MAX_CANTIDAD)
    return limpio


def sincronizar_carrito(cliente, items_local, owner, dirty, base):
    """
    Sincroniza el carrito del navegador con el del servidor. Reglas:

    1. Carrito local de OTRA cuenta (owner != cliente)  -> se descarta; gana el servidor.
    2. Carrito local anónimo (owner is None)            -> se FUSIONA con el del servidor.
    3. Carrito local de este cliente:
         - sin cambios pendientes (dirty = False)       -> gana el servidor.
         - con cambios y nadie más tocó el servidor
           (base == version)                            -> gana el local (propaga borrados).
         - con cambios pero el servidor cambió
           desde otro dispositivo (base != version)     -> se FUSIONA.
    Los ids que ya no existen en `productos` se eliminan del resultado.
    Devuelve (items_resultado, version, accion).
    """
    with transaction.atomic():
        carrito, _ = CarritoCliente.objects.select_for_update().get_or_create(cliente=cliente)
        en_servidor = items_de_datos(carrito.datos)

        if owner is not None and owner != cliente.pk:
            resultado, accion = dict(en_servidor), "servidor"
        elif owner is None:
            resultado, accion = fusionar(en_servidor, items_local), "fusion"
        elif not dirty:
            resultado, accion = dict(en_servidor), "servidor"
        elif base == carrito.version:
            resultado, accion = dict(items_local), "local"
        else:
            resultado, accion = fusionar(en_servidor, items_local), "fusion"

        existentes = set(Producto.objects.filter(pk__in=list(resultado)).values_list("pk", flat=True))
        resultado = {pid: q for pid, q in resultado.items() if pid in existentes}

        if resultado != en_servidor:
            carrito.datos = {str(pid): q for pid, q in resultado.items()}
            carrito.version += 1
            carrito.save()
        return resultado, carrito.version, accion


def _descontar_del_carrito(cliente, comprado):
    """Resta lo comprado del carrito persistente (conserva lo no comprado)."""
    carrito, _ = CarritoCliente.objects.select_for_update().get_or_create(cliente=cliente)
    actual = items_de_datos(carrito.datos)
    for pid, qty in comprado.items():
        if pid in actual:
            restante = actual[pid] - qty
            if restante > 0:
                actual[pid] = restante
            else:
                del actual[pid]
    carrito.datos = {str(pid): q for pid, q in actual.items()}
    carrito.version += 1
    carrito.save()
    return carrito.version


# ---------------------------------------------------------------------------
# Pedido
# ---------------------------------------------------------------------------
def _respuesta_pedido(pedido, duplicado, version=None):
    detalles = list(pedido.detalles.select_related("producto"))
    return {
        "ok": True,
        "id_pedido": pedido.pk,
        "total": str(pedido.total),
        "estado": pedido.estado,
        "duplicado": duplicado,
        "lineas": [
            {"id": d.producto_id, "nombre": d.producto.nombre, "qty": d.cantidad,
             "precio": str(d.precio_unitario)}
            for d in detalles
        ],
        "carrito_version": version,
    }


def crear_pedido(cliente, items, token, total_visto=None):
    """
    Crea el pedido y sus detalles en UNA transacción atómica.

    Pasos: (1) reserva el token de idempotencia, (2) verifica que todos los
    productos existan, (3) toma los precios vigentes de la BD, (4) recalcula
    subtotales y total, (5) si el total que el cliente VIO difiere del real,
    rechaza para que lo confirme de nuevo, (6) inserta Pedido + DetallePedido,
    (7) descuenta lo comprado del carrito guardado.
    Cualquier error revierte TODO (incluido el token) y no se confirma nada.
    Si el token ya se usó con el mismo contenido, devuelve el pedido existente.
    """
    if not items:
        raise CarritoError("carrito_vacio", "Tu carrito está vacío.")
    huella = _huella(items)

    try:
        with transaction.atomic():
            registro = PedidoToken.objects.create(token=token, cliente=cliente, huella=huella)

            lineas, no_disponibles, total = construir_lineas(items)
            if no_disponibles:
                raise CarritoError(
                    "productos_no_disponibles",
                    "Algunos productos ya no están disponibles. Revisa tu carrito.",
                    status=409,
                    detalle={"ids": no_disponibles},
                )
            if total_visto is not None and total_visto != total:
                raise CarritoError(
                    "precio_cambiado",
                    "Los precios cambiaron desde que viste tu carrito. Revisa el nuevo total y confirma de nuevo.",
                    status=409,
                    detalle={"total": str(total)},
                )

            pedido = Pedido.objects.create(
                cliente=cliente, fecha=timezone.localdate(), total=total, estado="Pendiente"
            )
            DetallePedido.objects.bulk_create(
                [
                    DetallePedido(
                        pedido=pedido,
                        producto_id=l["id"],
                        cantidad=l["qty"],
                        precio_unitario=Decimal(l["precio"]),
                    )
                    for l in lineas
                ]
            )
            registro.pedido = pedido
            registro.save(update_fields=["pedido"])
            version = _descontar_del_carrito(cliente, items)
    except IntegrityError:
        # Token repetido (doble clic / reintento): devolver el pedido ya creado.
        existente = PedidoToken.objects.filter(token=token).select_related("pedido").first()
        if existente is None or existente.pedido is None:
            raise
        if existente.cliente_id != cliente.pk or existente.huella != huella:
            raise CarritoError(
                "token_reutilizado",
                "Esta solicitud ya fue procesada con un contenido distinto. Recarga la página.",
                status=409,
            )
        return _respuesta_pedido(existente.pedido, duplicado=True)

    return _respuesta_pedido(pedido, duplicado=False, version=version)
