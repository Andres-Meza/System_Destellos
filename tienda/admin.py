from django.contrib import admin
from django.contrib.auth.hashers import identify_hasher, make_password

from .models import Cliente, DetallePedido, Pago, Pedido, Producto


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("id_producto", "nombre", "precio", "imagen")


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("id_cliente", "nombre", "correo", "direccion")

    def save_model(self, request, obj, form, change):
        # Nunca guardar contraseñas en texto plano desde el admin
        try:
            identify_hasher(obj.contrasena)
        except ValueError:
            obj.contrasena = make_password(obj.contrasena)
        super().save_model(request, obj, form, change)


admin.site.register(Pedido)
admin.site.register(DetallePedido)
admin.site.register(Pago)
