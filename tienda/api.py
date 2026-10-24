"""
Endpoints JSON del carrito y la compra.

Seguridad: todos son POST y pasan por el middleware CSRF de Django (el navegador
envía el token en la cabecera X-CSRFToken). Ninguno está exento de CSRF.
Ninguno confía en precios ni totales enviados por JavaScript.
"""
import json
import logging
import uuid
from decimal import Decimal, InvalidOperation
from functools import wraps

from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import carrito as svc

logger = logging.getLogger(__name__)
MAX_BODY = 64 * 1024  # 64 KB


def _error(codigo, mensaje, status=400, **extra):
    return JsonResponse({"ok": False, "codigo": codigo, "mensaje": mensaje, **extra}, status=status)


def endpoint_json(vista):
    """POST + cuerpo JSON válido + traducción de CarritoError a respuesta JSON."""

    @wraps(vista)
    @require_POST
    def envoltura(request, *args, **kwargs):
        if len(request.body) > MAX_BODY:
            return _error("demasiado_grande", "La solicitud es demasiado grande.", 413)
        try:
            datos = json.loads(request.body or b"{}")
        except (ValueError, UnicodeDecodeError):
            return _error("json_invalido", "La solicitud no es un JSON válido.")
        if not isinstance(datos, dict):
            return _error("json_invalido", "La solicitud no es un JSON válido.")
        try:
            return vista(request, datos, *args, **kwargs)
        except svc.CarritoError as e:
            return _error(e.codigo, e.mensaje, e.status, **e.detalle)

    return envoltura


@endpoint_json
def validar(request, datos):
    """Devuelve las líneas con precios y totales OFICIALES (no modifica nada)."""
    items = svc.parsear_items(datos.get("items", []), estricto=False)
    return JsonResponse({"ok": True, **svc.resumen(items)})


@endpoint_json
def sincronizar(request, datos):
    """Sincroniza el carrito local con el guardado en la BD (solo clientes con sesión)."""
    cliente = request.cliente
    if cliente is None:
        return _error("no_autenticado", "Inicia sesión para sincronizar tu carrito.", 401,
                      login=reverse("login"))
    items = svc.parsear_items(datos.get("items", []), estricto=False)
    owner, base = datos.get("owner"), datos.get("base")
    owner = owner if svc.es_entero(owner) else None
    base = base if svc.es_entero(base) else None
    resultado, version, accion = svc.sincronizar_carrito(
        cliente, items, owner, bool(datos.get("dirty")), base
    )
    return JsonResponse(
        {"ok": True, "version": version, "accion": accion, "owner": cliente.pk, **svc.resumen(resultado)}
    )


@endpoint_json
def checkout(request, datos):
    """Crea el pedido. Solo confirma (ok=True) si TODO se guardó correctamente."""
    cliente = request.cliente
    if cliente is None:
        return _error("no_autenticado", "Inicia sesión para finalizar tu compra.", 401,
                      login=reverse("login"))
    try:
        token = uuid.UUID(str(datos.get("token", "")))
    except ValueError:
        return _error("token_invalido", "Falta el identificador de la compra. Recarga la página.")

    items = svc.parsear_items(datos.get("items", []), estricto=True)

    total_visto = datos.get("total_visto")
    if total_visto is not None:
        try:
            total_visto = Decimal(str(total_visto)).quantize(svc.CENT)
        except (InvalidOperation, ValueError):
            return _error("solicitud_invalida", "El total enviado no es válido.")

    try:
        resultado = svc.crear_pedido(cliente, items, token, total_visto)
    except svc.CarritoError:
        raise
    except Exception:
        logger.exception("Error inesperado al crear el pedido (cliente=%s)", cliente.pk)
        # Nunca se presenta como compra exitosa.
        return _error("error_interno", "No pudimos registrar tu pedido. No se realizó ningún cargo. Inténtalo de nuevo.", 500)
    resultado["url"] = reverse("pedido_confirmado", args=[resultado["id_pedido"]])
    return JsonResponse(resultado, status=200 if resultado["duplicado"] else 201)
