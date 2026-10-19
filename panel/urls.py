from django.urls import path

from . import views

urlpatterns = [
  path("", views.InicioView.as_view(), name="panel_inicio"),
  # Productos
  path("productos/", views.ProductoListView.as_view(), name="panel_productos"),
  path("productos/nuevo/", views.ProductoCrearView.as_view(), name="panel_producto_nuevo"),
  path("productos/<int:pk>/editar/", views.ProductoEditarView.as_view(), name="panel_producto_editar"),
  path("productos/<int:pk>/eliminar/", views.ProductoEliminarView.as_view(), name="panel_producto_eliminar"),
  # Pedidos
  path("pedidos/", views.PedidoListView.as_view(), name="panel_pedidos"),
  path("pedidos/<int:pk>/", views.PedidoDetalleView.as_view(), name="panel_pedido_detalle"),
  path("pedidos/<int:pk>/estado/", views.PedidoEstadoView.as_view(), name="panel_pedido_estado"),
  # Clientes
  path("clientes/", views.ClienteListView.as_view(), name="panel_clientes"),
  # Usuarios (solo administrador)
  path("usuarios/", views.UsuarioListView.as_view(), name="panel_usuarios"),
  path("usuarios/nuevo/", views.UsuarioCrearView.as_view(), name="panel_usuario_nuevo"),
  path("usuarios/<int:pk>/editar/", views.UsuarioEditarView.as_view(), name="panel_usuario_editar"),
  path("usuarios/<int:pk>/contrasena/", views.UsuarioContrasenaView.as_view(), name="panel_usuario_contrasena"),
  path("usuarios/<int:pk>/estado/", views.UsuarioEstadoView.as_view(), name="panel_usuario_estado"),
]
