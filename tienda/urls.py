from django.urls import path

from . import api, views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("productos/", views.productos, name="productos"),
    path("producto/<int:pk>/", views.producto_detalle, name="producto_detalle"),
    path("checkout/", views.checkout, name="checkout"),
    path("pedido/<int:pk>/", views.pedido_confirmado, name="pedido_confirmado"),
    # API JSON (carrito persistente y compra)
    path("api/carrito/validar/", api.validar, name="api_carrito_validar"),
    path("api/carrito/sync/", api.sincronizar, name="api_carrito_sync"),
    path("api/checkout/", api.checkout, name="api_checkout"),
]
