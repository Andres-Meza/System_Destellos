from tienda.models import Cliente


class ClienteMiddleware:
    """Pone request.cliente (o None) según la sesión, para usarlo en las plantillas."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.cliente = None
        id_cliente = request.session.get("id_cliente")
        if id_cliente:
            request.cliente = Cliente.objects.filter(pk=id_cliente).first()
            if request.cliente is None:
                request.session.flush()
        return self.get_response(request)
