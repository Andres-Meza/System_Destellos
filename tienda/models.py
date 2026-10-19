"""
Modelos mapeados a las tablas que YA existen en MySQL (destellos.sql).
managed = False  ->  Django NO crea ni modifica estas tablas; solo las usa.
"""
from decimal import Decimal

from django.db import models
from django.templatetags.static import static
from django.urls import reverse


class Cliente(models.Model):
    id_cliente = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    correo = models.CharField(max_length=100, unique=True)
    contrasena = models.CharField(max_length=255)
    direccion = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "clientes"

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    id_producto = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    # Nombre del archivo dentro de static/img/ (ej: "pack1.png")
    imagen = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "productos"
        ordering = ["id_producto"]

    def __str__(self):
        return self.nombre

    @property
    def imagen_url(self):
        """URL estática de la imagen (static/img/<imagen>) o None si no tiene."""
        return static(f"img/{self.imagen}") if self.imagen else None

    @property
    def precio_texto(self):
        """Precio como texto con 2 decimales y punto (sin localizar), p. ej. '79.99'."""
        return str(self.precio.quantize(Decimal("0.01")))

    def get_absolute_url(self):
        return reverse("producto_detalle", args=[self.pk])


class Pedido(models.Model):
    id_pedido = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(
        Cliente, on_delete=models.DO_NOTHING, db_column="id_cliente", related_name="pedidos"
    )
    fecha = models.DateField()
    total = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=50, blank=True, null=True, default="Pendiente")

    class Meta:
        managed = False
        db_table = "pedidos"

    def __str__(self):
        return f"Pedido #{self.id_pedido}"


class DetallePedido(models.Model):
    id_detalle = models.AutoField(primary_key=True)
    pedido = models.ForeignKey(
        Pedido, on_delete=models.DO_NOTHING, db_column="id_pedido", related_name="detalles"
    )
    producto = models.ForeignKey(
        Producto, on_delete=models.DO_NOTHING, db_column="id_producto"
    )
    cantidad = models.IntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        managed = False
        db_table = "detalle_pedidos"


class Pago(models.Model):
    id_pago = models.AutoField(primary_key=True)
    pedido = models.ForeignKey(
        Pedido, on_delete=models.DO_NOTHING, db_column="id_pedido", related_name="pagos"
    )
    metodo_pago = models.CharField(max_length=50, blank=True, null=True)
    fecha_pago = models.DateField(blank=True, null=True)
    estado_pago = models.CharField(max_length=50, blank=True, null=True, default="Pendiente")

    class Meta:
        managed = False
        db_table = "pagos"


# ---------------------------------------------------------------------------
# Modelos NUEVOS (managed = True): los crea la migración 0001 de la app.
# No duplican nada existente: el esquema original no tiene carrito ni forma
# de evitar pedidos duplicados.
# ---------------------------------------------------------------------------
class CarritoCliente(models.Model):
    """
    Carrito persistente de un cliente autenticado (sincronizado con localStorage).
    `datos` = {"<id_producto>": cantidad}. NO guarda precios: los precios siempre
    se leen de `productos` en el momento de validar o comprar.
    `version` aumenta en cada cambio y sirve para detectar conflictos entre
    dispositivos al sincronizar.
    """
    cliente = models.OneToOneField(Cliente, on_delete=models.CASCADE, related_name="carrito")
    datos = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=0)
    actualizado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Carrito de {self.cliente_id} (v{self.version})"


class PedidoToken(models.Model):
    """
    Clave de idempotencia de la compra: el navegador genera un UUID por intento
    de compra; la restricción UNIQUE impide crear dos pedidos con el mismo UUID
    (doble clic, reintento por mala conexión, solicitud repetida).
    La tabla `pedidos` original no tiene dónde guardar esta clave.
    """
    token = models.UUIDField(unique=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="+")
    pedido = models.ForeignKey(Pedido, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    huella = models.CharField(max_length=64)  # sha256 de las líneas compradas
    creado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.token} -> pedido {self.pedido_id}"
