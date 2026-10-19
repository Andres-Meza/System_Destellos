from django.middleware.csrf import get_token
from django.urls import reverse

from .carrito import MAX_CANTIDAD


def tienda_config(request):
    """
    Configuración pública para el JavaScript del carrito (se imprime con json_script).
    Solo contiene datos no sensibles: el token CSRF es el mismo que Django ya expone
    al navegador en su cookie/formularios.
    """
    cliente = getattr(request, "cliente", None)
    return {
        "tienda_config": {
            "clienteId": cliente.pk if cliente else None,
            "csrf": get_token(request),
            "maxQty": MAX_CANTIDAD,
            "urls": {
                "validar": reverse("api_carrito_validar"),
                "sync": reverse("api_carrito_sync"),
                "checkout": reverse("api_checkout"),
                "login": reverse("login"),
                "productos": reverse("productos"),
                "inicio": reverse("inicio"),
            },
        }
    }
