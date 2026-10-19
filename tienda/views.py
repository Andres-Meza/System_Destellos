from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .carrito import MAX_CANTIDAD
from .models import Pedido, Producto

POR_PAGINA = 12


def inicio(request):
    return render(request, "tienda/index.html")


def productos(request):
    q = request.GET.get("q", "").strip()[:100]
    qs = Producto.objects.all()
    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(descripcion__icontains=q))
    pagina = Paginator(qs, POR_PAGINA).get_page(request.GET.get("page"))
    return render(request, "tienda/productos.html", {"pagina": pagina, "productos": pagina, "q": q})


def producto_detalle(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    return render(request, "tienda/producto_detalle.html", {"p": producto, "max_cantidad": MAX_CANTIDAD})


def checkout(request):
    if request.cliente is None:
        return redirect(f"{reverse('login')}?next={reverse('checkout')}")
    return render(request, "tienda/checkout.html")


def pedido_confirmado(request, pk):
    if request.cliente is None:
        return redirect(f"{reverse('login')}?next={reverse('pedido_confirmado', args=[pk])}")
    # Solo el dueño del pedido puede verlo.
    pedido = get_object_or_404(Pedido, pk=pk, cliente=request.cliente)
    detalles = pedido.detalles.select_related("producto")
    lineas = [{"d": d, "subtotal": d.precio_unitario * d.cantidad} for d in detalles]
    return render(request, "tienda/pedido_confirmado.html", {"pedido": pedido, "lineas": lineas})
